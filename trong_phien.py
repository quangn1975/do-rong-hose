"""Kiem tra gio mua trong phien: 11h30 so voi 13h15, 14h20 va dong cua, trong nhung ngay BUOI SANG bi ban manh.
Nguon: nen trong phien cua SSI (khoa trong Secrets, khong OTP). VNINDEX nen 5 phut, 100 ma VN100 nen 15 phut.
Quy tac an toan de SSI khong khoa: dang nhap DUNG 1 lan, nghi giua moi lan goi, hong lien tiep thi DUNG han, co tran so lan goi.
Ghi ra: so/trong_phien_ket_qua.txt (bang ket qua), so/trong_phien_ngay.csv (moi ngay 1 dong), so/trong_phien_ma.csv (moi ma moi ngay).
Khong in khoa."""
import os, sys, time, re
from datetime import datetime, timezone, timedelta
import pandas as pd

SECRETS = [v for v in (os.environ.get(k, "") for k in ("SSI_API_KEY", "SSI_API_SECRET")) if v]
OUT = "so"; os.makedirs(OUT, exist_ok=True)
VN = timezone(timedelta(hours=7)); now = datetime.now(VN)
NGHI = float(os.getenv("NGHI_GIAY", "2"))            # nghi giua 2 lan goi
TRAN_GOI = int(os.getenv("TRAN_GOI", "1600"))        # khong bao gio goi qua so nay trong 1 luot
PHI = 0.004                                          # phi mua 0,15% + phi ban 0,15% + thue ban 0,1%
dong, so_goi, hong_lien_tiep = [], 0, 0
def log(*a):
    s = " ".join(str(x) for x in a)
    for v in SECRETS: s = s.replace(v, "***")
    print(s, flush=True); dong.append(s); return s
def luu():
    open(f"{OUT}/trong_phien_ket_qua.txt", "w", encoding="utf-8").write(
        f"Lan chay: {now.strftime('%d/%m/%Y %H:%M')} (gio VN) - {so_goi} lan goi SSI\n" + "\n".join(dong) + "\n")

from ssi_sdk import Auth, Config
_auth = Auth(Config(api_key=os.environ["SSI_API_KEY"], api_secret=os.environ["SSI_API_SECRET"]))
try:
    _auth.authenticate()          # DUNG 1 lan, khong thu lai
except Exception as e:
    log("SSI tu choi dang nhap:", type(e).__name__, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(e)))[:200]); luu(); sys.exit(1)

def goi(path, **params):
    """Goi 1 lan; hong thi cho 30 giay thu lai dung 1 lan. Hong 5 lan lien tiep hoac cham tran thi dung ca chuong trinh."""
    global so_goi, hong_lien_tiep
    for lan in (1, 2):
        if so_goi >= TRAN_GOI:
            log(f"DUNG: da cham tran {TRAN_GOI} lan goi."); luu(); sys.exit(1)
        so_goi += 1
        try:
            body = _auth.rest_client.get("/api/v3/data/" + path, params=params)
            hong_lien_tiep = 0; time.sleep(NGHI)
            if isinstance(body, dict): body = body.get("data")
            return body or []
        except Exception as e:
            hong_lien_tiep += 1
            loi = f"{type(e).__name__}: " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(e)))[:160]
            if hong_lien_tiep >= 5:
                log("DUNG: hong 5 lan lien tiep, khong goi tiep de SSI khoi khoa. Loi cuoi:", loi); luu(); sys.exit(1)
            time.sleep(30)
    return []

def d(dt): return dt.strftime("%Y/%m/%d")
def nen(ma, tf, tu, den, buoc):
    """Lay nen trong phien theo tung o thoi gian nho (moi o < 1000 dong) de khong can lat trang."""
    kq, a = [], tu
    while a <= den:
        b = min(a + timedelta(days=buoc - 1), den)
        kq += goi("ohlc", symbol=ma, **{"from": d(a) + " 00:00:00", "to": d(b) + " 23:59:59"}, timeFrame=tf, pageIndex=1, pageSize=1000)
        a = b + timedelta(days=1)
    df = pd.DataFrame(kq)
    if not len(df): return df
    df["t"] = pd.to_datetime(df["tradingDate"], format="%Y/%m/%d %H:%M:%S", errors="coerce")
    for c in ("open", "high", "low", "close"): df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["t", "close"]).drop_duplicates("t").sort_values("t")
    df["ngay"] = df["t"].dt.strftime("%Y-%m-%d"); df["phut"] = df["t"].dt.hour * 60 + df["t"].dt.minute
    return df

