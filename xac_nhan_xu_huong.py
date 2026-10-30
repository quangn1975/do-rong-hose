"""Bang xac nhan xu huong (chay sau job 18:00, doc cac file data da co, khong goi API).
3 lop: (1) Gia VN-Index, (2) Do rong VN100, (3) Loai nha dau tu VN100 (vnstock: khoi ngoai, tu doanh, co lenh mua/ban).
Ket qua:
  data/xac_nhan_xu_huong.csv     bang hien tai (Sheet doc bang IMPORTDATA)
  data/xac_nhan_lich_su.csv      trang thai tung ngay (de sau nay do xem chi bao nao dung)
  data/xac_nhan_nen_dong_tien.csv tong hop dong tien VN100 theo ngay (ngoai, tu doanh, khoi luong/so lenh mua-ban)
Gioi han: 1 nam du lieu cho thay chua chi bao nao dang tin ro rang (do tin cay thap) -> chi de THAM KHAO / XAC NHAN, khong phai tin hieu mua ban.
"""
import pandas as pd, numpy as np, os

NEN = "data/xac_nhan_nen_dong_tien.csv"
# ---- 1. cap nhat tong hop dong tien theo ngay tu file chi tiet (chi ngay du ma) ----
nen = pd.read_csv(NEN, parse_dates=["ngay"]) if os.path.exists(NEN) else pd.DataFrame(columns=["ngay","ngoai","td","kB","kS","nB","nS"])
d = pd.read_csv("data/vn100_dong_tien_ngay.csv", parse_dates=["ngay"])
d = d[d.groupby("ngay")["ngoai_rong_ty"].transform(lambda x: x.notna().sum()) >= 90]
if len(d):
    d["kB"] = d.kl_tb_lenh_mua * d.so_lenh_mua; d["kS"] = d.kl_tb_lenh_ban * d.so_lenh_ban
    g = d.groupby("ngay")
    moi = pd.DataFrame({"ngoai": g.ngoai_rong_ty.sum(), "td": g.tudoanh_rong_ty.sum(), "kB": g.kB.sum(), "kS": g.kS.sum(),
                        "nB": g.so_lenh_mua.sum(), "nS": g.so_lenh_ban.sum()}).reset_index()
    nen = pd.concat([nen[~nen.ngay.isin(moi.ngay)], moi]).sort_values("ngay")
nen.to_csv(NEN, index=False, float_format="%.3f")
nen = nen.set_index("ngay")

# ---- 2. chi bao theo tung ngay ----
vn = pd.read_csv("data/thi_truong.csv", parse_dates=["date"]).set_index("date").sort_index()
c = vn["close"]; ma20 = c.rolling(20).mean()
H = pd.DataFrame(index=vn.index)
H["vnindex"] = c
H["vuot_dinh20"] = ((c >= c.shift(1).rolling(20).max()).rolling(5).max() == 1).where(c.shift(1).rolling(20).max().notna())
H["tren_ma20"] = (c > ma20).where(ma20.notna())
H["ma20_doc_len"] = (ma20 > ma20.shift(5)).where(ma20.shift(5).notna())
dr = pd.read_csv("data/vn100_do_rong.csv", parse_dates=["date"]).set_index("date")["pct_ma20"]
H["pct_ma20"] = dr.reindex(H.index)
H["do_rong_tren50"] = (H.pct_ma20 > 50).where(H.pct_ma20.notna())
n5 = nen.ngoai.rolling(5).sum(); t20 = nen.td.rolling(20).sum()
cod5 = (nen.kB.rolling(5).sum() / nen.nB.rolling(5).sum()) / (nen.kS.rolling(5).sum() / nen.nS.rolling(5).sum())
H["ngoai5_ty"] = n5.reindex(H.index)
H["ngoai5_manh"] = (n5 > n5.rolling(60).median()).where(n5.rolling(60).median().notna()).reindex(H.index)
H["tudoanh20_ty"] = t20.reindex(H.index)
H["tudoanh20_mua"] = (t20 > 0).where(t20.notna()).reindex(H.index)
H["codlenh5"] = cod5.reindex(H.index)
H["codlenh5_cao"] = (cod5 > cod5.rolling(60).median()).where(cod5.rolling(60).median().notna()).reindex(H.index)
H.index.name = "ngay"
H.to_csv("data/xac_nhan_lich_su.csv", float_format="%.3f")

