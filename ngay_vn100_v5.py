"""Thu lay du lieu vnstock the he 5 (tu doanh, khoi ngoai theo phien, thong ke cuoi phien) cho VN100.
Can khoa API con suat thiet bi. Ghi trang thai vao data/vn100_v5_trangthai.txt de biet co lay duoc hay khong."""
import os, sys, time
import pandas as pd
from datetime import datetime, timezone, timedelta
gio = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")
st = []
def ghi():
    open("data/vn100_v5_trangthai.txt", "w").write(f"{gio} (gio VN)\n" + "\n".join(st))
try:
    import vnstock
    vnstock.login(os.environ.get("VNSTOCK_API_KEY", ""))
    from vnstock import Market
    Market().equity("HPG").proprietary_flow(limit=1)
    st.append("Dang nhap OK")
except Exception as e:
    st.append("KHONG lay duoc (v5): " + type(e).__name__ + " " + str(e)[:150].replace(os.environ.get("VNSTOCK_API_KEY", "@@"), "***"))
    ghi(); sys.exit(0)
syms = open("data/vn100_ds.txt").read().split()
for fn, f in (("tu_doanh", "proprietary_flow"), ("khoi_ngoai_phien", "foreign_flow"), ("thong_ke_cuoi_phien", "session_stats")):
    rows = []
    for s in syms:
        try:
            r = getattr(Market().equity(s), f)(limit=1)
            if r is not None and len(r):
                r = r.copy(); r.insert(0, "ma", s); rows.append(r)
        except Exception as e:
            pass
        time.sleep(1.1)
    if rows:
        pd.concat(rows).to_csv(f"data/vn100_{fn}.csv", index=False)
        st.append(f"{fn}: {len(rows)}/{len(syms)} ma")
    else:
        st.append(f"{fn}: khong co du lieu")
ghi()
