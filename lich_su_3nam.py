"""Tai 3 nam gia ngay (OHLCV) cua ro VN30 + 15 ma chot + 33 ma lon, chay tay 1 lan.
Dung de cho may hoc thu tim quy luat (khong dung cho Google Sheet).
Ket qua: data/lich_su_3nam.csv (ma,ngay,open,high,low,close,volume), data/lich_su_3nam_trangthai.txt
"""
import sys, time
import pandas as pd
from ngay15 import lich_su, DELAY, now

SO_NGAY = 1150          # khoang 3 nam lich
CHOT = "VIC VHM MSN MCH TCB HDB VPB VCB FPT HPG MWG VNM GAS BSR GVR".split()
gio = now.strftime("%Y-%m-%d %H:%M")
st = []


def ghi():
    open("data/lich_su_3nam_trangthai.txt", "w").write(f"{gio} (gio VN)\n" + "\n".join(st) + "\n")


def vn30():
    from vnstock import Listing
    for src in ("VCI", "kbs"):
        try:
            s = Listing(source=src).symbols_by_group("VN30")
            s = list(s.astype(str)) if hasattr(s, "astype") else list(s)
            s = sorted(set(x.upper() for x in s if len(x) == 3))
            if len(s) >= 25:
                st.append(f"VN30: {len(s)} ma (nguon {src})")
                return s
        except Exception as e:
            st.append(f"VN30 loi {src}: {repr(e)[:100]}")
    return []


m33 = [l.strip().upper() for l in open("ma33.txt") if l.strip() and not l.startswith("#")]
ds = sorted(set(vn30()) | set(CHOT) | set(m33))
rows, loi = [], []
for i, s in enumerate(ds):
    df = lich_su(s, SO_NGAY)
    if df is None or len(df) < 100:
        loi.append(s)
    else:
        df.insert(0, "ma", s)
        df = df.rename(columns={"time": "ngay"})
        rows.append(df)
    if i % 10 == 0:
        print(i, s, flush=True)
    time.sleep(DELAY)

if not rows:
    st.append("Khong lay duoc ma nao")
    ghi()
    sys.exit(0)
out = pd.concat(rows, ignore_index=True)
out.to_csv("data/lich_su_3nam.csv", index=False)
st.append(f"OK {len(rows)}/{len(ds)} ma, {len(out)} dong, tu {out['ngay'].min()} den {out['ngay'].max()}")
if loi:
    st.append("thieu/ngan: " + " ".join(loi))
ghi()
