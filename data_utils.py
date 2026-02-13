#!/usr/bin/env python3
"""
Shared Data Utilities for Trading Scripts
- Rate limiting (1 req/sec default)
- Caching (24h default TTL)
- Batch downloading
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import pickle
import json
import warnings
warnings.filterwarnings('ignore')

# === CONFIGURATION ===
CACHE_DIR = '/Users/rara/clawd/trading/cache'
RATE_LIMIT_DELAY = 0.5  # seconds between API calls
DEFAULT_CACHE_TTL_HOURS = 24

os.makedirs(CACHE_DIR, exist_ok=True)

# === RATE LIMITING ===
_last_request_time = 0

def rate_limit(delay=RATE_LIMIT_DELAY):
    """Enforce rate limiting between API calls."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _last_request_time = time.time()


# === CACHING ===
def get_cache_path(key):
    """Get cache file path."""
    # Sanitize key for filesystem
    safe_key = "".join(c if c.isalnum() or c in '-_' else '_' for c in str(key))
    return os.path.join(CACHE_DIR, f"{safe_key}.pkl")


def load_from_cache(key, max_age_hours=DEFAULT_CACHE_TTL_HOURS):
    """Load data from cache if fresh enough."""
    cache_path = get_cache_path(key)
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


def save_to_cache(key, data):
    """Save data to cache."""
    cache_path = get_cache_path(key)
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"  Cache save error: {e}")


def clear_cache(older_than_hours=None):
    """Clear cache files, optionally only those older than X hours."""
    count = 0
    for f in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, f)
        if older_than_hours:
            age_hours = (time.time() - os.path.getmtime(path)) / 3600
            if age_hours < older_than_hours:
                continue
        os.remove(path)
        count += 1
    return count


# === DATA FETCHING ===
def get_stock_data(ticker, period='2y', interval='1d', use_cache=True, cache_ttl=24):
    """
    Get stock data with caching and rate limiting.
    
    Args:
        ticker: Stock symbol
        period: yfinance period ('1y', '2y', '5y', 'max')
        interval: yfinance interval ('1d', '1wk', '1mo')
        use_cache: Whether to use cache
        cache_ttl: Cache time-to-live in hours
    
    Returns:
        DataFrame with OHLCV data
    """
    cache_key = f"{ticker}_{period}_{interval}"
    
    # Try cache first
    if use_cache:
        cached = load_from_cache(cache_key, cache_ttl)
        if cached is not None:
            return cached
    
    # Rate limit before API call
    rate_limit()
    
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        
        if df.empty:
            return None
        
        # Flatten multi-index if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Cache the result
        if use_cache and not df.empty:
            save_to_cache(cache_key, df)
        
        return df
    
    except Exception as e:
        print(f"  Error fetching {ticker}: {e}")
        return None


def get_multiple_stocks(tickers, period='2y', interval='1d', use_cache=True, cache_ttl=24, show_progress=True):
    """
    Get data for multiple stocks efficiently.
    
    Args:
        tickers: List of stock symbols
        period/interval: yfinance params
        use_cache: Whether to use cache
        cache_ttl: Cache TTL in hours
        show_progress: Print progress
    
    Returns:
        Dict of {ticker: DataFrame}
    """
    results = {}
    total = len(tickers)
    
    for i, ticker in enumerate(tickers):
        if show_progress:
            print(f"  [{i+1}/{total}] {ticker}...", end=' ', flush=True)
        
        df = get_stock_data(ticker, period, interval, use_cache, cache_ttl)
        
        if df is not None and not df.empty:
            results[ticker] = df
            if show_progress:
                print(f"{len(df)} bars")
        else:
            if show_progress:
                print("no data")
    
    return results


def get_current_price(ticker, use_cache=True, cache_ttl=0.1):
    """Get current price with short cache (6 min default)."""
    cache_key = f"{ticker}_price"
    
    if use_cache:
        cached = load_from_cache(cache_key, cache_ttl)
        if cached is not None:
            return cached
    
    rate_limit()
    
    try:
        data = yf.Ticker(ticker).fast_info
        price = data.get('lastPrice', None)
        
        if price and use_cache:
            save_to_cache(cache_key, price)
        
        return price
    except:
        return None


def get_multiple_prices(tickers, use_cache=True):
    """Get current prices for multiple tickers."""
    prices = {}
    for ticker in tickers:
        price = get_current_price(ticker, use_cache)
        if price:
            prices[ticker] = price
    return prices


# === COMMON CALCULATIONS ===
def add_moving_averages(df, windows=[50, 200]):
    """Add moving averages to a DataFrame."""
    for w in windows:
        df[f'MA{w}'] = df['Close'].rolling(window=w).mean()
    return df


def add_volume_metrics(df, window=50):
    """Add volume-related metrics."""
    df['AvgVolume'] = df['Volume'].rolling(window=window).mean()
    df['VolumeRatio'] = df['Volume'] / df['AvgVolume']
    return df


# === CLI ===
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == 'clear':
            hours = int(sys.argv[2]) if len(sys.argv) > 2 else None
            count = clear_cache(hours)
            print(f"Cleared {count} cache files")
        
        elif cmd == 'stats':
            files = os.listdir(CACHE_DIR)
            total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
            print(f"Cache: {len(files)} files, {total_size/1024/1024:.2f} MB")
        
        elif cmd == 'test':
            ticker = sys.argv[2] if len(sys.argv) > 2 else 'AAPL'
            print(f"Testing {ticker}...")
            df = get_stock_data(ticker, period='1y')
            if df is not None:
                print(f"  Got {len(df)} bars")
                print(f"  Latest: {df['Close'].iloc[-1]:.2f}")
            else:
                print("  Failed")
    else:
        print("Usage:")
        print("  python data_utils.py clear [hours]  - Clear cache (optionally older than X hours)")
        print("  python data_utils.py stats          - Show cache stats")
        print("  python data_utils.py test [ticker]  - Test fetching a ticker")