# ---------- 1. SSI cho lui duoc bao xa? ----------
hom_qua = (now - timedelta(days=1)).replace(tzinfo=None)
xa_nhat = None
for n in (45, 90, 135, 180, 270, 360, 540, 700):
    a = hom_qua - timedelta(days=n + 6); b = hom_qua - timedelta(days=n)
    r = goi("ohlc", symbol="VNINDEX", **{"from": d(a) + " 00:00:00", "to": d(b) + " 23:59:59"}, timeFrame="5m", pageIndex=1, pageSize=1000)
    log(f"Do lui: cach day {n} ngay -> {len(r)} dong")
    if r: xa_nhat = n + 6
    else: break
if not xa_nhat:
    xa_nhat = 44
TU = hom_qua - timedelta(days=xa_nhat); DEN = hom_qua
log(f"Lay du lieu trong phien tu {d(TU)} den {d(DEN)}")

# ---------- 2. VNINDEX nen 5 phut ----------
ix = nen("VNINDEX", "5m", TU, DEN, 18)
if not len(ix): log("Khong co nen VNINDEX"); luu(); sys.exit(1)
def gia_luc(g, phut, tf):
    """Gia tai thoi diem 'phut' = gia dong cua cay nen cuoi cung da ket thuc truoc hoac dung luc do."""
    x = g[g["phut"] + tf <= phut]
    return x["close"].iloc[-1] if len(x) else float("nan")
def tom_tat(df, tf):
    r = []
    for ngay, g in df.groupby("ngay"):
        sang = g[g["phut"] < 690]
        if len(sang) < 3 or len(g[g["phut"] >= 780]) < 2: continue          # ngay thieu du lieu
        i_day = g["low"].idxmin()
        r.append({"ngay": ngay, "p1130": gia_luc(g, 690, tf), "p1315": gia_luc(g, 795, tf), "p1420": gia_luc(g, 860, tf),
                  "dong": g["close"].iloc[-1], "day": g["low"].min(), "day_sang": int(g.loc[i_day, "phut"] < 690)})
    return pd.DataFrame(r).set_index("ngay").sort_index() if r else pd.DataFrame()
vi = tom_tat(ix, 5)
vi["truoc"] = vi["dong"].shift(1)
NGAY = list(vi.index)
log(f"VNINDEX: {len(vi)} phien du du lieu ({NGAY[0]} -> {NGAY[-1]})")

# ---------- 3. 100 ma VN100 nen 15 phut ----------
vn100 = sorted({str(x.get("symbol")) for x in goi("securitiesByBoard", index="VN100") if isinstance(x, dict) and x.get("symbol")})
log(f"VN100: {len(vn100)} ma")
ma_rows, t0 = [], time.time()
for k, ma in enumerate(vn100):
    df = nen(ma, "15m", TU, DEN, 55)
    if not len(df): continue
    s = tom_tat(df, 15)
    if not len(s): continue
    s = s.reindex(NGAY); s["truoc"] = s["dong"].shift(1); s["ma"] = ma
    ma_rows.append(s.reset_index())
    if k % 20 == 0: log(f"  ma {k}/{len(vn100)} {ma} ({round(time.time() - t0)} giay, {so_goi} lan goi)")
mm = pd.concat(ma_rows, ignore_index=True) if ma_rows else pd.DataFrame()
mm.to_csv(f"{OUT}/trong_phien_ma.csv", index=False)
log(f"VN100: lay duoc {mm['ma'].nunique() if len(mm) else 0} ma, {so_goi} lan goi SSI")

