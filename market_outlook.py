#!/usr/bin/env python3
"""
Market Outlook - Comprehensive Market Analysis Tool

Combines:
1. Sector & Industry Analysis (S&P 500 stocks grouped by GICS sector)
2. Timeframe Continuity (Monthly/Weekly/Daily Strat scenarios)
3. Market Breadth Dashboard
4. Actionable Summary
5. Weekly Report Format

Run: python market_outlook.py
Output: market_outlook.json, market_outlook.md, updated index.html
"""
import os
import sys
import json
import pickle
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

import yfinance as yf
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, 'cache')

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

# S&P 500 Universe (same as generate_site.py)
UNIVERSE = [
    'A', 'AAL', 'AAPL', 'ABBV', 'ABNB', 'ABT', 'ACGL', 'ACN', 'ADBE', 'ADI',
    'ADM', 'ADP', 'ADSK', 'AEE', 'AEP', 'AES', 'AFL', 'AIG', 'AIZ', 'AJG',
    'AKAM', 'ALB', 'ALGN', 'ALL', 'ALLE', 'AMAT', 'AMCR', 'AMD', 'AME', 'AMGN',
    'AMP', 'AMT', 'AMZN', 'ANET', 'AON', 'AOS', 'APA', 'APD', 'APH',
    'APTV', 'ARE', 'ATO', 'AVB', 'AVGO', 'AVY', 'AWK', 'AXON', 'AXP', 'AZO',
    'BA', 'BAC', 'BALL', 'BAX', 'BBWI', 'BBY', 'BDX', 'BEN', 'BF-B', 'BG',
    'BIIB', 'BIO', 'BK', 'BKNG', 'BKR', 'BLDR', 'BLK', 'BMY', 'BR', 'BRK-B',
    'BRO', 'BSX', 'BWA', 'BX', 'BXP', 'C', 'CAG', 'CAH', 'CARR', 'CAT',
    'CB', 'CBOE', 'CBRE', 'CCI', 'CCL', 'CDNS', 'CDW', 'CE', 'CEG', 'CF',
    'CFG', 'CHD', 'CHRW', 'CHTR', 'CI', 'CINF', 'CL', 'CLX', 'CMCSA', 'CME',
    'CMG', 'CMI', 'CMS', 'CNC', 'CNP', 'COF', 'COO', 'COP', 'COR', 'COST',
    'CPAY', 'CPB', 'CPRT', 'CPT', 'CRL', 'CRM', 'CRWD', 'CSCO', 'CSGP', 'CSX',
    'CTAS', 'CTLT', 'CTRA', 'CTSH', 'CTVA', 'CVS', 'CVX', 'CZR', 'D', 'DAL',
    'DAY', 'DD', 'DE', 'DECK', 'DFS', 'DG', 'DGX', 'DHI', 'DHR', 'DIS',
    'DLR', 'DLTR', 'DOC', 'DOV', 'DOW', 'DPZ', 'DRI', 'DTE', 'DUK', 'DVA',
    'DVN', 'DXCM', 'EA', 'EBAY', 'ECL', 'ED', 'EFX', 'EG', 'EIX', 'EL',
    'ELV', 'EMN', 'EMR', 'ENPH', 'EOG', 'EPAM', 'EQIX', 'EQR', 'EQT', 'ES',
    'ESS', 'ETN', 'ETR', 'ETSY', 'EVRG', 'EW', 'EXC', 'EXPD', 'EXPE', 'EXR',
    'F', 'FANG', 'FAST', 'FCX', 'FDS', 'FDX', 'FE', 'FFIV', 'FI', 'FICO',
    'FIS', 'FITB', 'FMC', 'FOX', 'FOXA', 'FRT', 'FSLR', 'FTNT', 'FTV', 'GD',
    'GDDY', 'GE', 'GEHC', 'GEN', 'GEV', 'GILD', 'GIS', 'GL', 'GLW', 'GM',
    'GNRC', 'GOOG', 'GOOGL', 'GPC', 'GPN', 'GRMN', 'GS', 'GWW', 'HAL', 'HAS',
    'HBAN', 'HCA', 'HD', 'HES', 'HIG', 'HII', 'HLT', 'HOLX', 'HON', 'HPE',
    'HPQ', 'HRL', 'HSIC', 'HST', 'HSY', 'HUBB', 'HUM', 'HWM', 'IBM', 'ICE',
    'IDXX', 'IEX', 'IFF', 'ILMN', 'INCY', 'INTC', 'INTU', 'INVH', 'IP', 'IPG',
    'IQV', 'IR', 'IRM', 'ISRG', 'IT', 'ITW', 'IVZ', 'J', 'JBHT', 'JBL',
    'JCI', 'JKHY', 'JNJ', 'JNPR', 'JPM', 'K', 'KDP', 'KEY', 'KEYS', 'KHC',
    'KIM', 'KKR', 'KLAC', 'KMB', 'KMI', 'KMX', 'KO', 'KR', 'KVUE', 'L',
    'LDOS', 'LEN', 'LH', 'LHX', 'LIN', 'LKQ', 'LLY', 'LMT', 'LNT', 'LOW',
    'LRCX', 'LULU', 'LUV', 'LVS', 'LW', 'LYB', 'LYV', 'MA', 'MAA', 'MAR',
    'MAS', 'MCD', 'MCHP', 'MCK', 'MCO', 'MDLZ', 'MDT', 'MET', 'META', 'MGM',
    'MHK', 'MKC', 'MKTX', 'MLM', 'MMC', 'MMM', 'MNST', 'MO', 'MOH', 'MOS',
    'MPC', 'MPWR', 'MRK', 'MRNA', 'MRO', 'MS', 'MSCI', 'MSFT', 'MSI', 'MTB',
    'MTCH', 'MTD', 'MU', 'NCLH', 'NDAQ', 'NDSN', 'NEE', 'NEM', 'NFLX', 'NI',
    'NKE', 'NOC', 'NOW', 'NRG', 'NSC', 'NTAP', 'NTRS', 'NUE', 'NVDA', 'NVR',
    'NWS', 'NWSA', 'NXPI', 'O', 'ODFL', 'OKE', 'OMC', 'ON', 'ORCL', 'ORLY',
    'OTIS', 'OXY', 'PANW', 'PARA', 'PAYC', 'PAYX', 'PCAR', 'PCG', 'PEG', 'PEP',
    'PFE', 'PFG', 'PG', 'PGR', 'PH', 'PHM', 'PKG', 'PLD', 'PM', 'PNC',
    'PNR', 'PNW', 'PODD', 'POOL', 'PPG', 'PPL', 'PRU', 'PSA', 'PSX', 'PTC',
    'PWR', 'PYPL', 'QCOM', 'QRVO', 'RCL', 'REG', 'REGN', 'RF', 'RJF', 'RL',
    'RMD', 'ROK', 'ROL', 'ROP', 'ROST', 'RSG', 'RTX', 'RVTY', 'SBAC', 'SBUX',
    'SCHW', 'SHW', 'SJM', 'SLB', 'SMCI', 'SNA', 'SNPS', 'SO', 'SOLV', 'SPG',
    'SPGI', 'SRE', 'STE', 'STLD', 'STT', 'STX', 'STZ', 'SW', 'SWK', 'SWKS',
    'SYF', 'SYK', 'SYY', 'T', 'TAP', 'TDG', 'TDY', 'TECH', 'TEL', 'TER',
    'TFC', 'TFX', 'TGT', 'TJX', 'TMO', 'TMUS', 'TPR', 'TRGP', 'TRMB', 'TROW',
    'TRV', 'TSCO', 'TSLA', 'TSN', 'TT', 'TTWO', 'TXN', 'TXT', 'TYL', 'UAL',
    'UBER', 'UDR', 'UHS', 'ULTA', 'UNH', 'UNP', 'UPS', 'URI', 'USB', 'V',
    'VFC', 'VICI', 'VLO', 'VLTO', 'VMC', 'VRSK', 'VRSN', 'VRTX', 'VST', 'VTR',
    'VTRS', 'VZ', 'WAB', 'WAT', 'WBA', 'WBD', 'WDC', 'WEC', 'WELL', 'WFC',
    'WM', 'WMB', 'WMT', 'WRB', 'WST', 'WTW', 'WY', 'WYNN', 'XEL', 'XOM',
    'XYL', 'YUM', 'ZBH', 'ZBRA', 'ZTS'
]

