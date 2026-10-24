"""Tu dong: can kiet 33 ma lon, khoi ngoai toan HOSE, tin hieu doi chieu.
python auto33.py -> data/can_kiet33.csv, data/khoi_ngoai.csv, data/tin_hieu.csv
"""
import os, time, datetime as dt
import pandas as pd
from vnstock import Quote
from ngay15 import lich_su, ma_hose, DELAY, now

DFS = {}
MA33 = [l.strip().upper() for l in open("ma33.txt") if l.strip() and not l.startswith("#")]


def can_kiet():
    close = {}
    global DFS
    DFS = {}
    for s in MA33:
        df = lich_su(s, 420)
        time.sleep(DELAY)
        if df is not None:
            close[s] = df.set_index("time")["close"]
            DFS[s] = df.reset_index(drop=True)
    c = pd.DataFrame(close).sort_index().ffill()
    p20 = (c > c.rolling(20).mean()).sum(axis=1) / c.notna().sum(axis=1) * 100
    p50 = (c > c.rolling(50).mean()).sum(axis=1) / c.notna().sum(axis=1) * 100
    ck = (p20 < 20) | (p50 < 30)
    out = pd.DataFrame({"date": c.index, "pct_ma20": p20.round(1).values, "pct_ma50": p50.round(1).values,
                        "can_kiet": ck.astype(int).values, "so_ma": c.notna().sum(axis=1).values})
    last = -1
    ph = []
    for i, f in enumerate(out["can_kiet"]):
        if f: last = i
        ph.append("" if last < 0 else i - last)
    out["so_phien_tu_can_kiet"] = ph
    out["cua_A_mo"] = [1 if p != "" and p <= 3 else 0 for p in ph]
    out.tail(260).to_csv("data/can_kiet33.csv", index=False)
    return out


def phan_phien():
    """Ty le thoi gian phien da qua (0-1), de du kien KL ca ngay."""
    m = now.hour * 60 + now.minute
    if now.weekday() >= 5 or m >= 14 * 60 + 45 or m < 9 * 60:
        return 1.0
    if m <= 11 * 60 + 30:
        da = m - 9 * 60
    elif m < 13 * 60:
        da = 150
    else:
        da = 150 + m - 13 * 60
    return max(da, 15) / 255


def roe(sym):
    try:
        from vnstock import Finance
        df = Finance(source="VCI", symbol=sym, period="year").ratio(lang="en")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ["_".join(str(x) for x in c) for c in df.columns]
        c = next(c for c in df.columns if "roe" in str(c).lower())
        v = float(df[c].dropna().iloc[0])
        return v * 100 if abs(v) < 1.5 else v
    except Exception as e:
        print("roe loi", sym, repr(e)[:120])
        return None


def khoi_ngoai():
    """Bo loc FireAnt 'Loc realtime' cua anh: mua chu dong>60%, KL du kien vuot TB5 >=10%,
    NN mua rong>5 ty, ROE>16%."""
    from vnstock import Trading
    syms = ma_hose()
    pb = Trading(source="VCI").price_board(syms)
    pb.columns = ["_".join(str(x) for x in c) if isinstance(c, tuple) else str(c) for c in pb.columns]
    open("data/cot_bang_gia.txt", "w").write("\n".join(pb.columns))
    col = lambda suf: next(c for c in pb.columns if c.endswith(suf))
    d = pd.DataFrame({"ma": pb[col("symbol")], "gia": pb[col("match_price")], "tc": pb[col("ref_price")],
                      "kl": pb[col("accumulated_volume")],
                      "nn_mua": pb[col("foreign_buy_volume")], "nn_ban": pb[col("foreign_sell_volume")]})
    d["nn_rong"] = d["nn_mua"] - d["nn_ban"]
    d["nn_rong_ty"] = (d["nn_rong"] * d["gia"] / 1e9).round(2)
    d["pct"] = ((d["gia"] / d["tc"] - 1) * 100).round(2)
    mua = next((c for c in pb.columns if "total_buy" in c.lower() and "vol" in c.lower() or "active_buy" in c.lower()), None)
    ban = next((c for c in pb.columns if "total_sell" in c.lower() and "vol" in c.lower() or "active_sell" in c.lower()), None)
    d["pct_mua_chu_dong"] = ""
    if mua and ban:
        t = pb[mua] + pb[ban]
        d["pct_mua_chu_dong"] = (pb[mua] / t.where(t > 0) * 100).round(1)
    d["kl_vuot_tb5_pct"] = ""
    d["roe"] = ""
    d["loc_realtime"] = 0
    ph = phan_phien()
    for i in d.index[d["nn_rong_ty"] > 5]:
        s = d.at[i, "ma"]
        time.sleep(DELAY)
        h = lich_su(s, 15)
        if h is not None and len(h) >= 6:
            h = h[h["time"] < now.date().isoformat()] if ph < 1 else h
            tb5 = h["volume"].tail(6 if ph == 1 else 5).iloc[:-1].mean() if ph == 1 else h["volume"].tail(5).mean()
            d.at[i, "kl_vuot_tb5_pct"] = round((d.at[i, "kl"] / ph / tb5 - 1) * 100, 1)
        time.sleep(DELAY)
        d.at[i, "roe"] = roe(s) if roe(s) is not None else ""
    def ok(r):
        if r["nn_rong_ty"] <= 5: return 0
        if r["pct_mua_chu_dong"] != "" and r["pct_mua_chu_dong"] <= 60: return 0
        if r["kl_vuot_tb5_pct"] == "" or r["kl_vuot_tb5_pct"] < 10: return 0
        if r["roe"] == "" or r["roe"] <= 16: return 0
        return 1
    d["loc_realtime"] = d.apply(ok, axis=1)
    d["gio"] = now.strftime("%Y-%m-%d %H:%M")
    d.sort_values("nn_rong_ty", ascending=False).to_csv("data/khoi_ngoai.csv", index=False)


