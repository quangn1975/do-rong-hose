"""Lay BU khoi ngoai (cot mua / ban / rong) cho so/vn100_chi_tiet.csv khi SSI cong bo so khoi ngoai tre.
Chay buoi sang truoc gio mo cua. NHE va CHAM de SSI khong khoa:
  - Xem tep truoc: 2 phien moi nhat ma KHONG thieu khoi ngoai (duoi 20 ma trong) thi thoat ngay, KHONG dang nhap SSI.
  - Co thieu: dang nhap 1 lan, moi ma thieu goi 1 lan, nghi 1,5 giay giua cac lan goi, hong 3 ma thi dung.
  - Chi dien vao o dang trong; khong dung den so da co va cac cot khac. SSI chua co so thi de trong (khong tu dien 0).
Khong in khoa."""
import csv, os, sys, time
from datetime import datetime, timezone, timedelta

F = os.path.join(os.getenv("THU_MUC_RA", "so"), "vn100_chi_tiet.csv")
G, H, I = "Khối ngoại mua (tỷ)", "Khối ngoại bán (tỷ)", "Khối ngoại ròng (tỷ)"
now = datetime.now(timezone(timedelta(hours=7)))
SECRETS = [v for v in (os.environ.get(k, "") for k in ("SSI_API_KEY", "SSI_API_SECRET")) if v]
def log(*a):
    s = " ".join(str(x) for x in a)
    for v in SECRETS: s = s.replace(v, "***")
    print(s, flush=True)

with open(F, encoding="utf-8", newline="") as f:
    rows = list(csv.reader(f))
cot = rows[0]; iN, iM, iG, iH, iI = (cot.index(x) for x in ("Ngày", "Mã", G, H, I))
phien = sorted({r[iN] for r in rows[1:]})[-2:]
thieu = {}                                   # phien -> cac ma dang trong khoi ngoai
for r in rows[1:]:
    if r[iN] in phien and r[iG] == "" and r[iH] == "": thieu.setdefault(r[iN], set()).add(r[iM])
thieu = {p: m for p, m in thieu.items() if len(m) >= 20}     # vai ma trong le te = SSI khong co so, khong goi lai
if not thieu:
    log(f"Bu khoi ngoai: 2 phien moi nhat {phien} da du so, khong goi SSI"); sys.exit(0)
log("Bu khoi ngoai: thieu", {p: len(m) for p, m in thieu.items()})

from ssi_sdk import Auth, Config
auth = Auth(Config(api_key=os.environ["SSI_API_KEY"], api_secret=os.environ["SSI_API_SECRET"]))
try: auth.authenticate()                     # CHI 1 lan dang nhap; SSI tu choi thi thoi, khong thu don dap
except Exception as e:
    log("SSI tu choi dang nhap, giu nguyen tep:", type(e).__name__); sys.exit(0)

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None
tu, den = min(thieu).replace("-", "/"), max(thieu).replace("-", "/")
moi, hong = {}, 0                            # (phien, ma) -> (mua, ban, rong)
for ma in sorted(set().union(*thieu.values())):
    try:
        body = auth.rest_client.get("/api/v3/data/securitiesSummary", params={"symbol": ma, "from": tu, "to": den, "pageIndex": 1, "pageSize": 100})
        if isinstance(body, dict): body = body.get("data")
        for d in body or []:
            p = str(d.get("tradingDate"))[:10].replace("/", "-")
            b, s = num(d.get("totalForeignBuyValue")), num(d.get("totalForeignSellValue"))
            if p in thieu and ma in thieu[p] and b is not None and s is not None:
                moi[(p, ma)] = (round(b / 1e9, 1), round(s / 1e9, 1), round((b - s) / 1e9, 1))
    except Exception as e:
        hong += 1; log("loi", ma, type(e).__name__, str(e)[:120])
        if hong >= 3: log("Hong 3 ma, dung"); break
    time.sleep(1.5)

if not moi:
    log("Bu khoi ngoai: SSI CHUA co so khoi ngoai cho", sorted(thieu), "- giu nguyen tep, lan sau lay tiep"); sys.exit(0)
for r in rows[1:]:
    v = moi.get((r[iN], r[iM]))
    if v and r[iG] == "" and r[iH] == "": r[iG], r[iH], r[iI] = (str(x) for x in v)
with open(F, "w", encoding="utf-8", newline="") as f:
    csv.writer(f, lineterminator="\n").writerows(rows)
with open(os.path.join(os.path.dirname(F), "trang_thai.txt"), "a", encoding="utf-8") as f:
    f.write(f"Bu khoi ngoai {now.strftime('%d/%m/%Y %H:%M')} (gio VN): dien {len(moi)} o cho phien {', '.join(sorted(thieu))}, {hong} ma loi\n")
log(f"Bu khoi ngoai: da dien {len(moi)} dong, {hong} ma loi")
