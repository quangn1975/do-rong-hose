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


def khoi_ngoai():
    from vnstock import Trading
    syms = ma_hose()
    pb = Trading(source="VCI").price_board(syms)
    pb.columns = ["_".join(str(x) for x in c) if isinstance(c, tuple) else str(c) for c in pb.columns]
    col = lambda suf: next(c for c in pb.columns if c.endswith(suf))
    sym = col("symbol")
    d = pd.DataFrame({"ma": pb[sym], "gia": pb[col("match_price")], "tc": pb[col("ref_price")],
                      "kl": pb[col("accumulated_volume")],
                      "nn_mua": pb[col("foreign_buy_volume")], "nn_ban": pb[col("foreign_sell_volume")]})
    d["nn_rong"] = d["nn_mua"] - d["nn_ban"]
    d["pct"] = ((d["gia"] / d["tc"] - 1) * 100).round(2)
    d["loc_realtime"] = ((d["nn_rong"] >= 400000) & (d["pct"] > 0)).astype(int)  # NN mua rong >=400k co va gia xanh
    d["gio"] = now.strftime("%Y-%m-%d %H:%M")
    d.sort_values("nn_rong", ascending=False).to_csv("data/khoi_ngoai.csv", index=False)


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
