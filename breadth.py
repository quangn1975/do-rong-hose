"""Do rong thi truong HOSE: % co phieu dong cua tren MA20 / MA50 / MA200.

Cach tinh theo du an mo FTU-kudo/VN_Index_and_MA_ratio_analysis (Apache 2.0):
lay gia dong cua hang ngay cua toan bo co phieu HOSE qua vnstock, tinh MA cho
tung ma, roi dem ty le ma dong cua tren MA moi phien.
Ket qua ghi vao data/breadth.csv de Google Sheets doc bang IMPORTDATA.
"""
import os, sys, time, datetime as dt
import pandas as pd
from vnstock import Listing, Quote

START = "2025-01-01"          # du lich su cho MA200 tu giua 2025
OUT = "data/breadth.csv"
DELAY = float(os.getenv("VNSTOCK_DELAY", "3.2"))   # khach: ~20 lan goi/phut
today = (dt.datetime.utcnow() + dt.timedelta(hours=7)).date().isoformat()


def hose_symbols():
    for src in ("kbs", "VCI"):
        try:
            df = Listing(source=src).symbols_by_exchange(to_df=True)
            cols = {c.lower(): c for c in df.columns}
            ex = next((cols[c] for c in cols if "exchange" in c or c == "board"), None)
            sym = cols.get("symbol") or cols.get("ticker")
            if ex:
                df = df[df[ex].astype(str).str.upper().isin(["HOSE", "HSX"])]
            typ = next((cols[c] for c in cols if c in ("type", "stock_type", "organ_type")), None)
            if typ:
                t = df[typ].astype(str).str.upper()
                df = df[t.str.contains("STOCK") | t.str.contains("CP") | (t == "")]
            s = df[sym].astype(str).str.upper()
            s = sorted(set(s[s.str.fullmatch(r"[A-Z]{3}")]))
            if len(s) > 200:
                print(f"{len(s)} ma HOSE (nguon {src})")
                return s
        except Exception as e:
            print("Listing loi", src, e)
    sys.exit("Khong lay duoc danh sach ma HOSE")


def history(sym):
    for attempt in range(3):
        try:
            df = Quote(symbol=sym, source="VCI").history(start=START, end=today, interval="1D")
            if df is not None and len(df):
                df = df[["time", "close"]].copy()
                df["time"] = pd.to_datetime(df["time"]).dt.date
                df["symbol"] = sym
                return df
            return None
        except Exception as e:
            print("loi", sym, e)
            time.sleep(5)
    return None


def main():
    frames = []
    for i, s in enumerate(hose_symbols()):
        d = history(s)
        if d is not None:
            frames.append(d)
        if i % 50 == 0:
            print(i, s, flush=True)
        time.sleep(DELAY)
    full = pd.concat(frames).sort_values(["symbol", "time"])
    g = full.groupby("symbol")["close"]
    for n in (20, 50, 200):
        ma = g.transform(lambda x: x.rolling(n).mean())
        full[f"valid{n}"] = ma.notna()
        full[f"above{n}"] = ma.notna() & (full["close"] > ma)
    agg = full.groupby("time").agg(
        **{f"above{n}": (f"above{n}", "sum") for n in (20, 50, 200)},
        **{f"valid{n}": (f"valid{n}", "sum") for n in (20, 50, 200)},
    )
    out = pd.DataFrame(index=agg.index)
    for n in (20, 50, 200):
        out[f"pct_ma{n}"] = (agg[f"above{n}"] / agg[f"valid{n}"] * 100).round(2)
    out["so_ma_ma20"] = agg["valid20"]
    out = out[agg["valid20"] >= 100]          # bo cac ngay chua du ma
    # chay truoc 15:00 gio VN thi phien hom nay chua ket thuc: bo dong hom nay
    if (dt.datetime.utcnow() + dt.timedelta(hours=7)).hour < 15:
        out = out[[str(d) != today for d in out.index]]
    out.index.name = "date"
    os.makedirs("data", exist_ok=True)
    out.to_csv(OUT)
    print(out.tail())


if __name__ == "__main__":
    main()
