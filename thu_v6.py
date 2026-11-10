"""Chay thu vnstock the he 6 tren GitHub CHI voi khoa vnstock (khong khoa cong ty chung khoan, khong OTP).
Muc dich: biet loai so nao lay duoc: gia, chi so, khoi ngoai, tu doanh, BCTC, danh sach ro.
Ket qua: data/thu_v6.txt (khong in khoa)."""
import os, sys, inspect, traceback
from datetime import datetime, timezone, timedelta
import pandas as pd

K = os.environ.get("VNSTOCK_API_KEY", "")
out = []
def p(*a):
    s = " ".join(str(x) for x in a)
    if K: s = s.replace(K, "***")
    out.append(s); print(s, flush=True)
def ghi():
    open("data/thu_v6.txt", "w").write("\n".join(out)[:60000] + "\n")

now = datetime.now(timezone(timedelta(hours=7)))
p("Chay luc", now.strftime("%Y-%m-%d %H:%M"), "(gio VN)")
END = now.strftime("%Y-%m-%d"); START = (now - timedelta(days=45)).strftime("%Y-%m-%d")

def mo_ta(r):
    if isinstance(r, pd.DataFrame):
        return f"{len(r)} dong | cot: {list(r.columns)[:40]}\n{r.tail(2).to_string()[:900]}"
    if isinstance(r, (list, tuple, set)):
        r = list(r); return f"list {len(r)}: {r[:40]}"
    if isinstance(r, dict):
        return f"dict {list(r.keys())[:30]}"
    return f"{type(r).__name__}: {str(r)[:500]}"

def thu(label, *fns):
    """Thu lan luot cac cach goi, cach nao duoc thi dung."""
    err = ""
    for fn in fns:
        try:
            r = fn()
            if r is None or (hasattr(r, "__len__") and len(r) == 0):
                err = "tra ve rong"; continue
            p("## OK  ", label, "->", mo_ta(r)); return r
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:260]}"
    p("## LOI ", label, "->", err); return None

def ham(obj):
    res = []
    for n in dir(obj):
        if n.startswith("_"): continue
        try:
            a = getattr(obj, n)
            if callable(a):
                try: sig = str(inspect.signature(a))
                except Exception: sig = "(?)"
                res.append(n + sig)
        except Exception:
            pass
    return res

try:
    import vnstock
    p("vnstock", getattr(vnstock, "__version__", "?"))
    p("ten cong khai:", [n for n in dir(vnstock) if not n.startswith("_")][:80])
except Exception as e:
    p("KHONG import duoc vnstock:", repr(e)[:300]); ghi(); sys.exit(0)

try:
    vnstock.login(K); p("login: OK")
except Exception as e:
    p("login LOI:", type(e).__name__, str(e)[:300])

try:
    from vnstock import Market
except Exception as e:
    p("Khong co Market:", repr(e)[:200]); ghi(); sys.exit(0)
Fundamental = getattr(vnstock, "Fundamental", None)
Reference = getattr(vnstock, "Reference", None)

p("\n===== 1. GIA CO PHIEU (nguon mac dinh) =====")
try:
    e = Market().equity("FPT"); p("ham Market().equity:", ham(e))
except Exception as ex:
    e = None; p("Market().equity LOI:", type(ex).__name__, str(ex)[:300])
if e is not None:
    thu("gia FPT ohlcv", lambda: e.ohlcv(start=START, end=END), lambda: e.ohlcv(start=START, end=END, interval="1D"),
        lambda: e.ohlcv(limit=30), lambda: e.ohlcv())
    p("\n===== 2. KHOI NGOAI / TU DOANH / THONG KE NGAY =====")
    for fn in ("foreign_flow", "proprietary_flow", "trade_history", "active_flow", "session_stats", "summary", "quote"):
        if hasattr(e, fn):
            thu(fn + " FPT", lambda: getattr(e, fn)(limit=5), lambda: getattr(e, fn)())
        else:
            p("## KHONG CO HAM", fn)

p("\n===== 3. CHI SO =====")
for ix in ("VNINDEX", "VN30", "VN100"):
    try:
        i = Market().index(ix)
        if ix == "VNINDEX": p("ham Market().index:", ham(i))
        thu(f"chi so {ix} ohlcv", lambda: i.ohlcv(start=START, end=END), lambda: i.ohlcv(limit=30), lambda: i.ohlcv())
        if hasattr(i, "trade_history"):
            thu(f"chi so {ix} trade_history", lambda: i.trade_history(limit=5), lambda: i.trade_history())
    except Exception as ex:
        p("## LOI  chi so", ix, type(ex).__name__, str(ex)[:260])

p("\n===== 4. DANH SACH RO / DANH SACH MA =====")
if Reference is None:
    p("Khong co Reference")
else:
    try:
        R = Reference(); p("ham Reference():", ham(R))
    except Exception as ex:
        R = None; p("Reference() LOI:", type(ex).__name__, str(ex)[:260])
    if R is not None:
        for ix in ("VN30", "VN100", "VNINDEX", "HOSE"):
            try:
                ri = R.index(ix)
                if ix == "VN30": p("ham Reference().index:", ham(ri))
                for n in dir(ri):
                    if n.startswith("_"): continue
                    a = getattr(ri, n, None)
                    if callable(a):
                        thu(f"Reference.index({ix}).{n}", lambda: a())
            except Exception as ex:
                p("## LOI  Reference.index", ix, type(ex).__name__, str(ex)[:260])
        for n in ("equity", "listing", "symbols", "exchange", "industry", "search"):
            if hasattr(R, n):
                a = getattr(R, n)
                thu(f"Reference.{n}", lambda: a(), lambda: a("HOSE"), lambda: a(exchange="HOSE"))

p("\n===== 5. BAO CAO TAI CHINH =====")
if Fundamental is None:
    p("Khong co Fundamental")
else:
    try:
        f = Fundamental().equity("FPT"); p("ham Fundamental().equity:", ham(f))
        for n in dir(f):
            if n.startswith("_"): continue
            a = getattr(f, n, None)
            if callable(a):
                r = thu(f"Fundamental.{n} FPT", lambda: a(), lambda: a(period="quarter"))
                if isinstance(r, pd.DataFrame) and "period" in r.columns:
                    p("   ky moi nhat:", sorted(r["period"].astype(str).unique())[-6:])
    except Exception as ex:
        p("## LOI  Fundamental", type(ex).__name__, str(ex)[:260])

p("\n===== 6. TUNG NGUON (khong co khoa cong ty chung khoan) =====")
for src in ("vci", "kbs", "ssi", "tcbs", "dnse", "fhsc"):
    def goi(s=src):
        ee = Market(s).equity("FPT")
        try: return ee.ohlcv(start=START, end=END)
        except TypeError: return ee.ohlcv(limit=30)
    thu(f"nguon {src}: gia FPT", goi)
    def goi2(s=src):
        return Market(s).equity("FPT").foreign_flow(limit=5)
    thu(f"nguon {src}: khoi ngoai FPT", goi2)

ghi()
