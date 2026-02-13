#!/usr/bin/env python3
"""
Data Loader - Historical data management with caching
"""
import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

class DataLoader:
    def __init__(self, cache_db='../backtest.db'):
        self.cache_db = Path(__file__).parent.parent / cache_db
        self._init_cache()
    
    def _init_cache(self):
        """Initialize SQLite cache database."""
        conn = sqlite3.connect(self.cache_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_cache (
                ticker TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                adj_close REAL,
                PRIMARY KEY (ticker, date)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON price_cache(ticker)")
        conn.commit()
        conn.close()
    
    def get_data(self, ticker, start_date, end_date, use_cache=True):
        """
        Get historical data for a ticker.
        
        Args:
            ticker: Stock symbol
            start_date: Start date (datetime or str 'YYYY-MM-DD')
            end_date: End date (datetime or str 'YYYY-MM-DD')
            use_cache: Use cached data if available
            
        Returns:
            pandas DataFrame with OHLCV data
        """
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Try cache first
        if use_cache:
            df = self._load_from_cache(ticker, start_date, end_date)
            if df is not None and len(df) > 0:
                return df
        
        # Download from yfinance
        print(f"Downloading {ticker} data...")
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if len(df) == 0:
            return None
        
        # Handle MultiIndex columns from yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Save to cache
        self._save_to_cache(ticker, df)
        
        return df
    
    def _load_from_cache(self, ticker, start_date, end_date):
        """Load data from cache."""
        conn = sqlite3.connect(self.cache_db)
        query = """
            SELECT date, open, high, low, close, volume, adj_close
            FROM price_cache
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date
        """
        df = pd.read_sql_query(
            query,
            conn,
            params=(ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')),
            parse_dates=['date'],
            index_col='date'
        )
        conn.close()
        
        if len(df) == 0:
            return None
        
        # Rename columns to match yfinance format
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close']
        return df
    
    def _save_to_cache(self, ticker, df):
        """Save data to cache."""
        conn = sqlite3.connect(self.cache_db)
        
        # Prepare data for insertion
        records = []
        for date, row in df.iterrows():
            records.append((
                ticker,
                date.strftime('%Y-%m-%d'),
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume']),
                float(row.get('Adj Close', row['Close']))
            ))
        
        # Insert or replace records
        conn.executemany("""
            INSERT OR REPLACE INTO price_cache 
            (ticker, date, open, high, low, close, volume, adj_close)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
        
        conn.commit()
        conn.close()
    
    def get_multiple(self, tickers, start_date, end_date, use_cache=True):
        """
        Get data for multiple tickers.
        
        Returns:
            dict of {ticker: DataFrame}
        """
        data = {}
        for ticker in tickers:
            df = self.get_data(ticker, start_date, end_date, use_cache)
            if df is not None:
                data[ticker] = df
        return data
    
    def clear_cache(self, ticker=None):
        """Clear cache for ticker (or all if None)."""
        conn = sqlite3.connect(self.cache_db)
        if ticker:
            conn.execute("DELETE FROM price_cache WHERE ticker = ?", (ticker,))
        else:
            conn.execute("DELETE FROM price_cache")
        conn.commit()
        conn.close()


if __name__ == '__main__':
    # Test
    loader = DataLoader()
    df = loader.get_data('AAPL', '2023-01-01', '2024-01-01')
    print(df.head())
    print(f"\nLoaded {len(df)} days of data")
