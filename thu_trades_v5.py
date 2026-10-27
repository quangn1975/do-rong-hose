"""Thu trades cua vnstock 5 trong phien (cau truc, thu tu, match_type, phan trang)."""
import os, time
K = os.environ.get("VNSTOCK_API_KEY", "")
out = []
def p(*a): out.append(" ".join(str(x) for x in a))
import vnstock
vnstock.login(K)
from vnstock import Market
for sym in ("TCB", "VCB", "FPT"):
    e = Market().equity(sym)
    try:
        t = None
        for k0 in range(5):
            try:
                t = e.trades(limit=1000); break
            except Exception as ex0:
                p("thu lai", sym, k0, type(ex0).__name__, str(ex0)[:100]); time.sleep(8)
        if t is None: continue
        p("##", sym, "trang 1:", len(t), "cot", list(t.columns))
        p(t.head(3).to_string()); p(t.tail(2).to_string())
        p("match_type:", t["match_type"].astype(str).value_counts().to_dict())
        n, tot, last = len(t), t.copy(), t.iloc[-1]["id"]
        for k in range(30):
            time.sleep(0.5)
            t2 = e.trades(limit=1000, last_id=last)
            if t2 is None or not len(t2): break
            import pandas as pd; tot = pd.concat([tot, t2])
            n += len(t2); last = t2.iloc[-1]["id"]
        p("tong lenh khop lay duoc:", n, "so trang them:", k)
        p("id trung nhau?", tot["id"].duplicated().sum())
        g = tot.groupby(tot["match_type"].astype(str))["volume"].sum(); p("KL theo match_type:", g.to_dict())
        p("thoi gian dau/cuoi:", tot["time"].iloc[0], tot["time"].iloc[-1])
        p("KL tong tu bang gia:", "xem so khac")
        for sd in ("buy", "sell", "b", "s"):
            try:
                r = e.trades(limit=2, side=sd); p("side", sd, "->", len(r), r.to_string()[:300])
            except Exception as ex:
                p("side", sd, "LOI", str(ex)[:150])
    except Exception as ex:
        p("LOI", sym, type(ex).__name__, str(ex)[:300].replace(K or "@@", "***"))
open("data/vnstock5_trades.txt", "w").write("\n".join(out)[:20000])
