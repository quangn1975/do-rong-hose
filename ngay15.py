"""So lieu ngay cho file Theo doi thi truong va 15 ma chot.

python ngay15.py      -> data/thi_truong.csv, data/15_ma_chot.csv, data/do_rong_ngay.csv (khoang 2 phut)
python ngay15.py rs   -> data/rs.csv: xep hang muc tang gia 60 phien cua tung ma so voi toan san HOSE (khoang 30 phut)
Google Sheets doc cac file nay bang IMPORTDATA.
"""
import os, sys, csv, time, datetime as dt
import pandas as pd
from vnstock import Quote

DELAY = float(os.getenv("VNSTOCK_DELAY", "3.2"))
TU_NGAY = "2026-04-10"
MA = ["VIC", "VHM", "MSN", "MCH", "TCB", "HDB", "VPB", "VCB", "FPT", "HPG", "MWG", "VNM", "GAS", "BSR", "GVR"]
now = dt.datetime.utcnow() + dt.timedelta(hours=7)
today = now.date().isoformat()


def lich_su(sym, so_ngay):
    start = (now.date() - dt.timedelta(days=so_ngay)).isoformat()
    for attempt in range(3):
        try:
            df = Quote(symbol=sym, source="VCI").history(start=start, end=today, interval="1D")
            if df is not None and len(df):
                df = df[["time", "open", "high", "low", "close", "volume"]].copy()
                df["time"] = pd.to_datetime(df["time"]).dt.date.astype(str)
                return df.sort_values("time").reset_index(drop=True)
            return None
        except Exception as e:
            print("loi", sym, e, flush=True)
            time.sleep(6)
    return None


def ma_hose():
    from vnstock import Listing
    ls = Listing(source="VCI").symbols_by_exchange(to_df=True)
    cols = {c.lower(): c for c in ls.columns}
    ex = next((cols[c] for c in cols if "exchange" in c or c == "board"), None)
    ls = ls[ls[ex].astype(str).str.upper().isin(["HOSE", "HSX"])]
    typ = next((cols[c] for c in cols if c in ("type", "stock_type", "organ_type")), None)
    if typ:
        ls = ls[ls[typ].astype(str).str.upper().str.contains("STOCK")]
    return sorted(set(s for s in ls[cols["symbol"]].astype(str).str.upper() if len(s) == 3))


def do_rong():
    try:
        from vnstock import Trading
        syms = ma_hose()
        time.sleep(DELAY)
        pb = Trading(source="VCI").price_board(syms)
        pb.columns = ["_".join(str(x) for x in c) if isinstance(c, tuple) else str(c) for c in pb.columns]
        gia = next(c for c in pb.columns if c.endswith("match_price"))
        tc = next(c for c in pb.columns if c.endswith("ref_price"))
        pb = pb[(pb[gia] > 0) & (pb[tc] > 0)]
        up, dn = int((pb[gia] > pb[tc]).sum()), int((pb[gia] < pb[tc]).sum())
        return [up, dn, int(len(pb) - up - dn)]
    except Exception as e:
        print("Khong lay duoc do rong:", repr(e)[:300], flush=True)
        return None


def chi_bao(df):
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    d = c.diff()
    ag = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    df["rsi"] = 100 - 100 / (1 + ag / al)
    tp = (h + l + c) / 3
    m = tp.rolling(20).mean()
    md = tp.rolling(20).apply(lambda x: abs(x - x.mean()).mean(), raw=True)
    df["cci"] = (tp - m) / (0.015 * md)
    df["ma20"] = c.rolling(20).mean()
    df["vma20"] = v.rolling(20).mean()
    return df


def r(x, n=1):
    return "" if pd.isna(x) else round(float(x), n)


def ghi(path, rows, so_cot):
    os.makedirs("data", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for x in rows:
            w.writerow(list(x) + [""] * (so_cot - len(x)))


def nhanh():
    vni = lich_su("VNINDEX", 260)
    if vni is None:
        raise SystemExit("Khong lay duoc VN-Index")
    time.sleep(DELAY)
    # do rong tung ngay: giu lich su trong data/do_rong_ngay.csv, moi phien them mot dong sau gio dong cua
    dr = {}
    if os.path.exists("data/do_rong_ngay.csv"):
        for x in csv.reader(open("data/do_rong_ngay.csv", encoding="utf-8")):
            if len(x) >= 4 and x[0][:2] == "20":
                dr[x[0]] = x[1:4]
    if vni.time.iloc[-1] == today and now.hour >= 15:
        d = do_rong()
        if d:
            dr[today] = d
    ghi("data/do_rong_ngay.csv", [["date", "tang", "giam", "dung_gia"]] + [[k] + list(dr[k]) for k in sorted(dr)], 4)
    tt = [["date", "close", "high", "low", "kl_trieu", "tang", "giam", "dung_gia"]]
    for i in range(len(vni)):
        if vni.time[i] >= TU_NGAY:
            tt.append([vni.time[i], r(vni.close[i], 2), r(vni.high[i], 2), r(vni.low[i], 2), r(vni.volume[i] / 1e6, 1)]
                      + list(dr.get(vni.time[i], ["", "", ""])))
    ghi("data/thi_truong.csv", tt, 8)
    rs = {}
    if os.path.exists("data/rs.csv"):
        for x in csv.reader(open("data/rs.csv", encoding="utf-8")):
            if len(x) >= 2:
                rs[x[0]] = x[1]
    rows = [["ngay", vni.time.iloc[-1]],
            ["ma", "close", "pct", "kl_trieu", "kl_tb20_trieu", "ma20", "rs", "rsi", "rsi_truoc", "cci", "cci_truoc"]]
    ok = 0
    for s in MA:
        df = lich_su(s, 200)
        time.sleep(DELAY)
        if df is None or len(df) < 30:
            rows.append([s])
            continue
        if df["close"].median() > 5000:
            for c in ("open", "high", "low", "close"):
                df[c] = df[c] / 1000
        df = chi_bao(df)
        i = len(df) - 1
        rows.append([s, r(df.close[i], 2), r(df.close[i] / df.close[i - 1] - 1, 4), r(df.volume[i] / 1e6, 2),
                     r(df.vma20[i] / 1e6, 2), r(df.ma20[i], 2), rs.get(s, ""), r(df.rsi[i]), r(df.rsi[i - 1]),
                     r(df.cci[i]), r(df.cci[i - 1])])
        ok += 1
        print(rows[-1], flush=True)
    if ok < 8:
        raise SystemExit("Lay duoc qua it ma, khong ghi de file cu")
    ghi("data/15_ma_chot.csv", rows, 11)


def xep_hang():
    kq = []
    syms = ma_hose()
    for i, s in enumerate(syms):
        df = lich_su(s, 130)
        if df is not None and len(df) >= 61 and df.close.iloc[-61] > 0:
            kq.append([s, df.close.iloc[-1] / df.close.iloc[-61] - 1])
        if i % 50 == 0:
            print(i, s, flush=True)
        time.sleep(DELAY)
    if len(kq) < 200:
        raise SystemExit("Lay duoc qua it ma, khong ghi de file cu")
    df = pd.DataFrame(kq, columns=["ma", "tang60"])
    df["rs"] = (df["tang60"].rank(pct=True) * 99).round().clip(1, 99).astype(int)
    ghi("data/rs.csv", [["ma", "rs", "tang_60_phien"]] + [[a, c, round(b, 4)] for a, b, c in df.sort_values("ma").values], 3)
    print(df.sort_values("rs").tail(10))


if __name__ == "__main__":
    xep_hang() if len(sys.argv) > 1 and sys.argv[1] == "rs" else nhanh()
