"""Lay so thi truong tu SSI (khoa SSI trong Secrets, KHONG dang nhap vnstock, khong OTP).
Chay tren GitHub sau gio dong cua. Ghi ra thu muc so/:
  do_rong.csv        - moi phien 1 dong: % ma tren MA20/MA50/MA200 cua VN30, VN100, HOSE
  ro_dong_tien.csv   - moi phien x moi ro (VNINDEX, VN30, VN100): diem, so ma tang/giam, khoi ngoai, tu doanh
  vn100_chi_tiet.csv - 20 phien gan nhat x 100 ma VN100: gia, KL, khoi ngoai, lenh mua/ban, vi tri so voi MA
  danh_sach_ro.csv   - tat ca ma HOSE, danh dau ma thuoc VN30 / VN100
  trang_thai.txt     - lan chay gan nhat
Khong in khoa."""
import os, sys, time
from datetime import datetime, timezone, timedelta
import pandas as pd

SECRETS = [v for v in (os.environ.get(k, "") for k in ("SSI_API_KEY", "SSI_API_SECRET")) if v]
OUT = "so"; os.makedirs(OUT, exist_ok=True)
VN = timezone(timedelta(hours=7))
now = datetime.now(VN)
TODAY = now.strftime("%Y-%m-%d")
PHIEN_DANG_CHAY = now.weekday() < 5 and (now.hour, now.minute) < (15, 0)   # truoc 15:00: bo cay nen hom nay (chua chot)
END = TODAY
START_GIA = (now - timedelta(days=int(os.getenv("SO_NGAY_GIA", "760")))).strftime("%Y-%m-%d")
START_RO = (now - timedelta(days=150)).strftime("%Y-%m-%d")
START_CT = (now - timedelta(days=40)).strftime("%Y-%m-%d")
N_PHIEN_DO_RONG, N_PHIEN_RO, N_PHIEN_CT = 300, 90, 20
st = []
def log(*a):
    s = " ".join(str(x) for x in a)
    for v in SECRETS: s = s.replace(v, "***")
    print(s, flush=True); return s
def ghi_trang_thai(kq):
    open(f"{OUT}/trang_thai.txt", "w", encoding="utf-8").write(
        f"Lan chay: {now.strftime('%d/%m/%Y %H:%M')} (gio VN)\nKet qua: {kq}\n" + "\n".join(st) + "\n")

from vnstock import Market, Reference
M = Market("ssi"); R = Reference("ssi")

def goi(fn, lan=4, nghi=3):
    err = None
    for i in range(lan):
        try:
            return fn()
        except Exception as e:
            err = e; time.sleep(nghi * (i + 1))
    raise err
def ngay(s):
    return pd.to_datetime(s).dt.strftime("%Y-%m-%d")
def cot(df, *names):
    for n in names:
        if n in df.columns: return pd.to_numeric(df[n], errors="coerce")
    return pd.Series([float("nan")] * len(df), index=df.index)
def bo_hom_nay(df, c="ngay"):
    return df[df[c] < TODAY] if PHIEN_DANG_CHAY else df

# ---------- 1. Danh sach ----------
try:
    hose = goi(lambda: R.equity().list(exchange="HOSE"))
    hose = hose[hose["type"].astype(str).str.lower().eq("stock")] if "type" in hose.columns else hose
    vn30 = sorted(goi(lambda: R.index("VN30").members())["symbol"].astype(str))
    vn100 = sorted(goi(lambda: R.index("VN100").members())["symbol"].astype(str))
except Exception as e:
    st.append(log("LOI danh sach:", type(e).__name__, str(e)[:200])); ghi_trang_thai("HONG - khong lay duoc danh sach"); sys.exit(1)
syms = sorted(set(hose["symbol"].astype(str)) | set(vn30) | set(vn100))
ds = pd.DataFrame({"Mã": hose["symbol"].astype(str).values,
                   "Tên công ty": hose.get("organ_name", pd.Series([""] * len(hose))).astype(str).values,
                   "Ngành": hose.get("icb_name", pd.Series([""] * len(hose))).astype(str).values})
