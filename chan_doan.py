import os
from datetime import datetime, timezone, timedelta
import pandas as pd
from ssi_sdk import Auth, Config
auth = Auth(Config(api_key=os.environ["SSI_API_KEY"], api_secret=os.environ["SSI_API_SECRET"])); auth.authenticate()
now = datetime.now(timezone(timedelta(hours=7)))
out = []
def p(*a): s = " ".join(str(x) for x in a); out.append(s); print(s[:300], flush=True)
def api(path, **params):
    b = auth.rest_client.get("/api/v3/data/" + path, params=params)
    return (b.get("data") if isinstance(b, dict) else b) or []
vn30 = sorted(x["symbol"] for x in api("securitiesByBoard", index="VN30"))
F = (now - timedelta(days=760)).strftime("%Y/%m/%d 00:00:00"); T = now.strftime("%Y/%m/%d 23:59:59")
cl = {}
for s in vn30:
    d = pd.DataFrame(api("ohlc", symbol=s, **{"from": F, "to": T}, timeFrame="1d", pageIndex=1, pageSize=1000))
    cl[s] = pd.Series((pd.to_numeric(d["close"]) / 1000).values, index=d["tradingDate"].str.replace("/", "-").values)
px = pd.DataFrame(cl).sort_index()
for n, ngays in ((20, ["2025-12-31", "2026-04-15", "2026-04-28"]), (50, ["2026-03-31", "2026-04-29", "2026-05-15"]), (200, ["2026-09-22"])):
    ma = px.rolling(n, min_periods=int(n * 0.8)).mean()
    ma_chuan = px.rolling(n, min_periods=n).mean()
    for ng in ngays:
        hieu = (px.loc[ng] - ma.loc[ng])
        gan = hieu[hieu.abs() < 0.02].round(9).to_dict()
        thieu = [s for s in vn30 if pd.isna(px.loc[ng, s])]
        chua_du = [s for s in vn30 if pd.notna(ma.loc[ng, s]) and pd.isna(ma_chuan.loc[ng, s])]
        p(f"MA{n} {ng}: tren {int((px.loc[ng] > ma.loc[ng]).sum())}/{int(ma.loc[ng].notna().sum())} | sat MA (<0.02): {gan} | khong co gia: {thieu} | MA tinh khi chua du {n} phien: {chua_du}")
p("so phien moi ma:", {s: int(px[s].notna().sum()) for s in vn30 if px[s].notna().sum() < len(px)})
os.makedirs("so_thu", exist_ok=True); open("so_thu/chan_doan.txt", "w").write("\n".join(out) + "\n")