# GICS Sector mapping (we'll fetch this dynamically, but have fallbacks)
SECTOR_ETF_MAP = {
    'Information Technology': 'XLK',
    'Technology': 'XLK',
    'Health Care': 'XLV',
    'Healthcare': 'XLV',
    'Financials': 'XLF',
    'Financial Services': 'XLF',
    'Consumer Discretionary': 'XLY',
    'Consumer Cyclical': 'XLY',
    'Communication Services': 'XLC',
    'Industrials': 'XLI',
    'Consumer Staples': 'XLP',
    'Consumer Defensive': 'XLP',
    'Energy': 'XLE',
    'Utilities': 'XLU',
    'Real Estate': 'XLRE',
    'Materials': 'XLB',
    'Basic Materials': 'XLB',
}

# Canonical sector names
CANONICAL_SECTORS = [
    'Technology', 'Healthcare', 'Financials', 'Consumer Discretionary',
    'Communication Services', 'Industrials', 'Consumer Staples',
    'Energy', 'Utilities', 'Real Estate', 'Materials'
]

# Sector name normalization
def normalize_sector(sector: str) -> str:
    """Normalize sector names to canonical form."""
    if not sector:
        return 'Unknown'
    sector = sector.strip()
    mapping = {
        'Information Technology': 'Technology',
        'Health Care': 'Healthcare',
        'Financial Services': 'Financials',
        'Consumer Cyclical': 'Consumer Discretionary',
        'Consumer Defensive': 'Consumer Staples',
        'Basic Materials': 'Materials',
    }
    return mapping.get(sector, sector)


def get_cache_path(ticker: str, suffix: str = '') -> str:
    """Get cache file path for a ticker."""
    safe_ticker = ticker.replace('-', '_').replace('.', '_')
    return os.path.join(CACHE_DIR, f"{safe_ticker}{suffix}.pkl")


def load_cached_data(ticker: str, suffix: str = '', max_age_hours: int = 24) -> Optional[pd.DataFrame]:
    """Load data from cache if fresh enough."""
    cache_path = get_cache_path(ticker, suffix)
    if not os.path.exists(cache_path):
        return None
    
    try:
        mtime = os.path.getmtime(cache_path)
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        if age_hours > max_age_hours:
            return None
        
        with open(cache_path, 'rb') as f:
            return pickle.load(f)
    except Exception:
        return None


def save_to_cache(ticker: str, data: pd.DataFrame, suffix: str = ''):
    """Save data to cache."""
    try:
        cache_path = get_cache_path(ticker, suffix)
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
    except Exception:
        pass


def download_with_cache(ticker: str, period: str = '2y', interval: str = '1d', 
                        max_age_hours: int = 6) -> Optional[pd.DataFrame]:
    """Download data with caching."""
    suffix = f"_{period}_{interval}" if interval != '1d' else f"_{period}"
    
    # Try cache first
    cached = load_cached_data(ticker, suffix, max_age_hours)
    if cached is not None and len(cached) > 0:
        return cached
    
    # Download fresh
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) > 0:
            save_to_cache(ticker, df, suffix)
        return df
    except Exception as e:
        return None


# ==============================================================================
# Sector Info Cache
# ==============================================================================
SECTOR_CACHE_FILE = os.path.join(SCRIPT_DIR, 'sector_info_cache.json')


