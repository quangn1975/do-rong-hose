"""Lay so thi truong THANG tu SSI bang bo cong cu chinh thuc ssi-sdk (khoa SSI trong Secrets, khong OTP, KHONG dung vnstock).
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
OUT = os.getenv("THU_MUC_RA", "so"); os.makedirs(OUT, exist_ok=True)
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

from ssi_sdk import Auth, Config   # bo cong cu CHINH THUC cua SSI (pypi.org/project/ssi-sdk), khong dung thu vien vnstock
_auth = Auth(Config(api_key=os.environ["SSI_API_KEY"], api_secret=os.environ["SSI_API_SECRET"]))
_auth.authenticate()   # du lieu thi truong: khong can OTP
def api(path, **params):
    """Goi 1 dia chi du lieu cua SSI, tra ve danh sach dong. Het phien dang nhap thi dang nhap lai 1 lan."""
    err = None
    for i in range(4):
        try:
            body = _auth.rest_client.get("/api/v3/data/" + path, params=params)
            if isinstance(body, dict): body = body.get("data")
            return body or []
        except Exception as e:
            err = e
            if "Authentication" in type(e).__name__:
                try: _auth.authenticate()
                except Exception: pass
            time.sleep(2 * (i + 1))
    raise err
def so(df, c):
    return pd.to_numeric(df[c], errors="coerce") if c in df.columns else pd.Series([float("nan")] * len(df), index=df.index)
def bo_hom_nay(df, c="ngay"):
    return df[df[c] < TODAY] if PHIEN_DANG_CHAY else df
def d_ssi(s): return s.replace("-", "/")            # 2026-11-09 -> 2026/11/09
def d_iso(x): return str(x)[:10].replace("/", "-")   # 2026/11/09 -> 2026-11-09
def gia_ngay(symbol, start):
    r = api("ohlc", symbol=symbol, **{"from": d_ssi(start) + " 00:00:00", "to": d_ssi(END) + " 23:59:59"}, timeFrame="1d", pageIndex=1, pageSize=1000)
    d = pd.DataFrame(r)
    if not len(d): return d
    d["ngay"] = d["tradingDate"].map(d_iso)
    return d.drop_duplicates("ngay", keep="last").sort_values("ngay")

# ---------- 1. Danh sach ----------
try:
    hose = pd.DataFrame(api("securitiesByBoard", board="HOSE"))
    hose = hose[hose["stockType"].astype(str).str.lower().eq("stock")].drop_duplicates("symbol")
    vn30 = sorted(pd.DataFrame(api("securitiesByBoard", index="VN30"))["symbol"].astype(str))
    vn100 = sorted(pd.DataFrame(api("securitiesByBoard", index="VN100"))["symbol"].astype(str))
except Exception as e:
    st.append(log("LOI danh sach:", type(e).__name__, str(e)[:200])); ghi_trang_thai("HONG - khong lay duoc danh sach"); sys.exit(1)
syms = sorted(set(hose["symbol"].astype(str)) | set(vn30) | set(vn100))
ds = pd.DataFrame({"Mã": hose["symbol"].astype(str).values, "Tên công ty": hose["symbolNameVi"].astype(str).values, "Ngành": hose["icbName"].fillna("").astype(str).values})
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
        d = gia_ngay(s, START_GIA)
        if not len(d): loi.append(s); continue
        closes[s] = pd.Series((so(d, "close") / 1000).values, index=d["ngay"].values)
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
ix_gia = {}
for ix in ("VNINDEX", "VN30", "VN100"):
    try: ix_gia[ix] = gia_ngay(ix, START_RO)
    except Exception as e: st.append(log("loi diem", ix, type(e).__name__, str(e)[:150])); ix_gia[ix] = pd.DataFrame()
cac_phien = [x for x in (list(ix_gia["VNINDEX"]["ngay"]) if len(ix_gia["VNINDEX"]) else []) if not (PHIEN_DANG_CHAY and x >= TODAY)][-N_PHIEN_RO:]
for ix in ("VNINDEX", "VN30", "VN100"):
    rows = []
    for ng in cac_phien:
        try:
            r = api("indexSummary", index=ix, tradingDate=d_ssi(ng))
            if r: rows.append(r[0] if isinstance(r, list) else r)
        except Exception as e:
            if len(rows) < 2: log("loi tom tat ro", ix, ng, type(e).__name__, str(e)[:120])
    if not rows: st.append(log("khong co tom tat ro", ix)); continue
    h = pd.DataFrame(rows); h.index = h["tradingDate"].map(d_iso)
    h = h[~h.index.duplicated(keep="last")]
    m = pd.DataFrame({"Tăng/giảm (%)": so(h, "indexChangePercentage").round(2),
                      "GTGD (nghìn tỷ)": (so(h, "totalTradeValue") / 1e12).round(2),
                      "Số mã tăng": so(h, "totalAdvanceStock"), "Số mã giảm": so(h, "totalDeclineStock"), "Số mã đứng giá": so(h, "totalNoChangeStock"),
                      "Số mã trần": so(h, "totalCeilingStock"), "Số mã sàn": so(h, "totalFloorStock"),
                      "Khối ngoại ròng (tỷ)": (so(h, "netPurchasesForeignValue") / 1e9).round(1),
                      "Khối ngoại ròng (triệu cp)": (so(h, "netPurchasesForeignVolume") / 1e6).round(2),
                      "Tự doanh mua (tỷ)": (so(h, "totalPropBuyValue") / 1e9).round(1), "Tự doanh bán (tỷ)": (so(h, "totalPropSellValue") / 1e9).round(1)})
    m["Tự doanh ròng (tỷ)"] = ((so(h, "totalPropBuyValue") - so(h, "totalPropSellValue")) / 1e9).round(1)
    g = ix_gia[ix]
    if len(g):
        g = g.set_index("ngay")
        m["Điểm đóng cửa"] = so(g, "close").reindex(m.index); m["Khối lượng (triệu cp)"] = (so(g, "volume") / 1e6).round(1).reindex(m.index)
    else:
        m["Điểm đóng cửa"] = so(h, "indexValue"); m["Khối lượng (triệu cp)"] = (so(h, "totalTrade") / 1e6).round(1)
    m = m.sort_index()
    if ix in ("VN30", "VN100"):   # SSI khong tra so ma tang/giam theo ro con: tu dem tu gia dong cua tung ma
        tv = px[[x for x in (vn30 if ix == "VN30" else vn100) if x in px.columns]]
        ch = tv.diff().where(tv.notna() & tv.shift(1).notna())
        m["Số mã tăng"] = (ch > 0).sum(axis=1).reindex(m.index); m["Số mã giảm"] = (ch < 0).sum(axis=1).reindex(m.index)
        m["Số mã đứng giá"] = (ch == 0).sum(axis=1).reindex(m.index); m["Số mã trần"] = float("nan"); m["Số mã sàn"] = float("nan")
    m.insert(0, "Rổ", ix); m.index.name = "Ngày"
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
        h = pd.DataFrame(api("securitiesSummary", symbol=s, **{"from": d_ssi(START_CT), "to": d_ssi(END)}, pageIndex=1, pageSize=100))
        if not len(h): loi2.append(s); continue
        d = pd.DataFrame({"Ngày": h["tradingDate"].map(d_iso).values, "Mã": s,
            "Giá đóng cửa (nghìn đ)": (so(h, "close") / 1000).round(2).values,
            "Tăng/giảm (%)": so(h, "priceChangePercentage").round(2).values,
            "Khối lượng (triệu cp)": ((so(h, "totalMatch").fillna(0) + so(h, "totalDeal").fillna(0)) / 1e6).round(2).values,
            "GTGD (tỷ)": ((so(h, "totalMatchValue").fillna(0) + so(h, "totalDealValue").fillna(0)) / 1e9).round(1).values,
            "Khối ngoại mua (tỷ)": (so(h, "totalForeignBuyValue") / 1e9).round(1).values,
            "Khối ngoại bán (tỷ)": (so(h, "totalForeignSellValue") / 1e9).round(1).values,
            "Khối ngoại ròng (tỷ)": ((so(h, "totalForeignBuyValue") - so(h, "totalForeignSellValue")) / 1e9).round(1).values,
            "Số lệnh đặt mua": so(h, "totalBuy").values, "Số lệnh đặt bán": so(h, "totalSell").values,
            "KL TB mỗi lệnh mua": (so(h, "totalTradeBuy") / so(h, "totalBuy")).round(0).values,
            "KL TB mỗi lệnh bán": (so(h, "totalTradeSell") / so(h, "totalSell")).round(0).values})
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
