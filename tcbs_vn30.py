"""TCBS -> VN30 + quy ETF: Mua/Ban chu dong theo 3 nhom (Ca map / Soi gia / Cuu non). Chay tren GitHub.
Anh nhap Smart OTP o nut "Run workflow"; tep nay mo phien TCBS roi lay lenh khop TUNG MA, CHAM, trong cung 1 lan chay.

BAO MAT:
- Khong in, khong ghi ra tep: OTP, khoa API, ma phien (token). Moi dong in ra deu di qua bo loc che.
- Chi GOI CAC DIA CHI DOC SO LIEU THI TRUONG (bang gia, nen gia, lenh khop). Khong goi dia chi nao ve tai khoan, lenh, tien.
- Chi ghi so da cong gop vao thu muc so/tcbs. Khong luu phan hoi tho cua TCBS.
- Het viec thi xoa phien khoi may chu (buoc don dep trong workflow xoa them lan nua).
Phan loai theo TCBS: Ca map > 1 ty / lenh dat; Soi gia 200 trieu - 1 ty; Cuu non < 200 trieu.
Lenh dat duoc dung lai bang cach gop cac lan khop lien tiep cung giay, cung ben chu dong."""
import os, sys, re, csv, json, time, logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logging.disable(logging.WARNING)          # thu vien khong duoc ghi gi ra nhat ky cong khai
VN = timezone(timedelta(hours=7))
now = datetime.now(VN)
OUT = os.getenv("THU_MUC_RA", "so/tcbs"); os.makedirs(OUT, exist_ok=True)
SHARK, WOLF = 1_000_000_000, 200_000_000
GIU_PHIEN = 180                            # so phien giu lai trong bang tung ma

ev = {}
try: ev = json.load(open(os.environ.get("GITHUB_EVENT_PATH", "")))
except Exception: pass
OTP = re.sub(r"\D", "", str((ev.get("inputs") or {}).get("otp") or ""))
_BI_MAT = [v for v in (os.environ.get("TCBS_API_KEY", ""), OTP) if v]
def sach(s):
    s = str(s)
    for v in _BI_MAT: s = s.replace(v, "***")
    s = re.sub(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-\.]{8,}", "***", s)        # ma phien dang JWT
    s = re.sub(r"(?i)(bearer|token|authorization|apikey|api_key)(\W{1,4})[A-Za-z0-9_\-\.=+/]{12,}", r"\1\2***", s)
    return re.sub(r"[A-Za-z0-9_\-+/=]{48,}", "***", s)                             # chuoi dai bat thuong
st = []
def say(*a):
    s = sach(" ".join(str(x) for x in a)); print(s[:500], flush=True); return s
def ghi_trang_thai(kq):
    open(f"{OUT}/trang_thai.txt", "w", encoding="utf-8").write(
        f"Lan chay: {now.strftime('%d/%m/%Y %H:%M')} (gio VN)\nKet qua: {kq}\n" + "\n".join(st) + "\n")
def dung(kq, ma=1):
    ghi_trang_thai(kq); xoa_phien(); sys.exit(ma)

import vnstock_oapi as oapi
from vnstock_oapi.errors import RateLimitError
src = oapi.source("tcbs")
def xoa_phien():
    try: src.clear_auth()
    except Exception: pass

TRONG_PHIEN = now.weekday() < 5 and (9, 0) <= (now.hour, now.minute) < (15, 0)
THU = (TRONG_PHIEN and os.getenv("EP_DAY_DU") != "1") or os.getenv("CHI_THU") == "1"   # trong gio giao dich: chi thu 3 ma, KHONG ghi bang ngay
say("Chay luc", now.strftime("%d/%m/%Y %H:%M:%S"), "(gio VN) | che do:", "THU 3 ma (dang trong phien)" if THU else "DAY DU")
try:                                        # kho giu phien tam tren may chu phai san sang TRUOC khi dung OTP
    import keyring
    keyring.set_password("thu-kho", "x", "1"); _ok = keyring.get_password("thu-kho", "x") == "1"; keyring.delete_password("thu-kho", "x")
    if not _ok: raise RuntimeError("doc lai khong khop")
    say("Kho giu phien tam: san sang")
except Exception as e:
    st.append(say("Kho giu phien tam HONG:", type(e).__name__, sach(str(e))[:150])); dung("HONG - loi may chu, CHUA dung OTP")
if not OTP:
    say("Khong co OTP: dung, KHONG goi TCBS."); st.append("Chua nhap Smart OTP"); dung("CHUA CHAY - thieu OTP", 0)

