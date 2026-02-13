#!/usr/bin/env python3
"""
200-Week Moving Average Backtest
Strategy: Buy high-quality stocks when they touch the 200-week MA
Hypothesis: "If all you ever did was buy high-quality stocks on the 200-week MA, 
            you would beat the S&P 500 by a large margin over time."
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

# === RATE LIMITING & CACHING ===
CACHE_DIR = '/Users/rara/clawd/trading/cache'
RATE_LIMIT_DELAY = 0.5  # seconds between API calls
_last_request_time = 0

os.makedirs(CACHE_DIR, exist_ok=True)

def rate_limit():
    """Enforce rate limiting between API calls."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.time()

def get_cache_path(ticker, interval='1wk'):
    """Get cache file path for a ticker."""
    return os.path.join(CACHE_DIR, f"{ticker}_{interval}.pkl")

def load_from_cache(ticker, interval='1wk', max_age_hours=24):
    """Load data from cache if fresh enough."""
    cache_path = get_cache_path(ticker, interval)
    if os.path.exists(cache_path):
        mtime = os.path.getmtime(cache_path)
        age_hours = (time.time() - mtime) / 3600
        if age_hours < max_age_hours:
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except:
                pass
    return None

def save_to_cache(ticker, data, interval='1wk'):
    """Save data to cache."""
    cache_path = get_cache_path(ticker, interval)
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
    except:
        pass

# Import S&P 500 universe
from sp500_top200 import SP500_TOP200, SP500_TOP100, SP500_TOP50

# Default universe - can be overridden via command line
QUALITY_UNIVERSE = SP500_TOP200  # Use top 200 S&P 500 stocks

def get_weekly_data(ticker, years=15, use_cache=True):
    """Get weekly price data for a ticker with caching."""
    # Try cache first
    if use_cache:
        cached = load_from_cache(ticker, '1wk')
        if cached is not None:
            df = cached
            if len(df) >= 200:
                df['MA200'] = df['Close'].rolling(window=200).mean()
                df = df.dropna()
                return df
    
    # Rate limit before API call
    rate_limit()
    
    try:
        end = datetime.now()
        start = end - timedelta(days=years*365)
        df = yf.download(ticker, start=start, end=end, interval='1wk', progress=False)
        if len(df) < 200:
            return None
        
        # Flatten multi-index if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Cache the raw data
        if use_cache:
            save_to_cache(ticker, df, '1wk')
        
        df['MA200'] = df['Close'].rolling(window=200).mean()
        df = df.dropna()
        return df
    except Exception as e:
        return None


def find_200wma_touches(df, tolerance=0.02):
    """
    Find instances where price touches or dips below 200-week MA.
    tolerance: how close to MA counts as a "touch" (2% = within 2% of MA)
    """
    signals = []
    
    for i in range(1, len(df)):
        current_close = df['Close'].iloc[i]
        current_ma = df['MA200'].iloc[i]
        prev_close = df['Close'].iloc[i-1]
        prev_ma = df['MA200'].iloc[i-1]
        
        # Check if price touched or crossed below MA
        pct_from_ma = (current_close - current_ma) / current_ma
        
        # Signal: price within tolerance of MA or below it
        if pct_from_ma <= tolerance:
            # Make sure it was above MA recently (not in a death spiral)
            lookback = min(10, i)
            recent_prices = df['Close'].iloc[i-lookback:i]
            recent_mas = df['MA200'].iloc[i-lookback:i]
            
            # At least half the recent period was above MA
            above_ma_count = sum(recent_prices > recent_mas)
            if above_ma_count >= lookback * 0.3:
                signals.append({
                    'date': df.index[i],
                    'price': current_close,
                    'ma200': current_ma,
                    'pct_from_ma': pct_from_ma * 100
                })
    
    return signals


def backtest_200wma_strategy(ticker, hold_weeks=26, tolerance=0.02):
    """
    Backtest the 200-week MA strategy for a single stock.
    
    Entry: Buy when price touches 200-week MA (within tolerance)
    Exit: Sell after hold_weeks OR if price drops 15% below MA (stop loss)
    """
    df = get_weekly_data(ticker)
    if df is None or len(df) < 250:
        return None
    
    signals = find_200wma_touches(df, tolerance)
    if not signals:
        return None
    
    trades = []
    
    for signal in signals:
        entry_date = signal['date']
        entry_price = signal['price']
        
        # Find the entry index
        try:
            entry_idx = df.index.get_loc(entry_date)
        except:
            continue
        
        # Calculate exit
        exit_idx = min(entry_idx + hold_weeks, len(df) - 1)
        
        # Check for stop loss during holding period (15% below MA)
        stopped_out = False
        for j in range(entry_idx + 1, exit_idx + 1):
            if j >= len(df):
                break
            price = df['Close'].iloc[j]
            ma = df['MA200'].iloc[j]
            if price < ma * 0.85:  # 15% below MA = stop out
                exit_idx = j
                stopped_out = True
                break
        
        if exit_idx >= len(df):
            continue
            
        exit_date = df.index[exit_idx]
        exit_price = df['Close'].iloc[exit_idx]
        
        pct_return = (exit_price - entry_price) / entry_price * 100
        
        trades.append({
            'ticker': ticker,
            'entry_date': entry_date,
            'entry_price': entry_price,
            'exit_date': exit_date,
            'exit_price': exit_price,
            'hold_weeks': (exit_date - entry_date).days // 7,
            'return_pct': pct_return,
            'stopped_out': stopped_out
        })
    
    return trades


