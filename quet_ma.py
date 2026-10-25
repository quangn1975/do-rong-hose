"""Bo quet ma theo phuong an 25/10 (chay sau job 18:00, doc cac file data da co, khong goi API).
Trang thai theo % VN100 tren MA20:
  Nong  >70  -> khong mo moi, khong co danh sach
  Giua 30-70 -> mua khi: dong cua > dinh (high) 20 phien truoc, KL >= 1.5 x TB 20 phien, ty le lenh mua/ban 5 phien >= 1.3
  Can  <30   -> mua ma qua ban: dong cua thap hon MA20 tren 6% va phien nay hoi >= +1%
Cat lo theo cau truc: day thap nhat 5 phien gan nhat tru 1%. Gia tinh bang nghin dong.
Ket qua: data/quet_ma.csv (dong dau luon la dong trang thai, de Sheet doc duoc ca khi khong co ma)
"""
import pandas as pd, numpy as np

px = pd.read_csv("data/vn100_gia_70p.csv").sort_values(["ma", "ngay"])
dr = pd.read_csv("data/vn100_do_rong.csv").dropna(subset=["pct_ma20"]).iloc[-1]
tt = pd.read_csv("data/vn100_dong_tien_tomtat.csv").set_index("ma")

p20 = float(dr["pct_ma20"])
trang_thai = "Nóng" if p20 > 70 else ("Cạn" if p20 < 30 else "Giữa")
ngay = px["ngay"].max()
cols = ["ngay", "trang_thai", "pct_ma20", "ma", "ly_do", "gia_vao", "cat_lo", "cat_lo_pct",
        "kl_x_tb20", "ty_le_lenh_5p", "khoang_cach_ma20_pct", "ngoai_rong_5p_ty"]
rows = []

for ma, g in px.groupby("ma"):
    g = g.reset_index(drop=True)
    if len(g) < 30 or g["ngay"].iloc[-1] != ngay:
        continue
    c, h, l, v = g["close"], g["high"], g["low"], g["volume"]
    gia = float(c.iloc[-1])
    ma20 = float(c.tail(20).mean())
    dinh20 = float(h.iloc[-21:-1].max())
    tb20 = float(v.iloc[-21:-1].mean())
    kl_x = float(v.iloc[-1] / tb20) if tb20 > 0 else np.nan
    r5 = float(tt["ty_le_lenh_5p"].get(ma, np.nan))
    ngoai5 = float(tt["ngoai_rong_5p_ty"].get(ma, np.nan))
    hom_qua = float(c.iloc[-2])
    ret1 = gia / hom_qua - 1
    kc = gia / ma20 - 1
    # bo qua ma nghi dieu chinh gia (nhay >10.5% 1 phien trong 35 phien gan nhat)
    if (c.pct_change().tail(35).abs() > 0.105).any():
        continue
    ly_do = None
    if trang_thai == "Giữa" and gia > dinh20 and kl_x >= 1.5 and r5 >= 1.3:
        ly_do = "Vượt đỉnh 20 phiên + KL≥1,5 lần + lệnh mua/bán 5 phiên ≥1,3"
    elif trang_thai == "Cạn" and kc < -0.06 and ret1 > 0.01:
        ly_do = "Quá bán >6% dưới MA20 và hồi ≥+1%"
    if ly_do:
        cl = round(float(l.tail(5).min()) * 0.99, 2)
        rows.append([ngay, trang_thai, p20, ma, ly_do, round(gia, 2), cl, round(cl / gia - 1, 4),
                     round(kl_x, 2), round(r5, 2), round(kc, 4), round(ngoai5, 2)])

df = pd.DataFrame(rows, columns=cols)
if len(df):
    df = df.sort_values("ty_le_lenh_5p", ascending=False)
else:
    df.loc[0] = [ngay, trang_thai, p20, "", "Không có mã đạt điều kiện" if trang_thai != "Nóng"
                 else "Thị trường Nóng: không mở mới", "", "", "", "", "", "", ""]
df.to_csv("data/quet_ma.csv", index=False)
print(trang_thai, p20, len(rows), "ma")
print(df.to_string(index=False))
