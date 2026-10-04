"""Khung 1 gio: VN-Index va 15 ma chot.

Lay nen 1 gio qua vnstock, tinh RSI(14), CCI(20), MFI(14), MACD histogram, MA20,
dem so ma tang / giam / dung gia tren HOSE, ghi vao data/khung_1_gio.csv de
Google Sheets doc bang IMPORTDATA. Vi tri dong trong file la co dinh:
dong 1 thoi gian, dong 2-4 do rong, dong 5-20 tung ma, dong 21-50 VN-Index.
"""
import os, csv, time, datetime as dt
import pandas as pd
from vnstock import Quote

OUT = "data/khung_1_gio.csv"
DELAY = float(os.getenv("VNSTOCK_DELAY", "3.2"))
NHOM = [("VNINDEX", "Chỉ số"), ("VIC", "Vingroup"), ("VHM", "Vingroup"), ("MSN", "Masan"),
        ("MCH", "Masan"), ("TCB", "Ngân hàng"), ("HDB", "Ngân hàng"), ("VPB", "Ngân hàng"),
        ("VCB", "Ngân hàng"), ("FPT", "Công nghệ"), ("HPG", "Thép"), ("MWG", "Bán lẻ"),
        ("VNM", "Thực phẩm"), ("GAS", "Dầu khí"), ("BSR", "Dầu khí"), ("GVR", "Cao su")]
now = dt.datetime.utcnow() + dt.timedelta(hours=7)
today = now.date().isoformat()
start = (now.date() - dt.timedelta(days=75)).isoformat()


def bars(sym):
    for attempt in range(3):
        try:
            df = Quote(symbol=sym, source="VCI").history(start=start, end=today, interval="1H")
            if df is not None and len(df) > 40:
                df = df[["time", "open", "high", "low", "close", "volume"]].copy()
                df["time"] = pd.to_datetime(df["time"])
                df = df[df["volume"] > 0].sort_values("time").reset_index(drop=True)
                if sym != "VNINDEX" and df["close"].median() > 5000:   # dong -> nghin dong
                    for c in ("open", "high", "low", "close"):
                        df[c] = df[c] / 1000
                return df
        except Exception as e:
            print("loi", sym, e, flush=True)
        time.sleep(6)
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
    f = tp * v
    pos = f.where(tp > tp.shift(), 0).rolling(14).sum()
    neg = f.where(tp < tp.shift(), 0).rolling(14).sum()
    df["mfi"] = 100 - 100 / (1 + pos / neg)
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["mh"] = macd - macd.ewm(span=9, adjust=False).mean()
    df["ma20"] = c.rolling(20).mean()
    df["vma20"] = v.rolling(20).mean()
    return df


def macd_txt(a, p):
    if a > 0:
        return "Dương, tăng dần" if a >= p else "Dương, giảm dần"
    return "Âm, tăng dần" if a >= p else "Âm, giảm dần"


def trang_thai(df, i):
    r, rp, c, cp, m = df.rsi[i], df.rsi[i - 1], df.cci[i], df.cci[i - 1], df.mfi[i]
    if (rp < 30 <= r) or (cp < -100 <= c):
        return "Có tín hiệu mua"
    if r < 30 or c < -100 or m < 20:
        return "Quá bán, chờ quay đầu"
    if r > 70 or c > 100 or m > 80:
        return "Quá mua"
    return "Trung tính"


def nhan(t):
    return t.strftime("%d/%m %Hh")


def do_rong():
    """So ma tang, giam, dung gia tren HOSE tai luc chay. Loi thi tra ve o trong."""
    try:
        from vnstock import Listing, Trading
        ls = Listing(source="VCI").symbols_by_exchange(to_df=True)
        cols = {c.lower(): c for c in ls.columns}
        ex = next((cols[c] for c in cols if "exchange" in c or c == "board"), None)
        ls = ls[ls[ex].astype(str).str.upper().isin(["HOSE", "HSX"])]
        typ = next((cols[c] for c in cols if c in ("type", "stock_type", "organ_type")), None)
        if typ:
            ls = ls[ls[typ].astype(str).str.upper().str.contains("STOCK")]
        syms = sorted(set(s for s in ls[cols["symbol"]].astype(str).str.upper() if len(s) == 3))
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
        return ["", "", ""]


def r(x, n=1):
    return "" if pd.isna(x) else round(float(x), n)


def main():
    tung_ma, vni = [], None
    for sym, nhom in NHOM:
        df = bars(sym)
        time.sleep(DELAY)
        if df is None:
            tung_ma.append(["VN-Index" if sym == "VNINDEX" else sym, nhom] + [""] * 12 + ["Không lấy được số liệu"])
            continue
        df = chi_bao(df)
        i = len(df) - 1
        if sym == "VNINDEX":
            vni = df
        tung_ma.append(["VN-Index" if sym == "VNINDEX" else sym, nhom, nhan(df.time[i]), r(df.close[i], 2),
                        r(df.close[i] / df.close[i - 1] - 1, 4), r(df.rsi[i]), r(df.rsi[i - 1]), r(df.cci[i]),
                        r(df.cci[i - 1]), r(df.mfi[i]), macd_txt(df.mh[i], df.mh[i - 1]), r(df.ma20[i], 2),
                        r(df.close[i] / df.ma20[i] - 1, 4), r(df.volume[i] / df.vma20[i], 2), trang_thai(df, i)])
        print(tung_ma[-1], flush=True)
    rows = [["Cập nhật lúc", now.strftime("%d/%m/%Y %H:%M"), "Nến mới nhất", nhan(vni.time.iloc[-1]) if vni is not None else ""]]
    for ten, so in zip(("Mã tăng (HOSE)", "Mã giảm (HOSE)", "Đứng giá (HOSE)"), do_rong()):
        rows.append([ten, so])
    rows += tung_ma
    if vni is not None:
        for i in range(len(vni) - 1, max(len(vni) - 31, 20), -1):
            rows.append([nhan(vni.time[i]), r(vni.open[i], 2), r(vni.high[i], 2), r(vni.low[i], 2), r(vni.close[i], 2),
                         r(vni.volume[i] / 1e6), r(vni.rsi[i]), r(vni.cci[i]), r(vni.mfi[i]), r(vni.mh[i], 2),
                         macd_txt(vni.mh[i], vni.mh[i - 1]), r(vni.ma20[i], 2), trang_thai(vni, i)])
    if sum(1 for x in tung_ma if x[2] != "") < 8:
        raise SystemExit("Lay duoc qua it ma, khong ghi de file cu")
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for x in rows:
            w.writerow(list(x) + [""] * (15 - len(x)))
    print(rows[:4])


if __name__ == "__main__":
    main()