# Global SPY cache for fast lookups
_spy_data = None

def load_spy_data(years=15):
    """Pre-load SPY data once for all comparisons."""
    global _spy_data
    if _spy_data is not None:
        return _spy_data
    
    # Try cache first
    cached = load_from_cache('SPY', '1d_full')
    if cached is not None:
        _spy_data = cached
        return _spy_data
    
    print("  Pre-loading SPY data (one-time)...")
    rate_limit()
    
    try:
        end = datetime.now()
        start = end - timedelta(days=years*365)
        spy = yf.download('SPY', start=start, end=end, interval='1d', progress=False)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)
        
        save_to_cache('SPY', spy, '1d_full')
        _spy_data = spy
        return _spy_data
    except:
        return None

def get_spy_returns(start_date, end_date):
    """Get SPY return for the same period using pre-loaded data."""
    spy = load_spy_data()
    if spy is None or len(spy) < 2:
        return 0
    
    try:
        # Convert to datetime if needed
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        # Find closest dates in SPY data
        mask = (spy.index >= start_date) & (spy.index <= end_date)
        period_data = spy.loc[mask]
        
        if len(period_data) < 2:
            # Try expanding the window slightly
            mask = (spy.index >= start_date - timedelta(days=7)) & (spy.index <= end_date + timedelta(days=7))
            period_data = spy.loc[mask]
        
        if len(period_data) < 2:
            return 0
        
        return (period_data['Close'].iloc[-1] - period_data['Close'].iloc[0]) / period_data['Close'].iloc[0] * 100
    except:
        return 0


