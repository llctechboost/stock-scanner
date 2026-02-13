#!/usr/bin/env python3
"""
Pattern-Based System Backtest on S&P 500 Top 200
Compare our automated pattern system vs the 200-week MA strategy

Patterns: Cup w/ Handle, Breakout, VCP, Flat Base, Pocket Pivot
Rules: 10% stop / 20% target / 60d max hold / SPY > 200MA filter
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import pickle
import warnings
warnings.filterwarnings('ignore')

from sp500_top200 import SP500_TOP200
from data_utils import get_stock_data, rate_limit, load_from_cache, save_to_cache, CACHE_DIR

# Strategy parameters
TRAILING_STOP = 0.10   # 10% trailing stop
PROFIT_TARGET = 0.20   # 20% target
MAX_HOLD_DAYS = None   # No max hold limit


def detect_patterns(df):
    """
    Detect all 5 patterns. Returns list of signals.
    Each signal: (date, patterns[], volume_ratio)
    """
    if len(df) < 252:
        return []
    
    close = df['Close'].values
    volume = df['Volume'].values
    high = df['High'].values
    low = df['Low'].values
    opn = df['Open'].values
    n = len(close)
    
    ma50 = pd.Series(close).rolling(50).mean().values
    ma200 = pd.Series(close).rolling(200).mean().values
    vol_50 = pd.Series(volume).rolling(50).mean().values
    
    signals = []
    
    for i in range(252, n):
        pats = []
        vol_ratio = volume[i] / vol_50[i] if vol_50[i] > 0 else 1.0
        
        # Skip if below 200 MA (not in uptrend)
        if close[i] < ma200[i]:
            continue
        
        # 1. Pocket Pivot
        if close[i] > opn[i] and i > 11:
            max_down_vol = 0
            for k in range(i-10, i):
                if close[k] < opn[k]:
                    max_down_vol = max(max_down_vol, volume[k])
            if max_down_vol > 0 and volume[i] > max_down_vol:
                ma10 = np.mean(close[i-9:i+1])
                if close[i] > ma10:
                    pats.append('Pocket Pivot')
        
        # 2. Flat Base
        h40 = np.max(close[max(0,i-40):i+1])
        l40 = np.min(close[max(0,i-40):i+1])
        if l40 > 0:
            rng = (h40 - l40) / l40
            if 0.07 <= rng <= 0.18:
                position_in_range = (close[i] - l40) / (h40 - l40) if h40 > l40 else 0
                if position_in_range > 0.90:
                    h252 = np.max(close[max(0,i-252):i+1])
                    if h40 >= h252 * 0.92:
                        pats.append('Flat Base')
        
        # 3. VCP (Volatility Contraction Pattern)
        if i > 60:
            try:
                r1 = (np.max(close[i-60:i-30]) - np.min(close[i-60:i-30])) / close[i-40] if close[i-40] > 0 else 0
                r2 = (np.max(close[i-30:i-10]) - np.min(close[i-30:i-10])) / close[i-20] if close[i-20] > 0 else 0
                r3 = (np.max(close[i-10:i+1]) - np.min(close[i-10:i+1])) / close[i] if close[i] > 0 else 0
                
                if r1 > 0.05 and r2 < r1 * 0.8 and r3 < r2 * 0.8:
                    v1 = np.mean(volume[i-30:i-10])
                    v2 = np.mean(volume[i-10:i+1])
                    if v2 < v1:
                        pats.append('VCP')
            except:
                pass
        
        # 4. Breakout
        if i > 50 and not np.isnan(ma50[i]):
            prev_high = np.max(close[i-21:i])
            if close[i] > prev_high and vol_ratio > 1.5 and close[i] > ma50[i]:
                pats.append('Breakout')
        
        # 5. Cup with Handle
        if i > 80:
            try:
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
                            handle_depth = (handle_high - handle_low) / handle_high
                            if 0.03 <= handle_depth <= 0.15:
                                v_cup = np.mean(volume[i-50:i-15])
                                v_handle = np.mean(volume[i-10:i+1])
                                if v_handle < v_cup:
                                    pats.append('Cup w/ Handle')
            except:
                pass
        
        if pats:
            signals.append({
                'date': df.index[i],
                'idx': i,
                'price': close[i],
                'patterns': pats,
                'volume_ratio': vol_ratio
            })
    
    return signals


def simulate_trades(df, signals, trailing_stop_pct=TRAILING_STOP, target_pct=PROFIT_TARGET, max_days=MAX_HOLD_DAYS):
    """
    Simulate trades from signals with trailing stop.
    Returns list of completed trades.
    """
    close = df['Close'].values
    trades = []
    
    for sig in signals:
        entry_idx = sig['idx']
        entry_price = sig['price']
        entry_date = sig['date']
        
        # Initialize trailing stop from entry price
        highest_price = entry_price
        stop_price = entry_price * (1 - trailing_stop_pct)
        target_price = entry_price * (1 + target_pct)
        
        exit_idx = None
        exit_reason = None
        
        # Simulate forward (no max day limit if max_days is None)
        end_idx = len(close) if max_days is None else min(entry_idx + max_days + 1, len(close))
        
        for j in range(entry_idx + 1, end_idx):
            price = close[j]
            
            # Update trailing stop if new high
            if price > highest_price:
                highest_price = price
                stop_price = highest_price * (1 - trailing_stop_pct)
            
            # Check trailing stop
            if price <= stop_price:
                exit_idx = j
                exit_reason = 'trailing_stop'
                break
            
            # Check target
            if price >= target_price:
                exit_idx = j
                exit_reason = 'target'
                break
        
        # Max hold exit (only if max_days is set)
        if exit_idx is None and max_days is not None and entry_idx + max_days < len(close):
            exit_idx = entry_idx + max_days
            exit_reason = 'max_hold'
        
        if exit_idx is None:
            continue
        
        exit_price = close[exit_idx]
        exit_date = df.index[exit_idx]
        pct_return = (exit_price - entry_price) / entry_price * 100
        
        trades.append({
            'entry_date': entry_date,
            'entry_price': entry_price,
            'exit_date': exit_date,
            'exit_price': exit_price,
            'return_pct': pct_return,
            'patterns': sig['patterns'],
            'exit_reason': exit_reason,
            'hold_days': (exit_date - entry_date).days
        })
    
    return trades


def get_spy_regime(start_date, end_date):
    """Check if SPY was above 200 MA during the period."""
    cache_key = 'SPY_daily_full'
    spy = load_from_cache(cache_key, max_age_hours=24)
    
    if spy is None:
        rate_limit()
        spy = yf.download('SPY', period='15y', interval='1d', progress=False)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)
        save_to_cache(cache_key, spy)
    
    if spy is None or len(spy) < 200:
        return True  # Assume bull if no data
    
    spy['MA200'] = spy['Close'].rolling(200).mean()
    
    try:
        mask = (spy.index >= pd.to_datetime(start_date)) & (spy.index <= pd.to_datetime(end_date))
        period = spy.loc[mask]
        if len(period) > 0:
            return period['Close'].iloc[0] > period['MA200'].iloc[0]
    except:
        pass
    
    return True


def get_spy_return(start_date, end_date):
    """Get SPY return for comparison."""
    cache_key = 'SPY_daily_full'
    spy = load_from_cache(cache_key, max_age_hours=24)
    
    if spy is None:
        return 0
    
    try:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        mask = (spy.index >= start_date - timedelta(days=7)) & (spy.index <= end_date + timedelta(days=7))
        period = spy.loc[mask]
        if len(period) >= 2:
            return (period['Close'].iloc[-1] - period['Close'].iloc[0]) / period['Close'].iloc[0] * 100
    except:
        pass
    
    return 0


def run_backtest():
    """Run pattern backtest on S&P 500 top 200."""
    print(f"\n{'='*70}")
    print(f"  PATTERN-BASED SYSTEM BACKTEST — S&P 500 TOP 200")
    print(f"  Patterns: Cup w/ Handle, Breakout, VCP, Flat Base, Pocket Pivot")
    hold_str = "no limit" if MAX_HOLD_DAYS is None else f"{MAX_HOLD_DAYS}d max hold"
    print(f"  Rules: {int(TRAILING_STOP*100)}% trailing stop / {int(PROFIT_TARGET*100)}% target / {hold_str}")
    print(f"{'='*70}\n")
    
    # Pre-load SPY data
    print("Pre-loading SPY data...")
    get_spy_regime(datetime.now() - timedelta(days=365), datetime.now())
    
    all_trades = []
    stocks_with_signals = 0
    
    print(f"\nTesting {len(SP500_TOP200)} stocks...")
    
    for i, ticker in enumerate(SP500_TOP200):
        print(f"  [{i+1}/{len(SP500_TOP200)}] {ticker}...", end=' ', flush=True)
        
        # Get data with caching
        df = get_stock_data(ticker, period='15y', interval='1d', cache_ttl=24)
        
        if df is None or len(df) < 300:
            print("insufficient data")
            continue
        
        # Detect patterns
        signals = detect_patterns(df)
        
        if not signals:
            print("no signals")
            continue
        
        # Filter by SPY regime (only trade in bull markets)
        bull_signals = []
        for sig in signals:
            if get_spy_regime(sig['date'] - timedelta(days=7), sig['date']):
                bull_signals.append(sig)
        
        if not bull_signals:
            print(f"{len(signals)} signals (all in bear market)")
            continue
        
        # Simulate trades
        trades = simulate_trades(df, bull_signals)
        
        if trades:
            for t in trades:
                t['ticker'] = ticker
            all_trades.extend(trades)
            stocks_with_signals += 1
            print(f"{len(trades)} trades")
        else:
            print(f"{len(bull_signals)} signals, 0 complete trades")
    
    if not all_trades:
        print("\nNo trades generated!")
        return
    
    # Convert to DataFrame
    df_trades = pd.DataFrame(all_trades)
    df_trades['entry_date'] = pd.to_datetime(df_trades['entry_date'])
    df_trades['exit_date'] = pd.to_datetime(df_trades['exit_date'])
    
    # Calculate SPY comparison
    print("\nCalculating SPY comparison...")
    spy_returns = []
    for _, row in df_trades.iterrows():
        spy_ret = get_spy_return(row['entry_date'], row['exit_date'])
        spy_returns.append(spy_ret)
    df_trades['spy_return'] = spy_returns
    df_trades['alpha'] = df_trades['return_pct'] - df_trades['spy_return']
    
    # Results
    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}\n")
    
    print(f"Total Trades: {len(df_trades)}")
    print(f"Stocks with Trades: {stocks_with_signals}")
    print(f"Date Range: {df_trades['entry_date'].min().strftime('%Y-%m-%d')} to {df_trades['exit_date'].max().strftime('%Y-%m-%d')}")
    
    print(f"\n--- STRATEGY PERFORMANCE ---")
    print(f"Win Rate: {(df_trades['return_pct'] > 0).mean()*100:.1f}%")
    print(f"Average Return: {df_trades['return_pct'].mean():.2f}%")
    print(f"Median Return: {df_trades['return_pct'].median():.2f}%")
    print(f"Best Trade: {df_trades['return_pct'].max():.2f}%")
    print(f"Worst Trade: {df_trades['return_pct'].min():.2f}%")
    print(f"Std Dev: {df_trades['return_pct'].std():.2f}%")
    
    print(f"\n--- VS S&P 500 (SPY) ---")
    print(f"SPY Avg Return (same periods): {df_trades['spy_return'].mean():.2f}%")
    print(f"Strategy Alpha: {df_trades['alpha'].mean():.2f}%")
    print(f"Beat SPY Rate: {(df_trades['return_pct'] > df_trades['spy_return']).mean()*100:.1f}%")
    
    print(f"\n--- EXIT REASONS ---")
    exit_counts = df_trades['exit_reason'].value_counts()
    for reason, count in exit_counts.items():
        pct = count / len(df_trades) * 100
        avg_ret = df_trades[df_trades['exit_reason'] == reason]['return_pct'].mean()
        print(f"  {reason}: {count} ({pct:.1f}%) — avg return: {avg_ret:.2f}%")
    
    print(f"\n--- BY PATTERN ---")
    pattern_stats = []
    for _, row in df_trades.iterrows():
        for pat in row['patterns']:
            pattern_stats.append({
                'pattern': pat,
                'return': row['return_pct'],
                'alpha': row['alpha']
            })
    
    if pattern_stats:
        pat_df = pd.DataFrame(pattern_stats)
        by_pattern = pat_df.groupby('pattern').agg({
            'return': ['mean', 'count'],
            'alpha': 'mean'
        }).round(2)
        by_pattern.columns = ['avg_return', 'count', 'avg_alpha']
        by_pattern = by_pattern.sort_values('avg_return', ascending=False)
        print(by_pattern.to_string())
    
    print(f"\n--- TOP PERFORMERS (by avg return) ---")
    by_ticker = df_trades.groupby('ticker').agg({
        'return_pct': ['mean', 'count'],
        'alpha': 'mean'
    }).round(2)
    by_ticker.columns = ['avg_return', 'trades', 'avg_alpha']
    by_ticker = by_ticker.sort_values('avg_return', ascending=False)
    print(by_ticker.head(15).to_string())
    
    print(f"\n--- WORST PERFORMERS ---")
    print(by_ticker.tail(10).to_string())
    
    print(f"\n--- BY YEAR ---")
    df_trades['year'] = df_trades['entry_date'].dt.year
    by_year = df_trades.groupby('year').agg({
        'return_pct': ['mean', 'count'],
        'spy_return': 'mean',
        'alpha': 'mean'
    }).round(2)
    by_year.columns = ['strategy_return', 'trades', 'spy_return', 'alpha']
    print(by_year.to_string())
    
    # Annualized estimate
    print(f"\n--- ANNUALIZED ESTIMATES ---")
    avg_hold = df_trades['hold_days'].mean()
    trades_per_year = 252 / avg_hold if avg_hold > 0 else 4
    avg_return = df_trades['return_pct'].mean()
    avg_spy = df_trades['spy_return'].mean()
    
    # Cap at reasonable number
    trades_per_year = min(trades_per_year, 12)
    
    print(f"Avg Hold Time: {avg_hold:.1f} days")
    print(f"Est. Trades/Year: {trades_per_year:.1f}")
    print(f"Avg Return/Trade: {avg_return:.2f}%")
    print(f"Est. Annual Return: {avg_return * trades_per_year:.2f}%")
    print(f"Est. Annual Alpha: {(avg_return - avg_spy) * trades_per_year:.2f}%")
    
    # Save results
    results_file = '/Users/rara/clawd/trading/backtest_patterns_sp500_results.csv'
    df_trades.to_csv(results_file, index=False)
    print(f"\nDetailed results saved to: {results_file}")
    
    return df_trades


if __name__ == '__main__':
    run_backtest()
