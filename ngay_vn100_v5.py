"""Dong tien lon cua VN100 (vnstock the he 5, goi tra phi). Chay 18:00 hang ngay.
Moi ma lay 20 phien gan nhat:
  - khoi ngoai (foreign_flow), tu doanh (proprietary_flow): mua/ban/rong theo gia tri (ty dong)
  - trade_history: so lenh mua/ban, KL trung binh moi lenh mua/ban (lenh mua TB lon hon lenh ban TB = tien lon dang mua),
    KL mua - ban chu dong rong
Ket qua: data/vn100_dong_tien_ngay.csv (chi tiet) va data/vn100_dong_tien_tomtat.csv (moi ma 1 dong)
Trang thai: data/vn100_v5_trangthai.txt"""
import os, sys, time
import pandas as pd
from datetime import datetime, timezone, timedelta
gio = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")
K = os.environ.get("VNSTOCK_API_KEY", "")
st = []
def ghi():
    open("data/vn100_v5_trangthai.txt", "w").write(f"{gio} (gio VN)\n" + "\n".join(st) + "\n")
try:
    import vnstock
    vnstock.login(K)
    from vnstock import Market
except Exception as e:
    st.append("KHONG dang nhap duoc (v5): " + type(e).__name__ + " " + str(e)[:150].replace(K or "@@", "***"))
    ghi(); sys.exit(0)
N = 20
ds = open("data/vn100_ds.txt").read().split()
extra = [l.strip().upper() for l in open("ma33.txt") if l.strip() and not l.startswith("#")]
syms = sorted(set(ds) | set(extra))
DELAY = float(os.getenv("VNSTOCK_V5_DELAY", "0.8"))

def ngay(s): return pd.to_datetime(s).dt.strftime("%Y-%m-%d")
def lay(e, fn, **kw):
    for _ in range(2):
        try:
            r = getattr(e, fn)(limit=N, **kw)
            if r is not None and len(r): return r
            return None
        except Exception as ex:
            err = repr(ex)[:120]
            time.sleep(2)
    st.append(f"loi {fn}: {err}") if len(st) < 12 else None
    return None

rows, loi = [], 0
for i, s in enumerate(syms):
    e = Market().equity(s)
    d = None
    ff = lay(e, "foreign_flow"); time.sleep(DELAY)
    pf = lay(e, "proprietary_flow"); time.sleep(DELAY)
    th = lay(e, "trade_history"); time.sleep(DELAY)
    parts = []
    if ff is not None:
        t = pd.DataFrame({"ngay": ngay(ff["time"]), "ngoai_mua_ty": ff["buy_val"] / 1e9, "ngoai_ban_ty": ff["sell_val"] / 1e9, "ngoai_rong_ty": ff["net_val"] / 1e9}); parts.append(t.set_index("ngay"))
    if pf is not None:
        t = pd.DataFrame({"ngay": ngay(pf["time"]), "tudoanh_mua_ty": pf["buy_val"] / 1e9, "tudoanh_ban_ty": pf["sell_val"] / 1e9, "tudoanh_rong_ty": pf["net_val"] / 1e9}); parts.append(t.set_index("ngay"))
    if th is not None:
        t = pd.DataFrame({"ngay": ngay(th["trading_date"]), "gia_dong": th["close"], "kl": th["total_volume"],
                          "so_lenh_mua": th["total_buy_trade"], "so_lenh_ban": th["total_sell_trade"],
                          "kl_tb_lenh_mua": th["average_buy_trade_volume"], "kl_tb_lenh_ban": th["average_sell_trade_volume"],
                          "kl_mua_ban_chu_dong_rong": th["total_net_trade_volume"]}); parts.append(t.set_index("ngay"))
    if not parts:
        loi += 1; continue
    m = pd.concat(parts, axis=1)
    m = m.loc[:, ~m.columns.duplicated()]
    m.insert(0, "ma", s); rows.append(m.reset_index())
    if i % 20 == 0: print(i, s, flush=True)

if not rows:
    st.append("Khong lay duoc du lieu nao (kiem tra goi/thiet bi)"); ghi(); sys.exit(0)
all_ = pd.concat(rows).sort_values(["ma", "ngay"], ascending=[True, False])
all_["ty_le_lenh_mua_ban"] = (all_["kl_tb_lenh_mua"] / all_["kl_tb_lenh_ban"].where(all_["kl_tb_lenh_ban"] > 0)).round(2)
all_ = all_.round(3)
all_.to_csv("data/vn100_dong_tien_ngay.csv", index=False)

def tom(g):
    g = g.sort_values("ngay", ascending=False)
    a, f5 = g.iloc[0], g.head(5)
    return pd.Series({"ngay": a["ngay"],
        "ngoai_rong_ty": a.get("ngoai_rong_ty"), "ngoai_rong_5p_ty": f5["ngoai_rong_ty"].sum(),
        "tudoanh_rong_ty": a.get("tudoanh_rong_ty"), "tudoanh_rong_5p_ty": f5["tudoanh_rong_ty"].sum(),
        "ty_le_lenh_mua_ban": a.get("ty_le_lenh_mua_ban"), "ty_le_lenh_5p": round(f5["kl_tb_lenh_mua"].mean() / f5["kl_tb_lenh_ban"].mean(), 2) if f5["kl_tb_lenh_ban"].mean() else None,
        "kl_mua_ban_chu_dong_rong": a.get("kl_mua_ban_chu_dong_rong")})
cols = [c for c in ("ngoai_rong_ty", "tudoanh_rong_ty", "kl_tb_lenh_mua", "kl_tb_lenh_ban", "kl_mua_ban_chu_dong_rong") if c in all_.columns]
tomtat = all_.groupby("ma").apply(tom, include_groups=False).reset_index()
tomtat["gio"] = gio
tomtat.round(2).to_csv("data/vn100_dong_tien_tomtat.csv", index=False)
st.append(f"OK {len(rows)}/{len(syms)} ma, {loi} ma khong co du lieu")
ghi()
