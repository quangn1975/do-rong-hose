"""Tu dong: can kiet 33 ma lon, khoi ngoai toan HOSE, tin hieu doi chieu.
python auto33.py -> data/can_kiet33.csv, data/khoi_ngoai.csv, data/tin_hieu.csv
"""
import os, time, datetime as dt
import pandas as pd
from vnstock import Quote
from ngay15 import lich_su, ma_hose, DELAY, now

MA33 = [l.strip().upper() for l in open("ma33.txt") if l.strip() and not l.startswith("#")]


def can_kiet():
    close = {}
    for s in MA33:
        df = lich_su(s, 420)
        time.sleep(DELAY)
        if df is not None:
            close[s] = df.set_index("time")["close"]
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
    ]
    pd.DataFrame([(t, a, b) for a, b in rows], columns=["date", "tin_hieu", "da_co"]).to_csv("data/tin_hieu.csv", index=False)


if __name__ == "__main__":
    ck = can_kiet()
    time.sleep(DELAY)
    tin_hieu(ck)
    time.sleep(DELAY)
    try:
        khoi_ngoai()
    except Exception as e:
        print("khoi ngoai loi", repr(e)[:300])