def run_full_backtest(hold_weeks=26, tolerance=0.02):
    """Run backtest across all quality stocks."""
    print(f"\n{'='*70}")
    print(f"  200-WEEK MA BACKTEST")
    print(f"  Strategy: Buy quality stocks at 200-week MA, hold {hold_weeks} weeks")
    print(f"  Tolerance: {tolerance*100}% from MA | Stop: 15% below MA")
    print(f"  Cache: {CACHE_DIR}")
    print(f"{'='*70}\n")
    
    # Pre-load SPY data once (instead of per-trade)
    load_spy_data()
    
    all_trades = []
    
    print(f"Testing {len(QUALITY_UNIVERSE)} stocks...")
    for i, ticker in enumerate(QUALITY_UNIVERSE):
        print(f"  [{i+1}/{len(QUALITY_UNIVERSE)}] {ticker}...", end=' ')
        trades = backtest_200wma_strategy(ticker, hold_weeks, tolerance)
        if trades:
            all_trades.extend(trades)
            print(f"{len(trades)} trades")
        else:
            print("no signals")
    
    if not all_trades:
        print("\nNo trades found!")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(all_trades)
    df['entry_date'] = pd.to_datetime(df['entry_date'])
    df['exit_date'] = pd.to_datetime(df['exit_date'])
    
    # Calculate SPY comparison for each trade
    print("\nCalculating SPY comparison...")
    spy_returns = []
    for _, row in df.iterrows():
        spy_ret = get_spy_returns(row['entry_date'], row['exit_date'])
        spy_returns.append(spy_ret)
    df['spy_return_pct'] = spy_returns
    df['alpha'] = df['return_pct'] - df['spy_return_pct']
    
    # Results
    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}\n")
    
    print(f"Total Trades: {len(df)}")
    print(f"Date Range: {df['entry_date'].min().strftime('%Y-%m-%d')} to {df['exit_date'].max().strftime('%Y-%m-%d')}")
    print(f"Unique Stocks: {df['ticker'].nunique()}")
    
    print(f"\n--- STRATEGY PERFORMANCE ---")
    print(f"Win Rate: {(df['return_pct'] > 0).mean()*100:.1f}%")
    print(f"Average Return: {df['return_pct'].mean():.2f}%")
    print(f"Median Return: {df['return_pct'].median():.2f}%")
    print(f"Best Trade: {df['return_pct'].max():.2f}%")
    print(f"Worst Trade: {df['return_pct'].min():.2f}%")
    print(f"Std Dev: {df['return_pct'].std():.2f}%")
    
    print(f"\n--- VS S&P 500 (SPY) ---")
    print(f"SPY Avg Return (same periods): {df['spy_return_pct'].mean():.2f}%")
    print(f"Strategy Alpha: {df['alpha'].mean():.2f}%")
    print(f"Beat SPY Rate: {(df['return_pct'] > df['spy_return_pct']).mean()*100:.1f}%")
    
    print(f"\n--- RISK METRICS ---")
    print(f"Stopped Out: {df['stopped_out'].sum()} trades ({df['stopped_out'].mean()*100:.1f}%)")
    print(f"Avg Hold Time: {df['hold_weeks'].mean():.1f} weeks")
    
    # By ticker breakdown
    print(f"\n--- TOP PERFORMERS (by avg return) ---")
    by_ticker = df.groupby('ticker').agg({
        'return_pct': ['mean', 'count'],
        'alpha': 'mean'
    }).round(2)
    by_ticker.columns = ['avg_return', 'trades', 'avg_alpha']
    by_ticker = by_ticker.sort_values('avg_return', ascending=False)
    print(by_ticker.head(10).to_string())
    
    print(f"\n--- WORST PERFORMERS ---")
    print(by_ticker.tail(5).to_string())
    
    # Yearly breakdown
    print(f"\n--- BY YEAR ---")
    df['year'] = df['entry_date'].dt.year
    by_year = df.groupby('year').agg({
        'return_pct': ['mean', 'count'],
        'spy_return_pct': 'mean',
        'alpha': 'mean'
    }).round(2)
    by_year.columns = ['strategy_return', 'trades', 'spy_return', 'alpha']
    print(by_year.to_string())
    
    # Simulate compounded returns
    print(f"\n--- COMPOUNDED SIMULATION ---")
    print("(If you invested $10,000 in each trade)")
    
    # Sort by date
    df_sorted = df.sort_values('entry_date')
    
    # Simple: average all returns
    total_trades = len(df_sorted)
    avg_return = df_sorted['return_pct'].mean()
    avg_spy = df_sorted['spy_return_pct'].mean()
    
    # Annualized (assuming ~2 trades per stock per year on average)
    avg_hold_years = df_sorted['hold_weeks'].mean() / 52
    trades_per_year = 1 / avg_hold_years if avg_hold_years > 0 else 2
    
    strategy_annual = avg_return * min(trades_per_year, 4)  # Cap at 4 trades/year
    spy_annual = avg_spy * min(trades_per_year, 4)
    
    print(f"Avg Return per Trade: {avg_return:.2f}% (Strategy) vs {avg_spy:.2f}% (SPY)")
    print(f"Estimated Annual Return: {strategy_annual:.2f}% (Strategy) vs {spy_annual:.2f}% (SPY)")
    print(f"Annual Alpha: {strategy_annual - spy_annual:.2f}%")
    
    # Save results
    results_file = '/Users/rara/clawd/trading/backtest_200wma_results.csv'
    df.to_csv(results_file, index=False)
    print(f"\nDetailed results saved to: {results_file}")
    
    return df


def test_different_parameters():
    """Test different holding periods and tolerances."""
    print("\n" + "="*70)
    print("  PARAMETER SENSITIVITY ANALYSIS")
    print("="*70 + "\n")
    
    results = []
    
    for hold_weeks in [13, 26, 52]:  # 3mo, 6mo, 1yr
        for tolerance in [0.01, 0.02, 0.03, 0.05]:  # 1%, 2%, 3%, 5%
            print(f"\nTesting: {hold_weeks} weeks hold, {tolerance*100}% tolerance...")
            
            all_trades = []
            for ticker in QUALITY_UNIVERSE[:15]:  # Subset for speed
                trades = backtest_200wma_strategy(ticker, hold_weeks, tolerance)
                if trades:
                    all_trades.extend(trades)
            
            if all_trades:
                df = pd.DataFrame(all_trades)
                results.append({
                    'hold_weeks': hold_weeks,
                    'tolerance': tolerance * 100,
                    'trades': len(df),
                    'win_rate': (df['return_pct'] > 0).mean() * 100,
                    'avg_return': df['return_pct'].mean(),
                    'median_return': df['return_pct'].median()
                })
    
    if results:
        results_df = pd.DataFrame(results)
        print("\n" + "="*70)
        print("  PARAMETER COMPARISON")
        print("="*70)
        print(results_df.to_string(index=False))
        
        best = results_df.loc[results_df['avg_return'].idxmax()]
        print(f"\n🏆 BEST PARAMETERS:")
        print(f"   Hold: {best['hold_weeks']} weeks")
        print(f"   Tolerance: {best['tolerance']}%")
        print(f"   Avg Return: {best['avg_return']:.2f}%")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--optimize':
        test_different_parameters()
    else:
        # Default: 26-week hold, 2% tolerance
        df = run_full_backtest(hold_weeks=26, tolerance=0.02)
