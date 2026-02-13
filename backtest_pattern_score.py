#!/usr/bin/env python3
"""
Backtest: Pattern Detected + Score Filter (Optimized)
Only takes trades where a real pattern was detected.
Compares score thresholds on that filtered set.
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


# ── Fast vectorized pattern detectors ──────────────────────────────

def detect_patterns_vectorized(df):
    """
    Return a boolean Series (indexed like df) that is True on days
    where at least one pattern is detected. Also returns pattern names per date.
    Uses fast numpy/pandas ops instead of nested Python loops.
    """
    close = df['Close'].values
    volume = df['Volume'].values
    high = df['High'].values if 'High' in df.columns else close
    low = df['Low'].values if 'Low' in df.columns else close
    opn = df['Open'].values if 'Open' in df.columns else close
    n = len(close)
    
    pattern_flags = np.zeros(n, dtype=bool)
    pattern_names = [''] * n
    
    # Pre-compute rolling stats
    ma10 = pd.Series(close).rolling(10).mean().values
    ma20 = pd.Series(close).rolling(20).mean().values
    ma50 = pd.Series(close).rolling(50).mean().values
    vol_50 = pd.Series(volume).rolling(50).mean().values
    high_20 = pd.Series(close).rolling(20).max().values  # 20-day high
    high_60 = pd.Series(close).rolling(60).max().values
    low_20 = pd.Series(close).rolling(20).min().values
    low_60 = pd.Series(close).rolling(60).min().values
    
    for i in range(252, n):
        patterns_here = []
        
        # ── 1. Pocket Pivot ──
        # Up day, volume > max down-day volume in last 10 days
        if close[i] > opn[i] and i > 11:
            max_down_vol = 0
            for k in range(i-10, i):
                if close[k] < opn[k]:
                    max_down_vol = max(max_down_vol, volume[k])
            if max_down_vol > 0 and volume[i] > max_down_vol and close[i] > ma10[i]:
                patterns_here.append('Pocket Pivot')
        
        # ── 2. Flat Base ──
        # 25-60 day range of 10-15%, price near top of range, near 52wk high
        if not np.isnan(high_60[i]) and not np.isnan(low_60[i]):
            # Try ~40 day base
            h40 = np.max(close[max(0,i-40):i+1])
            l40 = np.min(close[max(0,i-40):i+1])
            if l40 > 0:
                rng = (h40 - l40) / l40
                if 0.07 <= rng <= 0.18:  # slightly relaxed
                    # Price near top
                    if h40 > 0 and (close[i] - l40) / (h40 - l40) > 0.90:
                        # Near 52wk high
                        h252 = np.max(close[max(0,i-252):i+1])
                        if h40 >= h252 * 0.92:
                            patterns_here.append('Flat Base')
        
        # ── 3. VCP (Volatility Contraction Pattern) ──
        # Progressively tighter contractions
        if i > 60:
            r1 = (np.max(close[i-60:i-30]) - np.min(close[i-60:i-30]))
            r2 = (np.max(close[i-30:i-10]) - np.min(close[i-30:i-10]))
            r3 = (np.max(close[i-10:i+1]) - np.min(close[i-10:i+1]))
            if close[i-40] > 0:
                r1p = r1 / close[i-40]
                r2p = r2 / close[i-20]
                r3p = r3 / close[i]
                if r1p > 0.05 and r2p < r1p * 0.8 and r3p < r2p * 0.8:
                    # Volume also contracting
                    v1 = np.mean(volume[i-30:i-10])
                    v2 = np.mean(volume[i-10:i+1])
                    if v2 < v1:
                        patterns_here.append('VCP')
        
        # ── 4. Breakout from base ──
        # Price breaks 20-day high on 1.5x volume, above 50ma
        if i > 50 and not np.isnan(ma50[i]):
            prev_high = np.max(close[i-21:i])
            if close[i] > prev_high and vol_50[i] > 0 and volume[i] > vol_50[i] * 1.5:
                if close[i] > ma50[i]:
                    patterns_here.append('Breakout')
        
        # ── 5. Cup with Handle (simplified fast version) ──
        # Look for U-shape: left high, dip 15-33%, recovery, small handle dip
        if i > 80:
            left_high = np.max(close[i-80:i-50])
            cup_low = np.min(close[i-50:i-15])
            right_side = np.max(close[i-15:i-5])
            if left_high > 0:
                depth = (left_high - cup_low) / left_high
                recovery = right_side / left_high
                if 0.12 <= depth <= 0.35 and recovery >= 0.90:
                    # Handle: small pullback in last 5-15 days
                    handle_high = np.max(close[i-15:i-3])
                    handle_low = np.min(close[i-10:i+1])
                    if handle_high > 0:
                        handle_depth = (handle_high - handle_low) / handle_high
                        if 0.03 <= handle_depth <= 0.15:
                            # Volume dry up in handle
                            handle_vol = np.mean(volume[i-10:i+1])
                            base_vol = np.mean(volume[i-50:i-10])
                            if handle_vol < base_vol:
                                patterns_here.append('Cup w/ Handle')

        if patterns_here:
            pattern_flags[i] = True
            pattern_names[i] = ','.join(patterns_here)
    
    return pattern_flags, pattern_names


def calculate_score(close, volume, idx):
    """Calculate money scanner score at index."""
    if idx < 200:
        return 0
    price = close[idx]
    score = 0

    perf_3m = (close[idx] / close[idx-63] - 1) if idx >= 63 else 0
    perf_6m = (close[idx] / close[idx-126] - 1) if idx >= 126 else 0
    rs_raw = perf_3m * 0.6 + perf_6m * 0.4
    score += min(25, max(0, rs_raw * 100))

    ma50 = np.mean(close[idx-49:idx+1])
    ma200 = np.mean(close[idx-199:idx+1]) if idx >= 199 else ma50
    if price > ma50: score += 10
    if price > ma200: score += 5
    if ma50 > ma200: score += 5

    avg_vol = np.mean(volume[idx-49:idx+1])
    recent_vol = np.mean(volume[idx-4:idx+1])
    if avg_vol > 0:
        if recent_vol > avg_vol * 1.5: score += 15
        elif recent_vol > avg_vol * 1.2: score += 10
        elif recent_vol > avg_vol: score += 5

    if idx > 60 and close[idx-40] > 0:
        recent_range = (np.max(close[idx-19:idx+1]) - np.min(close[idx-19:idx+1])) / price
        prior_range = (np.max(close[idx-59:idx-19]) - np.min(close[idx-59:idx-19])) / close[idx-40]
        if prior_range > 0:
            if recent_range < prior_range * 0.5: score += 15
            elif recent_range < prior_range * 0.7: score += 10
            elif recent_range < prior_range: score += 5

    h252 = np.max(close[max(0,idx-251):idx+1])
    pct_from_high = (h252 - price) / h252 if h252 > 0 else 1
    if pct_from_high < 0.05: score += 15
    elif pct_from_high < 0.10: score += 10
    elif pct_from_high < 0.20: score += 5

    if perf_3m > 0.30: score += 10
    elif perf_3m > 0.15: score += 7
    elif perf_3m > 0.05: score += 4
    elif perf_3m > 0: score += 2

    return round(score, 1)


def run_backtest():
    print(f"\n{'='*70}")
    print(f"📊 BACKTEST: Pattern + Score Filter (Optimized)")
    print(f"   Only trades where a CANSLIM pattern was detected")
    print(f"{'='*70}\n")

    start_date = '2021-01-01'
    end_date = '2026-01-31'
    stop_loss = 0.08
    profit_target = 0.20
    max_hold_days = 60
    thresholds = [0, 60, 70, 80, 85, 90]

    print(f"Period: {start_date} to {end_date}")
    print(f"Stop: {stop_loss*100}% | Target: {profit_target*100}% | Max Hold: {max_hold_days}d")
    print(f"Universe: {len(UNIVERSE)} stocks")
    print(f"Patterns: Pocket Pivot, Flat Base, VCP, Breakout, Cup w/ Handle\n")

    # Download
    print("Downloading data...")
    all_data = {}
    for i, ticker in enumerate(UNIVERSE):
        try:
            df = yf.download(ticker, start='2020-01-01', end=end_date, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 252:
                all_data[ticker] = df
            sys.stdout.write(f"\r  {i+1}/{len(UNIVERSE)}: {ticker} ({len(df)}d)   ")
            sys.stdout.flush()
        except:
            pass
    print(f"\n  ✅ {len(all_data)} stocks loaded\n")

    # Scan
    print("Scanning for patterns...")
    all_trades = []
    pattern_counts = {}
    scan_start = pd.Timestamp(start_date)

    for ticker, df in all_data.items():
        sys.stdout.write(f"\r  {ticker}...              ")
        sys.stdout.flush()

        close = df['Close'].values
        volume = df['Volume'].values
        low_arr = df['Low'].values if 'Low' in df.columns else close
        high_arr = df['High'].values if 'High' in df.columns else close

        flags, names = detect_patterns_vectorized(df)

        for i in range(len(df)):
            if not flags[i]:
                continue
            if df.index[i] < scan_start:
                continue
            if i + max_hold_days >= len(df):
                continue

            score = calculate_score(close, volume, i)
            entry_price = close[i]
            entry_date = df.index[i]
            detected = names[i]

            for pn in detected.split(','):
                pattern_counts[pn] = pattern_counts.get(pn, 0) + 1

            # Simulate trade
            exit_pct = None
            exit_reason = None
            exit_days = 0

            for j in range(1, min(max_hold_days + 1, len(df) - i)):
                loss = (low_arr[i+j] - entry_price) / entry_price
                if loss <= -stop_loss:
                    exit_pct = -stop_loss
                    exit_reason = 'stop'
                    exit_days = j
                    break
                gain = (high_arr[i+j] - entry_price) / entry_price
                if gain >= profit_target:
                    exit_pct = profit_target
                    exit_reason = 'target'
                    exit_days = j
                    break
                exit_days = j

            if exit_pct is None:
                final = close[min(i + max_hold_days, len(df) - 1)]
                exit_pct = (final - entry_price) / entry_price
                exit_reason = 'time'

            all_trades.append({
                'ticker': ticker,
                'date': entry_date.strftime('%Y-%m-%d'),
                'patterns': detected,
                'score': score,
                'return_pct': float(exit_pct),
                'exit_reason': exit_reason,
                'hold_days': exit_days
            })

    print(f"\n\n  Found {len(all_trades)} pattern trades")
    print(f"  Patterns: {pattern_counts}\n")

    if not all_trades:
        print("❌ No trades found.")
        return

    # ── Results by score threshold ──
    print(f"{'='*90}")
    print(f"{'Filter':>14} | {'Trades':>7} | {'Win%':>6} | {'Avg Ret':>8} | {'Total':>9} | {'Avg Win':>8} | {'Avg Loss':>9} | {'PF':>6}")
    print(f"{'-'*14}-+-{'-'*7}-+-{'-'*6}-+-{'-'*8}-+-{'-'*9}-+-{'-'*8}-+-{'-'*9}-+-{'-'*6}")

    results = {}
    for threshold in thresholds:
        trades = [t for t in all_trades if t['score'] >= threshold]
        if not trades:
            continue
        returns = [t['return_pct'] for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        wr = len(wins) / len(returns) * 100
        avg_r = np.mean(returns) * 100
        tot_r = np.sum(returns) * 100
        avg_w = np.mean(wins) * 100 if wins else 0
        avg_l = np.mean(losses) * 100 if losses else 0
        gw = sum(wins) if wins else 0
        gl = abs(sum(losses)) if losses else 0.001
        pf = gw / gl

        label = f"Score ≥{threshold}" if threshold > 0 else "ALL patterns"
        print(f"{label:>14} | {len(trades):>7} | {wr:>5.1f}% | {avg_r:>7.2f}% | {tot_r:>8.1f}% | {avg_w:>7.2f}% | {avg_l:>8.2f}% | {pf:>5.2f}x")
        results[threshold] = {
            'trades': len(trades), 'win_rate': round(wr,2), 'avg_return': round(avg_r,2),
            'total_return': round(tot_r,1), 'avg_win': round(avg_w,2), 'avg_loss': round(avg_l,2),
            'profit_factor': round(pf,2)
        }

    print(f"{'='*90}")

    # ── Per-pattern breakdown ──
    print(f"\n📊 Per-Pattern Breakdown:")
    print(f"{'-'*85}")
    for pn in sorted(pattern_counts.keys()):
        trades = [t for t in all_trades if pn in t['patterns']]
        returns = [t['return_pct'] for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        wr = len(wins)/len(returns)*100 if returns else 0
        avg_r = np.mean(returns)*100 if returns else 0
        gw = sum(wins) if wins else 0
        gl = abs(sum(losses)) if losses else 0.001
        pf = gw/gl
        print(f"  {pn:<20} | {len(trades):>5} trades | {wr:>5.1f}% win | {avg_r:>7.2f}% avg | {pf:>5.2f}x PF")

    # ── Per-pattern + score 80 ──
    print(f"\n📊 Per-Pattern (Score ≥ 80 only):")
    print(f"{'-'*85}")
    for pn in sorted(pattern_counts.keys()):
        trades = [t for t in all_trades if pn in t['patterns'] and t['score'] >= 80]
        if not trades:
            print(f"  {pn:<20} | {'no trades':>5}")
            continue
        returns = [t['return_pct'] for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        wr = len(wins)/len(returns)*100 if returns else 0
        avg_r = np.mean(returns)*100 if returns else 0
        gw = sum(wins) if wins else 0
        gl = abs(sum(losses)) if losses else 0.001
        pf = gw/gl
        print(f"  {pn:<20} | {len(trades):>5} trades | {wr:>5.1f}% win | {avg_r:>7.2f}% avg | {pf:>5.2f}x PF")

    # Save
    output = {
        'timestamp': datetime.now().isoformat(),
        'parameters': {
            'start_date': start_date, 'end_date': end_date,
            'stop_loss': stop_loss, 'profit_target': profit_target,
            'max_hold_days': max_hold_days,
            'universe': len(UNIVERSE), 'loaded': len(all_data)
        },
        'pattern_counts': pattern_counts,
        'results_by_score': {str(k):v for k,v in results.items()},
        'total_trades': len(all_trades),
        'trades': all_trades
    }
    with open('backtest_pattern_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n💾 Saved to backtest_pattern_results.json")

    # Key insight
    if 80 in results and 0 in results:
        r80, r0 = results[80], results[0]
        wr_d = r80['win_rate'] - r0['win_rate']
        pf_d = r80['profit_factor'] - r0['profit_factor']
        print(f"\n💡 KEY INSIGHT:")
        print(f"   Pattern only:        {r0['trades']} trades | {r0['win_rate']}% win | {r0['avg_return']}% avg | {r0['profit_factor']}x PF")
        print(f"   Pattern + Score≥80:  {r80['trades']} trades | {r80['win_rate']}% win | {r80['avg_return']}% avg | {r80['profit_factor']}x PF")
        if wr_d > 2 and pf_d > 0:
            print(f"   ✅ Combined filter is STRONG: +{wr_d:.1f}pp win rate, +{pf_d:.2f}x PF")
        elif wr_d > 0 or pf_d > 0.1:
            print(f"   ⚠️ Some improvement: {wr_d:+.1f}pp win rate, {pf_d:+.2f}x PF")
        else:
            print(f"   ❌ Score doesn't add value on top of patterns ({wr_d:+.1f}pp)")

if __name__ == '__main__':
    run_backtest()
