import os, json, time
from datetime import datetime, timezone, timedelta
import pandas as pd
from ssi_sdk import Auth, Config
auth = Auth(Config(api_key=os.environ["SSI_API_KEY"], api_secret=os.environ["SSI_API_SECRET"])); auth.authenticate()
now = datetime.now(timezone(timedelta(hours=7)))
out = []
def p(*a): s = " ".join(str(x) for x in a); out.append(s); print(s[:300], flush=True)
def api(path, **params):
    b = auth.rest_client.get("/api/v3/data/" + path, params=params)
    return (b.get("data") if isinstance(b, dict) else b) or [], (b if isinstance(b, dict) else {})
vn30 = sorted(x["symbol"] for x in api("securitiesByBoard", index="VN30")[0])
F = (now - timedelta(days=760)).strftime("%Y/%m/%d 00:00:00"); T = now.strftime("%Y/%m/%d 23:59:59")
tong_trung = 0
for s in vn30 + ["VNINDEX"]:
    r, body = api("ohlc", symbol=s, **{"from": F, "to": T}, timeFrame="1d", pageIndex=1, pageSize=1000)
    d = pd.DataFrame(r)
    dup = d[d.duplicated("tradingDate", keep=False)]
    tong_trung += len(dup)
    meta = {k: v for k, v in body.items() if k != "data"}
    p(f"{s}: {len(d)} dong, {d['tradingDate'].nunique()} ngay, trung {len(dup)} | meta {meta} | dau {d['tradingDate'].iloc[0]} cuoi {d['tradingDate'].iloc[-1]}")
    if len(dup): p(dup.sort_values('tradingDate').tail(6).to_string()[:900])
    if s in ("FPT", "VNM"):
        # thu trang 2 va cach lay tung doan ngan de so
        r2, b2 = api("ohlc", symbol=s, **{"from": F, "to": T}, timeFrame="1d", pageIndex=2, pageSize=1000)
        p(f"  trang 2: {len(r2)} dong")
        F2 = (now - timedelta(days=200)).strftime("%Y/%m/%d 00:00:00")
        r3, _ = api("ohlc", symbol=s, **{"from": F2, "to": T}, timeFrame="1d", pageIndex=1, pageSize=1000)
        a = d.drop_duplicates("tradingDate").set_index("tradingDate")["close"]; c = pd.DataFrame(r3).drop_duplicates("tradingDate").set_index("tradingDate")["close"]
        k = a.index.intersection(c.index); khac = (a[k] != c[k])
        p(f"  so voi doan 200 ngay: {len(k)} ngay chung, khac {int(khac.sum())}; vi du {[(i, a[i], c[i]) for i in khac[khac].index[:5]]}")
p("TONG DONG TRUNG NGAY:", tong_trung)
os.makedirs("so_thu", exist_ok=True); open("so_thu/chan_doan.txt", "w").write("\n".join(out) + "\n")
