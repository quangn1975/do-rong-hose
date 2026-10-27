"""% khoi luong khop do ben mua chu dong (match_type Buy / (Buy+Sell)) trong phien, cho cac ma ung vien cua bo loc 'Loc realtime'
(NN mua rong > 5 ty). Doc data/khoi_ngoai.csv do auto33.py vua ghi, ghi lai cot pct_mua_chu_dong va loc_realtime.
Dung vnstock 5 Market().equity(ma).trades (phan trang bang last_id)."""
import os, sys, time
import pandas as pd
LOG = []
def log(*a):
    LOG.append(" ".join(str(x) for x in a)); print(*a)
K = os.environ.get("VNSTOCK_API_KEY", "")
from datetime import datetime, timezone, timedelta
_n = datetime.now(timezone(timedelta(hours=7)))
if _n.weekday() >= 5 or not (9 * 60 <= _n.hour * 60 + _n.minute <= 14 * 60 + 50):
    print("Ngoai gio giao dich, bo qua"); sys.exit(0)
p = "data/khoi_ngoai.csv"
d = pd.read_csv(p)
if "nn_rong_ty" not in d.columns:
    sys.exit(0)
cand = d.index[d["nn_rong_ty"] > 5]
if len(cand) == 0:
    sys.exit(0)
try:
    import vnstock
    vnstock.login(K)
    from vnstock import Market
except Exception as e:
    log("Khong dang nhap duoc v5:", type(e).__name__, str(e)[:120].replace(K or "@@", "***")); open("data/mcd_trangthai.txt","w").write("\n".join(LOG)); sys.exit(0)

def mcd(sym, max_pages=60):
    """Trang 1 tra cac lenh khop moi nhat (toi da 1000); last_id = id nho nhat de lay lenh cu hon. Khu trung theo id."""
    e = Market().equity(sym)
    frames, seen, last = [], set(), None
    for _ in range(max_pages):
        kw = {"limit": 1000}
        if last is not None: kw["last_id"] = last
        t = None
        for _try in range(4):
            try:
                t = e.trades(**kw); break
            except Exception as ex:
                log(sym, "trades loi", type(ex).__name__, str(ex)[:120]); time.sleep(8)
        if t is None or not len(t): break
        t = t[~t["id"].isin(seen)]
        if not len(t): break
        seen |= set(t["id"]); frames.append(t)
        last = min(seen, key=lambda x: int(x))
        time.sleep(0.3)
    if not frames: return None, 0
    a = pd.concat(frames)
    mt = a["match_type"].astype(str).str.lower()
    buy, sell = float(a.loc[mt == "buy", "volume"].sum()), float(a.loc[mt == "sell", "volume"].sum())
    tot = buy + sell
    return (round(buy / tot * 100, 1) if tot > 0 else None), len(a)

d["pct_mua_chu_dong"] = pd.to_numeric(d["pct_mua_chu_dong"], errors="coerce")
for i in cand:
    s = d.at[i, "ma"]
    try:
        v, n = mcd(s)
        if v is not None: d.at[i, "pct_mua_chu_dong"] = v
        log(s, "mua chu dong", v, "% tren", n, "lenh khop")
    except Exception as ex:
        log(s, "loi", type(ex).__name__, str(ex)[:100])

def ok(r):
    if r["nn_rong_ty"] <= 5: return 0
    if pd.isna(r["pct_mua_chu_dong"]) or r["pct_mua_chu_dong"] <= 60: return 0
    kl = pd.to_numeric(r["kl_vuot_tb5_pct"], errors="coerce")
    if pd.isna(kl) or kl < 10: return 0
    roe = pd.to_numeric(r["roe"], errors="coerce")
    if pd.isna(roe) or roe <= 16: return 0
    return 1
d["loc_realtime"] = d.apply(ok, axis=1)
d.to_csv(p, index=False)
log("Loc realtime dat:", int(d["loc_realtime"].sum()), "ma")
open("data/mcd_trangthai.txt", "w").write(d["gio"].iloc[0] + "\n" + "\n".join(LOG))
