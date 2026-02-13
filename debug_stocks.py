#!/usr/bin/env python3
import yfinance as yf
import numpy as np

for t in ['NU', 'GOOG', 'GOOGL']:
    df = yf.download(t, period='1y', progress=False)
    if hasattr(df.columns, 'levels'):
        df.columns = df.columns.get_level_values(0)
    c = df['Close'].values
    v = df['Volume'].values
    o = df['Open'].values
    n = len(c)
    i = n - 1

    ma50 = np.mean(c[i-49:i+1])
    ma200 = np.mean(c[max(0,i-199):i+1])
    h252 = np.max(c[max(0,i-252):i+1])
    perf_3m = (c[i]/c[i-63]-1)*100 if i >= 63 else 0
    perf_6m = (c[i]/c[i-126]-1)*100 if i >= 126 else 0
    pct_from_high = (h252-c[i])/h252*100
    vol50 = np.mean(v[-50:])

    above_50 = "ABOVE" if c[i] > ma50 else "BELOW"
    above_200 = "ABOVE" if c[i] > ma200 else "BELOW"
    day_dir = "UP" if c[i] > o[i] else "DOWN"
    day_chg = (c[i]/o[i]-1)*100

    print(f"\n{t}: ${c[i]:.2f} ({n} bars)")
    print(f"  3M perf: {perf_3m:+.1f}% | 6M perf: {perf_6m:+.1f}%")
    print(f"  vs MA50: {above_50} (${ma50:.2f})")
    print(f"  vs MA200: {above_200} (${ma200:.2f})")
    print(f"  52wk high: ${h252:.2f} ({pct_from_high:.1f}% below)")
    print(f"  Last day: {day_dir} ({day_chg:+.1f}%)")
    print(f"  Avg vol: {vol50:,.0f}")

    # VCP check
    if i > 60 and c[i-40] > 0 and c[i-20] > 0:
        r1 = (np.max(c[i-60:i-30]) - np.min(c[i-60:i-30])) / c[i-40]
        r2 = (np.max(c[i-30:i-10]) - np.min(c[i-30:i-10])) / c[i-20]
        r3 = (np.max(c[i-10:i+1]) - np.min(c[i-10:i+1])) / c[i]
        v1 = np.mean(v[i-30:i-10])
        v2 = np.mean(v[i-10:i+1])
        print(f"  VCP: {r1*100:.1f}% -> {r2*100:.1f}% -> {r3*100:.1f}% vol_dec={v2<v1}")

    # Flat Base
    h40 = np.max(c[max(0,i-40):i+1])
    l40 = np.min(c[max(0,i-40):i+1])
    rng = (h40-l40)/l40 if l40 > 0 else 0
    pos = (c[i]-l40)/(h40-l40) if h40 > l40 else 0
    print(f"  Flat: range={rng*100:.1f}% pos={pos*100:.0f}% near_high={h40/h252*100:.0f}%")

    # Cup
    if i > 80:
        lh = np.max(c[i-80:i-50])
        cl = np.min(c[i-50:i-15])
        rs = np.max(c[i-15:i-5])
        depth = (lh-cl)/lh if lh > 0 else 0
        recov = rs/lh if lh > 0 else 0
        print(f"  Cup: depth={depth*100:.1f}% recovery={recov*100:.0f}%")
