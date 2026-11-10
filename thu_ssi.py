"""Chay thu tren GitHub: goi thang SSI qua vnstock_oapi (KHONG dang nhap vnstock, khong ton 'thiet bi').
Ket qua: data/thu_ssi.txt (khong in khoa)."""
import os, sys, time, inspect, json
from datetime import datetime, timezone, timedelta
SECRETS = [v for v in (os.environ.get(k, "") for k in ("VNSTOCK_API_KEY", "SSI_API_KEY", "SSI_API_SECRET")) if v]
out = []
def p(*a):
    s = " ".join(str(x) for x in a)
    for v in SECRETS: s = s.replace(v, "***")
    out.append(s); print(s, flush=True)
def ghi():
    open("data/thu_ssi.txt", "w").write("\n".join(out)[:60000] + "\n")
now = datetime.now(timezone(timedelta(hours=7)))
p("Chay luc", now.strftime("%Y-%m-%d %H:%M"), "(gio VN)")
END = now.strftime("%Y-%m-%d"); START = (now - timedelta(days=12)).strftime("%Y-%m-%d")
try:
    import vnstock_oapi as oapi
    p("vnstock_oapi", getattr(oapi, "__version__", "?"), "| ten:", [n for n in dir(oapi) if not n.startswith("_")][:60])
    src = oapi.source("ssi")
except Exception as e:
    p("LOI khoi dong:", type(e).__name__, str(e)[:300]); ghi(); sys.exit(0)
p("=== HAM CUA NGUON SSI ===")
for n in dir(src):
    if n.startswith("_"): continue
    a = getattr(src, n, None)
    if callable(a):
        try: sig = str(inspect.signature(a))
        except Exception: sig = "(?)"
        doc = (inspect.getdoc(a) or "").split("\n")[0][:110]
        p(f"  {n}{sig[:170]}  # {doc}")
def body(res):
    try:
        b = [e.body for e in res] if isinstance(res, (list, tuple)) else [getattr(res, "body", res)]
    except Exception:
        b = [res]
    return b
def thu(label, fn):
    t = time.time()
    try:
        res = fn(); b = body(res); x = b[0] if b else None
        d = x.get("data", x) if isinstance(x, dict) else x
        n = len(d) if isinstance(d, (list, dict)) else "?"
        mau = d[-1] if isinstance(d, list) and d else d
        p("## OK  ", label, f"-> {len(b)} trang, {n} muc, {round(time.time()-t,1)} giay | khoa ngoai:", list(x.keys())[:12] if isinstance(x, dict) else type(x).__name__)
        p("   mau:", json.dumps(mau, ensure_ascii=False, default=str)[:600])
        return res
    except Exception as e:
        p("## LOI ", label, "->", type(e).__name__ + ":", str(e)[:300]); return None
thu("ohlc FPT", lambda: src.ohlc("FPT", start=START, end=END))
thu("ohlc VNINDEX", lambda: src.ohlc("VNINDEX", start=START, end=END))
for n, kw in (("board", {"basket": "VN30"}), ("board", {"basket": "VN100"}), ("board", {"basket": "HOSE"}),
              ("foreign_room", {"basket": "VN30"}), ("foreign_flow", {"symbol": "FPT", "start": START, "end": END}),
              ("index_members", {"index": "VN100"}), ("members", {"index": "VN100"}), ("symbols", {"exchange": "HOSE"})):
    if hasattr(src, n):
        thu(f"{n} {kw}", lambda: getattr(src, n)(**kw))
# thu ca duong vnstock khong dang nhap (neu duoc thi dung ham co san)
try:
    from vnstock import Market, Reference
    M = Market("ssi"); R = Reference("ssi")
    def thu2(label, fn):
        t = time.time()
        try:
            r = fn(); p("## OK  [vnstock khong login]", label, "->", len(r), "dong,", round(time.time()-t,1), "giay | cot:", list(r.columns)[:10]); return r
        except Exception as e:
            p("## LOI [vnstock khong login]", label, "->", type(e).__name__ + ":", str(e)[:220]); return None
    thu2("gia FPT", lambda: M.equity("FPT").ohlcv(start=START, end=END))
    thu2("khoi ngoai FPT", lambda: M.equity("FPT").foreign_flow(start=START, end=END))
    thu2("thong ke phien VNINDEX", lambda: M.index("VNINDEX").trade_history(start=START, end=END))
    thu2("tu doanh ro VN100", lambda: M.index("VN100").proprietary_flow(start=START, end=END))
    v = thu2("thanh phan VN100", lambda: R.index("VN100").members())
    thu2("danh sach HOSE", lambda: R.equity().list(exchange="HOSE"))
    if v is not None:
        S2 = (now - timedelta(days=320)).strftime("%Y-%m-%d"); t = time.time(); ok = 0; loi = ""
        for s in list(v["symbol"])[:20]:
            try: ok += 1 if len(M.equity(s).ohlcv(start=S2, end=END)) else 0
            except Exception as e: loi = type(e).__name__ + ": " + str(e)[:200]
        p(f"## TOC DO: 20 ma gia ~320 ngay: {ok}/20 duoc, {round(time.time()-t,1)} giay. Loi cuoi: {loi or 'khong'}")
except Exception as e:
    p("LOI vnstock khong login:", type(e).__name__, str(e)[:300])
ghi()
