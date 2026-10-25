"""Bản chụp VN100 trong phiên (chạy lúc ~10:30, 11:25, 14:10, 14:25 giờ VN).
 - data/chup_phien.csv : mỗi lần chạy 1 dòng: độ rộng (% mã VN100 đang trên MA20/50/200), số mã tăng/giảm,
                         khối ngoại ròng VN100, VN-Index, gợi ý.
 - data/chup_gia.csv   : giá từng mã tại thời điểm chụp (giữ 60 ngày) để sau này so với giá đóng cửa,
                         kiểm chứng "sáng bị đẩy giá, chiều mới thật".
MA lấy từ data/vn100_ma_moc.csv (chốt phiên trước, do ngay_vn100.py ghi lúc 18:00).
"""
import os, sys
import pandas as pd
from ngay15 import lich_su, now

NG_NONG, NG_TRUNG_TINH, NG_CAN = 70, 40, 20   # % mã trên MA20
CAN_KIET_MA50 = 30


def goi_y(p20, p50):
    if p20 < NG_CAN or p50 < CAN_KIET_MA50:
        return "Cạn kiệt: vùng thuận lợi, được mở mới theo mức trần, chia 2-3 đợt"
    if p20 > NG_NONG:
        return "Nóng: không mở mới, giữ mã đang có và siết cắt lỗ"
    if p20 >= NG_TRUNG_TINH:
        return "Trung tính: mở mới ít, chỉ mã vượt kháng cự có khối lượng xác nhận"
    return "Thấp: mở theo mức trần, chia 2-3 đợt"


def main():
    from vnstock import Trading
    ds = open("data/vn100_ds.txt").read().split()
    mo = pd.read_csv("data/vn100_ma_moc.csv").set_index("ma")
    pb = Trading(source="VCI").price_board(ds)
    pb.columns = ["_".join(str(x) for x in c) if isinstance(c, tuple) else str(c) for c in pb.columns]
    ex = lambda *names: next((n for n in names if n in pb.columns), None)
    num = lambda name: pd.to_numeric(pb[name], errors="coerce") if name else pd.Series(float("nan"), index=pb.index)
    c_gia = ex("match_match_price")          # giá khớp gần nhất (không dùng match_avg_match_price = giá trung bình)
    c_tc = ex("match_reference_price", "listing_ref_price")
    c_atc = ex("match_match_price_atc")
    c_mua = ex("match_foreign_buy_value"); c_ban = ex("match_foreign_sell_value")
    d = pd.DataFrame({"ma": pb[ex("listing_symbol", "symbol")], "gia": num(c_gia), "gia_atc": num(c_atc),
                      "tham_chieu": num(c_tc), "kl": num(ex("match_accumulated_volume")),
                      "nn_rong_ty": (num(c_mua) - num(c_ban)) / 1e9})
    # lưu mẫu cột để kiểm tra khi cần
    pb[[c for c in (ex("listing_symbol"), c_gia, c_atc, c_tc, ex("match_avg_match_price"), ex("match_highest"),
                    ex("match_lowest"), c_mua, c_ban, ex("match_trading_session_id")) if c]].head(8).to_csv("data/chup_cot_mau.csv", index=False)
    # mã chưa khớp lệnh trong phiên thì lấy giá tham chiếu; sau 14:30 ưu tiên giá ATC
    d["gia"] = d["gia"].where(d["gia"] > 0, d["gia_atc"].where(d["gia_atc"] > 0, d["tham_chieu"]))
    d = d.dropna(subset=["gia"])
    res = {}
    for n in (20, 50, 200):
        m = d["ma"].map(mo[f"ma{n}"]) * 1000   # mốc MA lưu theo nghìn đồng, bảng giá theo đồng
        ok = m.notna()
        res[n] = round((d.loc[ok, "gia"] > m[ok]).sum() / max(ok.sum(), 1) * 100, 1)
    tang = int((d["gia"] > d["tham_chieu"]).sum()); giam = int((d["gia"] < d["tham_chieu"]).sum())
    vni = ""
    try:
        v = lich_su("VNINDEX", 10)
        if v is not None and len(v) and v["time"].iloc[-1] == now.date().isoformat():
            vni = round(float(v["close"].iloc[-1]), 2)
    except Exception as e:
        print("VN-Index loi", repr(e)[:120])
    row = {"ngay": now.strftime("%Y-%m-%d"), "gio": now.strftime("%H:%M"), "vnindex": vni,
           "pct_ma20": res[20], "pct_ma50": res[50], "pct_ma200": res[200],
           "so_ma": len(d), "so_tang": tang, "so_giam": giam,
           "ngoai_rong_vn100_ty": round(float(d["nn_rong_ty"].sum()), 1),
           "goi_y": goi_y(res[20], res[50])}
    f = "data/chup_phien.csv"
    old = pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()
    pd.concat([old, pd.DataFrame([row])], ignore_index=True).tail(400).to_csv(f, index=False)
    g = d[["ma", "gia", "kl", "nn_rong_ty"]].copy()
    g.insert(0, "gio", row["gio"]); g.insert(0, "ngay", row["ngay"])
    gf = "data/chup_gia.csv"
    old = pd.read_csv(gf) if os.path.exists(gf) else pd.DataFrame()
    allg = pd.concat([old, g], ignore_index=True)
    han = (now.date() - pd.Timedelta(days=60)).isoformat()
    allg[allg["ngay"] >= han].round(2).to_csv(gf, index=False)
    print(row)


if __name__ == "__main__":
    main()