# ---- 3. bang hien tai ----
def last(col):
    s = H[col].dropna()
    return (s.iloc[-1], s.index[-1]) if len(s) else (np.nan, None)
def nd(ts): return ts.strftime("%d/%m") if ts is not None else ""
rows = []
def add(lop, ten, tt, sl, ts, huong, gc): rows.append([lop, ten, tt, sl, nd(ts), huong, gc])
v, ts = last("vuot_dinh20"); cl, _ = last("vnindex")
add("1. Giá VN-Index", "Vượt đỉnh 20 phiên (trong 5 phiên gần đây)", "CÓ" if v else "KHÔNG", f"đóng cửa {cl:.0f}", ts, (1 if v else -1) if pd.notna(v) else 0,
    "Khớp luật 'vượt kháng cự mới mua'. Ít đổi trạng thái nên ít nhiễu.")
v, ts = last("tren_ma20"); add("1. Giá VN-Index", "Giá trên MA20", "CÓ" if v else "KHÔNG", f"MA20 = {ma20.dropna().iloc[-1]:.0f}", ts, 1 if v else -1, "MA20 = giá trung bình 20 phiên.")
v, ts = last("ma20_doc_len"); add("1. Giá VN-Index", "MA20 dốc lên (so 5 phiên trước)", "CÓ" if v else "KHÔNG", "", ts, 1 if v else -1, "")
p, ts = last("pct_ma20"); tt = "Nóng" if p > 70 else ("Cạn" if p < 30 else "Giữa")
add("2. Độ rộng VN100", "% mã trên MA20", f"{tt} ({p:.0f}%)", f"{p:.0f}%", ts, 1 if p > 50 else -1,
    "Luật của anh: trên 70% ngừng mở mới; dưới 30% là cạn kiệt. Độ rộng chỉ là 1 lớp, không dùng một mình.")
v, ts = last("tudoanh20_ty"); add("3. Loại nhà đầu tư (vnstock, VN100)", "Tự doanh ròng 20 phiên", "MUA RÒNG" if v > 0 else "BÁN RÒNG", f"{v:+.0f} tỷ", ts, 1 if v > 0 else -1,
    "Tự doanh = công ty chứng khoán đánh bằng vốn của mình. Là chỉ báo tốt nhất trong các loại nhà đầu tư em đã thử, nhưng vẫn chưa đủ chắc.")
v, ts = last("codlenh5_cao"); r_, _ = last("codlenh5"); add("3. Loại nhà đầu tư (vnstock, VN100)", "Cỡ lệnh mua so với cỡ lệnh bán (5 phiên)", "LỆNH MUA LỚN HƠN THƯỜNG LỆ" if v else "LỆNH MUA NHỎ HƠN THƯỜNG LỆ",
    f"tỷ số {r_:.2f}", ts, 1 if v else -1, "Đo xem tiền lớn có đang mua nhiều hơn bán không (so với trung vị 60 phiên của chính nó). Tỷ số dưới 1 là bình thường.")
v, ts = last("ngoai5_manh"); n_, _ = last("ngoai5_ty"); add("3. Loại nhà đầu tư (vnstock, VN100)", "Khối ngoại ròng 5 phiên", "MẠNH HƠN THƯỜNG LỆ" if v else "YẾU HƠN THƯỜNG LỆ", f"{n_:+.0f} tỷ", ts, 0,
    "Chỉ để theo dõi, KHÔNG tính vào số đếm: 1 năm qua khối ngoại 'mạnh hơn thường lệ' lại đi trước giai đoạn yếu hơn.")
tot = [r for r in rows if r[5] != 0]; up = sum(1 for r in tot if r[5] > 0)
rows.append(["Tổng hợp", "Số chỉ báo báo TĂNG", f"{up}/{len(tot)}", "", "", 0, "Chỉ là đếm đơn giản, chưa kiểm chứng. Dùng để xác nhận xu hướng đang diễn ra, không phải để dự đoán."])
pd.DataFrame(rows, columns=["lop", "chi_bao", "trang_thai", "so_lieu", "den_ngay", "tinh_vao_dem", "ghi_chu"]).to_csv("data/xac_nhan_xu_huong.csv", index=False)
print("OK", up, "/", len(tot))