def load_sector_cache() -> Dict[str, Dict]:
    """Load cached sector/industry info."""
    if os.path.exists(SECTOR_CACHE_FILE):
        try:
            mtime = os.path.getmtime(SECTOR_CACHE_FILE)
            age_days = (datetime.now().timestamp() - mtime) / 86400
            if age_days < 30:  # Cache valid for 30 days
                with open(SECTOR_CACHE_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
    return {}


def save_sector_cache(cache: Dict[str, Dict]):
    """Save sector/industry info to cache."""
    try:
        with open(SECTOR_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def get_stock_sector_info(ticker: str, sector_cache: Dict) -> Tuple[str, str]:
    """Get sector and industry for a stock."""
    if ticker in sector_cache:
        info = sector_cache[ticker]
        return info.get('sector', 'Unknown'), info.get('industry', 'Unknown')
    
    # Fetch from yfinance
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        sector = normalize_sector(info.get('sector', 'Unknown'))
        industry = info.get('industry', 'Unknown')
        
        # Cache it
        sector_cache[ticker] = {'sector': sector, 'industry': industry}
        return sector, industry
    except Exception:
        return 'Unknown', 'Unknown'


# ==============================================================================
# Strat Candle Scenarios
# ==============================================================================
def calculate_strat_scenario(open_price: float, high: float, low: float, close: float,
                             prev_high: float, prev_low: float) -> str:
    """
    Calculate Strat candle scenario.
    1 = Inside bar (current high < prev high AND current low > prev low)
    2U = Outside bar up OR higher high/higher low trending up
    2D = Outside bar down OR lower high/lower low trending down
    3 = Outside bar (both higher high AND lower low)
    """
    higher_high = high > prev_high
    lower_low = low < prev_low
    
    if higher_high and lower_low:
        return '3'  # Outside bar (reversal potential)
    elif not higher_high and not lower_low:
        return '1'  # Inside bar (consolidation)
    elif higher_high and not lower_low:
        return '2U'  # Uptrend
    else:  # lower_low and not higher_high
        return '2D'  # Downtrend


def get_timeframe_scenarios(df_daily: pd.DataFrame, df_weekly: pd.DataFrame, 
                            df_monthly: Optional[pd.DataFrame] = None) -> Dict:
    """Get Strat scenarios for all timeframes."""
    result = {
        'daily': None,
        'weekly': None,
        'monthly': None,
        'continuity_score': 0,
        'continuity_direction': 'MIXED',
        'full_continuity': False,
    }
    
    # Daily scenario
    if len(df_daily) >= 2:
        try:
            curr = df_daily.iloc[-1]
            prev = df_daily.iloc[-2]
            result['daily'] = calculate_strat_scenario(
                float(curr['Open']), float(curr['High']), float(curr['Low']), float(curr['Close']),
                float(prev['High']), float(prev['Low'])
            )
        except Exception:
            pass
    
    # Weekly scenario
    if len(df_weekly) >= 2:
        try:
            curr = df_weekly.iloc[-1]
            prev = df_weekly.iloc[-2]
            result['weekly'] = calculate_strat_scenario(
                float(curr['Open']), float(curr['High']), float(curr['Low']), float(curr['Close']),
                float(prev['High']), float(prev['Low'])
            )
        except Exception:
            pass
    
    # Monthly scenario (resample from daily if not provided)
    if df_monthly is not None and len(df_monthly) >= 2:
        try:
            curr = df_monthly.iloc[-1]
            prev = df_monthly.iloc[-2]
            result['monthly'] = calculate_strat_scenario(
                float(curr['Open']), float(curr['High']), float(curr['Low']), float(curr['Close']),
                float(prev['High']), float(prev['Low'])
            )
        except Exception:
            pass
    elif len(df_daily) >= 44:  # Need at least 2 months of daily data
        try:
            monthly = df_daily.resample('ME').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
            }).dropna()
            if len(monthly) >= 2:
                curr = monthly.iloc[-1]
                prev = monthly.iloc[-2]
                result['monthly'] = calculate_strat_scenario(
                    float(curr['Open']), float(curr['High']), float(curr['Low']), float(curr['Close']),
                    float(prev['High']), float(prev['Low'])
                )
        except Exception:
            pass
    
    # Calculate continuity
    scenarios = [result['monthly'], result['weekly'], result['daily']]
    valid_scenarios = [s for s in scenarios if s is not None]
    
    if len(valid_scenarios) >= 2:
        bullish = sum(1 for s in valid_scenarios if s in ('2U',))
        bearish = sum(1 for s in valid_scenarios if s in ('2D',))
        inside = sum(1 for s in valid_scenarios if s == '1')
        outside = sum(1 for s in valid_scenarios if s == '3')
        
        if bullish == len(valid_scenarios):
            result['continuity_score'] = 3
            result['continuity_direction'] = 'BULLISH'
            result['full_continuity'] = True
        elif bearish == len(valid_scenarios):
            result['continuity_score'] = 3
            result['continuity_direction'] = 'BEARISH'
            result['full_continuity'] = True
        elif bullish >= 2:
            result['continuity_score'] = 2
            result['continuity_direction'] = 'BULLISH'
        elif bearish >= 2:
            result['continuity_score'] = 2
            result['continuity_direction'] = 'BEARISH'
        elif inside >= 2:
            result['continuity_score'] = 1
            result['continuity_direction'] = 'CONSOLIDATING'
        else:
            result['continuity_score'] = 1
            result['continuity_direction'] = 'MIXED'
    
    return result


# ==============================================================================
# Squeeze Detection (from generate_site.py)
# ==============================================================================
def wilder_rma(series, length):
    """Wilder's RMA (SMMA)."""
    alpha = 1.0 / length
    return series.ewm(alpha=alpha, adjust=False).mean()


