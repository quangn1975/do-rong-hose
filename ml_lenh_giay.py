"""Chay 18:20 hang ngay (gio VN): cham diem hoc may cho ro 35 ma + ghi LENH GIAY (khong phai tien that).

Buoc 1: cap nhat gia ngay moi nhat vao data/lich_su_3nam.csv (bo bar hom nay neu chua dong cua)
Buoc 2: cho may hoc lai tu toan bo lich su, cham diem tung ma ("kha nang tang >2% trong 5 phien")
Buoc 3: cap nhat lenh giay dang mo (cat lo 5% hoac du 5 phien), mo lenh moi neu do rong ro < 30%
Ket qua: data/ml_diem.csv, data/ml_lenh_giay.csv, data/ml_trangthai.txt
Dat KHONG_CAP_NHAT=1 de chay thu ma khong goi vnstock.
"""
import os, sys, time, warnings
import datetime as dt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

warnings.filterwarnings("ignore")
CSV, DIEM, LENH, TT = "data/lich_su_3nam.csv", "data/ml_diem.csv", "data/ml_lenh_giay.csv", "data/ml_trangthai.txt"
NGUONG_DO_RONG, TOP_N, MAX_MO, CAT_LO, SO_PHIEN = 0.30, 3, 5, 0.05, 5
now = dt.datetime.utcnow() + dt.timedelta(hours=7)
gio = now.strftime("%Y-%m-%d %H:%M")
st = []


def ghi_tt():
    open(TT, "w").write(f"{gio} (gio VN)\n" + "\n".join(st) + "\n")


# ---------- Buoc 1: cap nhat gia ----------
d0 = pd.read_csv(CSV)
d0["ngay"] = d0["ngay"].astype(str)
if not os.getenv("KHONG_CAP_NHAT"):
    from ngay15 import lich_su, DELAY
    moi = []
    for s in sorted(d0["ma"].unique()):
        df = lich_su(s, 45)
        if df is not None and len(df):
            df = df.rename(columns={"time": "ngay"})
            df.insert(0, "ma", s)
            cu = d0[d0["ma"] == s]["close"].median()
            if cu and df["close"].median() / cu > 5:      # VCI doi don vi dong -> nghin dong
                for c in ("open", "high", "low", "close"):
                    df[c] = df[c] / 1000
            moi.append(df)
        time.sleep(DELAY)
    if moi:
        d0 = pd.concat([d0] + moi, ignore_index=True).drop_duplicates(["ma", "ngay"], keep="last")
        st.append(f"Cap nhat gia: {len(moi)}/{d0['ma'].nunique()} ma")
    else:
        st.append("KHONG cap nhat duoc gia (dung du lieu cu)")
# bo bar hom nay neu chua qua 15:10 (phien chua dong)
if now.hour * 60 + now.minute < 15 * 60 + 10:
    d0 = d0[d0["ngay"] != now.date().isoformat()]
d0 = d0.sort_values(["ma", "ngay"]).reset_index(drop=True)
d0.to_csv(CSV, index=False)


