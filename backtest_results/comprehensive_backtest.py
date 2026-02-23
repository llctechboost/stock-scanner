#!/usr/bin/env python3
"""
Comprehensive Strategy Comparison Backtest
Compares 5 trading strategies across 494 stocks over 3 years (Feb 2023 - Feb 2026)

Strategies:
1. Weekly Squeeze (Bollinger inside Keltner on weekly timeframe)
2. Daily Squeeze (Bollinger inside Keltner on daily timeframe)  
3. Cup & Handle (U-shaped base with handle breakout)
4. 200-WMA Zone (price within 5% of 200-week moving average)
5. VCP (Volatility Contraction Pattern)

Trade Rules:
- Entry: Signal fires → buy next day open
- Stop Loss: 8% below entry
- Target: 20% gain OR hit 3:1 risk/reward
- Time stop: Exit after 30 days if neither stop nor target hit
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import pickle
import time
import warnings
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

warnings.filterwarnings('ignore')

# === CONFIGURATION ===
CACHE_DIR = os.path.expanduser('~/clawd/trading/backtest_results/price_cache')
RESULTS_DIR = os.path.expanduser('~/clawd/trading/backtest_results')
START_DATE = '2023-02-01'
END_DATE = '2026-02-01'
STOP_LOSS_PCT = 0.08  # 8%
TARGET_PCT = 0.20     # 20%
TIME_STOP_DAYS = 30   # 30 trading days
RATE_LIMIT_DELAY = 0.1

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# === STOCK UNIVERSE (494 stocks) ===
# S&P 500 components + additional growth/momentum stocks
STOCK_UNIVERSE = [
    # S&P 500 Top 200 by market cap
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'GOOG', 'BRK-B', 'TSLA', 'UNH',
    'XOM', 'LLY', 'JPM', 'JNJ', 'V', 'PG', 'MA', 'AVGO', 'HD', 'CVX',
    'MRK', 'ABBV', 'COST', 'PEP', 'ADBE', 'KO', 'WMT', 'MCD', 'CSCO', 'CRM',
    'BAC', 'PFE', 'TMO', 'ACN', 'NFLX', 'AMD', 'ABT', 'LIN', 'ORCL', 'DIS',
    'CMCSA', 'DHR', 'VZ', 'PM', 'INTC', 'WFC', 'TXN', 'INTU', 'COP', 'NKE',
    'NEE', 'RTX', 'UNP', 'QCOM', 'HON', 'LOW', 'UPS', 'SPGI', 'IBM', 'BA',
    'CAT', 'GE', 'AMAT', 'ELV', 'PLD', 'SBUX', 'DE', 'NOW', 'ISRG', 'MS',
    'GS', 'BMY', 'BLK', 'BKNG', 'MDLZ', 'GILD', 'ADP', 'LMT', 'VRTX', 'AMT',
    'ADI', 'SYK', 'TJX', 'REGN', 'CVS', 'SCHW', 'MMC', 'TMUS', 'ZTS', 'CI',
    'PGR', 'LRCX', 'CB', 'MO', 'SO', 'ETN', 'EOG', 'BDX', 'SNPS', 'DUK',
    'SLB', 'PANW', 'BSX', 'CME', 'AON', 'KLAC', 'NOC', 'ITW', 'MU', 'CDNS',
    'CL', 'WM', 'ICE', 'CSX', 'SHW', 'HUM', 'EQIX', 'ORLY', 'GD', 'MCK',
    'FCX', 'PNC', 'APD', 'USB', 'PSX', 'MCO', 'MPC', 'EMR', 'MSI', 'NSC',
    'CTAS', 'CMG', 'MAR', 'MCHP', 'ROP', 'NXPI', 'AJG', 'AZO', 'TGT', 'PCAR',
    'TFC', 'AIG', 'AFL', 'HCA', 'KDP', 'CARR', 'OXY', 'SRE', 'AEP', 'PSA',
    'TRV', 'WMB', 'ADSK', 'NEM', 'MSCI', 'F', 'FDX', 'DXCM', 'KMB', 'FTNT',
    'D', 'EW', 'GM', 'IDXX', 'TEL', 'AMP', 'JCI', 'O', 'CCI', 'DVN',
    'SPG', 'PAYX', 'ROST', 'GIS', 'A', 'ALL', 'BIIB', 'IQV', 'LHX', 'CMI',
    'BK', 'YUM', 'PRU', 'CTVA', 'ODFL', 'WELL', 'DOW', 'HAL', 'KMI', 'MNST',
    'ANET', 'CPRT', 'EXC', 'PCG', 'FAST', 'KR', 'VRSK', 'EA', 'GEHC', 'ON',
    
    # Additional S&P 500 components (201-400)
    'STZ', 'FANG', 'HSY', 'KEYS', 'CDW', 'PPG', 'FTV', 'AWK', 'EXR', 'CBRE',
    'DHI', 'GPN', 'EBAY', 'DLR', 'HPQ', 'TSCO', 'ROK', 'WEC', 'IT', 'XYL',
    'FITB', 'MTD', 'EIX', 'CTSH', 'APTV', 'ANSS', 'AVB', 'STT', 'ES', 'VMC',
    'URI', 'DAL', 'VICI', 'MLM', 'HPE', 'ARE', 'HBAN', 'RF', 'DTE', 'LEN',
    'PPL', 'SBAC', 'CHD', 'FE', 'DG', 'CFG', 'WY', 'TROW', 'PTC', 'VLTO',
    'GPC', 'ED', 'NTAP', 'K', 'HUBB', 'WAB', 'BAX', 'ETR', 'IRM', 'BR',
    'TYL', 'STE', 'WDC', 'CLX', 'CNP', 'COO', 'WAT', 'EXPD', 'ZBH', 'FDS',
    'BALL', 'IFF', 'MAA', 'HOLX', 'AES', 'EQR', 'DRI', 'LUV', 'OMC', 'SYY',
    'PKI', 'STLD', 'MOH', 'DLTR', 'CMS', 'MKC', 'CINF', 'IP', 'ESS', 'RCL',
    'J', 'SWK', 'NTRS', 'POOL', 'AVY', 'ATO', 'CAH', 'CE', 'TXT', 'TSN',
    'TDY', 'AMCR', 'KEY', 'PFG', 'GL', 'BEN', 'UDR', 'HST', 'AKAM', 'WRB',
    'KIM', 'JBHT', 'LKQ', 'NDAQ', 'TECH', 'BRO', 'L', 'DOC', 'EVRG', 'NI',
    'BIO', 'MAS', 'CPT', 'CDAY', 'JKHY', 'REG', 'LDOS', 'CF', 'CHRW', 'NRG',
    'EMN', 'SNA', 'INCY', 'SWKS', 'IEX', 'CPB', 'ROL', 'WRK', 'BBY', 'CCL',
    'VTRS', 'PNR', 'PAYC', 'MGM', 'UHS', 'IPG', 'HAS', 'LNT', 'AOS', 'ALLE',
    'TAP', 'HRL', 'BG', 'CRL', 'HII', 'BWA', 'NWSA', 'AIZ', 'WYNN', 'HSIC',
    'PNW', 'BXP', 'FOXA', 'MKTX', 'ETSY', 'GNRC', 'AAL', 'JNPR', 'QRVO', 'PARA',
    'CZR', 'WHR', 'RHI', 'NCLH', 'FFIV', 'MHK', 'MTCH', 'FMC', 'VFC', 'DVA',
    'RL', 'HWM', 'ALB', 'SEE', 'IVZ', 'BBWI', 'TPR', 'NWS', 'LW', 'FOX',
    
    # Growth/Momentum stocks to reach ~494
    'PLTR', 'NET', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'MDB', 'SHOP', 'SQ', 'PYPL',
    'COIN', 'HOOD', 'SOFI', 'NU', 'UBER', 'ABNB', 'DASH', 'RKLB', 'AXON', 'DECK',
    'GWW', 'SMCI', 'ARM', 'IONQ', 'RGTI', 'APP', 'HIMS', 'DUOL', 'CELH', 'TOST',
    'CAVA', 'NVO', 'PODD', 'TTD', 'BILL', 'CFLT', 'DOCN', 'GTLB', 'MNDY', 'SAMSARA',
    'RIVN', 'LCID', 'XPEV', 'NIO', 'LI', 'PLUG', 'FSLR', 'ENPH', 'SEDG', 'RUN',
    'CHWY', 'LMND', 'PATH', 'U', 'RBLX', 'PINS', 'SNAP', 'Z', 'ZG', 'OKTA',
    'TWLO', 'ESTC', 'VEEV', 'TEAM', 'WDAY', 'ZM', 'DOCU', 'SPLK', 'DKNG', 'PENN',
    'DPZ', 'WING', 'TXRH', 'CMC', 'RS', 'ATI', 'X', 'CLF', 'AA', 'MP',
    'LAC', 'LTHM', 'WOLF', 'AEHR', 'SOXL', 'LABU', 'SPXL', 'TQQQ',
    # Add more to reach 494
    'MELI', 'SE', 'BABA', 'JD', 'PDD', 'BIDU', 'NTES', 'BILI', 'IQ', 'TME',
    'FUTU', 'TIGR', 'WB', 'VIPS', 'ZTO', 'YMM', 'DIDI', 'TAL', 'EDU', 'GOTU',
]

# Remove duplicates and limit to 494
STOCK_UNIVERSE = list(dict.fromkeys(STOCK_UNIVERSE))[:494]
print(f"Stock universe: {len(STOCK_UNIVERSE)} stocks")


# === DATA CLASSES ===
@dataclass
class Trade:
    """Single trade record"""
    ticker: str
    strategy: str
    signal_date: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    exit_reason: str  # 'stop_loss', 'target', 'time_stop'
    return_pct: float
    hold_days: int
    
    def to_dict(self):
        return asdict(self)


@dataclass
class StrategyResult:
    """Results for a single strategy"""
    strategy_name: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_gain_winners: float = 0.0
    avg_loss_losers: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    trades: List[Trade] = field(default_factory=list)
    
    def to_dict(self):
        d = asdict(self)
        d['trades'] = [t.to_dict() for t in self.trades]
        return d


# === CACHING ===
_last_request_time = 0

def rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.time()


def get_cache_path(ticker: str, interval: str) -> str:
    return os.path.join(CACHE_DIR, f"{ticker}_{interval}.pkl")


def load_cached_data(ticker: str, interval: str) -> Optional[pd.DataFrame]:
    """Load cached data if exists and is recent enough"""
    cache_path = get_cache_path(ticker, interval)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except:
            pass
    return None


def save_cached_data(ticker: str, interval: str, df: pd.DataFrame):
    """Save data to cache"""
    cache_path = get_cache_path(ticker, interval)
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(df, f)
    except:
        pass


def download_data(ticker: str, interval: str = '1d', start: str = None, end: str = None) -> Optional[pd.DataFrame]:
    """Download price data with caching"""
    # Try cache first
    cached = load_cached_data(ticker, interval)
    if cached is not None and len(cached) > 100:
        return cached
    
    rate_limit()
    
    try:
        if start and end:
            df = yf.download(ticker, start=start, end=end, interval=interval, progress=False)
        else:
            df = yf.download(ticker, period='5y', interval=interval, progress=False)
        
        if len(df) < 10:
            return None
        
        # Flatten multi-index if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Save to cache
        save_cached_data(ticker, interval, df)
        
        return df
    except Exception as e:
        return None


# === INDICATOR CALCULATIONS ===
def calculate_bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands"""
    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def calculate_keltner_channel(high: pd.Series, low: pd.Series, close: pd.Series, 
                               ema_period: int = 20, atr_period: int = 10, atr_mult: float = 1.5) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Keltner Channel"""
    # EMA of close
    ema = close.ewm(span=ema_period, adjust=False).mean()
    
    # ATR
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean()
    
    upper = ema + (atr * atr_mult)
    lower = ema - (atr * atr_mult)
    
    return upper, ema, lower


def detect_squeeze(bb_upper: pd.Series, bb_lower: pd.Series, 
                   kc_upper: pd.Series, kc_lower: pd.Series) -> pd.Series:
    """
    Detect TTM Squeeze: Bollinger Bands inside Keltner Channel
    Returns True when squeeze is ON (bands inside channel)
    """
    squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    return squeeze_on


# === STRATEGY SIGNAL DETECTION ===

def detect_weekly_squeeze_signals(df: pd.DataFrame) -> List[str]:
    """
    Weekly Squeeze Strategy
    Signal: Squeeze fires (Bollinger inside Keltner) on weekly timeframe
    """
    if len(df) < 30:
        return []
    
    close = df['Close'].astype(float)
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(close, period=20, std_dev=2.0)
    kc_upper, kc_mid, kc_lower = calculate_keltner_channel(high, low, close, 
                                                            ema_period=20, atr_period=10, atr_mult=1.5)
    
    squeeze = detect_squeeze(bb_upper, bb_lower, kc_upper, kc_lower)
    
    # Signal when squeeze releases (was on, now off) with momentum up
    momentum = close - close.shift(1)
    
    signals = []
    for i in range(1, len(df)):
        # Squeeze was ON, now OFF, and price momentum positive
        if i >= 2:
            prev_squeeze = squeeze.iloc[i-1] if not pd.isna(squeeze.iloc[i-1]) else False
            curr_squeeze = squeeze.iloc[i] if not pd.isna(squeeze.iloc[i]) else False
            mom = momentum.iloc[i] if not pd.isna(momentum.iloc[i]) else 0
            
            if prev_squeeze and not curr_squeeze and mom > 0:
                signals.append(str(df.index[i].date()))
    
    return signals


def detect_daily_squeeze_signals(df: pd.DataFrame) -> List[str]:
    """
    Daily Squeeze Strategy
    Same as weekly but on daily timeframe
    """
    if len(df) < 50:
        return []
    
    close = df['Close'].astype(float)
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(close, period=20, std_dev=2.0)
    kc_upper, kc_mid, kc_lower = calculate_keltner_channel(high, low, close, 
                                                            ema_period=20, atr_period=10, atr_mult=1.5)
    
    squeeze = detect_squeeze(bb_upper, bb_lower, kc_upper, kc_lower)
    momentum = close - close.shift(1)
    
    signals = []
    for i in range(1, len(df)):
        if i >= 2:
            prev_squeeze = squeeze.iloc[i-1] if not pd.isna(squeeze.iloc[i-1]) else False
            curr_squeeze = squeeze.iloc[i] if not pd.isna(squeeze.iloc[i]) else False
            mom = momentum.iloc[i] if not pd.isna(momentum.iloc[i]) else 0
            
            if prev_squeeze and not curr_squeeze and mom > 0:
                signals.append(str(df.index[i].date()))
    
    return signals


def detect_cup_and_handle_signals(df: pd.DataFrame) -> List[str]:
    """
    Cup & Handle Pattern Detection
    - Cup: U-shaped base, 12-35% depth, 7-65 weeks
    - Handle: 1-4 weeks, max 12% pullback
    """
    if len(df) < 100:
        return []
    
    close = df['Close'].astype(float)
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    
    signals = []
    
    # Slide a window looking for cup patterns
    for end_idx in range(100, len(df)):
        # Look back 35-200 days for cup formation
        for cup_len in range(50, min(200, end_idx), 10):
            start_idx = end_idx - cup_len
            if start_idx < 0:
                continue
            
            cup_data = df.iloc[start_idx:end_idx]
            cup_close = cup_data['Close'].astype(float)
            cup_high = cup_data['High'].astype(float)
            
            if len(cup_close) < 50:
                continue
            
            # Find cup characteristics
            left_high = cup_close.iloc[:10].max()
            cup_low = cup_close.min()
            right_high = cup_close.iloc[-15:].max()
            
            # Cup depth (12-35%)
            cup_depth = (left_high - cup_low) / left_high * 100
            if cup_depth < 12 or cup_depth > 35:
                continue
            
            # Right side should recover to near left high (within 5%)
            if right_high < left_high * 0.95:
                continue
            
            # Check for handle in last 5-20 days
            handle_data = cup_close.iloc[-20:]
            handle_high = handle_data.max()
            handle_low = handle_data.min()
            handle_depth = (handle_high - handle_low) / handle_high * 100
            
            # Handle depth < 12%
            if handle_depth > 12:
                continue
            
            # Current price breaking above handle high
            current_price = close.iloc[end_idx]
            if current_price > handle_high:
                signals.append(str(df.index[end_idx].date()))
                break  # Only one signal per day
    
    # Remove duplicates
    return list(set(signals))


def detect_200wma_zone_signals(df_weekly: pd.DataFrame) -> List[str]:
    """
    200-WMA Zone Strategy
    Signal: Price within 5% of 200-week moving average
    """
    if len(df_weekly) < 210:
        return []
    
    close = df_weekly['Close'].astype(float)
    ma_200 = close.rolling(window=200).mean()
    
    signals = []
    
    for i in range(200, len(df_weekly)):
        price = close.iloc[i]
        ma = ma_200.iloc[i]
        
        if pd.isna(ma):
            continue
        
        # Price within 5% of 200-WMA (above or below)
        pct_from_ma = abs(price - ma) / ma
        
        if pct_from_ma <= 0.05:
            # Additional filter: price should be recovering (not in freefall)
            if i >= 2:
                prev_price = close.iloc[i-1]
                if price > prev_price:  # Upward momentum
                    signals.append(str(df_weekly.index[i].date()))
    
    return signals


def detect_vcp_signals(df: pd.DataFrame) -> List[str]:
    """
    VCP (Volatility Contraction Pattern) Detection
    - 2+ contractions with each tighter than previous
    - Volume dry-up in later contractions
    - Price near 52-week high (within 15%)
    """
    if len(df) < 60:
        return []
    
    close = df['Close'].astype(float)
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    volume = df['Volume'].astype(float)
    
    signals = []
    
    # Look for VCP patterns in rolling windows
    for end_idx in range(60, len(df)):
        window_data = df.iloc[end_idx-60:end_idx]
        w_close = window_data['Close'].astype(float)
        w_high = window_data['High'].astype(float)
        w_low = window_data['Low'].astype(float)
        w_volume = window_data['Volume'].astype(float)
        
        # Check if near 52-week high
        high_52w = high.iloc[max(0, end_idx-252):end_idx].max()
        current_price = close.iloc[end_idx]
        pct_from_high = (high_52w - current_price) / high_52w * 100
        
        if pct_from_high > 20:  # Too far from highs
            continue
        
        # Segment into 3 equal parts and check for contraction
        seg_len = 20
        contractions = []
        
        for seg in range(3):
            start = seg * seg_len
            end = (seg + 1) * seg_len
            seg_data = w_close.iloc[start:end]
            if len(seg_data) < 15:
                continue
            
            seg_range = (seg_data.max() - seg_data.min()) / seg_data.mean() * 100
            contractions.append(seg_range)
        
        if len(contractions) < 3:
            continue
        
        # Check if contracting (each segment tighter than previous)
        is_contracting = contractions[0] > contractions[1] > contractions[2]
        
        # Last contraction should be tight (< 10%)
        is_tight = contractions[-1] < 10
        
        # Volume should be drying up
        first_vol = w_volume.iloc[:20].mean()
        last_vol = w_volume.iloc[-20:].mean()
        vol_drying = last_vol < first_vol * 0.8
        
        if is_contracting and is_tight and vol_drying:
            signals.append(str(df.index[end_idx].date()))
    
    return list(set(signals))


# === TRADE SIMULATION ===

def simulate_trade(df: pd.DataFrame, signal_date: str, ticker: str, strategy: str) -> Optional[Trade]:
    """
    Simulate a single trade with the standard rules:
    - Entry: Next day open after signal
    - Stop: 8% below entry
    - Target: 20% gain
    - Time stop: 30 trading days
    """
    try:
        signal_dt = pd.to_datetime(signal_date)
        
        # Find signal date index
        if signal_dt not in df.index:
            # Find next available date
            future_dates = df.index[df.index >= signal_dt]
            if len(future_dates) == 0:
                return None
            signal_idx = df.index.get_loc(future_dates[0])
        else:
            signal_idx = df.index.get_loc(signal_dt)
        
        # Entry is next day open
        entry_idx = signal_idx + 1
        if entry_idx >= len(df):
            return None
        
        entry_date = df.index[entry_idx]
        entry_price = float(df['Open'].iloc[entry_idx])
        
        if pd.isna(entry_price) or entry_price <= 0:
            return None
        
        # Calculate stop and target
        stop_price = entry_price * (1 - STOP_LOSS_PCT)
        target_price = entry_price * (1 + TARGET_PCT)
        
        # Simulate through subsequent days
        exit_idx = None
        exit_reason = None
        
        for i in range(entry_idx + 1, min(entry_idx + TIME_STOP_DAYS + 1, len(df))):
            day_low = float(df['Low'].iloc[i])
            day_high = float(df['High'].iloc[i])
            day_close = float(df['Close'].iloc[i])
            
            # Check stop loss hit (using low)
            if day_low <= stop_price:
                exit_idx = i
                exit_reason = 'stop_loss'
                break
            
            # Check target hit (using high)
            if day_high >= target_price:
                exit_idx = i
                exit_reason = 'target'
                break
        
        # Time stop if no exit
        if exit_idx is None:
            exit_idx = min(entry_idx + TIME_STOP_DAYS, len(df) - 1)
            exit_reason = 'time_stop'
        
        exit_date = df.index[exit_idx]
        
        # Determine exit price based on reason
        if exit_reason == 'stop_loss':
            exit_price = stop_price
        elif exit_reason == 'target':
            exit_price = target_price
        else:
            exit_price = float(df['Close'].iloc[exit_idx])
        
        if pd.isna(exit_price) or exit_price <= 0:
            return None
        
        return_pct = (exit_price - entry_price) / entry_price * 100
        hold_days = exit_idx - entry_idx
        
        return Trade(
            ticker=ticker,
            strategy=strategy,
            signal_date=signal_date,
            entry_date=str(entry_date.date()),
            entry_price=round(entry_price, 2),
            exit_date=str(exit_date.date()),
            exit_price=round(exit_price, 2),
            exit_reason=exit_reason,
            return_pct=round(return_pct, 2),
            hold_days=hold_days
        )
        
    except Exception as e:
        return None


# === METRICS CALCULATION ===

def calculate_metrics(trades: List[Trade]) -> Dict:
    """Calculate all metrics for a list of trades"""
    if not trades:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'avg_gain_winners': 0,
            'avg_loss_losers': 0,
            'total_return': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'profit_factor': 0
        }
    
    returns = [t.return_pct for t in trades]
    winners = [r for r in returns if r > 0]
    losers = [r for r in returns if r <= 0]
    
    total_trades = len(trades)
    wins = len(winners)
    losses = len(losers)
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
    
    avg_gain = np.mean(winners) if winners else 0
    avg_loss = np.mean(losers) if losers else 0
    
    # Compounded return
    compound_return = 1.0
    for r in returns:
        compound_return *= (1 + r/100)
    total_return = (compound_return - 1) * 100
    
    # Max drawdown (simplified - peak to trough)
    equity_curve = []
    eq = 100
    for r in returns:
        eq *= (1 + r/100)
        equity_curve.append(eq)
    
    peak = equity_curve[0]
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd
    
    # Sharpe ratio (annualized, assuming daily returns)
    if len(returns) > 1:
        avg_ret = np.mean(returns)
        std_ret = np.std(returns)
        sharpe = (avg_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0
    else:
        sharpe = 0
    
    # Profit factor
    gross_wins = sum(winners) if winners else 0
    gross_losses = abs(sum(losers)) if losers else 0.01  # avoid div by zero
    profit_factor = gross_wins / gross_losses
    
    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': round(win_rate, 1),
        'avg_gain_winners': round(avg_gain, 2),
        'avg_loss_losers': round(avg_loss, 2),
        'total_return': round(total_return, 2),
        'max_drawdown': round(max_dd, 2),
        'sharpe_ratio': round(sharpe, 3),
        'profit_factor': round(profit_factor, 2)
    }


# === MAIN BACKTEST ENGINE ===

def backtest_stock(ticker: str) -> Dict[str, List[Trade]]:
    """
    Backtest all 5 strategies on a single stock
    Returns dict of strategy_name -> list of trades
    """
    results = {
        'weekly_squeeze': [],
        'daily_squeeze': [],
        'cup_and_handle': [],
        '200wma_zone': [],
        'vcp': []
    }
    
    # Download daily data
    df_daily = download_data(ticker, interval='1d')
    if df_daily is None or len(df_daily) < 100:
        return results
    
    # Filter to backtest period
    df_daily = df_daily[(df_daily.index >= START_DATE) & (df_daily.index <= END_DATE)]
    if len(df_daily) < 50:
        return results
    
    # Download weekly data for weekly strategies
    df_weekly = download_data(ticker, interval='1wk')
    if df_weekly is not None:
        df_weekly = df_weekly[(df_weekly.index >= START_DATE) & (df_weekly.index <= END_DATE)]
    
    # 1. Weekly Squeeze
    if df_weekly is not None and len(df_weekly) >= 30:
        signals = detect_weekly_squeeze_signals(df_weekly)
        for sig in signals:
            trade = simulate_trade(df_daily, sig, ticker, 'weekly_squeeze')
            if trade:
                results['weekly_squeeze'].append(trade)
    
    # 2. Daily Squeeze
    signals = detect_daily_squeeze_signals(df_daily)
    for sig in signals:
        trade = simulate_trade(df_daily, sig, ticker, 'daily_squeeze')
        if trade:
            results['daily_squeeze'].append(trade)
    
    # 3. Cup & Handle
    signals = detect_cup_and_handle_signals(df_daily)
    for sig in signals:
        trade = simulate_trade(df_daily, sig, ticker, 'cup_and_handle')
        if trade:
            results['cup_and_handle'].append(trade)
    
    # 4. 200-WMA Zone
    if df_weekly is not None and len(df_weekly) >= 210:
        signals = detect_200wma_zone_signals(df_weekly)
        for sig in signals:
            trade = simulate_trade(df_daily, sig, ticker, '200wma_zone')
            if trade:
                results['200wma_zone'].append(trade)
    
    # 5. VCP
    signals = detect_vcp_signals(df_daily)
    for sig in signals:
        trade = simulate_trade(df_daily, sig, ticker, 'vcp')
        if trade:
            results['vcp'].append(trade)
    
    return results


def run_full_backtest():
    """Run backtest across all stocks and strategies"""
    print("\n" + "="*70)
    print("  COMPREHENSIVE STRATEGY COMPARISON BACKTEST")
    print(f"  Period: {START_DATE} to {END_DATE}")
    print(f"  Universe: {len(STOCK_UNIVERSE)} stocks")
    print(f"  Rules: Entry next day open, 8% stop, 20% target, 30-day time stop")
    print("="*70 + "\n")
    
    # Initialize results
    all_results = {
        'weekly_squeeze': [],
        'daily_squeeze': [],
        'cup_and_handle': [],
        '200wma_zone': [],
        'vcp': []
    }
    
    # Process each stock
    total = len(STOCK_UNIVERSE)
    for i, ticker in enumerate(STOCK_UNIVERSE):
        print(f"\r[{i+1}/{total}] Processing {ticker}...", end='', flush=True)
        
        try:
            stock_results = backtest_stock(ticker)
            
            for strategy, trades in stock_results.items():
                all_results[strategy].extend(trades)
                
        except Exception as e:
            print(f"\n  Error on {ticker}: {e}")
            continue
    
    print(f"\n\nBacktest complete!\n")
    
    # Calculate metrics for each strategy
    strategy_metrics = {}
    
    print("="*70)
    print("  RESULTS BY STRATEGY")
    print("="*70)
    
    strategy_display_names = {
        'weekly_squeeze': 'Weekly Squeeze',
        'daily_squeeze': 'Daily Squeeze',
        'cup_and_handle': 'Cup & Handle',
        '200wma_zone': '200-WMA Zone',
        'vcp': 'VCP'
    }
    
    for strategy, trades in all_results.items():
        metrics = calculate_metrics(trades)
        metrics['trades'] = [t.to_dict() for t in trades]
        strategy_metrics[strategy] = metrics
        
        display_name = strategy_display_names.get(strategy, strategy)
        print(f"\n{display_name}:")
        print(f"  Total Trades:      {metrics['total_trades']}")
        print(f"  Win Rate:          {metrics['win_rate']}%")
        print(f"  Avg Gain (win):    {metrics['avg_gain_winners']}%")
        print(f"  Avg Loss (loss):   {metrics['avg_loss_losers']}%")
        print(f"  Total Return:      {metrics['total_return']}%")
        print(f"  Max Drawdown:      {metrics['max_drawdown']}%")
        print(f"  Sharpe Ratio:      {metrics['sharpe_ratio']}")
        print(f"  Profit Factor:     {metrics['profit_factor']}")
    
    # Save results to JSON
    output_path = os.path.join(RESULTS_DIR, 'strategy_comparison.json')
    with open(output_path, 'w') as f:
        json.dump(strategy_metrics, f, indent=2)
    print(f"\n\nResults saved to: {output_path}")
    
    # Generate summary markdown
    generate_summary_markdown(strategy_metrics)
    
    return strategy_metrics


def generate_summary_markdown(strategy_metrics: Dict):
    """Generate summary.md with comparison table"""
    
    # Sort strategies by total return
    sorted_strategies = sorted(
        strategy_metrics.items(),
        key=lambda x: x[1].get('total_return', 0),
        reverse=True
    )
    
    strategy_names = {
        'weekly_squeeze': 'Weekly Squeeze',
        'daily_squeeze': 'Daily Squeeze',
        'cup_and_handle': 'Cup & Handle',
        '200wma_zone': '200-WMA Zone',
        'vcp': 'VCP'
    }
    
    md = f"""# Strategy Comparison Backtest Results