# ---------- 4. Tinh ----------
GIO = [("a 11h30", "p1130"), ("b 13h15", "p1315"), ("c 14h20", "p1420"), ("d dong cua", "dong")]
KY = (3, 10, 20)
# do rong luc 11h30: % ma VN100 dang giam so voi dong cua hom truoc
mm["giam_sang"] = (mm["p1130"] < mm["truoc"]).where(mm["p1130"].notna() & mm["truoc"].notna())
vi["pct_giam_1130"] = mm.groupby("ngay")["giam_sang"].mean().reindex(NGAY)
vi["so_ma"] = mm.groupby("ngay")["giam_sang"].count().reindex(NGAY)
# loi suat VNINDEX
pos = {n: i for i, n in enumerate(NGAY)}
for ten, cot in GIO:
    for h in KY:
        vi[f"vni_{cot}_{h}"] = [(vi["dong"].iloc[pos[n] + h] / vi.loc[n, cot] - 1 - PHI) if pos[n] + h < len(NGAY) else float("nan") for n in NGAY]
# loi suat trung binh VN100 (bo ma co buoc nhay gia qua 8% trong ky giu: thuong la ngay chia co tuc, chia tach)
cl = mm.pivot(index="ngay", columns="ma", values="dong").reindex(NGAY)
nhay = (cl / cl.shift(1) - 1).abs() > 0.08
for ten, cot in GIO:
    pv = mm.pivot(index="ngay", columns="ma", values=cot).reindex(NGAY)
    for h in KY:
        ret = cl.shift(-h) / pv - 1 - PHI
        xau = nhay.astype(float).shift(-1).rolling(h).max().shift(-(h - 1)).fillna(0).astype(bool)
        vi[f"vn100_{cot}_{h}"] = ret.mask(xau).mean(axis=1)
vi["hoi_1130_dong"] = vi["dong"] / vi["p1130"] - 1
vi["roi_sang"] = vi["p1130"] / vi["truoc"] - 1
vi.round(5).to_csv(f"{OUT}/trong_phien_ngay.csv")

def pct(x): return "—" if pd.isna(x) else f"{x * 100:.2f}%".replace(".", ",")
nhom = [("Sang can kiet: tu 65% ma VN100 giam luc 11h30", vi[vi["pct_giam_1130"] >= 0.65]),
        ("Sang can kiet MANH: tu 75% ma giam luc 11h30", vi[vi["pct_giam_1130"] >= 0.75]),
        ("Sang VNINDEX roi tu 1% luc 11h30", vi[vi["roi_sang"] <= -0.01]),
        ("Moc: moi ngay", vi[vi["pct_giam_1130"].notna()])]
log("")
log("BANG 1 - Buoi chieu co hoi khong (VNINDEX)")
log("Nhom | So ngay | % ngay dong cua cao hon 11h30 | Hoi TB 11h30->dong cua | % ngay 14h20 cao hon 11h30 | % ngay day nam buoi sang")
for ten, g in nhom:
    if not len(g): log(f"{ten} | 0"); continue
    log(f"{ten} | {len(g)} | {pct((g['dong'] > g['p1130']).mean())} | {pct(g['hoi_1130_dong'].mean())} | {pct((g['p1420'] > g['p1130']).mean())} | {pct(g['day_sang'].mean())}")
for nhan, tien in (("VNINDEX", "vni"), ("TRUNG BINH CAC MA VN100", "vn100")):
    log("")
    log(f"BANG 2 - {nhan}: lai TB / % thang (so ngay), da tru 0,4% phi thue, ban o gia dong cua sau 3, 10, 20 phien")
    log("Nhom | Gio mua | +3 phien | +10 phien | +20 phien")
    for ten, g in nhom:
        for tg, cot in GIO:
            o = []
            for h in KY:
                x = g[f"{tien}_{cot}_{h}"].dropna()
                o.append(f"{pct(x.mean())} / {pct((x > 0).mean())} ({len(x)})" if len(x) else "—")
            log(f"{ten} | {tg} | " + " | ".join(o))
log("")
log("Ghi chu: do rong 11h30 tinh tren 100 ma VN100 (khong phai ca san HOSE). Gia ma chua dieu chinh co tuc; da bo ma co buoc nhay >8% trong ky giu.")
luu()