ds["Thuộc VN30"] = ds["Mã"].isin(vn30).map({True: "x", False: ""})
ds["Thuộc VN100"] = ds["Mã"].isin(vn100).map({True: "x", False: ""})
ds = ds.sort_values(["Thuộc VN30", "Thuộc VN100", "Mã"], ascending=[False, False, True])
ds.to_csv(f"{OUT}/danh_sach_ro.csv", index=False)
st.append(log(f"Danh sach: HOSE {len(hose)} ma, VN30 {len(vn30)}, VN100 {len(vn100)}"))

# ---------- 2. Gia tat ca ma -> do rong ----------
closes, loi = {}, []
t0 = time.time()
for i, s in enumerate(syms):
    try:
        d = goi(lambda: M.equity(s).ohlcv(start=START_GIA, end=END))
        if d is None or not len(d): loi.append(s); continue
        x = pd.Series(pd.to_numeric(d["close"], errors="coerce").values, index=ngay(d["time"]).values)
        closes[s] = x[~x.index.duplicated(keep="last")]
    except Exception as e:
        loi.append(s)
        if len(loi) <= 3: log("loi gia", s, type(e).__name__, str(e)[:150])
    if i % 50 == 0: log(f"gia {i}/{len(syms)} {s} ({round(time.time() - t0)} giay)")
px = pd.DataFrame(closes).sort_index()
px = px[px.index < TODAY] if PHIEN_DANG_CHAY else px
st.append(log(f"Gia: {px.shape[1]}/{len(syms)} ma, {px.shape[0]} phien ({px.index.min()} -> {px.index.max()}), {len(loi)} ma loi, {round(time.time() - t0)} giay"))
if px.shape[1] < 300 or px.shape[0] < 220:
    ghi_trang_thai("HONG - thieu du lieu gia, giu nguyen bang cu"); sys.exit(1)

tren = {}
for n in (20, 50, 200):
    ma = px.rolling(n, min_periods=int(n * 0.8)).mean()   # ma it thanh khoan: can co gia it nhat 80% so phien cua ky
    tren[n] = (px > ma).astype(float).where(ma.notna() & px.notna())   # 1 = tren MA, 0 = duoi, NaN = khong khop lenh phien do / chua du du lieu
def do_rong(ma, n):
    t = tren[n][[m for m in ma if m in px.columns]]
    return (t.sum(axis=1) / t.count(axis=1) * 100).round(1), t.count(axis=1)
dr = pd.DataFrame(index=px.index)
for ten, ma in (("VN30", vn30), ("VN100", vn100), ("HOSE", list(hose["symbol"].astype(str)))):
    for n in (20, 50, 200):
        dr[f"{ten}: % mã trên MA{n}"], dem = do_rong(ma, n)
        if n == 200: dr[f"_dem_{ten}"] = dem
dr["HOSE: số mã được tính"] = tren[20][[m for m in hose["symbol"].astype(str) if m in px.columns]].count(axis=1)
dr = dr[dr["_dem_HOSE"] >= 200].drop(columns=[c for c in dr.columns if c.startswith("_dem_")])

