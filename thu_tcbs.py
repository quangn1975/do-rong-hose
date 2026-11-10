"""Thu TCBS tren GitHub: can khoa ten gi, va KHONG co Smart OTP thi goi duoc nhung gi. Khong in khoa."""
import os, json, inspect, re
from datetime import datetime, timezone, timedelta
SECRETS = [v for k, v in os.environ.items() if k.startswith("TCBS") and v]
out = []
def p(*a):
    s = " ".join(str(x) for x in a)
    for v in SECRETS: s = s.replace(v, "***")
    s = re.sub(r"eyJ[A-Za-z0-9_\-\.]{20,}", "***TOKEN***", s)
    out.append(s); print(s[:300], flush=True)
now = datetime.now(timezone(timedelta(hours=7)))
p("Chay luc", now.strftime("%Y-%m-%d %H:%M"), "(gio VN) | bien TCBS co trong moi truong:", sorted(k for k in os.environ if k.startswith("TCBS")))
END = now.strftime("%Y-%m-%d"); START = (now - timedelta(days=7)).strftime("%Y-%m-%d")
import vnstock_oapi as oapi
src = oapi.source("tcbs")
for name in ("status", "check"):
    try: p(f"## {name}:", json.dumps(getattr(src, name)(), ensure_ascii=False, default=str)[:900])
    except Exception as e: p(f"## {name} LOI:", type(e).__name__, str(e)[:500])
p("=== HAM CUA NGUON TCBS ===")
for n in dir(src):
    if n.startswith("_"): continue
    try: a = getattr(src, n, None)
    except Exception: continue
    if callable(a):
        try: sig = str(inspect.signature(a))
        except Exception: sig = "(?)"
        p(f"  {n}{sig[:150]}  # {(inspect.getdoc(a) or '').splitlines()[0][:110] if inspect.getdoc(a) else ''}")
def thu(label, fn):
    try:
        res = fn(); b = [e.body for e in res]; x = b[0] if b else None
        d = x.get("data", x) if isinstance(x, dict) else x
        p("## OK  ", label, f"-> {len(b)} trang, {len(d) if hasattr(d, '__len__') else '?'} muc | mau:", json.dumps(d[0] if isinstance(d, list) and d else d, ensure_ascii=False, default=str)[:300])
    except Exception as e:
        p("## LOI ", label, "->", type(e).__name__ + ":", str(e)[:400], "| code:", getattr(e, "code", ""), "| action:", str(getattr(e, "action", ""))[:200])
thu("gia FPT (ohlc)", lambda: src.ohlc("FPT", start=START, end=END))
thu("bang gia ro VN30 (board)", lambda: src.board(basket="VN30"))
thu("room ngoai VN30 (foreign_room)", lambda: src.foreign_room(basket="VN30"))
thu("lenh khop FPT (stock/price-history)", lambda: src.raw("stock/price-history", only_page=0, ticker="FPT", page=0, size=20, headIndex=-1))
if hasattr(src, "trades"): thu("lenh khop FPT (trades)", lambda: src.trades("FPT", limit=20))
thu("mo phien KHONG co OTP (authenticate)", lambda: [type("E", (), {"body": src.authenticate()})()])
for v in ("ohlc", "board"):
    try: p(f"## PREVIEW {v}:", json.dumps(src.preview(v, "FPT") if v == "ohlc" else src.preview(v, basket="VN30"), ensure_ascii=False, default=str)[:700])
    except Exception as e: p(f"## PREVIEW {v} LOI:", type(e).__name__, str(e)[:300])
os.makedirs("so_thu", exist_ok=True); open("so_thu/thu_tcbs.txt", "w").write("\n".join(out) + "\n")
