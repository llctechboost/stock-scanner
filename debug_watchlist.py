#!/usr/bin/env python3
"""Debug why watchlist is empty."""
import yfinance as yf
import numpy as np

UNIVERSE = [
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO',
    'PLTR', 'NET', 'CRWD', 'PANW', 'NOW', 'SHOP', 'SMCI', 'ARM', 'APP', 'HIMS',
    'GS', 'JPM', 'V', 'MA', 'COIN', 'HOOD', 'SOFI', 'NU',
    'LLY', 'NVO', 'UNH', 'ISRG', 'VRTX',
    'UBER', 'ABNB', 'AXON', 'DECK', 'GWW', 'URI',
    'ASML', 'LRCX', 'KLAC', 'AMAT', 'COST', 'TJX', 'HD', 'LOW'
]

for t in UNIVERSE:
    try:
        df = yf.download(t, period='1y', progress=False)
        if hasattr(df.columns, 'levels'):
            df.columns = df.columns.get_level_values(0)
        c = df['Close'].values
        v = df['Volume'].values
        o = df['Open'].values
        n = len(c)
        i = n - 1
        if n < 200:
            continue

        ma50 = np.mean(c[i-49:i+1])
        ma200 = np.mean(c[max(0,i-199):i+1])
        h252 = np.max(c[max(0,i-252):i+1])
        pct_from_high = (h252 - c[i]) / h252
        vol50 = np.mean(v[-50:])
        vol_ratio = v[i] / vol50 if vol50 > 0 else 0

        tags = []

        # Flat base check (relaxed)
        h40 = np.max(c[max(0,i-40):i+1])
        l40 = np.min(c[max(0,i-40):i+1])
        rng = (h40 - l40) / l40 if l40 > 0 else 99
        pos = (c[i] - l40) / (h40 - l40) if h40 > l40 else 0
        near_high = h40 / h252 if h252 > 0 else 0

        if rng <= 0.22 and near_high >= 0.85:
            status = []
            if 0.07 <= rng <= 0.18 and pos > 0.90 and near_high >= 0.92:
                status.append("FLAT BASE ACTIVE")
            else:
                if rng > 0.18:
                    status.append(f"rng={rng*100:.0f}%>18")
                if pos < 0.90:
                    status.append(f"pos={pos*100:.0f}%<90")
                if near_high < 0.92:
                    status.append(f"hi={near_high*100:.0f}%<92")
            tags.append(f"FB[{','.join(status)}]")

        # VCP check (relaxed)
        if i > 60 and c[i-40] > 0 and c[i-20] > 0:
            r1 = (np.max(c[i-60:i-30]) - np.min(c[i-60:i-30])) / c[i-40]
            r2 = (np.max(c[i-30:i-10]) - np.min(c[i-30:i-10])) / c[i-20]
            r3 = (np.max(c[i-10:i+1]) - np.min(c[i-10:i+1])) / c[i]
            if r1 > 0.05 and r2 < r1:  # at least some contraction
                tags.append(f"VCP[{r1*100:.0f}->{r2*100:.0f}->{r3*100:.0f}]")

        # Near breakout
        if c[i] > ma50:
            prev_high = np.max(c[i-21:i])
            pct_away = (prev_high - c[i]) / c[i]
            if 0 < pct_away <= 0.05:
                tags.append(f"NearBO[{pct_away*100:.1f}%away]")

        # Momentum
        perf_3m = (c[i] / c[i-63] - 1) if i >= 63 else 0

        if tags or pct_from_high < 0.05:
            above = ""
            if c[i] > ma50 and c[i] > ma200:
                above = ">both"
            elif c[i] > ma50:
                above = ">50"
            elif c[i] > ma200:
                above = ">200"
            else:
                above = "<both"
            print(f"{t:<7} ${c[i]:>8.2f} | {pct_from_high*100:>5.1f}% from hi | {above:<6} | 3M:{perf_3m*100:+.0f}% | {' '.join(tags)}")
    except:
        pass