# ---------- 3. Theo ro: diem, do rong tang/giam, khoi ngoai, tu doanh ----------
ro_rows = []
for ix in ("VNINDEX", "VN30", "VN100"):
    parts = []
    try:
        o = goi(lambda: M.index(ix).ohlcv(start=START_RO, end=END))
        parts.append(pd.DataFrame({"Điểm đóng cửa": pd.to_numeric(o["close"], errors="coerce").values,
                                   "Khối lượng (triệu cp)": (pd.to_numeric(o["volume"], errors="coerce") / 1e6).round(1).values}, index=ngay(o["time"]).values))
    except Exception as e: st.append(log("loi diem", ix, type(e).__name__, str(e)[:150]))
    try:
        h = goi(lambda: M.index(ix).trade_history(start=START_RO, end=END))
        parts.append(pd.DataFrame({"Tăng/giảm (%)": (cot(h, "percent_price_change") * 100).round(2).values,
                                   "GTGD (nghìn tỷ)": (cot(h, "total_value") / 1e12).round(2).values,
                                   "Số mã tăng": cot(h, "total_stock_up_price").values, "Số mã giảm": cot(h, "total_stock_down_price").values,
                                   "Số mã đứng giá": cot(h, "total_stock_no_change_price").values,
                                   "Số mã trần": cot(h, "total_stock_ceiling").values, "Số mã sàn": cot(h, "total_stock_floor").values},
                                  index=ngay(h["trading_date"]).values))
    except Exception as e: st.append(log("loi thong ke", ix, type(e).__name__, str(e)[:150]))
    try:
        f = goi(lambda: M.index(ix).foreign_flow(start=START_RO, end=END))
        parts.append(pd.DataFrame({"Khối ngoại ròng (tỷ)": (cot(f, "foreign_net_value", "net_val") / 1e9).round(1).values,
                                   "Khối ngoại ròng (triệu cp)": (cot(f, "foreign_net_volume", "net_vol") / 1e6).round(2).values}, index=ngay(f["time"]).values))
    except Exception as e: st.append(log("loi khoi ngoai", ix, type(e).__name__, str(e)[:150]))
    try:
        p = goi(lambda: M.index(ix).proprietary_flow(start=START_RO, end=END))
        parts.append(pd.DataFrame({"Tự doanh mua (tỷ)": (cot(p, "proprietary_buy_value") / 1e9).round(1).values,
                                   "Tự doanh bán (tỷ)": (cot(p, "proprietary_sell_value") / 1e9).round(1).values,
                                   "Tự doanh ròng (tỷ)": (cot(p, "proprietary_net_value") / 1e9).round(1).values}, index=ngay(p["time"]).values))
    except Exception as e: st.append(log("loi tu doanh", ix, type(e).__name__, str(e)[:150]))
    if not parts: continue
    parts = [q[~q.index.duplicated(keep="last")] for q in parts]
    m = pd.concat(parts, axis=1).sort_index()
    m = m[m.index < TODAY] if PHIEN_DANG_CHAY else m
    if "Điểm đóng cửa" in m.columns: m = m[m["Điểm đóng cửa"].notna()]
    if ix in ("VN30", "VN100"):   # SSI khong tra so ma tang/giam theo ro con: tu dem tu gia dong cua tung ma
        tv = px[[x for x in (vn30 if ix == "VN30" else vn100) if x in px.columns]]
        ch = tv.diff().where(tv.notna() & tv.shift(1).notna())
        m["Số mã tăng"] = (ch > 0).sum(axis=1).reindex(m.index); m["Số mã giảm"] = (ch < 0).sum(axis=1).reindex(m.index)
        m["Số mã đứng giá"] = (ch == 0).sum(axis=1).reindex(m.index); m["Số mã trần"] = float("nan"); m["Số mã sàn"] = float("nan")
    m = m.tail(N_PHIEN_RO); m.insert(0, "Rổ", ix); m.index.name = "Ngày"
    ro_rows.append(m.reset_index())
    log("ro", ix, len(m), "phien")
if ro_rows:
    ro = pd.concat(ro_rows)
    cols = ["Ngày", "Rổ", "Điểm đóng cửa", "Tăng/giảm (%)", "Khối lượng (triệu cp)", "GTGD (nghìn tỷ)", "Số mã tăng", "Số mã giảm", "Số mã đứng giá", "Số mã trần", "Số mã sàn",
            "Khối ngoại ròng (tỷ)", "Khối ngoại ròng (triệu cp)", "Tự doanh mua (tỷ)", "Tự doanh bán (tỷ)", "Tự doanh ròng (tỷ)"]
    for c in cols:
        if c not in ro.columns: ro[c] = float("nan")
    ro["_tt"] = ro["Rổ"].map({"VNINDEX": 0, "VN30": 1, "VN100": 2})
    ro = ro.sort_values(["Ngày", "_tt"], ascending=[False, True])[cols]
    for c in ("Số mã tăng", "Số mã giảm", "Số mã đứng giá", "Số mã trần", "Số mã sàn"): ro[c] = ro[c].astype("Int64")
    ro.to_csv(f"{OUT}/ro_dong_tien.csv", index=False)
    st.append(log(f"Ro dong tien: {len(ro)} dong, phien moi nhat {ro['Ngày'].max()}"))
    vni = ro[ro["Rổ"] == "VNINDEX"].set_index("Ngày")["Điểm đóng cửa"]
    dr.insert(0, "VN-Index đóng cửa", vni.reindex(dr.index))