def calculate_squeeze(df, bb_len=20, bb_mult=2.0, kc_len=20, kc_mult=2.0, atr_len=10):
    """Calculate Squeeze indicator."""
    min_len = max(bb_len, kc_len, atr_len) + 5
    if len(df) < min_len:
        return False, 0, 'NONE', 0
    
    try:
        close = df['Close']
        high = df['High'] if 'High' in df.columns else close
        low = df['Low'] if 'Low' in df.columns else close
        
        # Bollinger Bands
        bb_basis = close.rolling(bb_len).mean()
        bb_dev = bb_mult * close.rolling(bb_len).std()
        bb_upper = bb_basis + bb_dev
        bb_lower = bb_basis - bb_dev
        bb_width = bb_upper - bb_lower
        
        # Keltner Channels
        kc_basis = close.ewm(span=kc_len, adjust=False).mean()
        
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        tr.iloc[0] = high.iloc[0] - low.iloc[0]
        
        atr = wilder_rma(tr, atr_len)
        kc_upper = kc_basis + (kc_mult * atr)
        kc_lower = kc_basis - (kc_mult * atr)
        kc_width = kc_upper - kc_lower
        
        # Squeeze detection
        squeeze_on_series = (bb_upper < kc_upper) & (bb_lower > kc_lower)
        
        # Count consecutive squeeze bars
        squeeze_count_series = pd.Series(0, index=df.index)
        for i in range(len(squeeze_on_series)):
            if squeeze_on_series.iloc[i]:
                squeeze_count_series.iloc[i] = (squeeze_count_series.iloc[i-1] + 1) if i > 0 else 1
        
        idx = -1
        current_kc_width = float(kc_width.iloc[idx])
        current_bb_width = float(bb_width.iloc[idx])
        squeeze_on = bool(squeeze_on_series.iloc[idx])
        squeeze_count = int(squeeze_count_series.iloc[idx])
        
        # Depth calculation
        if current_kc_width > 0:
            depth = (current_kc_width - current_bb_width) / current_kc_width
        else:
            depth = 0
        
        # Classification
        min_bars_high = 10
        min_bars_med = 5
        depth_high = 0.25
        depth_med = 0.10
        
        is_high = squeeze_on and squeeze_count >= min_bars_high and depth >= depth_high
        is_med = squeeze_on and not is_high and squeeze_count >= min_bars_med and depth >= depth_med
        is_low = squeeze_on and not is_high and not is_med
        
        if is_high:
            state = 'HIGH'
        elif is_med:
            state = 'MED'
        elif is_low:
            state = 'LOW'
        else:
            state = 'NONE'
        
        # Score
        if squeeze_on:
            depth_norm = max(0, min(1, (depth - depth_med) / max(depth_high - depth_med, 1e-4)))
            dur_norm = max(0, min(1, (squeeze_count - min_bars_med) / max(min_bars_high - min_bars_med, 1e-4)))
            score_raw = 0.6 * depth_norm + 0.4 * dur_norm
            squeeze_score = int(round(score_raw * 100))
        else:
            squeeze_score = 0
        
        return squeeze_on, squeeze_score, state, squeeze_count
        
    except Exception:
        return False, 0, 'NONE', 0


# ==============================================================================
# Market Breadth
# ==============================================================================
def calculate_breadth_metrics(stock_data: List[Dict]) -> Dict:
    """Calculate market breadth metrics from stock data."""
    total = len(stock_data)
    if total == 0:
        return {}
    
    advancing = sum(1 for s in stock_data if s.get('daily_change', 0) > 0)
    declining = sum(1 for s in stock_data if s.get('daily_change', 0) < 0)
    unchanged = total - advancing - declining
    
    above_20sma = sum(1 for s in stock_data if s.get('above_20sma', False))
    above_50sma = sum(1 for s in stock_data if s.get('above_50sma', False))
    above_200sma = sum(1 for s in stock_data if s.get('above_200sma', False))
    
    new_highs = sum(1 for s in stock_data if s.get('near_52w_high', False))
    new_lows = sum(1 for s in stock_data if s.get('near_52w_low', False))
    
    # Advance/Decline ratio
    ad_ratio = round(advancing / max(declining, 1), 2)
    
    # Breadth thrust calculation
    pct_advancing = (advancing / total) * 100
    
    # McClellan-style calculation (simplified)
    # Normally uses EMA of (advances - declines), here we approximate
    ad_diff = advancing - declining
    ad_pct = (ad_diff / total) * 100
    
    return {
        'total_stocks': total,
        'advancing': advancing,
        'declining': declining,
        'unchanged': unchanged,
        'ad_ratio': ad_ratio,
        'ad_diff': ad_diff,
        'pct_advancing': round(pct_advancing, 1),
        'pct_above_20sma': round((above_20sma / total) * 100, 1),
        'pct_above_50sma': round((above_50sma / total) * 100, 1),
        'pct_above_200sma': round((above_200sma / total) * 100, 1),
        'new_highs': new_highs,
        'new_lows': new_lows,
        'hl_ratio': round(new_highs / max(new_lows, 1), 2),
    }


