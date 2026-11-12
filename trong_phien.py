"""Kiem tra gio mua trong phien: 11h30 so voi 13h15, 14h20 va dong cua, trong nhung ngay BUOI SANG bi ban manh.
KHONG goi SSI: chi doc tep cong don so/trong_phien_cong_don.csv (lich SSI hang ngay lay_so_ssi.py tu ghi them moi phien).
VNINDEX lay nen 5 phut (dung 14h20); 100 ma VN100 lay nen 15 phut (gia 14h15).
Ghi ra: so/trong_phien_ket_qua.txt (bang ket qua), so/trong_phien_ngay.csv (moi ngay 1 dong)."""
import os, sys
from datetime import datetime, timezone, timedelta
import pandas as pd

OUT = "so"
VN = timezone(timedelta(hours=7)); now = datetime.now(VN)
PHI = 0.004                                          # phi mua 0,15% + phi ban 0,15% + thue ban 0,1%
dong = []
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); dong.append(s); return s
def luu():
    open(f"{OUT}/trong_phien_ket_qua.txt", "w", encoding="utf-8").write(
        f"Lan chay: {now.strftime('%d/%m/%Y %H:%M')} (gio VN) - doc tep cong don, khong goi SSI\n" + "\n".join(dong) + "\n")

F = f"{OUT}/trong_phien_cong_don.csv"
if not os.path.exists(F): log("Chua co tep cong don"); luu(); sys.exit(1)
cd = pd.read_csv(F, dtype={"ngay": str, "ma": str}).drop_duplicates(["ngay", "ma"], keep="last")
vi = cd[cd["ma"] == "VNINDEX"].drop(columns="ma").set_index("ngay").sort_index()
if len(vi) < 5: log("Tep cong don qua it phien"); luu(); sys.exit(1)
vi["truoc"] = vi["dong"].shift(1)
NGAY = list(vi.index)
mm = cd[(cd["ma"] != "VNINDEX") & cd["ngay"].isin(NGAY)].sort_values(["ma", "ngay"]).copy()
mm["truoc"] = mm.groupby("ma")["dong"].shift(1)
log(f"Du lieu: {len(vi)} phien ({NGAY[0]} -> {NGAY[-1]}), {mm['ma'].nunique()} ma VN100")

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