dr = dr.tail(N_PHIEN_DO_RONG).sort_index(ascending=False); dr.index.name = "Ngày"
dr.reset_index().to_csv(f"{OUT}/do_rong.csv", index=False)
st.append(log(f"Do rong: {len(dr)} phien, moi nhat {dr.index.max()}"))

# ---------- 4. Chi tiet VN100 ----------
ct, loi2 = [], []
for i, s in enumerate(vn100):
    try:
        h = goi(lambda: M.equity(s).trade_history(start=START_CT, end=END))
        if h is None or not len(h): loi2.append(s); continue
        d = pd.DataFrame({"Ngày": ngay(h["trading_date"]).values, "Mã": s,
            "Giá đóng cửa (nghìn đ)": (cot(h, "close") / 1000).round(2).values,
            "Tăng/giảm (%)": (cot(h, "percent_price_change") * 100).round(2).values,
            "Khối lượng (triệu cp)": (cot(h, "total_volume") / 1e6).round(2).values,
            "GTGD (tỷ)": (cot(h, "total_value") / 1e9).round(1).values,
            "Khối ngoại mua (tỷ)": (cot(h, "foreign_buy_value") / 1e9).round(1).values,
            "Khối ngoại bán (tỷ)": (cot(h, "foreign_sell_value") / 1e9).round(1).values,
            "Khối ngoại ròng (tỷ)": (cot(h, "foreign_net_value") / 1e9).round(1).values,
            "Số lệnh đặt mua": cot(h, "total_buy_trade").values, "Số lệnh đặt bán": cot(h, "total_sell_trade").values,
            "KL TB mỗi lệnh mua": (cot(h, "total_buy_trade_volume") / cot(h, "total_buy_trade")).round(0).values,
            "KL TB mỗi lệnh bán": (cot(h, "total_sell_trade_volume") / cot(h, "total_sell_trade")).round(0).values})
        for c_ in ("Số lệnh đặt mua", "Số lệnh đặt bán", "KL TB mỗi lệnh mua", "KL TB mỗi lệnh bán"): d[c_] = d[c_].round(0).astype("Int64")
        d["Lệnh mua / lệnh bán (lần)"] = (d["KL TB mỗi lệnh mua"].astype(float) / d["KL TB mỗi lệnh bán"].astype(float)).round(2)
        for n in (20, 50, 200):
            if s in px.columns:
                t = tren[n][s]; d[f"Trên MA{n}"] = d["Ngày"].map(lambda x: "" if pd.isna(t.get(x, float("nan"))) else ("x" if t.get(x) == 1 else "-"))
            else: d[f"Trên MA{n}"] = ""
        d["Thuộc VN30"] = "x" if s in vn30 else ""
        ct.append(bo_hom_nay(d, "Ngày").sort_values("Ngày").tail(N_PHIEN_CT))
    except Exception as e:
        loi2.append(s)
        if len(loi2) <= 3: log("loi chi tiet", s, type(e).__name__, str(e)[:150])
    if i % 25 == 0: log(f"chi tiet {i}/{len(vn100)} {s}")
if len(ct) >= 80:
    c = pd.concat(ct).sort_values(["Ngày", "Mã"], ascending=[False, True])
    c.to_csv(f"{OUT}/vn100_chi_tiet.csv", index=False)
    st.append(log(f"VN100 chi tiet: {len(ct)}/100 ma, {len(c)} dong, phien moi nhat {c['Ngày'].max()}, {len(loi2)} ma loi"))
else:
    st.append(log(f"VN100 chi tiet: chi lay duoc {len(ct)} ma, giu bang cu"))
ghi_trang_thai("OK")