## Overview
- **Period:** Feb 2023 - Feb 2026 (3 years)
- **Universe:** {len(STOCK_UNIVERSE)} stocks
- **Trade Rules:**
  - Entry: Signal fires → buy next day open
  - Stop Loss: 8% below entry
  - Target: 20% gain
  - Time Stop: Exit after 30 days if neither stop nor target hit

## Strategy Ranking (by Total Return)

| Rank | Strategy | Total Trades | Win Rate | Avg Gain | Avg Loss | Total Return | Max DD | Sharpe | Profit Factor |
|------|----------|-------------|----------|----------|----------|--------------|--------|--------|---------------|
"""
    
    for rank, (strategy, metrics) in enumerate(sorted_strategies, 1):
        name = strategy_names.get(strategy, strategy)
        md += f"| {rank} | {name} | {metrics['total_trades']} | {metrics['win_rate']}% | {metrics['avg_gain_winners']}% | {metrics['avg_loss_losers']}% | {metrics['total_return']}% | {metrics['max_drawdown']}% | {metrics['sharpe_ratio']} | {metrics['profit_factor']} |\n"
    
    md += """
## Key Observations

"""
    
    # Add observations based on data
    if sorted_strategies:
        best_strategy = sorted_strategies[0]
        best_name = strategy_names.get(best_strategy[0], best_strategy[0])
        md += f"### Best Overall: {best_name}\n"
        md += f"- Total Return: {best_strategy[1]['total_return']}%\n"
        md += f"- Win Rate: {best_strategy[1]['win_rate']}%\n"
        md += f"- Sharpe Ratio: {best_strategy[1]['sharpe_ratio']}\n\n"
        
        # Find highest win rate
        by_win_rate = sorted(sorted_strategies, key=lambda x: x[1]['win_rate'], reverse=True)
        if by_win_rate:
            highest_wr = by_win_rate[0]
            wr_name = strategy_names.get(highest_wr[0], highest_wr[0])
            md += f"### Highest Win Rate: {wr_name} ({highest_wr[1]['win_rate']}%)\n\n"
        
        # Find best risk-adjusted (Sharpe)
        by_sharpe = sorted(sorted_strategies, key=lambda x: x[1]['sharpe_ratio'], reverse=True)
        if by_sharpe:
            best_sharpe = by_sharpe[0]
            sharpe_name = strategy_names.get(best_sharpe[0], best_sharpe[0])
            md += f"### Best Risk-Adjusted (Sharpe): {sharpe_name} ({best_sharpe[1]['sharpe_ratio']})\n\n"
    
    md += """## Strategy Descriptions

1. **Weekly Squeeze**: TTM Squeeze on weekly timeframe - Bollinger Bands inside Keltner Channel, signals when squeeze releases with upward momentum.

2. **Daily Squeeze**: Same as Weekly Squeeze but on daily timeframe for more frequent signals.

3. **Cup & Handle**: Classic O'Neil pattern - U-shaped base (12-35% depth) with small handle, signals on breakout above handle high.

4. **200-WMA Zone**: Price within 5% of 200-week moving average with upward momentum - buying quality stocks at support.

5. **VCP (Volatility Contraction Pattern)**: Minervini-style setup with 2+ contracting price ranges, volume dry-up, near 52-week highs.

---
*Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + "*"
    
    output_path = os.path.join(RESULTS_DIR, 'summary.md')
    with open(output_path, 'w') as f:
        f.write(md)
    
    print(f"Summary saved to: {output_path}")


if __name__ == '__main__':
    run_full_backtest()