# ---------- Buoc 2: dac trung + hoc may ----------
def feat(g):
    g = g.copy()
    c, h, l, v = g["close"], g["high"], g["low"], g["volume"]
    g["ret1"] = c.pct_change()
    g["ret5"] = c.pct_change(5)
    g["ret20"] = c.pct_change(20)
    g["vol_ratio"] = v / v.rolling(20, min_periods=10).mean()
    g["c_vs_ma20"] = c / c.rolling(20, min_periods=10).mean() - 1
    g["c_vs_ma50"] = c / c.rolling(50, min_periods=30).mean() - 1
    dl = c.diff()
    up = dl.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    dn = (-dl.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    g["rsi"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    g["macd_hist"] = (macd - macd.ewm(span=9, adjust=False).mean()) / c
    g["macd_up"] = (g["macd_hist"].diff() > 0).astype(int)
    tp = (h + l + c) / 3
    mf = tp * v
    pos = mf.where(tp.diff() > 0, 0).rolling(14).sum()
    neg = mf.where(tp.diff() < 0, 0).rolling(14).sum()
    g["mfi"] = 100 - 100 / (1 + pos / neg.replace(0, np.nan))
    g["effort_result"] = g["vol_ratio"] / (g["ret1"].abs() * 100 + 0.5)
    g["range_pos"] = (c - l) / (h - l).replace(0, np.nan)
    g["fwd5"] = c.shift(-5) / c - 1
    return g


d = pd.concat([feat(g) for _, g in d0.groupby("ma")], ignore_index=True)
d["tren_ma20"] = (d["c_vs_ma20"] > 0).astype(float).where(d["c_vs_ma20"].notna())
d["breadth"] = d.groupby("ngay")["tren_ma20"].transform("mean")
d["mkt_ret5"] = d.groupby("ngay")["ret5"].transform("mean")
F = ["ret1", "ret5", "ret20", "vol_ratio", "c_vs_ma20", "c_vs_ma50", "rsi", "macd_hist", "macd_up", "mfi",
     "effort_result", "range_pos", "breadth", "mkt_ret5"]
hoc = d.dropna(subset=F + ["fwd5"]).copy()
hoc["y"] = (hoc["fwd5"] > 0.02).astype(int)
mdl = GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=1)
mdl.fit(hoc[F], hoc["y"])
st.append(f"Hoc tu {len(hoc)} dong, den ngay {hoc['ngay'].max()}")

ngay_cuoi = d["ngay"].max()
hn = d[d["ngay"] == ngay_cuoi].dropna(subset=F).copy()
if hn.empty:
    st.append(f"Khong du dac trung cho ngay {ngay_cuoi}")
    ghi_tt()
    sys.exit(0)
hn["diem"] = mdl.predict_proba(hn[F])[:, 1]
hn = hn.sort_values("diem", ascending=False).reset_index(drop=True)
hn["hang"] = hn.index + 1
do_rong = float(hn["breadth"].iloc[0])
dk = do_rong < NGUONG_DO_RONG
hn["de_xuat"] = np.where(dk & (hn["hang"] <= TOP_N), "Mo lenh giay", "-")
out = pd.DataFrame({"ngay": hn["ngay"], "ma": hn["ma"], "diem_pct": (hn["diem"] * 100).round(1), "hang": hn["hang"],
                    "gia_dong": hn["close"], "do_rong_ro_pct": round(do_rong * 100),
                    "dieu_kien_do_rong": "Dat" if dk else "Chua", "de_xuat": hn["de_xuat"]})
out.to_csv(DIEM, index=False)
st.append(f"Ngay {ngay_cuoi}: do rong ro {round(do_rong * 100)}% tren MA20 (nguong < {int(NGUONG_DO_RONG * 100)}%) -> {'DAT' if dk else 'chua dat'}")

# ---------- Buoc 3: lenh giay ----------
COT = ["ma", "ngay_mo", "gia_vao", "diem_pct", "do_rong_pct", "ngay_dong", "gia_ra", "ly_do_dong", "loi_pct", "trang_thai"]
lenh = pd.read_csv(LENH) if os.path.exists(LENH) else pd.DataFrame(columns=COT)
for c in ("ma", "ngay_mo", "ngay_dong", "ly_do_dong", "trang_thai"):      # cot chu: tranh pandas ep thanh so
    lenh[c] = lenh[c].astype(object).where(lenh[c].notna(), "").astype(str)
for c in ("gia_vao", "diem_pct", "do_rong_pct", "gia_ra", "loi_pct"):
    lenh[c] = pd.to_numeric(lenh[c], errors="coerce").astype(float)
close = d0.pivot(index="ngay", columns="ma", values="close")
da_dong = 0
for i, r in lenh[lenh["trang_thai"] == "mo"].iterrows():
    seq = close[r["ma"]].dropna()
    seq = seq[seq.index > r["ngay_mo"]]
    for k, (ngay, c) in enumerate(seq.items(), 1):
        ly = "cat lo 5%" if c <= r["gia_vao"] * (1 - CAT_LO) else ("du 5 phien" if k >= SO_PHIEN else None)
        if ly:
            lenh.loc[i, ["ngay_dong", "gia_ra", "ly_do_dong", "loi_pct", "trang_thai"]] = [ngay, c, ly, round((c / r["gia_vao"] - 1) * 100, 2), "dong"]
            da_dong += 1
            break
moi_mo = 0
if dk and ngay_cuoi not in set(lenh["ngay_mo"].astype(str)):
    dang_mo = set(lenh.loc[lenh["trang_thai"] == "mo", "ma"])
    cho = MAX_MO - len(dang_mo)
    for _, r in hn[hn["hang"] <= TOP_N].iterrows():
        if cho <= 0:
            break
        if r["ma"] in dang_mo:
            continue
        lenh.loc[len(lenh)] = [r["ma"], ngay_cuoi, r["close"], round(r["diem"] * 100, 1), round(do_rong * 100), "", np.nan, "", np.nan, "mo"]
        cho -= 1
        moi_mo += 1
lenh.to_csv(LENH, index=False)
dong = lenh[lenh["trang_thai"] == "dong"]
st.append(f"Lenh giay: mo moi {moi_mo}, vua dong {da_dong}, dang mo {int((lenh['trang_thai'] == 'mo').sum())}")
if len(dong):
    st.append(f"Da dong {len(dong)} lenh: thang {round((dong['loi_pct'].astype(float) > 0).mean() * 100)}%, loi TB {round(dong['loi_pct'].astype(float).mean(), 2)}%")
ghi_tt()
print(open(TT).read())
