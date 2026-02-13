#!/usr/bin/env python3
"""
Backtest: Score Filter Comparison
Compares trading results for different money scanner score thresholds:
- All signals (no filter)
- Score 60+
- Score 70+
- Score 80+
- Score 85+

Uses historical data to calculate the money scanner score at each point,
then only takes trades when the score meets the threshold.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys

# Stock universe (same as money_scanner.py)
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

def calculate_score_at_date(df, idx):
    """Calculate money scanner score for a stock at a given index position."""
    if idx < 200:
        return 0
    
    close = df['Close'].iloc[:idx+1]
    volume = df['Volume'].iloc[:idx+1]
    price = close.iloc[-1]
    score = 0
    
    # 1. RS (25 pts)
    if len(close) > 63:
        perf_3m = (close.iloc[-1] / close.iloc[-63] - 1)
    else:
        perf_3m = 0
    if len(close) > 126:
        perf_6m = (close.iloc[-1] / close.iloc[-126] - 1)
    else:
        perf_6m = 0
    rs_raw = perf_3m * 0.6 + perf_6m * 0.4
    score += min(25, max(0, rs_raw * 100))
    
    # 2. Price vs MAs (20 pts)
    ma50 = close.iloc[-50:].mean()
    ma200 = close.iloc[-200:].mean() if len(close) >= 200 else ma50
    if price > ma50: score += 10
    if price > ma200: score += 5
    if ma50 > ma200: score += 5
    
    # 3. Volume (15 pts)
    avg_vol = volume.iloc[-50:].mean()
    recent_vol = volume.iloc[-5:].mean()
    if recent_vol > avg_vol * 1.5: score += 15
    elif recent_vol > avg_vol * 1.2: score += 10
    elif recent_vol > avg_vol: score += 5
    
    # 4. Volatility contraction (15 pts)
    if len(close) > 60:
        recent_range = (close.iloc[-20:].max() - close.iloc[-20:].min()) / price
        prior_range = (close.iloc[-60:-20].max() - close.iloc[-60:-20].min()) / close.iloc[-40]
        if prior_range > 0:
            if recent_range < prior_range * 0.5: score += 15
            elif recent_range < prior_range * 0.7: score += 10
            elif recent_range < prior_range: score += 5
    
    # 5. Breakout proximity (15 pts)
    high_52w = close.iloc[-252:].max() if len(close) >= 252 else close.max()
    pct_from_high = (high_52w - price) / high_52w if high_52w > 0 else 1
    if pct_from_high < 0.05: score += 15
    elif pct_from_high < 0.10: score += 10
    elif pct_from_high < 0.20: score += 5
    
    # 6. 3M performance (10 pts)
    if perf_3m > 0.30: score += 10
    elif perf_3m > 0.15: score += 7
    elif perf_3m > 0.05: score += 4
    elif perf_3m > 0: score += 2
    
    return round(score, 1)


def detect_breakout(df, idx, lookback=20):
    """Simple breakout detection: price breaks above 20-day high on above-avg volume."""
    if idx < lookback + 50:
        return False
    
    close = df['Close'].iloc[:idx+1]
    volume = df['Volume'].iloc[:idx+1]
    
    price = close.iloc[-1]
    prev_high = close.iloc[-(lookback+1):-1].max()
    avg_vol = volume.iloc[-50:].mean()
    today_vol = volume.iloc[-1]
    
    return price > prev_high and today_vol > avg_vol * 1.3


def run_backtest():
    """Run the score-filtered backtest comparison."""
    print(f"\n{'='*70}")
    print(f"📊 BACKTEST: Score Filter Comparison")
    print(f"   Does filtering by score 80+ improve win rate and returns?")
    print(f"{'='*70}\n")
    
    # Parameters
    start_date = '2021-01-01'
    end_date = '2026-01-31'
    stop_loss = 0.08      # 8% stop
    profit_target = 0.20  # 20% target
    max_hold_days = 60    # Max 60 day hold
    
    thresholds = [0, 60, 70, 80, 85, 90]
    
    print(f"Period: {start_date} to {end_date}")
    print(f"Stop Loss: {stop_loss*100}% | Profit Target: {profit_target*100}% | Max Hold: {max_hold_days} days")
    print(f"Universe: {len(UNIVERSE)} stocks")
    print(f"Thresholds: {thresholds}\n")
    
    # Download data
    print("Downloading historical data...")
    all_data = {}
    for i, ticker in enumerate(UNIVERSE):
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 200:
                all_data[ticker] = df
                sys.stdout.write(f"\r  Loaded {i+1}/{len(UNIVERSE)}: {ticker} ({len(df)} days)")
                sys.stdout.flush()
        except:
            pass
    print(f"\n  Loaded {len(all_data)} stocks with sufficient data\n")
    
    # For each stock, find breakout days and calculate scores
    print("Scanning for breakout signals and calculating scores...")
    all_trades = []  # (ticker, date, score, entry_price, result_pct)
    
    for ticker, df in all_data.items():
        sys.stdout.write(f"\r  Scanning: {ticker}          ")
        sys.stdout.flush()
        
        for i in range(252, len(df) - max_hold_days):
            if detect_breakout(df, i):
                score = calculate_score_at_date(df, i)
                entry_price = df['Close'].iloc[i]
                entry_date = df.index[i]
                
                # Simulate trade forward
                best_gain = 0
                exit_pct = None
                exit_reason = None
                exit_days = 0
                
                for j in range(1, min(max_hold_days + 1, len(df) - i)):
                    future_price = df['Close'].iloc[i + j]
                    change = (future_price - entry_price) / entry_price
                    
                    # Check stop loss
                    day_low = df['Low'].iloc[i + j] if 'Low' in df.columns else future_price
                    intraday_change = (day_low - entry_price) / entry_price
                    
                    if intraday_change <= -stop_loss:
                        exit_pct = -stop_loss
                        exit_reason = 'stop_loss'
                        exit_days = j
                        break
                    
                    # Check profit target
                    day_high = df['High'].iloc[i + j] if 'High' in df.columns else future_price
                    intraday_high = (day_high - entry_price) / entry_price
                    
                    if intraday_high >= profit_target:
                        exit_pct = profit_target
                        exit_reason = 'profit_target'
                        exit_days = j
                        break
                    
                    best_gain = max(best_gain, change)
                    exit_days = j
                
                if exit_pct is None:
                    # Time exit
                    final_price = df['Close'].iloc[min(i + max_hold_days, len(df) - 1)]
                    exit_pct = (final_price - entry_price) / entry_price
                    exit_reason = 'time_exit'
                
                all_trades.append({
                    'ticker': ticker,
                    'date': entry_date.strftime('%Y-%m-%d'),
                    'score': score,
                    'entry_price': entry_price,
                    'return_pct': exit_pct,
                    'exit_reason': exit_reason,
                    'hold_days': exit_days,
                    'best_gain': best_gain
                })
    
    print(f"\n\n  Found {len(all_trades)} total breakout trades\n")
    
    # Analyze by threshold
    print(f"{'='*70}")
    print(f"{'Threshold':>10} | {'Trades':>7} | {'Win Rate':>8} | {'Avg Return':>10} | {'Total Return':>12} | {'Avg Win':>8} | {'Avg Loss':>8} | {'Profit Factor':>13}")
    print(f"{'-'*10}-+-{'-'*7}-+-{'-'*8}-+-{'-'*10}-+-{'-'*12}-+-{'-'*8}-+-{'-'*8}-+-{'-'*13}")
    
    results = {}
    
    for threshold in thresholds:
        trades = [t for t in all_trades if t['score'] >= threshold]
        
        if not trades:
            print(f"{'≥'+str(threshold):>10} | {'0':>7} | {'N/A':>8} | {'N/A':>10} | {'N/A':>12} | {'N/A':>8} | {'N/A':>8} | {'N/A':>13}")
            continue
        
        returns = [t['return_pct'] for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        
        win_rate = len(wins) / len(returns) * 100
        avg_return = np.mean(returns) * 100
        total_return = np.sum(returns) * 100
        avg_win = np.mean(wins) * 100 if wins else 0
        avg_loss = np.mean(losses) * 100 if losses else 0
        gross_wins = sum(wins) if wins else 0
        gross_losses = abs(sum(losses)) if losses else 0.001
        profit_factor = gross_wins / gross_losses
        
        label = f"≥{threshold}" if threshold > 0 else "ALL"
        print(f"{label:>10} | {len(trades):>7} | {win_rate:>7.1f}% | {avg_return:>9.2f}% | {total_return:>11.1f}% | {avg_win:>7.2f}% | {avg_loss:>7.2f}% | {profit_factor:>12.2f}x")
        
        results[threshold] = {
            'trades': len(trades),
            'win_rate': win_rate,
            'avg_return': avg_return,
            'total_return': total_return,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'best_trade': max(returns) * 100,
            'worst_trade': min(returns) * 100
        }
    
    print(f"{'='*70}")
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'parameters': {
            'start_date': start_date,
            'end_date': end_date,
            'stop_loss': stop_loss,
            'profit_target': profit_target,
            'max_hold_days': max_hold_days,
            'universe_size': len(UNIVERSE),
            'stocks_loaded': len(all_data)
        },
        'results': {str(k): v for k, v in results.items()},
        'total_trades_found': len(all_trades)
    }
    
    with open('backtest_score_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nResults saved to backtest_score_results.json")
    
    # Summary insight
    if 80 in results and 0 in results:
        r80 = results[80]
        r_all = results[0]
        print(f"\n💡 KEY INSIGHT:")
        print(f"   Score 80+ filter: {r80['win_rate']:.1f}% win rate, {r80['avg_return']:.2f}% avg return, {r80['profit_factor']:.2f}x profit factor")
        print(f"   No filter:        {r_all['win_rate']:.1f}% win rate, {r_all['avg_return']:.2f}% avg return, {r_all['profit_factor']:.2f}x profit factor")
        wr_diff = r80['win_rate'] - r_all['win_rate']
        pf_diff = r80['profit_factor'] - r_all['profit_factor']
        if wr_diff > 0 and pf_diff > 0:
            print(f"   ✅ Score 80+ IMPROVES win rate by {wr_diff:.1f}pp and profit factor by {pf_diff:.2f}x")
        elif wr_diff > 0:
            print(f"   ⚠️ Score 80+ improves win rate (+{wr_diff:.1f}pp) but profit factor changed by {pf_diff:.2f}x")
        else:
            print(f"   ❌ Score 80+ doesn't improve results — win rate changed by {wr_diff:.1f}pp")

if __name__ == '__main__':
    run_backtest()