# ---------- Mo phien ----------
try:
    r = src.authenticate(OTP)
    say("Mo phien TCBS: OK, con han khoang", round(float((r or {}).get("expires_in_s", 0)) / 3600, 1), "gio")
except Exception as e:
    t = sach(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(e))))[:200]
    st.append(say("Mo phien TCBS HONG:", type(e).__name__, "|", t))
    dung("HONG - TCBS khong nhan OTP (ma het han hoac go nham). Lay ma moi roi bam chay lai, CHI THU LAI 1 LAN.")

delay = 0.7          # giay nghi giua 2 lan goi; tu tang khi TCBS bao qua tai
so_lan_qua_tai = 0
def goi(fn, *a, **k):
    """Goi TCBS cham. Bi bao qua tai (429) thi nghi lau dan roi thu lai, dong thoi di cham hon ve sau."""
    global delay, so_lan_qua_tai
    for lan in range(8):
        try:
            res = fn(*a, **k); time.sleep(delay); return res
        except RateLimitError as e:
            so_lan_qua_tai += 1
            cho = min(300, max(float(getattr(e, "retry_after", 0) or 0) + 2, 30 * (lan + 1)))
            delay = min(3.0, delay * 1.5)
            say(f"    TCBS bao qua tai: nghi {round(cho)} giay, tu gio moi lan goi cach nhau {round(delay, 1)} giay")
            time.sleep(cho)
    raise RateLimitError("qua tai qua lau")
def bodies(res): return [e.body for e in res]
def rows_of(res):
    out = []
    for b in bodies(res):
        d = b.get("data") if isinstance(b, dict) else None
        if isinstance(d, list): out.extend(d)
    return out
def pick(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""): return d[k]
    return None
def num(x):
    try: return float(x)
    except Exception: return 0.0

def lay_lenh_khop(t):
    rows, page, total = [], 0, None
    while True:
        env = goi(src.raw, "stock/price-history", only_page=page, ticker=t, page=page, size=100, headIndex=-1)
        b = env[0].body if env else {}
        d = (b.get("data") if isinstance(b, dict) else None) or []
        rows.extend(d)
        total = b.get("total") if isinstance(b, dict) and isinstance(b.get("total"), int) else total
        page += 1
        if not d or total is None or page * 100 >= total: break
    return rows, total

def gop_nhom(rows):
    """Gop cac lan khop lien tiep cung giay + cung ben chu dong thanh 1 LENH DAT, roi chia nhom theo gia tri."""
    orders, last_key = [], None
    for r in rows:
        p = float(pick(r, "p", "price") or 0); v = float(pick(r, "v", "volume") or 0)
        if p and p < 1000: p *= 1000
        side = str(pick(r, "a", "side") or "").upper()
        if side in ("BU", "B", "BUY"): s = "mua"
        elif side in ("SD", "S", "SELL"): s = "ban"
        else:
            last_key = None; continue
        key = (pick(r, "t", "time"), s)
        if key == last_key and orders: orders[-1][1] += p * v
        else: orders.append([s, p * v])
        last_key = key
    m = defaultdict(float)
    for s, val in orders:
        m[(s, "camap" if val > SHARK else ("soigia" if val >= WOLF else "cuunon"))] += val
    return m

NHOM = ("camap", "soigia", "cuunon")
# Bo cuc DUNG NHU 3 tab cu cua file Google Sheet "VN30 chu dong" (Tong VN30, Tung ma, Quy ETF): cac tab do tu doc cac tep nay,
# nen KHONG doi thu tu / ten cot. Ngay tang dan (cu o tren) vi bieu do cong don can thu tu do.
COT_MA = ["Ngày", "Mã", "Số lệnh khớp", "Mua CĐ (tỷ)", "Bán CĐ (tỷ)", "Ròng (tỷ)",
          "Mua: Cá mập", "Mua: Sói già", "Mua: Cừu non", "Bán: Cá mập", "Bán: Sói già", "Bán: Cừu non",
          "Cá mập ròng", "Sói già ròng", "Cừu non ròng",
          "Giá đóng cửa", "% thay đổi giá", "GTGD (tỷ)", "NN mua (tỷ)", "NN bán (tỷ)", "NN ròng (tỷ)"]
COT_TONG = ["Ngày", "Mua chủ động (nghìn tỷ)", "Bán chủ động (nghìn tỷ)", "Mua trừ bán (nghìn tỷ)",
            "Mua CĐ: Cá mập", "Mua CĐ: Sói già", "Mua CĐ: Cừu non", "Bán CĐ: Cá mập", "Bán CĐ: Sói già", "Bán CĐ: Cừu non",
            "Cá mập ròng (nghìn tỷ)", "Sói già ròng (nghìn tỷ)", "Cừu non ròng (nghìn tỷ)",
            "Khối ngoại mua (tỷ)", "Khối ngoại bán (tỷ)", "Khối ngoại ròng (tỷ)"]