def get_vix_info() -> Dict:
    """Get VIX level and trend."""
    try:
        df = yf.download('^VIX', period='3mo', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return {}
        
        close = df['Close']
        current = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else current
        avg_10d = float(close.tail(10).mean())
        avg_30d = float(close.tail(30).mean())
        
        # Classify
        if current < 15:
            label = 'LOW'
        elif current < 20:
            label = 'NORMAL'
        elif current < 25:
            label = 'ELEVATED'
        elif current < 30:
            label = 'HIGH'
        else:
            label = 'EXTREME'
        
        return {
            'level': round(current, 2),
            'change': round(current - prev, 2),
            'change_pct': round(((current - prev) / prev) * 100, 2) if prev > 0 else 0,
            'avg_10d': round(avg_10d, 2),
            'avg_30d': round(avg_30d, 2),
            'trend': 'RISING' if current > avg_10d else 'FALLING',
            'label': label,
        }
    except Exception:
        return {}


def get_spy_levels() -> Dict:
    """Get SPY key support/resistance levels."""
    try:
        df = yf.download('SPY', period='1y', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return {}
        
        close = df['Close']
        current = float(close.iloc[-1])
        high_52w = float(close.max())
        low_52w = float(close.min())
        
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
        
        # Find recent swing levels
        recent = close.tail(20)
        recent_high = float(recent.max())
        recent_low = float(recent.min())
        
        return {
            'price': round(current, 2),
            'high_52w': round(high_52w, 2),
            'low_52w': round(low_52w, 2),
            'ma20': round(ma20, 2),
            'ma50': round(ma50, 2),
            'ma200': round(ma200, 2) if ma200 else None,
            'recent_high': round(recent_high, 2),
            'recent_low': round(recent_low, 2),
            'above_20ma': current > ma20,
            'above_50ma': current > ma50,
            'above_200ma': current > ma200 if ma200 else None,
            'pct_from_high': round(((current - high_52w) / high_52w) * 100, 2),
        }
    except Exception:
        return {}


# ==============================================================================
# Main Analysis
# ==============================================================================
def analyze_stock(ticker: str, sector_cache: Dict) -> Optional[Dict]:
    """Analyze a single stock comprehensively."""
    try:
        # Get sector info
        sector, industry = get_stock_sector_info(ticker, sector_cache)
        
        # Download daily data
        df_daily = download_with_cache(ticker, period='2y', interval='1d')
        if df_daily is None or len(df_daily) < 50:
            return None
        
        # Download weekly data
        df_weekly = download_with_cache(ticker, period='5y', interval='1wk')
        if df_weekly is None:
            df_weekly = df_daily.resample('W').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
            }).dropna()
        
        close = df_daily['Close']
        volume = df_daily['Volume']
        price = float(close.iloc[-1])
        
        # Daily change
        daily_change = float(close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else 0
        
        # Moving averages
        ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else price
        ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else price
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else price
        
        # Performance metrics
        perf_1w = float(close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0
        perf_1m = float(close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0
        perf_3m = float(close.iloc[-1] / close.iloc[-63] - 1) * 100 if len(close) >= 63 else 0
        
        # 52-week metrics
        high_52w = float(close.iloc[-252:].max()) if len(close) >= 252 else float(close.max())
        low_52w = float(close.iloc[-252:].min()) if len(close) >= 252 else float(close.min())
        pct_from_high = ((price - high_52w) / high_52w) * 100
        pct_from_low = ((price - low_52w) / low_52w) * 100
        
        # Squeeze detection
        daily_sq_on, daily_sq_score, daily_sq_state, daily_sq_bars = calculate_squeeze(df_daily)
        weekly_sq_on, weekly_sq_score, weekly_sq_state, weekly_sq_bars = calculate_squeeze(df_weekly)
        
        # Timeframe continuity
        continuity = get_timeframe_scenarios(df_daily, df_weekly)
        
        # Volume analysis
        avg_vol = float(volume.rolling(50).mean().iloc[-1]) if len(volume) >= 50 else float(volume.mean())
        recent_vol = float(volume.iloc[-5:].mean())
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
        
        # Relative strength (vs SPY approximation - using 3m perf as proxy)
        rs_score = perf_3m  # Will be compared to sector average later
        
        # Setup classification
        is_bullish = (
            price > ma50 and 
            ma50 > ma200 and 
            (continuity['continuity_direction'] in ('BULLISH', 'CONSOLIDATING') or perf_1m > 0)
        )
        is_bearish = (
            price < ma50 and 
            ma50 < ma200 and 
            (continuity['continuity_direction'] == 'BEARISH' or perf_1m < -5)
        )
        
        # Risk score (lower is better for entry)
        # Based on pattern tightness, squeeze readiness, etc.
        volatility = float(close.pct_change().std() * np.sqrt(252) * 100)  # Annualized vol
        tightness = (high_52w - price) / high_52w * 100  # Distance from high
        risk_score = volatility * 0.3 + tightness * 0.3
        if daily_sq_on or weekly_sq_on:
            risk_score *= 0.8  # Lower risk if in squeeze
        
        return {
            'ticker': ticker,
            'sector': sector,
            'industry': industry,
            'price': round(price, 2),
            'daily_change': round(daily_change, 2),
            'perf_1w': round(perf_1w, 2),
            'perf_1m': round(perf_1m, 2),
            'perf_3m': round(perf_3m, 2),
            'ma20': round(ma20, 2),
            'ma50': round(ma50, 2),
            'ma200': round(ma200, 2),
            'above_20sma': price > ma20,
            'above_50sma': price > ma50,
            'above_200sma': price > ma200,
            'high_52w': round(high_52w, 2),
            'low_52w': round(low_52w, 2),
            'pct_from_high': round(pct_from_high, 2),
            'pct_from_low': round(pct_from_low, 2),
            'near_52w_high': pct_from_high >= -5,
            'near_52w_low': pct_from_low <= 5,
            'daily_squeeze_on': daily_sq_on,
            'daily_squeeze_score': daily_sq_score,
            'daily_squeeze_state': daily_sq_state,
            'daily_squeeze_bars': daily_sq_bars,
            'weekly_squeeze_on': weekly_sq_on,
            'weekly_squeeze_score': weekly_sq_score,
            'weekly_squeeze_state': weekly_sq_state,
            'weekly_squeeze_bars': weekly_sq_bars,
            'strat_daily': continuity['daily'],
            'strat_weekly': continuity['weekly'],
            'strat_monthly': continuity['monthly'],
            'continuity_score': continuity['continuity_score'],
            'continuity_direction': continuity['continuity_direction'],
            'full_continuity': continuity['full_continuity'],
            'vol_ratio': round(vol_ratio, 2),
            'is_bullish': is_bullish,
            'is_bearish': is_bearish,
            'rs_score': round(rs_score, 2),
            'risk_score': round(risk_score, 2),
            'volatility': round(volatility, 1),
        }
        
    except Exception as e:
        return None


def analyze_sector(sector: str, stocks: List[Dict]) -> Dict:
    """Analyze a sector based on its constituent stocks."""
    total = len(stocks)
    if total == 0:
        return {}
    
    # Squeeze stats
    daily_squeeze_count = sum(1 for s in stocks if s.get('daily_squeeze_on', False))
    weekly_squeeze_count = sum(1 for s in stocks if s.get('weekly_squeeze_on', False))
    
    # Bullish/Bearish breakdown
    bullish_count = sum(1 for s in stocks if s.get('is_bullish', False))
    bearish_count = sum(1 for s in stocks if s.get('is_bearish', False))
    neutral_count = total - bullish_count - bearish_count
    
    # Average performance
    avg_perf_1m = np.mean([s.get('perf_1m', 0) for s in stocks])
    avg_perf_3m = np.mean([s.get('perf_3m', 0) for s in stocks])
    
    # Stocks above MAs
    above_50ma = sum(1 for s in stocks if s.get('above_50sma', False))
    above_200ma = sum(1 for s in stocks if s.get('above_200sma', False))
    
    # Full continuity stocks
    full_continuity = [s for s in stocks if s.get('full_continuity', False)]
    bullish_continuity = [s for s in full_continuity if s.get('continuity_direction') == 'BULLISH']
    bearish_continuity = [s for s in full_continuity if s.get('continuity_direction') == 'BEARISH']
    
    # Top actionable stocks (bullish, in squeeze or tight pattern)
    actionable = sorted(
        [s for s in stocks if s.get('is_bullish', False) and 
         (s.get('daily_squeeze_on', False) or s.get('weekly_squeeze_on', False) or s.get('pct_from_high', -100) >= -10)],
        key=lambda x: (-x.get('continuity_score', 0), -x.get('perf_3m', 0))
    )[:5]
    
    # Overall sector bias
    bullish_pct = (bullish_count / total) * 100
    if bullish_pct >= 65:
        bias = 'BULLISH'
        emoji = '🟢'
    elif bullish_pct >= 50:
        bias = 'LEAN BULLISH'
        emoji = '🟢'
    elif bullish_pct >= 35:
        bias = 'MIXED'
        emoji = '🟡'
    elif bullish_pct >= 20:
        bias = 'LEAN BEARISH'
        emoji = '🔴'
    else:
        bias = 'BEARISH'
        emoji = '🔴'
    
    return {
        'sector': sector,
        'total_stocks': total,
        'bullish_count': bullish_count,
        'bearish_count': bearish_count,
        'neutral_count': neutral_count,
        'bullish_pct': round(bullish_pct, 1),
        'bearish_pct': round((bearish_count / total) * 100, 1),
        'daily_squeeze_count': daily_squeeze_count,
        'weekly_squeeze_count': weekly_squeeze_count,
        'pct_in_daily_squeeze': round((daily_squeeze_count / total) * 100, 1),
        'pct_in_weekly_squeeze': round((weekly_squeeze_count / total) * 100, 1),
        'avg_perf_1m': round(avg_perf_1m, 2),
        'avg_perf_3m': round(avg_perf_3m, 2),
        'pct_above_50ma': round((above_50ma / total) * 100, 1),
        'pct_above_200ma': round((above_200ma / total) * 100, 1),
        'bullish_continuity': [s['ticker'] for s in bullish_continuity],
        'bearish_continuity': [s['ticker'] for s in bearish_continuity],
        'top_actionable': [{'ticker': s['ticker'], 'setup': f"{s.get('strat_weekly', '?')}/{s.get('strat_daily', '?')}", 'squeeze': 'W' if s.get('weekly_squeeze_on') else 'D' if s.get('daily_squeeze_on') else '-'} for s in actionable],
        'bias': bias,
        'emoji': emoji,
    }


def generate_weekly_report(stock_data: List[Dict], sector_analysis: Dict, 
                           breadth: Dict, vix: Dict, spy: Dict) -> str:
    """Generate markdown weekly report."""
    now = datetime.now()
    
    # Determine overall market bias
    total_bullish = sum(1 for s in stock_data if s.get('is_bullish', False))
    total_bearish = sum(1 for s in stock_data if s.get('is_bearish', False))
    total = len(stock_data)
    
    bullish_pct = (total_bullish / total) * 100 if total > 0 else 50
    
    if bullish_pct >= 60 and vix.get('label', '') not in ('HIGH', 'EXTREME'):
        overall_bias = 'BULLISH'
        bias_emoji = '🟢'
    elif bullish_pct >= 45:
        overall_bias = 'NEUTRAL'
        bias_emoji = '🟡'
    else:
        overall_bias = 'BEARISH'
        bias_emoji = '🔴'
    
    report = f"""
MARKET OUTLOOK - {now.strftime('%b %d, %Y')}
{'═' * 50}
Overall Bias: {bias_emoji} {overall_bias}
Breadth: {breadth.get('pct_above_50sma', 0):.0f}% above 50MA | {breadth.get('new_highs', 0)} new highs vs {breadth.get('new_lows', 0)} new lows
VIX: {vix.get('level', 0):.1f} ({vix.get('label', 'N/A')}) - {vix.get('trend', 'N/A')}
SPY: ${spy.get('price', 0):.2f} ({spy.get('pct_from_high', 0):+.1f}% from high)

SECTOR ROTATION
{'─' * 50}
"""
    
    # Sort sectors by bullish percentage
    sorted_sectors = sorted(sector_analysis.values(), key=lambda x: x.get('bullish_pct', 0), reverse=True)
    
    for sec in sorted_sectors:
        squeeze_info = f"{sec.get('weekly_squeeze_count', 0)}W/{sec.get('daily_squeeze_count', 0)}D squeezes"
        report += f"{sec.get('emoji', '⚪')} {sec.get('sector', 'Unknown'):<22} ({sec.get('bullish_pct', 0):.0f}% bullish, {squeeze_info})\n"
    
    report += f"\nTOP SETUPS\n{'─' * 50}\n"
    
    # Get top setups: full continuity + squeeze
    top_setups = sorted(
        [s for s in stock_data if s.get('is_bullish', False) and 
         (s.get('weekly_squeeze_on', False) or s.get('full_continuity', False))],
        key=lambda x: (-x.get('continuity_score', 0), -x.get('weekly_squeeze_score', 0), -x.get('perf_3m', 0))
    )[:10]
    
    for i, s in enumerate(top_setups, 1):
        setup_type = []
        if s.get('weekly_squeeze_on'):
            setup_type.append('Weekly Squeeze')
        if s.get('daily_squeeze_on'):
            setup_type.append('Daily Squeeze')
        if s.get('full_continuity'):
            setup_type.append(f"Full Cont ({s.get('continuity_direction', '')})")
        
        report += f"{i:2}. {s['ticker']:<6} - {', '.join(setup_type)}, {s.get('sector', 'Unknown')} ({s.get('perf_3m', 0):+.1f}% 3M)\n"
    
    # Full continuity stocks
    bullish_full_cont = [s for s in stock_data if s.get('full_continuity') and s.get('continuity_direction') == 'BULLISH']
    bearish_full_cont = [s for s in stock_data if s.get('full_continuity') and s.get('continuity_direction') == 'BEARISH']
    
    report += f"\nFULL CONTINUITY (Monthly+Weekly+Daily aligned)\n{'─' * 50}\n"
    
    if bullish_full_cont:
        tickers = ', '.join([s['ticker'] for s in sorted(bullish_full_cont, key=lambda x: -x.get('perf_3m', 0))[:15]])
        report += f"🟢 BULLISH: {tickers}\n"
    else:
        report += "🟢 BULLISH: None\n"
    
    if bearish_full_cont:
        tickers = ', '.join([s['ticker'] for s in sorted(bearish_full_cont, key=lambda x: x.get('perf_3m', 0))[:15]])
        report += f"🔴 BEARISH: {tickers}\n"
    else:
        report += "🔴 BEARISH: None\n"
    
    # What to avoid
    report += f"\nWHAT TO AVOID\n{'─' * 50}\n"
    
    # Stocks breaking down: bearish, below MAs, high vol
    breaking_down = sorted(
        [s for s in stock_data if s.get('is_bearish', False) and s.get('pct_from_high', 0) < -15],
        key=lambda x: x.get('perf_1m', 0)
    )[:5]
    
    if breaking_down:
        for s in breaking_down:
            report += f"  ⚠️  {s['ticker']} - {s.get('pct_from_high', 0):.1f}% from high, {s.get('perf_1m', 0):+.1f}% 1M\n"
    else:
        report += "  No major breakdowns detected\n"
    
    # Weak sectors
    weak_sectors = [sec for sec in sorted_sectors if sec.get('bullish_pct', 100) < 40]
    if weak_sectors:
        report += f"\nWeak Sectors: {', '.join([s.get('sector', '') for s in weak_sectors[:3]])}\n"
    
    # Key levels
    report += f"\nKEY LEVELS TO WATCH\n{'─' * 50}\n"
    report += f"SPY: Support ${spy.get('ma50', 0):.2f} (50MA), ${spy.get('ma200', 0):.2f} (200MA) | Resistance ${spy.get('recent_high', 0):.2f}\n"
    
    report += f"\n{'═' * 50}\nGenerated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return report


def generate_html_sections(stock_data: List[Dict], sector_analysis: Dict,
                           breadth: Dict, vix: Dict, spy: Dict) -> str:
    """Generate HTML sections for the enhanced dashboard."""
    now = datetime.now()
    
    # Sort sectors
    sorted_sectors = sorted(sector_analysis.values(), key=lambda x: x.get('bullish_pct', 0), reverse=True)
    
    # Sector heatmap
    sector_html = '<div class="sector-heatmap">'
    for sec in sorted_sectors:
        bullish_pct = sec.get('bullish_pct', 50)
        if bullish_pct >= 65:
            color = '#22c55e'  # green
        elif bullish_pct >= 50:
            color = '#84cc16'  # lime
        elif bullish_pct >= 35:
            color = '#eab308'  # yellow
        elif bullish_pct >= 20:
            color = '#f97316'  # orange
        else:
            color = '#ef4444'  # red
        
        sector_html += f'''
        <div class="sector-card" style="border-left: 4px solid {color}">
            <div class="sector-name">{sec.get('sector', 'Unknown')}</div>
            <div class="sector-stat">{bullish_pct:.0f}% bullish</div>
            <div class="sector-squeeze">{sec.get('weekly_squeeze_count', 0)}W/{sec.get('daily_squeeze_count', 0)}D sq</div>
        </div>
        '''
    sector_html += '</div>'
    
    # Full continuity section
    bullish_cont = [s for s in stock_data if s.get('full_continuity') and s.get('continuity_direction') == 'BULLISH']
    bearish_cont = [s for s in stock_data if s.get('full_continuity') and s.get('continuity_direction') == 'BEARISH']
    
    continuity_html = '<div class="continuity-section">'
    continuity_html += '<h4>🎯 Full Timeframe Continuity (M+W+D aligned)</h4>'
    
    if bullish_cont:
        continuity_html += '<div class="cont-bullish"><span class="cont-label">🟢 BULLISH:</span> '
        continuity_html += ', '.join([f'<a href="#" onclick="loadChart(\'{s["ticker"]}\')">{s["ticker"]}</a>' 
                                      for s in sorted(bullish_cont, key=lambda x: -x.get('perf_3m', 0))[:15]])
        continuity_html += '</div>'
    
    if bearish_cont:
        continuity_html += '<div class="cont-bearish"><span class="cont-label">🔴 BEARISH:</span> '
        continuity_html += ', '.join([f'<a href="#" onclick="loadChart(\'{s["ticker"]}\')">{s["ticker"]}</a>' 
                                      for s in sorted(bearish_cont, key=lambda x: x.get('perf_3m', 0))[:15]])
        continuity_html += '</div>'
    
    continuity_html += '</div>'
    
    # Market breadth dashboard
    breadth_html = f'''
    <div class="breadth-dashboard">
        <h4>📊 Market Breadth</h4>
        <div class="breadth-grid">
            <div class="breadth-item">
                <span class="breadth-label">A/D Ratio</span>
                <span class="breadth-value">{breadth.get('ad_ratio', 1):.2f}</span>
            </div>
            <div class="breadth-item">
                <span class="breadth-label">Above 50MA</span>
                <span class="breadth-value">{breadth.get('pct_above_50sma', 0):.0f}%</span>
            </div>
            <div class="breadth-item">
                <span class="breadth-label">Above 200MA</span>
                <span class="breadth-value">{breadth.get('pct_above_200sma', 0):.0f}%</span>
            </div>
            <div class="breadth-item">
                <span class="breadth-label">New Highs/Lows</span>
                <span class="breadth-value">{breadth.get('new_highs', 0)}/{breadth.get('new_lows', 0)}</span>
            </div>
            <div class="breadth-item">
                <span class="breadth-label">VIX</span>
                <span class="breadth-value">{vix.get('level', 0):.1f} ({vix.get('label', 'N/A')})</span>
            </div>
            <div class="breadth-item">
                <span class="breadth-label">SPY from High</span>
                <span class="breadth-value">{spy.get('pct_from_high', 0):+.1f}%</span>
            </div>
        </div>
    </div>
    '''
    
    return {
        'sector_heatmap': sector_html,
        'continuity': continuity_html,
        'breadth': breadth_html,
        'timestamp': now.strftime("%B %d, %Y • %I:%M %p EST"),
    }


# ==============================================================================
# Main Function
# ==============================================================================
def run_market_outlook(quick_mode: bool = False):
    """Run comprehensive market outlook analysis."""
    print("=" * 60)
    print("  📊 COMPREHENSIVE MARKET OUTLOOK")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Load sector cache
    print("\n📁 Loading sector info cache...")
    sector_cache = load_sector_cache()
    initial_cache_size = len(sector_cache)
    
    # Analyze stocks
    universe = UNIVERSE[:100] if quick_mode else UNIVERSE
    print(f"\n🔍 Analyzing {len(universe)} stocks...")
    
    stock_data = []
    for i, ticker in enumerate(universe):
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(universe)} stocks...")
        
        result = analyze_stock(ticker, sector_cache)
        if result:
            stock_data.append(result)
    
    print(f"✅ Analyzed {len(stock_data)} stocks successfully")
    
    # Save updated sector cache
    if len(sector_cache) > initial_cache_size:
        print(f"💾 Saving sector cache ({len(sector_cache)} stocks)...")
        save_sector_cache(sector_cache)
    
    # Group by sector
    print("\n📊 Analyzing sectors...")
    sector_groups = defaultdict(list)
    for stock in stock_data:
        sector = stock.get('sector', 'Unknown')
        sector_groups[sector].append(stock)
    
    sector_analysis = {}
    for sector, stocks in sector_groups.items():
        if sector != 'Unknown':
            sector_analysis[sector] = analyze_sector(sector, stocks)
    
    # Market breadth
    print("\n📏 Calculating market breadth...")
    breadth = calculate_breadth_metrics(stock_data)
    
    # VIX
    print("\n😰 Fetching VIX data...")
    vix = get_vix_info()
    
    # SPY levels
    print("\n📈 Getting SPY levels...")
    spy = get_spy_levels()
    
    # Generate weekly report
    print("\n📝 Generating weekly report...")
    report = generate_weekly_report(stock_data, sector_analysis, breadth, vix, spy)
    
    # Print report to console
    print("\n" + report)
    
    # Compile full output
    output = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_stocks': len(stock_data),
            'bullish_count': sum(1 for s in stock_data if s.get('is_bullish', False)),
            'bearish_count': sum(1 for s in stock_data if s.get('is_bearish', False)),
            'in_daily_squeeze': sum(1 for s in stock_data if s.get('daily_squeeze_on', False)),
            'in_weekly_squeeze': sum(1 for s in stock_data if s.get('weekly_squeeze_on', False)),
            'full_continuity_bullish': len([s for s in stock_data if s.get('full_continuity') and s.get('continuity_direction') == 'BULLISH']),
            'full_continuity_bearish': len([s for s in stock_data if s.get('full_continuity') and s.get('continuity_direction') == 'BEARISH']),
        },
        'breadth': breadth,
        'vix': vix,
        'spy': spy,
        'sectors': sector_analysis,
        'stocks': stock_data,
        'top_setups': sorted(
            [s for s in stock_data if s.get('is_bullish', False) and 
             (s.get('weekly_squeeze_on', False) or s.get('full_continuity', False))],
            key=lambda x: (-x.get('continuity_score', 0), -x.get('weekly_squeeze_score', 0), -x.get('perf_3m', 0))
        )[:20],
        'full_continuity': {
            'bullish': [s['ticker'] for s in stock_data if s.get('full_continuity') and s.get('continuity_direction') == 'BULLISH'],
            'bearish': [s['ticker'] for s in stock_data if s.get('full_continuity') and s.get('continuity_direction') == 'BEARISH'],
        }
    }
    
    # Save JSON
    json_path = os.path.join(SCRIPT_DIR, 'market_outlook.json')
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n💾 Saved JSON to {json_path}")
    
    # Save markdown report
    md_path = os.path.join(SCRIPT_DIR, 'market_outlook.md')
    with open(md_path, 'w') as f:
        f.write(report)
    print(f"💾 Saved report to {md_path}")
    
    # Generate HTML sections
    html_sections = generate_html_sections(stock_data, sector_analysis, breadth, vix, spy)
    
    print("\n" + "=" * 60)
    print("  ✅ MARKET OUTLOOK COMPLETE")
    print("=" * 60)
    
    return output, html_sections


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Market Outlook Analysis')
    parser.add_argument('--quick', action='store_true', help='Quick mode (100 stocks)')
    args = parser.parse_args()
    
    run_market_outlook(quick_mode=args.quick)
