"""Tim hieu cach thu vien goi SSI (dia chi, tham so) de viet lai goi THANG SSI, khong can thu vien vnstock.
Chi in cau truc yeu cau (khoa da duoc che), khong in khoa. Ket qua: data/thu_ssi.txt"""
import os, sys, json, inspect, re
from datetime import datetime, timezone, timedelta
SECRETS = [v for v in (os.environ.get(k, "") for k in ("SSI_API_KEY", "SSI_API_SECRET")) if v]
out = []
def p(*a):
    s = " ".join(str(x) for x in a)
    for v in SECRETS: s = s.replace(v, "***")
    s = re.sub(r"eyJ[A-Za-z0-9_\-\.]{20,}", "***TOKEN***", s)
    out.append(s); print(s[:300], flush=True)
def ghi(): open("data/thu_ssi.txt", "w").write("\n".join(out)[:150000] + "\n")
now = datetime.now(timezone(timedelta(hours=7)))
END = now.strftime("%Y-%m-%d"); START = (now - timedelta(days=6)).strftime("%Y-%m-%d")
import vnstock_oapi as oapi
src = oapi.source("ssi")
def xem(label, *a, **k):
    try: p("## PREVIEW", label, "->", json.dumps(src.preview(*a, **k), ensure_ascii=False, default=str)[:1500])
    except Exception as e: p("## PREVIEW LOI", label, type(e).__name__, str(e)[:300])
    try: p("## PLAN", label, "->", str(src.plan(*a, **k))[:1500])
    except Exception as e: p("## PLAN LOI", label, type(e).__name__, str(e)[:200])
xem("ohlc FPT", "ohlc", "FPT", start=START, end=END)
xem("ohlc VNINDEX", "ohlc", "VNINDEX", start=START, end=END)
xem("index VN30", "index", "VN30", start=START, end=END)
xem("foreign FPT", "foreign", "FPT", start=START, end=END)
xem("index_summary VN100", "index_summary", "VN100", start=START, end=END)
xem("index_members VN100", "index_members", "VN100")
xem("index_list", "index_list")
xem("symbols HOSE", "symbols", "HOSE")
xem("summary FPT", "summary", "FPT", start=START, end=END)
xem("security FPT", "security", "FPT")
def mau(label, fn):
    try:
        res = fn(); b = [e.body for e in res]; x = b[0]
        d = x.get("data", x) if isinstance(x, dict) else x
        p("## MAU", label, f"-> {len(b)} trang | khoa ngoai: {list(x.keys())[:12] if isinstance(x, dict) else type(x).__name__} | so muc: {len(d) if hasattr(d,'__len__') else '?'}")
        p("   ", json.dumps(d[0] if isinstance(d, list) and d else d, ensure_ascii=False, default=str)[:1800])
        e0 = res[0]
        p("   envelope:", {k: str(getattr(e0, k, None))[:200] for k in dir(e0) if not k.startswith("_") and k not in ("body",) and not callable(getattr(e0, k, None))})
    except Exception as e: p("## MAU LOI", label, type(e).__name__, str(e)[:300])
mau("index_summary VN100", lambda: src.index_summary("VN100", start=START, end=END))
mau("index_summary VNINDEX", lambda: src.index_summary("VNINDEX", start=START, end=END))
mau("summary FPT", lambda: src.summary("FPT", start=START, end=END))
mau("foreign FPT", lambda: src.foreign("FPT", start=START, end=END))
mau("index VN30", lambda: src.index("VN30", start=START, end=END))
mau("symbols HOSE", lambda: src.symbols("HOSE"))
mau("index_members VN30", lambda: src.index_members("VN30"))
# ma nguon phan SSI: dia chi goc, cach lay token
try:
    import vnstock_oapi.ssi as m
    p("## FILE", getattr(m, "__file__", "?"))
    import pkgutil
    path = list(getattr(m, "__path__", [])) or [os.path.dirname(m.__file__)]
    for root, _, files in os.walk(path[0] if os.path.isdir(path[0]) else os.path.dirname(m.__file__)):
        for f in sorted(files):
            if f.endswith((".py", ".json", ".yaml", ".yml", ".toml")) and "ssi" in (root + f).lower():
                t = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
                p(f"## SRC {os.path.join(root, f)} ({len(t)} ky tu)"); p(t[:14000])
except Exception as e:
    p("## SRC LOI", type(e).__name__, str(e)[:300])
ghi()
