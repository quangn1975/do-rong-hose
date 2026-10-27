"""ROE (4 quy gan nhat, %) cua VN100 + 33 ma, vnstock 5 Fundamental.ratio. Ket qua: data/roe_vn.csv (ma, roe, ky).
Dung cho bo loc realtime (ROE>16%). Chay 18:00 cung job dong tien."""
import os, re, sys, time
import pandas as pd
K = os.environ.get("VNSTOCK_API_KEY", "")
import vnstock
vnstock.login(K)
from vnstock import Fundamental
ds = open("data/vn100_ds.txt").read().split()
extra = [l.strip().upper() for l in open("ma33.txt") if l.strip() and not l.startswith("#")]
syms = sorted(set(ds) | set(extra))
rows, loi = [], 0
for s in syms:
    try:
        r = Fundamental().equity(s).ratio()
        r = r[(r["id"] == "RT_PRT_ROE") & r["period"].astype(str).str.match(r"^\d{4}-Q\d$")].dropna(subset=["value"])
        if len(r):
            r = r.sort_values("period")
            v = float(r["value"].iloc[-1]); v = v * 100 if abs(v) < 1.5 else v
            rows.append([s, round(v, 2), r["period"].iloc[-1]])
        else:
            loi += 1
    except Exception as e:
        loi += 1
        if loi <= 3: print("loi", s, type(e).__name__, str(e)[:120].replace(K or "@@", "***"))
    time.sleep(0.8)
out = pd.DataFrame(rows, columns=["ma", "roe", "ky"])
if len(out) >= 50:
    out.to_csv("data/roe_vn.csv", index=False)
print("ROE", len(out), "ma;", loi, "ma khong co")
