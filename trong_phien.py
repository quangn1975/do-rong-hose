"""Kiem tra gio mua trong phien: 11h30 so voi 14h20 (du lieu trong phien cua SSI, khoa trong Secrets, khong OTP).
BUOC THU (CHE_DO=thu): chi goi vai chuc lan, that cham, de biet SSI cho lay nen trong phien kieu nao va lui duoc bao xa.
Quy tac an toan de SSI khong khoa: dang nhap DUNG 1 lan, nghi giua moi lan goi, hong lien tiep thi DUNG han (khong goi don).
Khong in khoa."""
import os, sys, time, re
from datetime import datetime, timezone, timedelta

SECRETS = [v for v in (os.environ.get(k, "") for k in ("SSI_API_KEY", "SSI_API_SECRET")) if v]
OUT = "so"; os.makedirs(OUT, exist_ok=True)
VN = timezone(timedelta(hours=7)); now = datetime.now(VN)
NGHI = float(os.getenv("NGHI_GIAY", "3"))        # nghi giua 2 lan goi
dong = []
def log(*a):
    s = " ".join(str(x) for x in a)
    for v in SECRETS: s = s.replace(v, "***")
    print(s, flush=True); dong.append(s); return s
def luu():
    open(f"{OUT}/thu_trong_phien.txt", "w", encoding="utf-8").write(
        f"Lan chay: {now.strftime('%d/%m/%Y %H:%M')} (gio VN)\n" + "\n".join(dong) + "\n")

from ssi_sdk import Auth, Config
_auth = Auth(Config(api_key=os.environ["SSI_API_KEY"], api_secret=os.environ["SSI_API_SECRET"]))
try:
    _auth.authenticate()          # DUNG 1 lan, khong thu lai
except Exception as e:
    log("SSI tu choi dang nhap:", type(e).__name__, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(e)))[:200])
    luu(); sys.exit(1)

hong_lien_tiep = 0
def goi(path, **params):
    """Goi 1 lan duy nhat (khong tu thu lai), roi nghi. Hong 5 lan lien tiep thi dung ca chuong trinh."""
    global hong_lien_tiep
    try:
        body = _auth.rest_client.get("/api/v3/data/" + path, params=params)
        hong_lien_tiep = 0
        if isinstance(body, dict): body = body.get("data")
        return body or [], None
    except Exception as e:
        hong_lien_tiep += 1
        loi = f"{type(e).__name__}: " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(e)))[:160]
        if hong_lien_tiep >= 5:
            log("DUNG: hong 5 lan lien tiep, khong goi tiep de SSI khoi khoa. Loi cuoi:", loi); luu(); sys.exit(1)
        return [], loi
    finally:
        time.sleep(NGHI)

def d(dt): return dt.strftime("%Y/%m/%d")
gan = (now - timedelta(days=9), now - timedelta(days=1))                 # tuan vua roi
xa1 = (now - timedelta(days=372), now - timedelta(days=365))              # 1 nam truoc
xa2 = (now - timedelta(days=725), now - timedelta(days=718))              # 2 nam truoc
KHUNG = ["1h", "60m", "30m", "15m", "5m", "1m", "60", "15", "5", "1"]

log("=== BUOC THU: SSI cho lay nen trong phien kieu nao ===")
dung_duoc = {}
for ma in ("VNINDEX", "SSI"):
    for tf in KHUNG:
        r, loi = goi("ohlc", symbol=ma, **{"from": d(gan[0]) + " 00:00:00", "to": d(gan[1]) + " 23:59:59"},
                     timeFrame=tf, pageIndex=1, pageSize=1000)
        if loi: log(f"{ma} khung {tf}: LOI {loi}"); continue
        if not r: log(f"{ma} khung {tf}: 0 dong"); continue
        cot = list(r[0].keys()) if isinstance(r[0], dict) else []
        ngay = sorted({str(x.get("tradingDate", ""))[:10] for x in r if isinstance(x, dict)})
        so_dong_moi_ngay = round(len(r) / max(1, len(ngay)), 1)
        log(f"{ma} khung {tf}: {len(r)} dong, {len(ngay)} ngay, ~{so_dong_moi_ngay} dong/ngay")
        if so_dong_moi_ngay > 1.5:
            dung_duoc.setdefault(ma, []).append(tf)
            log("   cot:", cot)
            log("   dong dau:", r[0]); log("   dong 2:", r[1] if len(r) > 1 else ""); log("   dong cuoi:", r[-1])
for ma, tfs in dung_duoc.items():
    for tf in tfs[:3]:
        for ten, (a, b) in (("1 nam truoc", xa1), ("2 nam truoc", xa2)):
            r, loi = goi("ohlc", symbol=ma, **{"from": d(a) + " 00:00:00", "to": d(b) + " 23:59:59"},
                         timeFrame=tf, pageIndex=1, pageSize=1000)
            log(f"{ma} khung {tf} {ten} ({d(a)}-{d(b)}): " + (f"LOI {loi}" if loi else f"{len(r)} dong" + (f", dau: {r[0]}" if r else "")))
log("Khung dung duoc:", dung_duoc if dung_duoc else "KHONG CO khung trong phien nao")
luu()
