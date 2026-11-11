"""THU 1 LAN: nhap Smart OTP o nut Run workflow -> GitHub mo phien TCBS -> lay thu 2 ma, cham.
Khong in OTP, khong in khoa, khong in token. Chi doc so lieu thi truong.
Khong co OTP: chi tu kiem tra moi truong (khong goi TCBS)."""
import os, json, re, time
from datetime import datetime, timezone, timedelta
T0 = time.time()
ev = {}
try: ev = json.load(open(os.environ.get("GITHUB_EVENT_PATH", "")))
except Exception: pass
OTP = str((ev.get("inputs") or {}).get("otp") or "").strip()
SECRETS = [v for v in (os.environ.get("TCBS_API_KEY", ""), OTP) if v]
out = []
def p(*a):
    s = " ".join(str(x) for x in a)
    for v in SECRETS: s = s.replace(v, "***")
    s = re.sub(r"eyJ[A-Za-z0-9_\-\.]{20,}", "***TOKEN***", s)
    out.append(s); print(s[:400], flush=True)
def ghi():
    os.makedirs("so_thu", exist_ok=True); open("so_thu/thu_tcbs.txt", "w").write("\n".join(out) + "\n")
now = datetime.now(timezone(timedelta(hours=7)))
p("Chay luc", now.strftime("%Y-%m-%d %H:%M:%S"), "(gio VN) | co OTP:", bool(OTP), "| do dai OTP:", len(OTP))
try:
    import keyring
    keyring.set_password("thu-kho-khoa", "x", "1"); ok = keyring.get_password("thu-kho-khoa", "x") == "1"
    p("## kho luu phien (keyring):", type(keyring.get_keyring()).__name__, "| ghi/doc duoc:", ok)
except Exception as e:
    p("## kho luu phien LOI:", type(e).__name__, str(e)[:200])
import vnstock_oapi as oapi
src = oapi.source("tcbs")
try: p("## trang thai truoc:", json.dumps(src.status(), ensure_ascii=False, default=str)[:400])
except Exception as e: p("## status LOI:", type(e).__name__, str(e)[:200])
if not OTP:
    p("Khong co OTP: dung o day, KHONG goi TCBS."); ghi(); raise SystemExit(0)
p(f"## Tu luc may chu bat dau chay tep nay den luc gui OTP: {round(time.time() - T0, 1)} giay")
try:
    r = src.authenticate(OTP)
    p("## MO PHIEN: OK | cac truong tra ve:", sorted(r.keys()) if isinstance(r, dict) else type(r).__name__)
except Exception as e:
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(e)))[:500]
    p("## MO PHIEN LOI:", type(e).__name__, "|", t, "| http:", getattr(e, "http_status", ""), "| code:", getattr(e, "code", ""))
    ghi(); raise SystemExit(0)
try: p("## trang thai sau:", json.dumps(src.status(), ensure_ascii=False, default=str)[:400])
except Exception as e: p("## status LOI:", type(e).__name__, str(e)[:200])
END = now.strftime("%Y-%m-%d"); START = (now - timedelta(days=7)).strftime("%Y-%m-%d")
def thu(label, fn):
    t = time.time()
    try:
        res = fn(); b = [e.body for e in res]; x = b[0] if b else None
        d = x.get("data", x) if isinstance(x, dict) else x
        p("## OK  ", label, f"-> {len(d) if hasattr(d, '__len__') else '?'} muc, {round(time.time() - t, 1)} giay | mau:", json.dumps(d[0] if isinstance(d, list) and d else d, ensure_ascii=False, default=str)[:260])
    except Exception as e:
        p("## LOI ", label, "->", type(e).__name__ + ":", re.sub(r"\s+", " ", str(e))[:300], "| http:", getattr(e, "http_status", ""))
thu("gia FPT", lambda: src.ohlc("FPT", start=START, end=END)); time.sleep(6)
thu("bang gia ro VN30", lambda: src.board(basket="VN30")); time.sleep(6)
for ma in ("FPT", "HPG"):
    for trang in (0, 1):
        thu(f"lenh khop {ma} trang {trang}", lambda: src.raw("stock/price-history", only_page=trang, ticker=ma, page=trang, size=100, headIndex=-1)); time.sleep(6)
ghi()
