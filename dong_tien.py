"""dong_tien.py -> data/dong_tien.csv
Tu tung lenh khop trong phien (vnstock quote.intraday) tinh:
 - % mua chu dong (khoi luong mua chu dong / (mua + ban chu dong))
 - theo co lenh (gia tri 1 lenh): ca map / soi gia / ca nhan(cuu non): KL mua CD, ban CD, mua rong (ty dong)
NGUONG la so tu dat, CHUA doi chieu voi TCInvest -> chinh trong NGUONG_* sau khi doi chieu."""
import os, sys, time
import pandas as pd
from datetime import datetime, timezone, timedelta
DELAY = float(os.getenv("VNSTOCK_DELAY", "3.2"))
NGUONG_CA_MAP = float(os.getenv("NGUONG_CA_MAP", "1e9"))   # >= 1 ty / lenh (tam)
NGUONG_SOI_GIA = float(os.getenv("NGUONG_SOI_GIA", "2e8"))  # 200 trieu - 1 ty (tam)
now = datetime.now(timezone(timedelta(hours=7)))


def ticks(sym):
    from vnstock import Vnstock
    q = Vnstock().stock(symbol=sym, source="VCI").quote
    for ps in (100000, 20000, 5000):
        try:
            df = q.intraday(page_size=ps)
            if df is not None and len(df):
                return df
        except Exception as e:
            print("intraday loi", sym, ps, repr(e)[:120])
        time.sleep(DELAY)
    return None


def tinh(sym):
    df = ticks(sym)
    if df is None: return None
    df = df[df["match_type"].isin(["Buy", "Sell"])].copy()
    if df.empty: return None
    px = df["price"].astype(float)
    px = px * 1000 if px.median() < 1000 else px          # nghin dong -> dong
    df["gt"] = px * df["volume"].astype(float)
    df["nhom"] = pd.cut(df["gt"], [-1, NGUONG_SOI_GIA, NGUONG_CA_MAP, 1e18], labels=["ca_nhan", "soi_gia", "ca_map"], right=False)
    buy = df["match_type"] == "Buy"
    out = {"ma": sym, "so_lenh": len(df), "ngay": str(df["time"].iloc[-1])[:10],
           "pct_mua_chu_dong": round(df.loc[buy, "volume"].sum() / df["volume"].sum() * 100, 1)}
    for g in ("ca_map", "soi_gia", "ca_nhan"):
        m = df["nhom"] == g
        gm, gb = df.loc[m & buy, "gt"].sum(), df.loc[m & ~buy, "gt"].sum()
        out[g + "_mua_ty"] = round(gm / 1e9, 2); out[g + "_ban_ty"] = round(gb / 1e9, 2)
        out[g + "_rong_ty"] = round((gm - gb) / 1e9, 2)
    return out


if __name__ == "__main__":
    syms = [s.strip() for s in open("ma33.txt").read().replace(",", "\n").split() if s.strip()]
    if len(sys.argv) > 1: syms = sys.argv[1].split(",")
    rows = []
    for s in syms:
        t0 = time.time()
        try:
            r = tinh(s)
            if r: rows.append(r)
            print(s, "OK" if r else "trong", round(time.time() - t0, 1), "s", flush=True)
        except Exception as e:
            print(s, "loi", repr(e)[:150], flush=True)
        time.sleep(DELAY)
    d = pd.DataFrame(rows)
    d["gio"] = now.strftime("%Y-%m-%d %H:%M")
    d.to_csv("data/dong_tien.csv", index=False)