def dong_ma(session, t, n, m, bi):
    mua = sum(m[("mua", g)] for g in NHOM); ban = sum(m[("ban", g)] for g in NHOM)
    nh = [round(m[(s, g)] / 1e9, 2) for s in ("mua", "ban") for g in NHOM]
    return ([session, t, n, round(mua / 1e9, 2), round(ban / 1e9, 2), round((mua - ban) / 1e9, 2)] + nh +
            [round(nh[i] - nh[i + 3], 2) for i in range(3)] +        # rong tung nhom = mua - ban (tu so da lam tron, nhu tab cu)
            [bi.get("close", 0), round(bi.get("pct", 0), 2), round(bi.get("gtgd", 0) / 1e9, 2),
             round(bi.get("nn_mua", 0) / 1e9, 2), round(bi.get("nn_ban", 0) / 1e9, 2), round((bi.get("nn_mua", 0) - bi.get("nn_ban", 0)) / 1e9, 2)])
def thong_tin_bang(rows, loc=None):
    info = {}
    for r in rows:
        sym = str(pick(r, "symbol", "ticker", "t") or "").upper()
        if not sym or (loc and not loc(sym)): continue
        avg = num(pick(r, "avg")) or num(pick(r, "matchPrice"))
        info[sym] = {"close": num(pick(r, "matchPrice")), "pct": num(pick(r, "changePercent")), "gtgd": num(pick(r, "totalVal", "totalValue")),
                     "nn_mua": num(pick(r, "buyForeignQtty")) * avg, "nn_ban": num(pick(r, "sellForeignQtty")) * avg}
    return info
def ghi_bang(ten, cot, dong_moi, khoa, giu=None):
    """Ghi de cac dong cung khoa (ngay / ngay+ma), giu lai lich su; moi nhat o tren."""
    p = f"{OUT}/{ten}"; cu = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f: cu = [r for r in csv.reader(f)][1:]
    moi = {tuple(str(x) for x in r[:khoa]) for r in dong_moi}
    tat = [r for r in cu if r and tuple(r[:khoa]) not in moi] + [[str(x) for x in r] for r in dong_moi]
    tat.sort(key=lambda r: (r[0], *([r[1]] if khoa > 1 else [])))      # ngay tang dan, trong ngay xep theo ma
    if giu:
        ngay_giu = sorted({r[0] for r in tat}, reverse=True)[:giu]; tat = [r for r in tat if r[0] in ngay_giu]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cot); w.writerows(tat)

