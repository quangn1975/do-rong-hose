"""Thu cach lay ROE va ty le mua chu dong trong phien bang vnstock 5 (chi in cau truc, khong in khoa)."""
import os, sys, traceback
K = os.environ.get("VNSTOCK_API_KEY", "")
out = []
def p(*a):
    out.append(" ".join(str(x) for x in a))
def safe(label, fn):
    try:
        r = fn(); p("##", label, "OK"); return r
    except Exception as e:
        p("##", label, "LOI", type(e).__name__, str(e)[:300].replace(K or "@@", "***")); return None
import vnstock
vnstock.login(K)
from vnstock import Market
try:
    from vnstock import Fundamental
except Exception as e:
    Fundamental = None; p("Khong import duoc Fundamental", repr(e)[:200])
e = Market().equity("FPT")
t = safe("trades limit=1000", lambda: e.trades(limit=1000))
if t is not None:
    p("cot:", list(t.columns)); p(t.head(4).to_string()); p("so dong", len(t))
    for c in t.columns:
        if t[c].dtype == object or str(t[c].dtype).startswith("str"):
            p("gia tri", c, t[c].astype(str).value_counts().head(5).to_dict())
if Fundamental is not None:
    f = safe("Fundamental().equity", lambda: Fundamental().equity("FPT"))
    if f is not None:
        p("ham:", [x for x in dir(f) if not x.startswith("_")])
        for fn in ("ratio", "ratios", "metrics", "indicators", "financial_ratio"):
            if hasattr(f, fn):
                r = safe(fn, lambda: getattr(f, fn)())
                if r is not None:
                    p("cot", fn, list(r.columns)[:80])
                    p("ky co trong du lieu:", sorted(r["period"].astype(str).unique())[-8:])
                    m = r[r["name"].astype(str).str.contains("ROE|ROA|ROIC|vốn chủ", case=False, regex=True)]
                    p(m.tail(12).to_string()[:3000])
if t is not None:
    p("id dau/cuoi:", t.iloc[0].to_dict() if len(t) else None, t.iloc[-1].to_dict() if len(t) else None)
    r2 = safe("trades side=buy", lambda: e.trades(limit=3, side="buy"))
    if r2 is not None: p(r2.to_string())
open("data/vnstock5_loc.txt", "w").write("\n".join(out)[:20000])
