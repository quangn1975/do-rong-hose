"""Chay 18:00 hang ngay (gio VN), sau khi san dong cua.
 - data/vn100_do_rong.csv : % ma trong VN100 dong cua tren MA20 / MA50 / MA200 moi phien (thuoc do do rong)
 - data/vn100_ngoai.csv   : khoi ngoai mua/ban/rong cua tung ma VN100 cuoi phien (bang gia VCI)
"""
import os, time, sys
import pandas as pd
from ngay15 import lich_su, DELAY, now


def ds_vn100():
    from vnstock import Listing
    for src in ("VCI", "kbs"):
        try:
            s = Listing(source=src).symbols_by_group("VN100")
            s = list(s.astype(str)) if hasattr(s, "astype") else list(s)
            s = sorted(set(x.upper() for x in s if len(x) == 3))
            if len(s) >= 90:
                print("VN100:", len(s), "ma (nguon", src + ")")
                return s
        except Exception as e:
            print("VN100 loi", src, repr(e)[:150])
    sys.exit("Khong lay duoc danh sach VN100")


def do_rong(syms):
    close = {}
    for i, s in enumerate(syms):
        df = lich_su(s, 420)
        if df is not None:
            close[s] = df.set_index("time")["close"]
        if i % 20 == 0: print(i, s, flush=True)
        time.sleep(DELAY)
    c = pd.DataFrame(close).sort_index().ffill()
    out = pd.DataFrame(index=c.index)
    for n in (20, 50, 200):
        ma = c.rolling(n).mean()
        out[f"pct_ma{n}"] = ((c > ma).sum(axis=1) / ma.notna().sum(axis=1).where(ma.notna().sum(axis=1) > 0) * 100).round(1)
    out["so_ma"] = c.notna().sum(axis=1)
    # mốc MA chốt phiên của từng mã: dùng cho bản chụp trong phiên (ngay_chup.py)
    mo = pd.DataFrame({"ma": c.columns, "dong_cua": c.iloc[-1].values,
                       "ma20": c.rolling(20).mean().iloc[-1].values,
                       "ma50": c.rolling(50).mean().iloc[-1].values,
                       "ma200": c.rolling(200).mean().iloc[-1].values})
    mo["ngay"] = c.index[-1]
    mo.round(2).to_csv("data/vn100_ma_moc.csv", index=False)
    out.index.name = "date"
    out.tail(260).to_csv("data/vn100_do_rong.csv")
    print(out.tail(3))


def ngoai(syms):
    from vnstock import Trading
    pb = Trading(source="VCI").price_board(syms)
    pb.columns = ["_".join(str(x) for x in c) if isinstance(c, tuple) else str(c) for c in pb.columns]
    col = lambda suf: next(c for c in pb.columns if c.endswith(suf))
    d = pd.DataFrame({"ma": pb[col("symbol")], "gia": pb[col("match_price")], "kl": pb[col("accumulated_volume")],
                      "nn_mua": pb[col("foreign_buy_volume")], "nn_ban": pb[col("foreign_sell_volume")]})
    d["nn_rong"] = d["nn_mua"] - d["nn_ban"]
    d["nn_rong_ty"] = (d["nn_rong"] * d["gia"] / 1e9).round(2)
    d["ngay"] = now.strftime("%Y-%m-%d"); d["gio"] = now.strftime("%H:%M")
    d.sort_values("nn_rong_ty", ascending=False).to_csv("data/vn100_ngoai.csv", index=False)


if __name__ == "__main__":
    syms = ds_vn100()
    open("data/vn100_ds.txt", "w").write("\n".join(syms))
    time.sleep(DELAY)
    try: ngoai(syms)
    except Exception as e: print("ngoai loi", repr(e)[:200])
    do_rong(syms)