def chi_so_vn():
    """Den thi truong cua VN-Index: MA50, MA200, day nen SOS, so phien duoi day SOS, death cross."""
    vn = lich_su("VNINDEX", 420).reset_index(drop=True)
    c, h, l, o, v = vn["close"], vn["high"], vn["low"], vn["open"], vn["volume"]
    rng = h - l
    sos = ((c > o) & (rng > rng.rolling(14).mean().shift(1)) & (v > 1.2 * v.rolling(20).mean().shift(1))
           & ((c - l) / rng.where(rng > 0) >= 0.8) & (c > h.rolling(5).max().shift(1)))
    idx = sos[sos].index
    ma50, ma200 = c.rolling(50).mean().iloc[-1], c.rolling(200).mean().iloc[-1]
    if len(idx):
        k = idx[-1]
        day = float(l[k]); ngay = vn.at[k, "time"]
        dem = 0
        for x in c.iloc[k + 1:][::-1]:
            if x < day: dem += 1
            else: break
    else:
        day, ngay, dem = "", "", 0
    rows = [("ngay", vn["time"].iloc[-1]), ("close", round(float(c.iloc[-1]), 2)), ("ma50", round(float(ma50), 2)),
            ("ma200", round(float(ma200), 2)), ("ngay_sos", ngay), ("day_sos", day), ("so_phien_duoi_sos", dem),
            ("den_long", "Xau" if dem > 3 else "Tot"), ("den_ma200", "Xau" if c.iloc[-1] < ma200 else "Tot"),
            ("death_cross", int(ma50 < ma200))]
    pd.DataFrame(rows, columns=["khoa", "gia_tri"]).to_csv("data/vnindex_chi_so.csv", index=False)


def dem_sos():
    """So ma trong 33 ma co nen SOS o phien cuoi (5 dieu cua anh Long)."""
    n, tong = 0, 0
    for s, d in DFS.items():
        if len(d) < 30: continue
        c, h, l, o, v = d["close"], d["high"], d["low"], d["open"], d["volume"]
        rng = h - l
        r = rng.iloc[-1]
        ok = (c.iloc[-1] > o.iloc[-1] and r > rng.iloc[-15:-1].mean() and v.iloc[-1] > 1.2 * v.iloc[-21:-1].mean()
              and r > 0 and (c.iloc[-1] - l.iloc[-1]) / r >= 0.8 and c.iloc[-1] > h.iloc[-6:-1].max())
        tong += 1
        n += int(ok)
    return n, tong


def nn_lich_su():
    """Moi phien (sau 15h) ghi tong NN mua rong HOSE (ty); kiem tra 5 phien lien tiep mua rong."""
    p = "data/nn_lich_su.csv"
    try:
        kn = pd.read_csv("data/khoi_ngoai.csv")
        tong = round(float(kn["nn_rong_ty"].sum()), 1)
    except Exception:
        return 0
    ngay = now.date().isoformat()
    h = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame(columns=["date", "nn_rong_ty"])
    if now.weekday() < 5 and (now.hour * 60 + now.minute) >= 15 * 60:
        h = h[h["date"] != ngay]
        h = pd.concat([h, pd.DataFrame([[ngay, tong]], columns=h.columns)])
        h.sort_values("date").to_csv(p, index=False)
    h = h.sort_values("date")
    return int(len(h) >= 5 and (h["nn_rong_ty"].tail(5) > 0).all())


def tin_hieu(ck):
    vn = lich_su("VNINDEX", 420)
    c, h, v = vn["close"], vn["high"], vn["volume"]
    ma50, ma200 = c.rolling(50).mean(), c.rolling(200).mean()
    vma = v.rolling(20).mean()
    t = vn["time"].iloc[-1]
    rows = [
        ("Dinh VN-Index cham 1725", int(h.tail(3).max() >= 1725)),
        ("Dong cua tren 1735 voi KL lon", int(c.iloc[-1] > 1735 and v.iloc[-1] > 1.2 * vma.iloc[-1])),
        ("Lay lai MA200", int(c.iloc[-1] > ma200.iloc[-1])),
        ("MA50 tren MA200 (golden cross)", int(ma50.iloc[-1] > ma200.iloc[-1])),
        ("Can kiet 33 ma trong 3 phien", int(ck["cua_A_mo"].iloc[-1])),
        ("Nen SOS trong cac ma lon", int(dem_sos()[0] >= 7)),
        ("Khoi ngoai mua rong 5 phien", nn_lich_su()),
    ]
    pd.DataFrame([(t, a, b) for a, b in rows], columns=["date", "tin_hieu", "da_co"]).to_csv("data/tin_hieu.csv", index=False)


if __name__ == "__main__":
    ck = can_kiet()
    time.sleep(DELAY)
    try:
        khoi_ngoai()
    except Exception as e:
        print("khoi ngoai loi", repr(e)[:300])
    time.sleep(DELAY)
    tin_hieu(ck)
    chi_so_vn()
