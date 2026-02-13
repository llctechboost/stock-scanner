#!/usr/bin/env python3
"""
Master Backtest: All 5 optimization tests
1. Stop loss / profit target grid
2. Market regime filter (SPY above MA)
3. Volume confirmation levels
4. Hold period optimization
5. Pattern combo analysis

Detects patterns once, then runs all simulations on cached signals.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import json, sys

UNIVERSE = [
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO', 'CRM',
    'PLTR', 'NET', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'MDB', 'PANW', 'NOW', 'SHOP',
    'SMCI', 'ARM', 'APP', 'HIMS', 'DUOL', 'CELH', 'TOST', 'CAVA',
    'GS', 'JPM', 'V', 'MA', 'AXP', 'COIN', 'HOOD', 'SOFI', 'NU',
    'LLY', 'NVO', 'UNH', 'ISRG', 'DXCM', 'PODD', 'VRTX',
    'UBER', 'ABNB', 'DASH', 'RKLB', 'AXON', 'DECK', 'GWW', 'URI',
    'ASML', 'LRCX', 'KLAC', 'AMAT', 'MRVL', 'QCOM',
    'COST', 'TJX', 'LULU', 'NKE', 'HD', 'LOW'
]


def detect_patterns(df):
    """Vectorized pattern detection. Returns list of (index, pattern_names, volume_ratio)."""
    close = df['Close'].values
    volume = df['Volume'].values
    high = df['High'].values if 'High' in df.columns else close
    low = df['Low'].values if 'Low' in df.columns else close
    opn = df['Open'].values if 'Open' in df.columns else close
    n = len(close)

    ma50_s = pd.Series(close).rolling(50).mean().values
    vol_50 = pd.Series(volume).rolling(50).mean().values

    signals = []

    for i in range(252, n):
        pats = []
        vol_ratio = volume[i] / vol_50[i] if vol_50[i] > 0 else 1.0

        # Pocket Pivot
        if close[i] > opn[i] and i > 11:
            max_dv = 0
            for k in range(i-10, i):
                if close[k] < opn[k]:
                    max_dv = max(max_dv, volume[k])
            if max_dv > 0 and volume[i] > max_dv:
                ma10 = np.mean(close[i-9:i+1])
                if close[i] > ma10:
                    pats.append('Pocket Pivot')

        # Flat Base
        h40 = np.max(close[max(0,i-40):i+1])
        l40 = np.min(close[max(0,i-40):i+1])
        if l40 > 0:
            rng = (h40 - l40) / l40
            if 0.07 <= rng <= 0.18:
                if h40 > 0 and (close[i] - l40) / (h40 - l40) > 0.90:
                    h252 = np.max(close[max(0,i-252):i+1])
                    if h40 >= h252 * 0.92:
                        pats.append('Flat Base')

        # VCP
        if i > 60 and close[i-40] > 0 and close[i-20] > 0:
            r1 = (np.max(close[i-60:i-30]) - np.min(close[i-60:i-30])) / close[i-40]
            r2 = (np.max(close[i-30:i-10]) - np.min(close[i-30:i-10])) / close[i-20]
            r3 = (np.max(close[i-10:i+1]) - np.min(close[i-10:i+1])) / close[i]
            if r1 > 0.05 and r2 < r1 * 0.8 and r3 < r2 * 0.8:
                v1 = np.mean(volume[i-30:i-10])
                v2 = np.mean(volume[i-10:i+1])
                if v2 < v1:
                    pats.append('VCP')

        # Breakout
        if i > 50 and not np.isnan(ma50_s[i]):
            prev_high = np.max(close[i-21:i])
            if close[i] > prev_high and vol_ratio > 1.5 and close[i] > ma50_s[i]:
                pats.append('Breakout')

        # Cup w/ Handle
        if i > 80:
            left_high = np.max(close[i-80:i-50])
            cup_low = np.min(close[i-50:i-15])
            right_side = np.max(close[i-15:i-5])
            if left_high > 0:
                depth = (left_high - cup_low) / left_high
                recovery = right_side / left_high
                if 0.12 <= depth <= 0.35 and recovery >= 0.90:
                    handle_high = np.max(close[i-15:i-3])
                    handle_low = np.min(close[i-10:i+1])
                    if handle_high > 0:
                        hd = (handle_high - handle_low) / handle_high
                        if 0.03 <= hd <= 0.15:
                            hv = np.mean(volume[i-10:i+1])
                            bv = np.mean(volume[i-50:i-10])
                            if hv < bv:
                                pats.append('Cup w/ Handle')

        if pats:
            signals.append({
                'idx': i,
                'date': df.index[i],
                'patterns': pats,
                'pattern_str': ','.join(pats),
                'num_patterns': len(pats),
                'entry_price': close[i],
                'vol_ratio': vol_ratio
            })

    return signals


def simulate_trade(close, high, low, entry_idx, entry_price, stop_loss, profit_target, max_hold):
    """Simulate a single trade. Returns (return_pct, exit_reason, hold_days)."""
    n = len(close)
    for j in range(1, min(max_hold + 1, n - entry_idx)):
        loss = (low[entry_idx + j] - entry_price) / entry_price
        if loss <= -stop_loss:
            return -stop_loss, 'stop', j
        gain = (high[entry_idx + j] - entry_price) / entry_price
        if gain >= profit_target:
            return profit_target, 'target', j
    # Time exit
    end_idx = min(entry_idx + max_hold, n - 1)
    ret = (close[end_idx] - entry_price) / entry_price
    return ret, 'time', min(max_hold, n - entry_idx - 1)


def simulate_trailing(close, high, low, entry_idx, entry_price, stop_loss, trail_pct, max_hold):
    """Simulate trade with trailing stop."""
    n = len(close)
    highest = entry_price
    for j in range(1, min(max_hold + 1, n - entry_idx)):
        highest = max(highest, high[entry_idx + j])
        # Initial hard stop
        loss = (low[entry_idx + j] - entry_price) / entry_price
        if loss <= -stop_loss:
            return -stop_loss, 'stop', j
        # Trailing stop from highest point
        trail_loss = (low[entry_idx + j] - highest) / highest
        if trail_loss <= -trail_pct and highest > entry_price:
            ret = (low[entry_idx + j] - entry_price) / entry_price
            return max(ret, -stop_loss), 'trail', j
    end_idx = min(entry_idx + max_hold, n - 1)
    ret = (close[end_idx] - entry_price) / entry_price
    return ret, 'time', min(max_hold, n - entry_idx - 1)


def calc_stats(returns):
    """Calculate stats from list of return percentages."""
    if not returns:
        return None
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gw = sum(wins) if wins else 0
    gl = abs(sum(losses)) if losses else 0.001
    return {
        'trades': len(returns),
        'win_rate': round(len(wins) / len(returns) * 100, 1),
        'avg_return': round(np.mean(returns) * 100, 2),
        'total_return': round(np.sum(returns) * 100, 1),
        'avg_win': round(np.mean(wins) * 100, 2) if wins else 0,
        'avg_loss': round(np.mean(losses) * 100, 2) if losses else 0,
        'profit_factor': round(gw / gl, 2),
        'max_consec_loss': max_consecutive(returns, False),
        'max_consec_win': max_consecutive(returns, True),
    }


def max_consecutive(returns, is_win):
    """Count max consecutive wins or losses."""
    max_c = 0
    curr = 0
    for r in returns:
        if (is_win and r > 0) or (not is_win and r <= 0):
            curr += 1
            max_c = max(max_c, curr)
        else:
            curr = 0
    return max_c


def print_table(title, rows, headers):
    """Print formatted results table."""
    print(f"\n{'='*90}")
    print(f"  {title}")
    print(f"{'='*90}")
    # Header
    h_str = ' | '.join(f"{h:>{w}}" for h, w in headers)
    print(f"  {h_str}")
    print(f"  {'-' * (sum(w for _, w in headers) + 3 * (len(headers)-1))}")
    for row in rows:
        r_str = ' | '.join(f"{v:>{w}}" for v, (_, w) in zip(row, headers))
        print(f"  {r_str}")


def run():
    print(f"\n{'#'*70}")
    print(f"#  MASTER BACKTEST — 5 Optimization Tests")
    print(f"#  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'#'*70}\n")

    start_date = '2021-01-01'
    end_date = '2026-01-31'
    scan_start = pd.Timestamp(start_date)

    # ── DOWNLOAD DATA ──
    print("📥 Downloading data...")
    all_data = {}
    for i, t in enumerate(UNIVERSE):
        try:
            df = yf.download(t, start='2020-01-01', end=end_date, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 252:
                all_data[t] = df
            sys.stdout.write(f"\r  {i+1}/{len(UNIVERSE)}: {t}     ")
            sys.stdout.flush()
        except:
            pass

    # Download SPY for market regime
    spy = yf.download('SPY', start='2020-01-01', end=end_date, progress=False)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    spy_close = spy['Close']
    spy_ma50 = spy_close.rolling(50).mean()
    spy_ma200 = spy_close.rolling(200).mean()

    print(f"\n  ✅ {len(all_data)} stocks + SPY loaded\n")

    # ── DETECT PATTERNS (once) ──
    print("🔍 Detecting patterns across all stocks...")
    all_signals = {}  # ticker -> list of signal dicts
    total_sigs = 0
    for ticker, df in all_data.items():
        sys.stdout.write(f"\r  {ticker}...              ")
        sys.stdout.flush()
        sigs = detect_patterns(df)
        # Filter to our backtest window and ensure room for trades
        sigs = [s for s in sigs if s['date'] >= scan_start and s['idx'] + 15 < len(df)]
        all_signals[ticker] = sigs
        total_sigs += len(sigs)
    print(f"\n  ✅ {total_sigs} pattern signals cached\n")

    results = {}

    # ════════════════════════════════════════════════════════
    # TEST 1: Stop Loss / Profit Target Grid
    # ════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("📊 TEST 1: Stop Loss / Profit Target Optimization")
    print("="*70)

    stops = [0.05, 0.08, 0.10, 0.12, 0.15]
    targets = [0.15, 0.20, 0.25, 0.30, 0.40]
    max_hold = 60

    t1_rows = []
    t1_best = (None, 0)

    for sl in stops:
        for pt in targets:
            rets = []
            for ticker, sigs in all_signals.items():
                df = all_data[ticker]
                c, h, l = df['Close'].values, df['High'].values, df['Low'].values
                for s in sigs:
                    r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], sl, pt, max_hold)
                    rets.append(r)
            st = calc_stats(rets)
            if st:
                label = f"{sl*100:.0f}%/{pt*100:.0f}%"
                t1_rows.append([label, str(st['trades']), f"{st['win_rate']}%",
                               f"{st['avg_return']}%", f"{st['profit_factor']}x",
                               f"{st['avg_win']}%", f"{st['avg_loss']}%"])
                if st['profit_factor'] > t1_best[1]:
                    t1_best = (label, st['profit_factor'], st)

    headers = [('Stop/Target', 12), ('Trades', 7), ('Win%', 7), ('Avg Ret', 8),
               ('PF', 7), ('Avg Win', 8), ('Avg Loss', 9)]
    print_table("Stop Loss / Profit Target Grid", t1_rows, headers)

    if t1_best[0]:
        print(f"\n  🏆 BEST: {t1_best[0]} → {t1_best[2]['win_rate']}% win, {t1_best[2]['avg_return']}% avg, {t1_best[2]['profit_factor']}x PF")
    results['test1_stop_target'] = {'best': t1_best[0], 'stats': t1_best[2] if t1_best[0] else None}

    # ════════════════════════════════════════════════════════
    # TEST 2: Market Regime Filter
    # ════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("📊 TEST 2: Market Regime Filter (SPY MA)")
    print("="*70)

    sl, pt, mh = 0.08, 0.20, 60
    regimes = {
        'No filter': lambda d: True,
        'SPY > 50MA': lambda d: spy_close.asof(d) > spy_ma50.asof(d) if d in spy_close.index or True else True,
        'SPY > 200MA': lambda d: spy_close.asof(d) > spy_ma200.asof(d) if d in spy_close.index or True else True,
        'SPY > Both': lambda d: (spy_close.asof(d) > spy_ma50.asof(d)) and (spy_close.asof(d) > spy_ma200.asof(d)),
        'SPY < 50MA': lambda d: spy_close.asof(d) < spy_ma50.asof(d),
    }

    t2_rows = []
    for name, filt in regimes.items():
        rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                try:
                    if not filt(s['date']):
                        continue
                except:
                    continue
                r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], sl, pt, mh)
                rets.append(r)
        st = calc_stats(rets)
        if st:
            t2_rows.append([name, str(st['trades']), f"{st['win_rate']}%",
                           f"{st['avg_return']}%", f"{st['profit_factor']}x",
                           f"{st['avg_win']}%", f"{st['avg_loss']}%"])

    headers = [('Regime', 14), ('Trades', 7), ('Win%', 7), ('Avg Ret', 8),
               ('PF', 7), ('Avg Win', 8), ('Avg Loss', 9)]
    print_table("Market Regime (SPY)", t2_rows, headers)
    results['test2_regime'] = t2_rows

    # ════════════════════════════════════════════════════════
    # TEST 3: Volume Confirmation
    # ════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("📊 TEST 3: Entry Volume Threshold")
    print("="*70)

    vol_thresholds = [1.0, 1.3, 1.5, 2.0, 2.5, 3.0]
    t3_rows = []

    for vt in vol_thresholds:
        rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                if s['vol_ratio'] < vt:
                    continue
                r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], sl, pt, mh)
                rets.append(r)
        st = calc_stats(rets)
        if st:
            t3_rows.append([f"≥{vt}x avg", str(st['trades']), f"{st['win_rate']}%",
                           f"{st['avg_return']}%", f"{st['profit_factor']}x",
                           f"{st['avg_win']}%", f"{st['avg_loss']}%"])

    headers = [('Vol Thresh', 12), ('Trades', 7), ('Win%', 7), ('Avg Ret', 8),
               ('PF', 7), ('Avg Win', 8), ('Avg Loss', 9)]
    print_table("Volume at Entry", t3_rows, headers)
    results['test3_volume'] = t3_rows

    # ════════════════════════════════════════════════════════
    # TEST 4: Hold Period + Trailing Stop
    # ════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("📊 TEST 4: Hold Period & Trailing Stop")
    print("="*70)

    # Fixed target
    hold_periods = [15, 30, 45, 60, 90]
    t4a_rows = []
    for mh in hold_periods:
        rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                if s['idx'] + mh >= len(df):
                    continue
                r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], sl, pt, mh)
                rets.append(r)
        st = calc_stats(rets)
        if st:
            t4a_rows.append([f"{mh} days", str(st['trades']), f"{st['win_rate']}%",
                            f"{st['avg_return']}%", f"{st['profit_factor']}x",
                            f"{st['avg_win']}%", f"{st['avg_loss']}%"])

    headers = [('Max Hold', 10), ('Trades', 7), ('Win%', 7), ('Avg Ret', 8),
               ('PF', 7), ('Avg Win', 8), ('Avg Loss', 9)]
    print_table("Hold Period (fixed 8%/20% stop/target)", t4a_rows, headers)

    # Trailing stop variations
    trail_pcts = [0.05, 0.08, 0.10, 0.12, 0.15]
    t4b_rows = []
    mh = 60
    for tp in trail_pcts:
        rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                if s['idx'] + mh >= len(df):
                    continue
                r, _, _ = simulate_trailing(c, h, l, s['idx'], s['entry_price'], sl, tp, mh)
                rets.append(r)
        st = calc_stats(rets)
        if st:
            t4b_rows.append([f"{tp*100:.0f}% trail", str(st['trades']), f"{st['win_rate']}%",
                            f"{st['avg_return']}%", f"{st['profit_factor']}x",
                            f"{st['avg_win']}%", f"{st['avg_loss']}%"])

    headers = [('Trail Stop', 10), ('Trades', 7), ('Win%', 7), ('Avg Ret', 8),
               ('PF', 7), ('Avg Win', 8), ('Avg Loss', 9)]
    print_table("Trailing Stop (8% hard stop, 60d max, no fixed target)", t4b_rows, headers)
    results['test4_hold'] = {'fixed': t4a_rows, 'trailing': t4b_rows}

    # ════════════════════════════════════════════════════════
    # TEST 5: Pattern Combos (single vs multi)
    # ════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("📊 TEST 5: Pattern Combinations")
    print("="*70)

    sl, pt, mh = 0.08, 0.20, 60
    t5_rows = []

    # By number of simultaneous patterns
    for n_pats in [1, 2, 3]:
        label = f"Exactly {n_pats}" if n_pats < 3 else f"{n_pats}+ patterns"
        rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                if n_pats < 3 and s['num_patterns'] != n_pats:
                    continue
                if n_pats >= 3 and s['num_patterns'] < n_pats:
                    continue
                r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], sl, pt, mh)
                rets.append(r)
        st = calc_stats(rets)
        if st:
            t5_rows.append([label, str(st['trades']), f"{st['win_rate']}%",
                           f"{st['avg_return']}%", f"{st['profit_factor']}x",
                           f"{st['avg_win']}%", f"{st['avg_loss']}%"])

    # By specific pattern
    pat_names = ['Pocket Pivot', 'Flat Base', 'VCP', 'Breakout', 'Cup w/ Handle']
    for pn in pat_names:
        rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                if pn not in s['patterns']:
                    continue
                r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], sl, pt, mh)
                rets.append(r)
        st = calc_stats(rets)
        if st:
            t5_rows.append([pn, str(st['trades']), f"{st['win_rate']}%",
                           f"{st['avg_return']}%", f"{st['profit_factor']}x",
                           f"{st['avg_win']}%", f"{st['avg_loss']}%"])

    # Specific combos
    combos = [
        ('Breakout+VCP', ['Breakout', 'VCP']),
        ('Breakout+Cup', ['Breakout', 'Cup w/ Handle']),
        ('VCP+Flat', ['VCP', 'Flat Base']),
        ('PP+Breakout', ['Pocket Pivot', 'Breakout']),
    ]
    for name, required in combos:
        rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                if all(p in s['patterns'] for p in required):
                    r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], sl, pt, mh)
                    rets.append(r)
        st = calc_stats(rets)
        if st and st['trades'] >= 10:
            t5_rows.append([name, str(st['trades']), f"{st['win_rate']}%",
                           f"{st['avg_return']}%", f"{st['profit_factor']}x",
                           f"{st['avg_win']}%", f"{st['avg_loss']}%"])

    headers = [('Pattern', 16), ('Trades', 7), ('Win%', 7), ('Avg Ret', 8),
               ('PF', 7), ('Avg Win', 8), ('Avg Loss', 9)]
    print_table("Pattern Combinations", t5_rows, headers)
    results['test5_patterns'] = t5_rows

    # ════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ════════════════════════════════════════════════════════
    print(f"\n\n{'#'*70}")
    print(f"#  SUMMARY — Best Settings Found")
    print(f"{'#'*70}")

    # Find overall best combo by running best settings together
    # Use insights from above (will print best from each)
    print(f"\n  Test 1 (Stop/Target): Best → {t1_best[0]} ({t1_best[2]['profit_factor']}x PF)" if t1_best[0] else "")
    print(f"  Test 2 (Regime): See table above")
    print(f"  Test 3 (Volume): See table above")
    print(f"  Test 4 (Hold): See tables above")
    print(f"  Test 5 (Patterns): See table above")

    # Save all results
    with open('backtest_master_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': {k: str(v) for k, v in results.items()},
            'total_signals': total_sigs
        }, f, indent=2, default=str)
    print(f"\n  💾 Saved to backtest_master_results.json")
    print(f"\n{'#'*70}\n")


if __name__ == '__main__':
    run()
