"""Chay thu tren GitHub: nguon SSI (khoa SSI trong Secrets) co lay duoc so tu may chu GitHub khong.
Ket qua: data/thu_ssi.txt (khong in khoa)."""
import os, sys, time
from datetime import datetime, timezone, timedelta
SECRETS = [v for v in (os.environ.get(k, "") for k in ("VNSTOCK_API_KEY", "SSI_API_KEY", "SSI_API_SECRET")) if v]
out = []
def p(*a):
    s = " ".join(str(x) for x in a)
    for v in SECRETS: s = s.replace(v, "***")
    out.append(s); print(s, flush=True)
def ghi():
    open("data/thu_ssi.txt", "w").write("\n".join(out)[:40000] + "\n")
now = datetime.now(timezone(timedelta(hours=7)))
p("Chay luc", now.strftime("%Y-%m-%d %H:%M"), "(gio VN)")
p("Co khoa trong moi truong:", {k: bool(os.environ.get(k)) for k in ("VNSTOCK_API_KEY", "SSI_API_KEY", "SSI_API_SECRET")})
END = now.strftime("%Y-%m-%d"); START = (now - timedelta(days=12)).strftime("%Y-%m-%d")
try:
    import vnstock
    vnstock.login(os.environ.get("VNSTOCK_API_KEY", "")); p("login vnstock: OK", vnstock.__version__)
    from vnstock import Market, Reference
    M = Market("ssi"); R = Reference("ssi")
except Exception as e:
    p("LOI khoi dong:", type(e).__name__, str(e)[:300]); ghi(); sys.exit(0)
def thu(label, fn):
    t = time.time()
    try:
        r = fn(); n = len(r) if hasattr(r, "__len__") else "?"
        p("## OK  ", label, "->", n, "dong |", round(time.time() - t, 1), "giay | cot:", list(getattr(r, "columns", []))[:14])
        try: p(r.sort_values(r.columns[0]).tail(1).to_string()[:500])
        except Exception: p(str(r)[:300])
        return r
    except Exception as e:
        p("## LOI ", label, "->", type(e).__name__ + ":", str(e)[:300]); return None
thu("gia FPT", lambda: M.equity("FPT").ohlcv(start=START, end=END))
thu("khoi ngoai FPT", lambda: M.equity("FPT").foreign_flow(start=START, end=END))
thu("thong ke phien FPT", lambda: M.equity("FPT").trade_history(start=START, end=END))
thu("chi so VNINDEX", lambda: M.index("VNINDEX").ohlcv(start=START, end=END))
thu("thong ke phien VNINDEX", lambda: M.index("VNINDEX").trade_history(start=START, end=END))
thu("khoi ngoai theo ro VN30", lambda: M.index("VN30").foreign_flow(start=START, end=END))
thu("tu doanh theo ro VN100", lambda: M.index("VN100").proprietary_flow(start=START, end=END))
vn100 = thu("thanh phan VN100", lambda: R.index("VN100").members())
thu("thanh phan VN30", lambda: R.index("VN30").members())
thu("danh sach ma HOSE", lambda: R.equity().list(exchange="HOSE"))
# do toc do: 20 ma lien tiep, de biet 408 ma mat bao lau va co bi gioi han khong
if vn100 is not None:
    syms = list(vn100["symbol"])[:20]; t = time.time(); ok = 0; loi = ""
    S2 = (now - timedelta(days=320)).strftime("%Y-%m-%d")
    for s in syms:
        try:
            d = M.equity(s).ohlcv(start=S2, end=END); ok += 1 if len(d) else 0
        except Exception as e:
            loi = type(e).__name__ + ": " + str(e)[:200]
    p(f"## TOC DO: 20 ma gia ~320 ngay: {ok}/20 duoc, {round(time.time() - t, 1)} giay, so dong ma cuoi: {len(d) if ok else 0}. Loi cuoi: {loi or 'khong'}")
ghi()