try:
    # ---------- 1. Bang gia ro VN30 ----------
    board_res = goi(src.board, basket="VN30")
    board = rows_of(board_res); board_date = None
    for b in bodies(board_res):
        if isinstance(b, dict) and b.get("tradingDate"): board_date = str(b["tradingDate"])
    info = thong_tin_bang(board)
    tickers = sorted(info)
    if len(tickers) < 25:
        st.append(say("Khong doc duoc danh sach VN30:", len(tickers), "ma")); dung("HONG - khong doc duoc danh sach VN30")
    # ---------- 2. Ngay phien ----------
    session = now.strftime("%Y-%m-%d")
    try:
        bars = rows_of(goi(src.ohlc, tickers[0], start=(now - timedelta(days=14)).strftime("%Y-%m-%d"), end=now.strftime("%Y-%m-%d"), interval="1D"))
        dates = sorted(str(pick(r, "tradingDate", "t", "time"))[:10] for r in bars if pick(r, "tradingDate", "t", "time"))
        if dates: session = dates[-1]
    except Exception as e: say("khong lay duoc ngay tu nen gia:", type(e).__name__)
    if board_date:
        try: session = datetime.strptime(board_date, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError: pass
    say(f"Phien: {session} | VN30: {len(tickers)} ma")
    if THU: tickers = tickers[:3]

    # ---------- 3. Lenh khop tung ma ----------
    t0 = time.time(); dong, tot, thieu, chua_du = [], defaultdict(float), [], []
    def lam(ds, thong_tin, nhan):
        for i, t in enumerate(ds, 1):
            try:
                rows, total = lay_lenh_khop(t)
            except RateLimitError:
                thieu.append(t); say(f"  {nhan} [{i}/{len(ds)}] {t}: TCBS chan qua lau, de lai lay sau"); continue
            m = gop_nhom(rows)
            if isinstance(total, int) and total > len(rows): chua_du.append(f"{t} {len(rows)}/{total}")
            yield t, len(rows), m, thong_tin.get(t, {})
            mua = sum(m[("mua", g)] for g in NHOM); ban = sum(m[("ban", g)] for g in NHOM)
            say(f"  {nhan} [{i}/{len(ds)}] {t}: {len(rows)} lenh khop, mua CD {mua/1e9:.0f} ty, ban CD {ban/1e9:.0f} ty ({round(time.time() - t0)} giay)")
    xong = {}
    for t, n, m, bi in lam(tickers, info, "VN30"): xong[t] = (n, m, bi)
    if thieu:                                   # khong bo ma: nghi 3 phut roi lay not cac ma con thieu
        con = list(thieu); thieu.clear(); say(f"Nghi 180 giay roi lay not {len(con)} ma con thieu: {', '.join(con)}"); time.sleep(180)
        for t, n, m, bi in lam(con, info, "VN30 (lay not)"): xong[t] = (n, m, bi)
    for t in tickers:
        if t in xong:
            n, m, bi = xong[t]; dong.append(dong_ma(session, t, n, m, bi))
            for k, v in m.items(): tot[k] += v
    st.append(say(f"VN30: {len(xong)}/{len(tickers)} ma, {sum(v[0] for v in xong.values())} lenh khop, {round((time.time() - t0) / 60, 1)} phut, TCBS bao qua tai {so_lan_qua_tai} lan, toc do cuoi {round(delay, 1)} giay/lan goi"))
    if chua_du: st.append(say("CANH BAO chua lay du lenh:", "; ".join(chua_du)))
    if thieu: st.append(say("CON THIEU MA:", ", ".join(thieu)))

    if THU:
        st.append("Che do THU trong gio giao dich: chi 3 ma, KHONG ghi vao bang ngay.")
        with open(f"{OUT}/thu_trong_phien.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(COT_MA); w.writerows(dong)
        dung("THU OK" if len(xong) == len(tickers) else "THU - thieu ma", 0)

    if dong: ghi_bang("tung_ma.csv", COT_MA, dong, 2, GIU_PHIEN)
    if len(xong) == len(tickers) and not chua_du:
        mua = sum(tot[("mua", g)] for g in NHOM); ban = sum(tot[("ban", g)] for g in NHOM)
        def share(s, g):
            tt = sum(tot[(s, x)] for x in NHOM); return round(tot[(s, g)] / tt, 3) if tt else 0      # ty le 0-1, nhu tab cu
        nn_mua = sum(info[t]["nn_mua"] for t in tickers); nn_ban = sum(info[t]["nn_ban"] for t in tickers)
        row = [session, round(mua / 1e12, 3), round(ban / 1e12, 3), round((mua - ban) / 1e12, 3)] + \
              [share(s, g) for s in ("mua", "ban") for g in NHOM] + \
              [round((tot[("mua", g)] - tot[("ban", g)]) / 1e12, 3) for g in NHOM] + \
              [round(nn_mua / 1e9, 1), round(nn_ban / 1e9, 1), round((nn_mua - nn_ban) / 1e9, 1)]
        ghi_bang("tong_vn30.csv", COT_TONG, [row], 1)
        st.append(say("Tong VN30:", json.dumps(dict(zip(["ngay", "mua", "ban", "rong"], row[:4])))))
    else:
        st.append(say("KHONG ghi dong tong VN30 vi chua du 30 ma (tranh so sai)."))

    # ---------- 4. Quy ETF tren HOSE ----------
    try:
        etf_info = thong_tin_bang(rows_of(goi(src.board, basket="HOSE")), lambda s: s.startswith("E1") or s.startswith("FUE"))
        etfs = sorted(etf_info); dong_etf = []
        for t, n, m, bi in lam(etfs, etf_info, "ETF"): dong_etf.append(dong_ma(session, t, n, m, bi))
        if dong_etf: ghi_bang("quy_etf.csv", [c.replace("Mã", "Mã quỹ ETF") if c == "Mã" else c for c in COT_MA], dong_etf, 2, GIU_PHIEN)
        st.append(say(f"Quy ETF: {len(dong_etf)}/{len(etfs)} ma"))
    except Exception as e:
        st.append(say("LOI phan quy ETF (phan VN30 da ghi xong):", type(e).__name__, sach(str(e))[:150]))
    dung("OK" if (len(xong) == len(tickers) and not chua_du) else "CHUA DU - xem cac dong duoi", 0)
except SystemExit:
    raise
except Exception as e:
    st.append(say("LOI:", type(e).__name__, sach(re.sub(r"\s+", " ", str(e)))[:300]))
    dung("HONG - xem dong loi ben duoi")
