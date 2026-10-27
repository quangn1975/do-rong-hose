"""Thu phan trang trades (last_id) cua vnstock 5 trong phien."""
import os, time
import pandas as pd
K = os.environ.get("VNSTOCK_API_KEY", "")
out = []
def p(*a): out.append(" ".join(str(x) for x in a))
import vnstock
vnstock.login(K)
from vnstock import Market
def get(e, **kw):
    for k in range(4):
        try: return e.trades(**kw)
        except Exception as ex:
            p("loi", type(ex).__name__, str(ex)[:100]); time.sleep(6)
for sym in ("HPG", "VIC"):
    e = Market().equity(sym)
    t1 = get(e, limit=1000)
    p("##", sym, "trang1:", len(t1), "id min/max", t1["id"].min(), t1["id"].max(), "time", t1["time"].min(), t1["time"].max())
    p("   id dau/cuoi trang:", t1["id"].iloc[0], t1["id"].iloc[-1], "| 3 dong dau:", t1["id"].head(3).tolist(), "| 3 dong cuoi:", t1["id"].tail(3).tolist())
    seen = set(t1["id"])
    for name, lid in (("min_id", t1["id"].min()), ("max_id", t1["id"].max()), ("dong_cuoi", t1["id"].iloc[-1]), ("dong_dau", t1["id"].iloc[0])):
        t2 = get(e, limit=1000, last_id=lid)
        if t2 is None or not len(t2): p("   last_id =", name, "->", 0, "dong"); continue
        new = len(set(t2["id"]) - seen)
        p("   last_id =", name, "->", len(t2), "dong, moi:", new, "id min/max", t2["id"].min(), t2["id"].max(), "time", t2["time"].min(), t2["time"].max())
        time.sleep(0.5)
open("data/vnstock5_trades.txt", "w").write("\n".join(out)[:20000])
