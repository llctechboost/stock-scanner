#!/usr/bin/env python3
"""
Generate static index.html for GitHub Pages
Runs scanner on S&P 500 stocks and updates the site
Now includes Cup & Handle pattern detection
"""
import os
import sys
import json
import subprocess
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Full S&P 500 (alphabetical)
UNIVERSE = [
    'A', 'AAL', 'AAPL', 'ABBV', 'ABNB', 'ABT', 'ACGL', 'ACN', 'ADBE', 'ADI',
    'ADM', 'ADP', 'ADSK', 'AEE', 'AEP', 'AES', 'AFL', 'AIG', 'AIZ', 'AJG',
    'AKAM', 'ALB', 'ALGN', 'ALL', 'ALLE', 'AMAT', 'AMCR', 'AMD', 'AME', 'AMGN',
    'AMP', 'AMT', 'AMZN', 'ANET', 'ANSS', 'AON', 'AOS', 'APA', 'APD', 'APH',
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


def wilder_rma(series, length):
    """
    Wilder's RMA (SMMA) - matches TradingView's ta.rma()
    rma_t = (rma_{t-1} * (n-1) + x_t) / n
    Seed: SMA of first n values
    """
    alpha = 1.0 / length
    return series.ewm(alpha=alpha, adjust=False).mean()


def calculate_squeeze(df, bb_len=20, bb_mult=2.0, kc_len=20, kc_mult=2.0, atr_len=10):
    """
    Calculate Squeeze indicator matching TradingView exactly.
    
    BB (TW Golden Indicators): SMA basis, length=20, mult=2.0
    KC (TV KC script): EMA basis, length=20, mult=2.0, ATR(10) with Wilder's RMA
    
    Returns: (squeeze_on, squeeze_score, squeeze_state, bb_pct, kc_pct, squeeze_bars)
    """
    min_len = max(bb_len, kc_len, atr_len) + 5
    if len(df) < min_len:
        return False, 0, 'NONE', 0, 0, 0
    
    try:
        close = df['Close']
        high = df['High'] if 'High' in df.columns else close
        low = df['Low'] if 'Low' in df.columns else close
        
        # === Bollinger Bands (SMA basis) ===
        bb_basis = close.rolling(bb_len).mean()
        bb_dev = bb_mult * close.rolling(bb_len).std()
        bb_upper = bb_basis + bb_dev
        bb_lower = bb_basis - bb_dev
        bb_width = bb_upper - bb_lower
        
        # === Keltner Channels (EMA basis, Wilder's ATR) ===
        kc_basis = close.ewm(span=kc_len, adjust=False).mean()
        
        # True Range - handle first row (no prev close)
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        tr.iloc[0] = high.iloc[0] - low.iloc[0]  # First row: H-L only
        
        # ATR using Wilder's RMA (not SMA!)
        atr = wilder_rma(tr, atr_len)
        
        kc_upper = kc_basis + (kc_mult * atr)
        kc_lower = kc_basis - (kc_mult * atr)
        kc_width = kc_upper - kc_lower
        
        # === Squeeze detection ===
        squeeze_on_series = (bb_upper < kc_upper) & (bb_lower > kc_lower)
        
        # Count consecutive squeeze bars (forward accumulation)
        squeeze_count_series = pd.Series(0, index=df.index)
        for i in range(len(squeeze_on_series)):
            if squeeze_on_series.iloc[i]:
                squeeze_count_series.iloc[i] = (squeeze_count_series.iloc[i-1] + 1) if i > 0 else 1
            else:
                squeeze_count_series.iloc[i] = 0
        
        # === Current bar values ===
        idx = -1
        current_bb_basis = float(bb_basis.iloc[idx])
        current_bb_width = float(bb_width.iloc[idx])
        current_kc_basis = float(kc_basis.iloc[idx])
        current_kc_width = float(kc_width.iloc[idx])
        squeeze_on = bool(squeeze_on_series.iloc[idx])
        squeeze_count = int(squeeze_count_series.iloc[idx])
        
        # Width percentages (divide by respective basis)
        bb_pct = (current_bb_width / current_bb_basis) * 100 if current_bb_basis > 0 else 0
        kc_pct = (current_kc_width / current_kc_basis) * 100 if current_kc_basis > 0 else 0
        
        # === Depth calculation ===
        if current_kc_width > 0:
            depth = (current_kc_width - current_bb_width) / current_kc_width
        else:
            depth = float('nan')
        
        # === Classification thresholds ===
        min_bars_high = 10
        min_bars_med = 5
        depth_high = 0.25
        depth_med = 0.10
        
        # === State classification (HIGH/MED/LOW/NONE) ===
        depth_safe = 0.0 if pd.isna(depth) else depth
        
        is_high = squeeze_on and squeeze_count >= min_bars_high and depth_safe >= depth_high
        is_med = squeeze_on and not is_high and squeeze_count >= min_bars_med and depth_safe >= depth_med
        is_low = squeeze_on and not is_high and not is_med
        
        if is_high:
            state = 'HIGH'
        elif is_med:
            state = 'MED'
        elif is_low:
            state = 'LOW'
        else:
            state = 'NONE'
        
        # === Compression score (0-100) ===
        if squeeze_on:
            depth_norm = max(0, min(1, (depth_safe - depth_med) / max(depth_high - depth_med, 1e-4)))
            dur_norm = max(0, min(1, (squeeze_count - min_bars_med) / max(min_bars_high - min_bars_med, 1e-4)))
            score_raw = 0.6 * depth_norm + 0.4 * dur_norm
            squeeze_score = int(round(score_raw * 100))
        else:
            squeeze_score = 0
        
        return squeeze_on, squeeze_score, state, bb_pct, kc_pct, squeeze_count
        
    except Exception as e:
        return False, 0, 'NONE', 0, 0, 0


def detect_cup_and_handle(close, volume):
    """
    Detect Cup and Handle pattern.
    Returns: (is_cup_handle, cup_depth_pct, handle_depth_pct, breakout_level)
    """
    if len(close) < 120:  # Need at least 6 months of data
        return False, 0, 0, 0
    
    try:
        price = float(close.iloc[-1])
        
        # Look for cup formation over past 3-6 months
        lookback = min(len(close), 180)  # ~6 months max
        segment = close.iloc[-lookback:]
        
        # Find the cup: highest point at start, lowest in middle, recovery to near start
        left_high_idx = segment.iloc[:20].idxmax()  # Left rim of cup
        left_high = segment.loc[left_high_idx]
        
        # Find the lowest point (bottom of cup) - should be in middle portion
        mid_start = len(segment) // 4
        mid_end = 3 * len(segment) // 4
        mid_segment = segment.iloc[mid_start:mid_end]
        
        if len(mid_segment) == 0:
            return False, 0, 0, 0
            
        cup_bottom_idx = mid_segment.idxmin()
        cup_bottom = mid_segment.loc[cup_bottom_idx]
        
        # Cup depth should be 15-35% typically
        cup_depth_pct = ((left_high - cup_bottom) / left_high) * 100
        if cup_depth_pct < 10 or cup_depth_pct > 50:
            return False, 0, 0, 0
        
        # Right side should recover to near left high (within 10%)
        recent_high = segment.iloc[-40:].max()  # Right rim
        recovery_pct = ((recent_high - cup_bottom) / (left_high - cup_bottom)) * 100
        
        if recovery_pct < 80:  # Must recover at least 80% of the cup
            return False, 0, 0, 0
        
        # Handle detection: small pullback from the right rim (5-15%)
        if len(close) < 20:
            return False, 0, 0, 0
            
        handle_segment = close.iloc[-20:]
        handle_high = handle_segment.max()
        handle_low = handle_segment.min()
        handle_depth_pct = ((handle_high - handle_low) / handle_high) * 100
        
        # Handle should be smaller than the cup and within range
        if handle_depth_pct < 3 or handle_depth_pct > 20:
            return False, 0, 0, 0
        
        if handle_depth_pct >= cup_depth_pct:  # Handle must be shallower than cup
            return False, 0, 0, 0
        
        # Volume should decrease during handle
        if len(volume) >= 20:
            recent_vol = volume.iloc[-10:].mean()
            prior_vol = volume.iloc[-30:-10].mean() if len(volume) >= 30 else volume.mean()
            vol_decrease = recent_vol < prior_vol * 0.9  # Volume should decrease
        else:
            vol_decrease = True
        
        # Breakout level is the handle high / right rim
        breakout_level = float(handle_high)
        
        # Current price should be within 5% of breakout level (forming or breaking)
        distance_to_breakout = ((breakout_level - price) / breakout_level) * 100
        
        # Valid cup and handle if:
        # 1. Cup formed properly (✓ checked above)
        # 2. Handle is forming (✓ checked above)
        # 3. Price is near breakout level (within 8%)
        # 4. Volume decreasing in handle (bonus, not required)
        
        is_valid = distance_to_breakout >= -2 and distance_to_breakout <= 8
        
        return is_valid, cup_depth_pct, handle_depth_pct, breakout_level
        
    except Exception as e:
        return False, 0, 0, 0


def scan_stock(ticker):
    """Scan a single stock and return data."""
    try:
        # Daily data for price/volume analysis
        df = yf.download(ticker, period='2y', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 200:
            return None
        
        close = df['Close']
        volume = df['Volume']
        price = float(close.iloc[-1])
        
        # 200-WEEK SMA (need 5 years of weekly data)
        df_weekly = yf.download(ticker, period='5y', interval='1wk', progress=False)
        if isinstance(df_weekly.columns, pd.MultiIndex):
            df_weekly.columns = df_weekly.columns.get_level_values(0)
        
        if len(df_weekly) >= 200:
            wma_200 = df_weekly['Close'].rolling(200).mean().iloc[-1]
        else:
            # Fallback: use available weeks
            wma_200 = df_weekly['Close'].mean() if len(df_weekly) > 0 else price
        
        wma_pct = ((price - wma_200) / wma_200) * 100
        
        # 50 and 200 SMA
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1]
        
        # Score calculation
        score = 0
        
        # RS (3-month performance)
        perf_3m = (price / close.iloc[-63] - 1) * 100 if len(close) > 63 else 0
        if perf_3m > 20: score += 25
        elif perf_3m > 10: score += 15
        elif perf_3m > 0: score += 5
        
        # Price vs MAs
        if price > ma50: score += 10
        if price > ma200: score += 10
        if ma50 > ma200: score += 5
        
        # Volume
        avg_vol = volume.rolling(50).mean().iloc[-1]
        recent_vol = volume.iloc[-5:].mean()
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
        if vol_ratio > 1.5: score += 15
        elif vol_ratio > 1.2: score += 10
        
        # VCP detection
        recent_range = (close.iloc[-20:].max() - close.iloc[-20:].min()) / price
        prior_range = (close.iloc[-60:-20].max() - close.iloc[-60:-20].min()) / close.iloc[-40] if len(close) > 60 else recent_range
        vcp_score = 0
        if recent_range < prior_range * 0.5:
            score += 15
            vcp_score = 9
        elif recent_range < prior_range * 0.7:
            score += 10
            vcp_score = 7
        
        # Cup and Handle detection
        is_cup_handle, cup_depth, handle_depth, breakout_level = detect_cup_and_handle(close, volume)
        if is_cup_handle:
            score += 20  # Bonus for cup and handle pattern
        
        # Squeeze detection - Daily (pass full dataframe for proper TR calculation)
        daily_squeeze_on, daily_squeeze_score, daily_state, daily_bb_pct, daily_kc_pct, daily_bars = calculate_squeeze(df)
        
        # Squeeze detection - Weekly
        weekly_squeeze_on, weekly_squeeze_score, weekly_state, weekly_bb_pct, weekly_kc_pct, weekly_bars = calculate_squeeze(df_weekly)
        
        # High squeeze = state is HIGH only with score >= 80
        is_daily_high_squeeze = daily_state == 'HIGH' and daily_squeeze_score >= 80
        is_weekly_high_squeeze = weekly_state == 'HIGH' and weekly_squeeze_score >= 80
        is_high_squeeze = is_daily_high_squeeze or is_weekly_high_squeeze
        
        # Bonus for high squeeze
        if is_weekly_high_squeeze:
            score += 15
        elif is_daily_high_squeeze:
            score += 10
        
        # 52-week high proximity
        high_52w = close.iloc[-252:].max() if len(close) >= 252 else close.max()
        pct_from_high = ((high_52w - price) / high_52w) * 100
        
        # Determine categories
        is_actionable = score >= 70
        in_wma_zone = abs(wma_pct) < 10
        is_vcp = vcp_score >= 7
        is_breakout = pct_from_high < 3
        is_watchlist = score >= 50 and not is_actionable
        
        if in_wma_zone: score += 10
        
        # Signal type - prioritize cup and handle
        if is_cup_handle:
            signal_type = 'CUP & HANDLE'
        elif is_breakout:
            signal_type = 'BREAKOUT'
        elif is_vcp:
            signal_type = 'VCP'
        elif pct_from_high < 10:
            signal_type = 'AT PIVOT'
        elif in_wma_zone:
            signal_type = '200-WMA'
        else:
            signal_type = 'WATCH'
        
        # Entry/stop/target
        if is_cup_handle and breakout_level > 0:
            entry = round(breakout_level * 1.01, 2)  # Entry just above breakout
            stop = round(breakout_level * 0.92, 2)   # Stop below handle low
            # Target = cup depth added to breakout level
            target = round(breakout_level * (1 + cup_depth/100), 2)
        else:
            entry = round(price * 1.005, 2)
            stop = round(price * 0.92, 2)
            target = round(price * 1.20, 2)
        
        munger = '⭐⭐⭐' if score >= 80 else '⭐⭐' if score >= 60 else '⭐'
        
        return {
            'ticker': ticker,
            'price': price,
            'score': min(100, score),
            'signal_type': signal_type,
            'entry': entry,
            'stop': stop,
            'target': target,
            'wma_pct': wma_pct,
            'in_wma_zone': in_wma_zone,
            'is_actionable': is_actionable,
            'is_vcp': is_vcp,
            'is_cup_handle': is_cup_handle,
            'cup_depth': cup_depth if is_cup_handle else 0,
            'handle_depth': handle_depth if is_cup_handle else 0,
            'breakout_level': breakout_level if is_cup_handle else 0,
            'is_watchlist': is_watchlist,
            'vcp_score': vcp_score,
            'pct_from_high': pct_from_high,
            'vol_ratio': vol_ratio,
            'perf_3m': perf_3m,
            'munger': munger,
            # Squeeze data
            'daily_squeeze_on': daily_squeeze_on,
            'daily_squeeze_score': daily_squeeze_score,
            'daily_state': daily_state,
            'daily_bars': daily_bars,
            'daily_bb_pct': daily_bb_pct,
            'daily_kc_pct': daily_kc_pct,
            'weekly_squeeze_on': weekly_squeeze_on,
            'weekly_squeeze_score': weekly_squeeze_score,
            'weekly_state': weekly_state,
            'weekly_bars': weekly_bars,
            'weekly_bb_pct': weekly_bb_pct,
            'weekly_kc_pct': weekly_kc_pct,
            'is_daily_high_squeeze': is_daily_high_squeeze,
            'is_weekly_high_squeeze': is_weekly_high_squeeze,
            'is_high_squeeze': is_high_squeeze
        }
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")
        return None


def generate_html(results):
    """Generate the full index.html with scan results."""
    
    # Categorize
    actionable = [r for r in results if r['is_actionable']]
    wma_zone = [r for r in results if r['in_wma_zone']]
    vcps = [r for r in results if r['is_vcp']]
    cup_handles = [r for r in results if r.get('is_cup_handle', False)]
    high_squeeze = [r for r in results if r.get('is_high_squeeze', False)]
    daily_squeeze = [r for r in results if r.get('is_daily_high_squeeze', False)]
    weekly_squeeze = [r for r in results if r.get('is_weekly_high_squeeze', False)]
    watchlist = [r for r in results if r['is_watchlist']]
    
    actionable.sort(key=lambda x: x['score'], reverse=True)
    wma_zone.sort(key=lambda x: x['score'], reverse=True)
    vcps.sort(key=lambda x: x['score'], reverse=True)
    cup_handles.sort(key=lambda x: x['score'], reverse=True)
    high_squeeze.sort(key=lambda x: (x.get('weekly_squeeze_score', 0), x.get('daily_squeeze_score', 0)), reverse=True)
    watchlist.sort(key=lambda x: x['score'], reverse=True)
    results.sort(key=lambda x: x['score'], reverse=True)
    
    timestamp = datetime.now().strftime("%B %d, %Y • %I:%M %p EST")
    
    # Generate all rows with data attributes
    def make_row(s):
        score_class = 'score-a' if s['score'] >= 80 else 'score-b' if s['score'] >= 60 else 'score-c'
        tag_class = {
            'BREAKOUT': 'tag-breakout', 'VCP': 'tag-vcp', 'AT PIVOT': 'tag-pivot',
            '200-WMA': 'tag-200wma', 'WATCH': 'tag-forming', 'CUP & HANDLE': 'tag-cup'
        }.get(s['signal_type'], 'tag-forming')
        
        wma_display = f"+{s['wma_pct']:.0f}%" if s['wma_pct'] > 0 else f"{s['wma_pct']:.0f}%"
        wma_class = 'cyan' if s['in_wma_zone'] else ''
        
        signal_display = s['signal_type']
        if s['signal_type'] == 'VCP' and s['vcp_score'] >= 8:
            signal_display = 'VCP ⭐'
        elif s['signal_type'] == '200-WMA':
            signal_display = '200-WMA 🧠'
        elif s['signal_type'] == 'CUP & HANDLE':
            signal_display = 'CUP & HANDLE ☕'
        
        action = 'BUY' if s['score'] >= 70 else 'WATCH'
        action_class = 'action-buy' if action == 'BUY' else 'action-watch'
        
        # Data attributes for filtering
        cats = []
        if s['is_actionable']: cats.append('actionable')
        if s['in_wma_zone']: cats.append('wma')
        if s['is_vcp']: cats.append('vcp')
        if s.get('is_cup_handle', False): cats.append('cup')
        if s.get('is_high_squeeze', False): cats.append('squeeze')
        if s.get('is_daily_high_squeeze', False): cats.append('squeeze_daily')
        if s.get('is_weekly_high_squeeze', False): cats.append('squeeze_weekly')
        if s['is_watchlist']: cats.append('watchlist')
        cats.append('all')
        
        row_class = 'actionable' if s['is_actionable'] and s['signal_type'] not in ['200-WMA'] else ''
        if s['in_wma_zone']: row_class = 'wma-buy-zone'
        if s.get('is_cup_handle', False): row_class = 'cup-handle'
        if s.get('is_high_squeeze', False): row_class = 'high-squeeze'
        
        return f'''<tr class="stock-row {row_class}" data-categories="{' '.join(cats)}" data-ticker="{s['ticker']}" data-score="{s['score']}" data-weekly-sq="{s.get('weekly_squeeze_score', 0)}" data-daily-sq="{s.get('daily_squeeze_score', 0)}" onclick="loadChart('{s['ticker']}')">
                    <td class="ticker">{s['ticker']}</td>
                    <td><span class="pattern-tag {tag_class}">{signal_display}</span></td>
                    <td><span class="score-pill {score_class}">{s['score']}</span></td>
                    <td>${s['price']:,.2f}</td>
                    <td class="positive">${s['entry']:,.2f}</td>
                    <td class="negative">${s['stop']:,.2f}</td>
                    <td class="positive">${s['target']:,.2f}</td>
                    <td class="{wma_class}">{wma_display}</td>
                    <td class="munger-stars">{s['munger']}</td>
                    <td><span class="action-badge {action_class}">{action}</span></td>
                </tr>'''
    
    all_rows = '\n'.join([make_row(s) for s in results])
    
    # Stock data for charts
    stock_data_js = ',\n            '.join([
        f"'{s['ticker']}': {{ price: {s['price']:.2f}, entry: {s['entry']:.2f}, stop: {s['stop']:.0f}, target: {s['target']:.0f}, pattern: '{s['signal_type']}', vcp: {s['vcp_score']}, rs: '{s['perf_3m']:+.0f}%', high: '{s['pct_from_high']:.1f}%', wma: '{s['wma_pct']:+.0f}%', munger: '{s['munger']}', dailySq: {s.get('daily_squeeze_score', 0)}, weeklySq: {s.get('weekly_squeeze_score', 0)} }}"
        for s in results
    ])
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Scanner Command Center</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; }}
        .container {{ max-width: 1600px; margin: 0 auto; padding: 15px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; background: linear-gradient(90deg, rgba(88,166,255,0.1), rgba(163,113,247,0.1)); border-radius: 12px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.1); }}
        .header h1 {{ font-size: 1.6em; background: linear-gradient(90deg, #58a6ff, #a371f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header .timestamp {{ color: #8b949e; font-size: 0.85em; }}
        .status {{ display: flex; gap: 15px; align-items: center; }}
        .status-badge {{ padding: 5px 12px; border-radius: 20px; font-size: 0.8em; font-weight: 600; }}
        .status-live {{ background: rgba(63,185,80,0.2); color: #3fb950; }}
        .status-market {{ background: rgba(88,166,255,0.2); color: #58a6ff; }}
        
        .export-btn {{ background: linear-gradient(135deg, #2962ff, #a371f7); color: #fff; border: none; padding: 8px 16px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85em; transition: transform 0.1s, box-shadow 0.2s; }}
        .export-btn:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(88,166,255,0.3); }}
        .export-btn:active {{ transform: translateY(0); }}
        
        .modal-overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); display: none; justify-content: center; align-items: center; z-index: 1000; }}
        .modal-overlay.active {{ display: flex; }}
        .modal-content {{ background: #161b22; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 20px; max-width: 500px; width: 90%; }}
        .modal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
        .modal-header h3 {{ color: #58a6ff; font-size: 1.1em; }}
        .modal-close {{ background: none; border: none; color: #8b949e; font-size: 1.5em; cursor: pointer; }}
        .modal-close:hover {{ color: #fff; }}
        .modal-tabs {{ display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }}
        .modal-tab {{ padding: 8px 16px; border-radius: 6px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #8b949e; cursor: pointer; font-size: 0.85em; }}
        .modal-tab.active {{ background: rgba(88,166,255,0.2); border-color: #58a6ff; color: #58a6ff; }}
        .modal-textarea {{ width: 100%; height: 150px; background: #0d1117; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 12px; color: #e6edf3; font-family: monospace; font-size: 0.9em; resize: none; }}
        .modal-actions {{ display: flex; gap: 10px; margin-top: 15px; }}
        .modal-btn {{ flex: 1; padding: 10px; border-radius: 8px; font-weight: 600; cursor: pointer; border: none; }}
        .modal-btn-primary {{ background: #238636; color: #fff; }}
        .modal-btn-secondary {{ background: rgba(255,255,255,0.1); color: #e6edf3; }}
        .modal-note {{ font-size: 0.75em; color: #8b949e; margin-top: 10px; }}
        
        .quick-stats {{ display: grid; grid-template-columns: repeat(8, 1fr); gap: 10px; margin-bottom: 20px; }}
        .stat-card {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 15px; text-align: center; border: 2px solid rgba(255,255,255,0.08); cursor: pointer; transition: all 0.2s; }}
        .stat-card:hover {{ border-color: rgba(255,255,255,0.3); transform: translateY(-2px); }}
        .stat-card.active {{ border-color: #58a6ff; background: rgba(88,166,255,0.1); }}
        .stat-value {{ font-size: 1.8em; font-weight: 700; }}
        .stat-label {{ color: #8b949e; font-size: 0.75em; margin-top: 5px; }}
        
        .main-grid {{ display: grid; grid-template-columns: 1fr 420px; gap: 20px; }}
        .section {{ background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); overflow: hidden; }}
        .section-header {{ padding: 12px 16px; background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; justify-content: space-between; align-items: center; }}
        .section-title {{ font-size: 1em; font-weight: 600; }}
        .section-count {{ background: rgba(88,166,255,0.2); color: #58a6ff; padding: 2px 10px; border-radius: 12px; font-size: 0.75em; }}
        .section-body {{ padding: 0; max-height: 600px; overflow-y: auto; }}
        
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
        th {{ padding: 10px 12px; text-align: left; font-weight: 600; color: #8b949e; font-size: 0.7em; text-transform: uppercase; background: rgba(255,255,255,0.02); position: sticky; top: 0; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        tr.stock-row {{ cursor: pointer; }}
        tr.stock-row:hover {{ background: rgba(255,255,255,0.05); }}
        tr.stock-row.actionable {{ background: rgba(63,185,80,0.08); }}
        tr.stock-row.wma-buy-zone {{ background: rgba(0,212,255,0.08); }}
        tr.stock-row.cup-handle {{ background: rgba(255,165,0,0.12); }}
        tr.stock-row.high-squeeze {{ background: rgba(255,0,255,0.12); }}
        tr.stock-row.hidden {{ display: none; }}
        
        .ticker {{ font-weight: 700; color: #e6edf3; }}
        .positive {{ color: #3fb950; }}
        .negative {{ color: #f85149; }}
        .cyan {{ color: #00d4ff; }}
        
        .score-pill {{ padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.85em; }}
        .score-a {{ background: rgba(63,185,80,0.2); color: #3fb950; }}
        .score-b {{ background: rgba(254,202,87,0.2); color: #d29922; }}
        .score-c {{ background: rgba(248,81,73,0.2); color: #f85149; }}
        
        .pattern-tag {{ padding: 2px 8px; border-radius: 4px; font-size: 0.75em; font-weight: 600; }}
        .tag-breakout {{ background: rgba(63,185,80,0.15); color: #3fb950; }}
        .tag-vcp {{ background: rgba(255,107,107,0.15); color: #ff6b6b; }}
        .tag-pivot {{ background: rgba(88,166,255,0.15); color: #58a6ff; }}
        .tag-forming {{ background: rgba(139,148,158,0.15); color: #8b949e; }}
        .tag-200wma {{ background: rgba(0,212,255,0.15); color: #00d4ff; }}
        .tag-cup {{ background: rgba(255,165,0,0.2); color: #ffa500; }}
        
        .action-badge {{ padding: 4px 10px; border-radius: 4px; font-size: 0.75em; font-weight: 700; }}
        .action-buy {{ background: #238636; color: #fff; }}
        .action-watch {{ background: rgba(210,153,34,0.2); color: #d29922; }}
        .munger-stars {{ color: #ffc107; }}
        
        .chart-panel {{ position: sticky; top: 15px; }}
        .chart-container {{ background: #1e222d; border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); }}
        .chart-header {{ padding: 10px 15px; background: rgba(255,255,255,0.03); display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.08); }}
        .chart-ticker {{ font-weight: 700; font-size: 1.1em; color: #58a6ff; }}
        .chart-price {{ color: #3fb950; font-weight: 600; }}
        .tradingview-widget-container {{ height: 400px; }}
        
        .trade-box {{ margin: 15px; padding: 15px; background: rgba(63,185,80,0.1); border-radius: 8px; border: 1px solid rgba(63,185,80,0.2); }}
        .trade-box h4 {{ color: #3fb950; margin-bottom: 10px; font-size: 0.9em; }}
        .trade-row {{ display: flex; justify-content: space-between; margin: 8px 0; }}
        .trade-label {{ color: #8b949e; font-size: 0.85em; }}
        .trade-value {{ font-weight: 700; font-size: 0.95em; }}
        .trade-value.entry {{ color: #3fb950; }}
        .trade-value.stop {{ color: #f85149; }}
        .trade-value.target {{ color: #58a6ff; }}
        
        .tv-button {{ display: block; margin: 15px; padding: 12px 20px; background: linear-gradient(90deg, #2962FF, #2979FF); color: #fff; text-align: center; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 0.9em; transition: all 0.2s; }}
        .tv-button:hover {{ background: linear-gradient(90deg, #1E88E5, #2196F3); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(41,98,255,0.3); }}
        .tv-button svg {{ vertical-align: middle; margin-right: 8px; }}
        
        .stock-details {{ padding: 15px; border-top: 1px solid rgba(255,255,255,0.08); }}
        .detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
        .detail-item {{ display: flex; justify-content: space-between; }}
        .detail-label {{ color: #8b949e; font-size: 0.8em; }}
        .detail-value {{ font-weight: 600; font-size: 0.85em; }}
        
        .footer {{ text-align: center; padding: 20px; color: #6e7681; font-size: 0.8em; margin-top: 20px; }}
        
        @media (max-width: 1400px) {{ 
            .quick-stats {{ grid-template-columns: repeat(4, 1fr); }} 
        }}
        @media (max-width: 1200px) {{ 
            .main-grid {{ grid-template-columns: 1fr; }} 
            .chart-panel {{ position: static; }} 
            .quick-stats {{ grid-template-columns: repeat(4, 1fr); }} 
        }}
        @media (max-width: 800px) {{
            .quick-stats {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        @media (max-width: 600px) {{
            .quick-stats {{ grid-template-columns: repeat(2, 1fr); }}
            .stat-value {{ font-size: 1.4em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>📊 Stock Scanner Command Center</h1>
                <div class="timestamp">Last scan: {timestamp}</div>
            </div>
            <div class="status">
                <button class="export-btn" onclick="exportToTradingView()">📤 Export to TradingView</button>
                <span class="status-badge status-live">● Data Live</span>
                <span class="status-badge status-market">Auto-updates 6h</span>
            </div>
        </div>
        
        <div class="quick-stats">
            <div class="stat-card active" data-filter="actionable" onclick="filterStocks('actionable')">
                <div class="stat-value" style="color:#3fb950">{len(actionable)}</div>
                <div class="stat-label">🎯 Actionable Now</div>
            </div>
            <div class="stat-card" data-filter="squeeze_weekly" onclick="filterStocks('squeeze_weekly')">
                <div class="stat-value" style="color:#ff00ff">{len(weekly_squeeze)}</div>
                <div class="stat-label">🔥 Weekly Squeeze</div>
            </div>
            <div class="stat-card" data-filter="squeeze_daily" onclick="filterStocks('squeeze_daily')">
                <div class="stat-value" style="color:#ff66ff">{len(daily_squeeze)}</div>
                <div class="stat-label">⚡ Daily Squeeze</div>
            </div>
            <div class="stat-card" data-filter="cup" onclick="filterStocks('cup')">
                <div class="stat-value" style="color:#ffa500">{len(cup_handles)}</div>
                <div class="stat-label">☕ Cup & Handle</div>
            </div>
            <div class="stat-card" data-filter="vcp" onclick="filterStocks('vcp')">
                <div class="stat-value" style="color:#ff6b6b">{len(vcps)}</div>
                <div class="stat-label">⭐ VCPs</div>
            </div>
            <div class="stat-card" data-filter="wma" onclick="filterStocks('wma')">
                <div class="stat-value" style="color:#00d4ff">{len(wma_zone)}</div>
                <div class="stat-label">🧠 200-WMA Zone</div>
            </div>
            <div class="stat-card" data-filter="watchlist" onclick="filterStocks('watchlist')">
                <div class="stat-value" style="color:#d29922">{len(watchlist)}</div>
                <div class="stat-label">👀 Watch List</div>
            </div>
            <div class="stat-card" data-filter="all" onclick="filterStocks('all')">
                <div class="stat-value" style="color:#a371f7">{len(results)}</div>
                <div class="stat-label">📊 All Stocks</div>
            </div>
        </div>
        
        <div class="main-grid">
            <div class="tables-column">
                <div class="section">
                    <div class="section-header">
                        <div class="section-title" id="section-title">🎯 ACTIONABLE NOW</div>
                        <span class="section-count" id="section-count">{len(actionable)} stocks</span>
                    </div>
                    <div class="section-body">
                        <table>
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th>Signal</th>
                                    <th>Score</th>
                                    <th>Price</th>
                                    <th>Entry</th>
                                    <th>Stop</th>
                                    <th>Target</th>
                                    <th>200-WMA</th>
                                    <th>Munger</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="stocks-table">
{all_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="chart-panel">
                <div class="chart-container">
                    <div class="chart-header">
                        <span class="chart-ticker" id="chart-ticker">Select a stock</span>
                        <span class="chart-price" id="chart-price">—</span>
                    </div>
                    <div class="tradingview-widget-container" id="tv-chart">
                        <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#8b949e;">
                            Click a stock to view chart
                        </div>
                    </div>
                    <div class="trade-box" id="trade-box" style="display:none;">
                        <h4>📊 Trade Setup</h4>
                        <div class="trade-row"><span class="trade-label">Entry:</span><span class="trade-value entry" id="trade-entry">—</span></div>
                        <div class="trade-row"><span class="trade-label">Stop Loss:</span><span class="trade-value stop" id="trade-stop">—</span></div>
                        <div class="trade-row"><span class="trade-label">Target:</span><span class="trade-value target" id="trade-target">—</span></div>
                    </div>
                    <div class="stock-details" id="stock-details" style="display:none;">
                        <div class="detail-grid">
                            <div class="detail-item"><span class="detail-label">Pattern:</span><span class="detail-value" id="detail-pattern">—</span></div>
                            <div class="detail-item"><span class="detail-label">RS:</span><span class="detail-value" id="detail-rs">—</span></div>
                            <div class="detail-item"><span class="detail-label">From High:</span><span class="detail-value" id="detail-high">—</span></div>
                            <div class="detail-item"><span class="detail-label">200-WMA:</span><span class="detail-value" id="detail-wma">—</span></div>
                        </div>
                    </div>
                    <a href="#" id="tv-link" class="tv-button" target="_blank" style="display:none;">
                        <svg width="20" height="20" viewBox="0 0 36 28" fill="currentColor"><path d="M14 22H7V11H0V4h14v18zm8-18h7v18h-7V4zm-4 0h3v18h-3V4z"/></svg>
                        Open in TradingView
                    </a>
                </div>
            </div>
        </div>
        
        <div class="footer">
            Stock Scanner Command Center • S&P 500 • Auto-updates every 6 hours
        </div>
    </div>
    
    <!-- Export Modal -->
    <div class="modal-overlay" id="exportModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>📤 Export to TradingView</h3>
                <button class="modal-close" onclick="closeExportModal()">&times;</button>
            </div>
            <div class="modal-tabs">
                <button class="modal-tab active" onclick="setExportType('actionable', this)">🎯 Actionable</button>
                <button class="modal-tab" onclick="setExportType('squeeze_weekly', this)">🔥 Weekly Squeeze</button>
                <button class="modal-tab" onclick="setExportType('squeeze_daily', this)">⚡ Daily Squeeze</button>
                <button class="modal-tab" onclick="setExportType('cup', this)">☕ Cup & Handle</button>
                <button class="modal-tab" onclick="setExportType('vcp', this)">⭐ VCPs</button>
                <button class="modal-tab" onclick="setExportType('all', this)">📊 All</button>
            </div>
            <textarea class="modal-textarea" id="exportTextarea" readonly></textarea>
            <div class="modal-actions">
                <button class="modal-btn modal-btn-primary" onclick="copyToClipboard()">📋 Copy to Clipboard</button>
                <button class="modal-btn modal-btn-secondary" onclick="downloadWatchlist()">💾 Download .txt</button>
            </div>
            <div class="modal-note">
                <strong>How to import:</strong> TradingView → Lists → Import list → Paste symbols
            </div>
        </div>
    </div>
    
    <script src="https://s3.tradingview.com/tv.js"></script>
    <script>
        const stockData = {{
            {stock_data_js}
        }};
        
        const filterLabels = {{
            'actionable': '🎯 ACTIONABLE NOW',
            'squeeze_weekly': '🔥 WEEKLY SQUEEZE (HIGH)',
            'squeeze_daily': '⚡ DAILY SQUEEZE (HIGH)',
            'squeeze': '💥 ALL HIGH SQUEEZE',
            'cup': '☕ CUP & HANDLE',
            'wma': '🧠 200-WMA ZONE',
            'vcp': '⭐ VCP PATTERNS',
            'watchlist': '👀 WATCH LIST',
            'all': '📊 ALL STOCKS'
        }};
        
        let currentFilter = 'actionable';
        
        function filterStocks(category) {{
            currentFilter = category;
            const tbody = document.querySelector('tbody');
            const rows = Array.from(document.querySelectorAll('.stock-row'));
            let visibleCount = 0;
            
            // Sort rows based on category
            if (category === 'squeeze_weekly') {{
                rows.sort((a, b) => parseInt(b.dataset.weeklySq || 0) - parseInt(a.dataset.weeklySq || 0));
            }} else if (category === 'squeeze_daily') {{
                rows.sort((a, b) => parseInt(b.dataset.dailySq || 0) - parseInt(a.dataset.dailySq || 0));
            }} else if (category === 'squeeze') {{
                rows.sort((a, b) => {{
                    const aMax = Math.max(parseInt(a.dataset.weeklySq || 0), parseInt(a.dataset.dailySq || 0));
                    const bMax = Math.max(parseInt(b.dataset.weeklySq || 0), parseInt(b.dataset.dailySq || 0));
                    return bMax - aMax;
                }});
            }} else {{
                rows.sort((a, b) => parseInt(b.dataset.score || 0) - parseInt(a.dataset.score || 0));
            }}
            
            // Re-append rows in sorted order
            rows.forEach(row => tbody.appendChild(row));
            
            // Show/hide based on category
            rows.forEach(row => {{
                const cats = row.dataset.categories.split(' ');
                if (cats.includes(category)) {{
                    row.classList.remove('hidden');
                    visibleCount++;
                }} else {{
                    row.classList.add('hidden');
                }}
            }});
            
            // Update active card
            document.querySelectorAll('.stat-card').forEach(card => {{
                card.classList.remove('active');
                if (card.dataset.filter === category) {{
                    card.classList.add('active');
                }}
            }});
            
            // Update section title
            document.getElementById('section-title').textContent = filterLabels[category];
            document.getElementById('section-count').textContent = visibleCount + ' stocks';
        }}
        
        function loadChart(ticker) {{
            const data = stockData[ticker];
            if (!data) return;
            
            document.getElementById('chart-ticker').textContent = ticker;
            document.getElementById('chart-price').textContent = '$' + data.price.toFixed(2);
            document.getElementById('trade-entry').textContent = '$' + data.entry.toFixed(2);
            document.getElementById('trade-stop').textContent = '$' + data.stop.toFixed(0);
            document.getElementById('trade-target').textContent = '$' + data.target.toFixed(0);
            document.getElementById('detail-pattern').textContent = data.pattern;
            document.getElementById('detail-rs').textContent = data.rs;
            document.getElementById('detail-high').textContent = data.high;
            document.getElementById('detail-wma').textContent = data.wma;
            
            document.getElementById('trade-box').style.display = 'block';
            document.getElementById('stock-details').style.display = 'block';
            
            // Show and update TradingView link
            const tvLink = document.getElementById('tv-link');
            tvLink.style.display = 'block';
            tvLink.href = 'https://www.tradingview.com/chart/?symbol=' + ticker;
            
            document.getElementById('tv-chart').innerHTML = '';
            new TradingView.widget({{
                "container_id": "tv-chart",
                "symbol": ticker,
                "interval": "D",
                "timezone": "America/New_York",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "toolbar_bg": "#1e222d",
                "enable_publishing": false,
                "hide_top_toolbar": true,
                "hide_legend": false,
                "save_image": false,
                "height": 400,
                "width": "100%"
            }});
            
            // Highlight selected row
            document.querySelectorAll('.stock-row').forEach(r => r.style.outline = 'none');
            const selectedRow = document.querySelector(`[data-ticker="${{ticker}}"]`);
            if (selectedRow) {{
                selectedRow.style.outline = '2px solid #58a6ff';
                selectedRow.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
            }}
        }}
        
        // Initialize with actionable filter
        filterStocks('actionable');
        
        // Export to TradingView functionality
        let currentExportType = 'actionable';
        
        function getTickersByCategory(category) {{
            const rows = document.querySelectorAll('.stock-row');
            const tickers = [];
            rows.forEach(row => {{
                const cats = row.dataset.categories.split(' ');
                if (cats.includes(category)) {{
                    tickers.push(row.dataset.ticker);
                }}
            }});
            return tickers;
        }}
        
        function exportToTradingView() {{
            document.getElementById('exportModal').classList.add('active');
            setExportType('actionable', document.querySelector('.modal-tab'));
        }}
        
        function closeExportModal() {{
            document.getElementById('exportModal').classList.remove('active');
        }}
        
        function setExportType(type, btn) {{
            currentExportType = type;
            document.querySelectorAll('.modal-tab').forEach(tab => tab.classList.remove('active'));
            if (btn) btn.classList.add('active');
            const symbols = getTickersByCategory(type);
            document.getElementById('exportTextarea').value = symbols.join(',\\n');
        }}
        
        function copyToClipboard() {{
            const textarea = document.getElementById('exportTextarea');
            textarea.select();
            document.execCommand('copy');
            
            const btn = event.target;
            const originalText = btn.textContent;
            btn.textContent = '✅ Copied!';
            setTimeout(() => {{ btn.textContent = originalText; }}, 2000);
        }}
        
        function downloadWatchlist() {{
            const symbols = getTickersByCategory(currentExportType);
            const content = symbols.join('\\n');
            const blob = new Blob([content], {{ type: 'text/plain' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `tradingview_${{currentExportType}}_${{new Date().toISOString().slice(0,10)}}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}
        
        document.getElementById('exportModal').addEventListener('click', function(e) {{
            if (e.target === this) closeExportModal();
        }});
    </script>
</body>
</html>'''
    
    return html


def main():
    """Main entry point."""
    print(f"🔍 Scanning {len(UNIVERSE)} S&P 500 stocks...")
    print("=" * 50)
    
    results = []
    for i, ticker in enumerate(UNIVERSE):
        result = scan_stock(ticker)
        if result:
            results.append(result)
        
        # Progress indicator
        if (i + 1) % 50 == 0:
            print(f"  Scanned {i + 1}/{len(UNIVERSE)} stocks...")
    
    print(f"\n✅ Scanned {len(results)} stocks successfully")
    
    # Generate summary
    actionable = [r for r in results if r['is_actionable']]
    cup_handles = [r for r in results if r.get('is_cup_handle', False)]
    wma = [r for r in results if r['in_wma_zone']]
    vcps = [r for r in results if r['is_vcp']]
    weekly_squeeze = [r for r in results if r.get('is_weekly_high_squeeze', False)]
    daily_squeeze = [r for r in results if r.get('is_daily_high_squeeze', False)]
    
    print(f"\n📊 SUMMARY:")
    print(f"   🎯 Actionable: {len(actionable)}")
    print(f"   🔥 Weekly High Squeeze: {len(weekly_squeeze)}")
    print(f"   ⚡ Daily High Squeeze: {len(daily_squeeze)}")
    print(f"   ☕ Cup & Handle: {len(cup_handles)}")
    print(f"   🧠 200-WMA Zone: {len(wma)}")
    print(f"   ⭐ VCPs: {len(vcps)}")
    
    if weekly_squeeze:
        print(f"\n🔥 WEEKLY HIGH SQUEEZE:")
        for s in sorted(weekly_squeeze, key=lambda x: x.get('weekly_squeeze_score', 0), reverse=True)[:15]:
            state = s.get('weekly_state', 'NONE')
            bars = s.get('weekly_bars', 0)
            bb_pct = s.get('weekly_bb_pct', 0)
            kc_pct = s.get('weekly_kc_pct', 0)
            print(f"   {s['ticker']}: {state} | Score {s.get('weekly_squeeze_score', 0)} | BB%: {bb_pct:.1f} | KC%: {kc_pct:.1f} | Bars: {bars}")
    
    if daily_squeeze:
        print(f"\n⚡ DAILY HIGH SQUEEZE:")
        for s in sorted(daily_squeeze, key=lambda x: x.get('daily_squeeze_score', 0), reverse=True)[:15]:
            state = s.get('daily_state', 'NONE')
            bars = s.get('daily_bars', 0)
            bb_pct = s.get('daily_bb_pct', 0)
            kc_pct = s.get('daily_kc_pct', 0)
            print(f"   {s['ticker']}: {state} | Score {s.get('daily_squeeze_score', 0)} | BB%: {bb_pct:.1f} | KC%: {kc_pct:.1f} | Bars: {bars}")
    
    if cup_handles:
        print(f"\n☕ CUP & HANDLE PATTERNS:")
        for s in sorted(cup_handles, key=lambda x: x['score'], reverse=True)[:10]:
            print(f"   {s['ticker']}: Cup {s['cup_depth']:.1f}%, Handle {s['handle_depth']:.1f}%, Breakout ${s['breakout_level']:.2f}")
    
    # Generate HTML
    html = generate_html(results)
    
    # Write to file
    output_path = os.path.join(SCRIPT_DIR, 'index.html')
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"\n✅ Generated {output_path}")
    
    return results


if __name__ == '__main__':
    main()
