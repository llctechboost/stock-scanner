#!/usr/bin/env python3
"""
Market Health & Trend Module
Tracks overall market condition: indices, VIX, breadth, regime, sector rotation, alerts.
Outputs clean summary to stdout and saves JSON to market_health_latest.json.
"""

import os
import sys
import json
import warnings
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'market_health_latest.json')

INDICES = {
    'SPY': 'S&P 500',
    'QQQ': 'Nasdaq 100',
    'DIA': 'Dow 30',
    'IWM': 'Russell 2000',
}

SECTOR_ETFS = {
    'XLK': 'Technology',
    'XLF': 'Financials',
    'XLE': 'Energy',
    'XLV': 'Healthcare',
    'XLY': 'Consumer Disc',
    'XLI': 'Industrials',
    'XLP': 'Consumer Staples',
    'XLU': 'Utilities',
    'XLRE': 'Real Estate',
    'XLC': 'Communication',
    'XLB': 'Materials',
}

# Offensive vs Defensive classification
OFFENSIVE_SECTORS = {'XLK', 'XLY', 'XLF', 'XLI', 'XLC', 'XLB'}
DEFENSIVE_SECTORS = {'XLP', 'XLU', 'XLV', 'XLRE', 'XLE'}

# A broader stock universe for breadth estimation
STOCK_UNIVERSE = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'TSLA', 'BRK-B', 'UNH', 'JNJ',
    'JPM', 'V', 'PG', 'XOM', 'HD', 'MA', 'CVX', 'MRK', 'ABBV', 'LLY',
    'PEP', 'KO', 'COST', 'AVGO', 'WMT', 'MCD', 'CSCO', 'ACN', 'TMO', 'ABT',
    'CRM', 'ADBE', 'NFLX', 'AMD', 'INTC', 'QCOM', 'TXN', 'HON', 'UNP', 'LOW',
    'NEE', 'PM', 'UPS', 'RTX', 'BA', 'CAT', 'DE', 'GS', 'MS', 'BLK',
    'SCHW', 'AXP', 'SPGI', 'SYK', 'MDT', 'BMY', 'GILD', 'AMGN', 'PFE', 'ISRG',
    'NOW', 'PANW', 'SNOW', 'CRWD', 'SQ', 'SHOP', 'COIN', 'MARA', 'PLTR', 'SOFI',
    'ROKU', 'DKNG', 'NET', 'ENPH', 'FSLR', 'CEG', 'VST', 'SMCI', 'ARM', 'MSTR',
    'F', 'GM', 'DAL', 'UAL', 'LUV', 'DIS', 'CMCSA', 'T', 'VZ', 'TMUS',
    'CL', 'GIS', 'K', 'SJM', 'WBA', 'DG', 'DLTR', 'TGT', 'ROST', 'TJX',
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def calc_ma(series, window):
    """Calculate simple moving average."""
    return series.rolling(window=window, min_periods=window).mean()


def calc_rsi(series, period=14):
    """Calculate RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def safe_pct(a, b):
    """Safe percentage change from b to a."""
    if b is None or b == 0 or pd.isna(b):
        return None
    return ((a - b) / b) * 100


def download_safe(tickers, period='1y', progress=False):
    """Download data safely, handling multi-index columns."""
    try:
        df = yf.download(tickers, period=period, progress=progress, auto_adjust=True)
        return df
    except Exception as e:
        print(f"  ⚠️  Download error: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 1. Index Analysis
# ---------------------------------------------------------------------------
def analyze_indices():
    """Fetch and analyze major market indices."""
    print("📊 Fetching index data...")
    results = {}

    for ticker, name in INDICES.items():
        try:
            df = yf.download(ticker, period='1y', progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if df.empty or len(df) < 50:
                print(f"  ⚠️  Insufficient data for {ticker}")
                continue

            close = df['Close']
            current_price = float(close.iloc[-1])

            # Daily change
            if len(close) >= 2:
                daily_change = safe_pct(close.iloc[-1], close.iloc[-2])
            else:
                daily_change = None

            # Weekly change (5 trading days)
            if len(close) >= 6:
                weekly_change = safe_pct(close.iloc[-1], close.iloc[-6])
            else:
                weekly_change = None

            # Monthly change (21 trading days)
            if len(close) >= 22:
                monthly_change = safe_pct(close.iloc[-1], close.iloc[-22])
            else:
                monthly_change = None

            # Moving averages
            ma50 = calc_ma(close, 50)
            ma200 = calc_ma(close, 200)

            ma50_val = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else None
            ma200_val = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else None

            above_50ma = current_price > ma50_val if ma50_val else None
            above_200ma = current_price > ma200_val if ma200_val else None

            # Golden/death cross: 50MA vs 200MA
            ma50_above_200ma = ma50_val > ma200_val if (ma50_val and ma200_val) else None

            # 52-week high
            high_52w = float(close.max())
            dist_from_high = safe_pct(current_price, high_52w)  # will be negative

            # RSI
            rsi = calc_rsi(close)
            rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

            results[ticker] = {
                'name': name,
                'price': round(current_price, 2),
                'daily_change_pct': round(daily_change, 2) if daily_change is not None else None,
                'weekly_change_pct': round(weekly_change, 2) if weekly_change is not None else None,
                'monthly_change_pct': round(monthly_change, 2) if monthly_change is not None else None,
                'ma50': round(ma50_val, 2) if ma50_val else None,
                'ma200': round(ma200_val, 2) if ma200_val else None,
                'above_50ma': above_50ma,
                'above_200ma': above_200ma,
                'ma50_above_200ma': ma50_above_200ma,
                'high_52w': round(high_52w, 2),
                'dist_from_high_pct': round(dist_from_high, 2) if dist_from_high is not None else None,
                'rsi': round(rsi_val, 1) if rsi_val else None,
            }
            print(f"  ✅ {ticker} ({name}): ${current_price:.2f}  daily={daily_change:+.2f}%  {'↑50MA' if above_50ma else '↓50MA'}  {'↑200MA' if above_200ma else '↓200MA'}")

        except Exception as e:
            print(f"  ❌ {ticker}: {e}")
            continue

    return results


# ---------------------------------------------------------------------------
# 2. VIX Analysis
# ---------------------------------------------------------------------------
def analyze_vix():
    """Fetch VIX data and classify fear level."""
    print("\n😰 Fetching VIX data...")
    try:
        df = yf.download('^VIX', period='3mo', progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty:
            print("  ⚠️  No VIX data")
            return {}

        close = df['Close']
        current = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else current
        daily_change_pct = safe_pct(current, prev_close)

        # Classify
        if current < 15:
            label = 'LOW FEAR'
            emoji = '😎'
        elif current < 20:
            label = 'NEUTRAL'
            emoji = '😐'
        elif current < 25:
            label = 'ELEVATED'
            emoji = '😟'
        elif current < 30:
            label = 'HIGH FEAR'
            emoji = '😨'
        else:
            label = 'EXTREME FEAR'
            emoji = '🤯'

        # Check for spike (>20% single-day move)
        spiked = abs(daily_change_pct) > 20 if daily_change_pct is not None else False

        # 10-day and 30-day averages
        vix_10d_avg = float(close.tail(10).mean())
        vix_30d_avg = float(close.tail(30).mean())

        result = {
            'level': round(current, 2),
            'label': label,
            'emoji': emoji,
            'daily_change_pct': round(daily_change_pct, 2) if daily_change_pct is not None else None,
            'spiked': spiked,
            'avg_10d': round(vix_10d_avg, 2),
            'avg_30d': round(vix_30d_avg, 2),
            'trend': 'RISING' if current > vix_10d_avg else 'FALLING',
        }
        print(f"  VIX: {current:.2f} — {emoji} {label} (daily: {daily_change_pct:+.1f}%)")
        return result

    except Exception as e:
        print(f"  ❌ VIX error: {e}")
        return {}


# ---------------------------------------------------------------------------
# 3. Market Breadth
# ---------------------------------------------------------------------------
def analyze_breadth():
    """Estimate market breadth using sector ETFs and stock universe."""
    print("\n📏 Analyzing market breadth...")

    # Use sector ETFs for advance/decline
    sector_tickers = list(SECTOR_ETFS.keys())
    advancing = 0
    declining = 0
    above_50ma_count = 0
    above_200ma_count = 0
    new_highs = 0
    new_lows = 0
    total_analyzed = 0

    # Analyze our stock universe for breadth
    print("  Scanning stock universe for breadth...")
    batch_size = 20
    all_tickers = STOCK_UNIVERSE + sector_tickers

    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i + batch_size]
        try:
            data = yf.download(batch, period='1y', progress=False, auto_adjust=True)
            if data.empty:
                continue

            for ticker in batch:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        if ticker not in data['Close'].columns:
                            continue
                        close = data['Close'][ticker].dropna()
                    else:
                        close = data['Close'].dropna()

                    if len(close) < 50:
                        continue

                    total_analyzed += 1
                    current = float(close.iloc[-1])
                    prev = float(close.iloc[-2]) if len(close) >= 2 else current

                    # Advancing/declining
                    if current > prev:
                        advancing += 1
                    elif current < prev:
                        declining += 1

                    # Above 50MA
                    ma50 = float(close.rolling(50).mean().iloc[-1])
                    if not pd.isna(ma50) and current > ma50:
                        above_50ma_count += 1

                    # Above 200MA
                    if len(close) >= 200:
                        ma200 = float(close.rolling(200).mean().iloc[-1])
                        if not pd.isna(ma200) and current > ma200:
                            above_200ma_count += 1

                    # New highs/lows (52-week)
                    high_52w = float(close.max())
                    low_52w = float(close.min())
                    if current >= high_52w * 0.98:  # Within 2% of 52w high
                        new_highs += 1
                    if current <= low_52w * 1.02:  # Within 2% of 52w low
                        new_lows += 1

                except Exception:
                    continue
        except Exception as e:
            print(f"  ⚠️  Batch error: {e}")
            continue

    if total_analyzed == 0:
        total_analyzed = 1  # avoid division by zero

    ad_ratio = round(advancing / max(declining, 1), 2)
    pct_above_50ma = round((above_50ma_count / total_analyzed) * 100, 1)
    pct_above_200ma = round((above_200ma_count / total_analyzed) * 100, 1)

    # Breadth score (0-100)
    breadth_score = 0
    if ad_ratio > 1.5:
        breadth_score += 30
    elif ad_ratio > 1.0:
        breadth_score += 20
    elif ad_ratio > 0.7:
        breadth_score += 10

    if pct_above_50ma > 70:
        breadth_score += 30
    elif pct_above_50ma > 50:
        breadth_score += 20
    elif pct_above_50ma > 30:
        breadth_score += 10

    if pct_above_200ma > 70:
        breadth_score += 25
    elif pct_above_200ma > 50:
        breadth_score += 15
    elif pct_above_200ma > 30:
        breadth_score += 8

    if new_highs > new_lows:
        breadth_score += 15
    elif new_highs == new_lows:
        breadth_score += 7

    # Label
    if breadth_score >= 75:
        breadth_label = 'STRONG'
    elif breadth_score >= 55:
        breadth_label = 'HEALTHY'
    elif breadth_score >= 35:
        breadth_label = 'MIXED'
    elif breadth_score >= 20:
        breadth_label = 'WEAKENING'
    else:
        breadth_label = 'POOR'

    result = {
        'advancing': advancing,
        'declining': declining,
        'ad_ratio': ad_ratio,
        'pct_above_50ma': pct_above_50ma,
        'pct_above_200ma': pct_above_200ma,
        'new_highs': new_highs,
        'new_lows': new_lows,
        'total_analyzed': total_analyzed,
        'breadth_score': breadth_score,
        'breadth_label': breadth_label,
    }

    print(f"  A/D Ratio: {ad_ratio:.2f} ({advancing}↑ / {declining}↓)")
    print(f"  Above 50MA: {pct_above_50ma}%  |  Above 200MA: {pct_above_200ma}%")
    print(f"  New Highs: {new_highs}  |  New Lows: {new_lows}")
    print(f"  Breadth Score: {breadth_score}/100 — {breadth_label}")

    return result


# ---------------------------------------------------------------------------
# 4. Sector Rotation
# ---------------------------------------------------------------------------
def analyze_sector_rotation():
    """Analyze sector rotation patterns."""
    print("\n🔄 Analyzing sector rotation...")

    sectors_data = []
    offensive_perf = []
    defensive_perf = []

    for etf, name in SECTOR_ETFS.items():
        try:
            df = yf.download(etf, period='6mo', progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if df.empty or len(df) < 50:
                continue

            close = df['Close']
            volume = df['Volume']
            current = float(close.iloc[-1])

            # Performance windows
            perf_1w = safe_pct(close.iloc[-1], close.iloc[-6]) if len(close) >= 6 else None
            perf_1m = safe_pct(close.iloc[-1], close.iloc[-22]) if len(close) >= 22 else None
            perf_3m = safe_pct(close.iloc[-1], close.iloc[-66]) if len(close) >= 66 else None

            # Volume trend (recent vs avg)
            avg_vol = float(volume.tail(50).mean())
            recent_vol = float(volume.tail(5).mean())
            vol_ratio = round(recent_vol / max(avg_vol, 1), 2)

            # Relative strength (simple: 1m perf)
            rs = perf_1m if perf_1m is not None else 0

            # Money flow score: combine perf + volume
            mf_score = rs * vol_ratio if rs is not None else 0

            # RSI
            rsi = calc_rsi(close)
            rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50

            # MA status
            ma50 = float(calc_ma(close, 50).iloc[-1]) if len(close) >= 50 else None
            above_50ma = current > ma50 if ma50 else None

            sector_info = {
                'etf': etf,
                'sector': name,
                'price': round(current, 2),
                'perf_1w': round(perf_1w, 2) if perf_1w is not None else None,
                'perf_1m': round(perf_1m, 2) if perf_1m is not None else None,
                'perf_3m': round(perf_3m, 2) if perf_3m is not None else None,
                'vol_ratio': vol_ratio,
                'rsi': round(rsi_val, 1),
                'mf_score': round(mf_score, 2),
                'above_50ma': above_50ma,
            }
            sectors_data.append(sector_info)

            # Track offensive vs defensive
            if etf in OFFENSIVE_SECTORS:
                offensive_perf.append(perf_1m or 0)
            else:
                defensive_perf.append(perf_1m or 0)

        except Exception as e:
            print(f"  ⚠️  {etf}: {e}")
            continue

    # Sort by mf_score
    sectors_data.sort(key=lambda x: x['mf_score'], reverse=True)

    # Leading/lagging
    leading = [s for s in sectors_data if s['mf_score'] > 0][:5]
    lagging = [s for s in reversed(sectors_data) if s['mf_score'] < 0][:5]

    # Rotation direction
    avg_off = np.mean(offensive_perf) if offensive_perf else 0
    avg_def = np.mean(defensive_perf) if defensive_perf else 0

    if avg_off > avg_def + 1:
        rotation_direction = 'RISK-ON'
        rotation_signal = 'BULLISH'
    elif avg_def > avg_off + 1:
        rotation_direction = 'RISK-OFF'
        rotation_signal = 'BEARISH'
    else:
        rotation_direction = 'NEUTRAL'
        rotation_signal = 'NEUTRAL'

    result = {
        'sectors': sectors_data,
        'leading': [{'sector': s['sector'], 'etf': s['etf'], 'mf_score': s['mf_score'], 'perf_1m': s['perf_1m']} for s in leading],
        'lagging': [{'sector': s['sector'], 'etf': s['etf'], 'mf_score': s['mf_score'], 'perf_1m': s['perf_1m']} for s in lagging],
        'offensive_avg_perf': round(avg_off, 2),
        'defensive_avg_perf': round(avg_def, 2),
        'rotation_direction': rotation_direction,
        'rotation_signal': rotation_signal,
    }

    print(f"  Leading: {', '.join(s['sector'] for s in leading)}")
    print(f"  Lagging: {', '.join(s['sector'] for s in lagging)}")
    print(f"  Rotation: {rotation_direction} ({rotation_signal})")
    print(f"  Offensive avg 1M: {avg_off:+.2f}%  |  Defensive avg 1M: {avg_def:+.2f}%")

    return result


# ---------------------------------------------------------------------------
# 5. Market Regime Classification
# ---------------------------------------------------------------------------
def classify_regime(indices, vix, breadth, rotation):
    """Classify current market regime."""
    print("\n🏛️  Classifying market regime...")

    spy = indices.get('SPY', {})
    score = 0
    signals = []

    # SPY above 50MA (+2) or below (-1)
    if spy.get('above_50ma'):
        score += 2
        signals.append('SPY above 50MA ✅')
    else:
        score -= 1
        signals.append('SPY below 50MA ⚠️')

    # SPY above 200MA (+2) or below (-2)
    if spy.get('above_200ma'):
        score += 2
        signals.append('SPY above 200MA ✅')
    else:
        score -= 2
        signals.append('SPY below 200MA 🚨')

    # Golden cross: 50MA above 200MA (+1)
    if spy.get('ma50_above_200ma'):
        score += 1
        signals.append('Golden Cross (50MA > 200MA) ✅')
    else:
        score -= 1
        signals.append('Death Cross (50MA < 200MA) ⚠️')

    # Breadth
    bs = breadth.get('breadth_score', 50)
    if bs >= 70:
        score += 2
        signals.append(f'Breadth strong ({bs}/100) ✅')
    elif bs >= 50:
        score += 1
        signals.append(f'Breadth healthy ({bs}/100)')
    elif bs >= 30:
        score -= 1
        signals.append(f'Breadth mixed ({bs}/100) ⚠️')
    else:
        score -= 2
        signals.append(f'Breadth poor ({bs}/100) 🚨')

    # VIX
    vix_level = vix.get('level', 20)
    if vix_level < 15:
        score += 1
        signals.append(f'VIX low ({vix_level:.1f}) ✅')
    elif vix_level < 20:
        pass  # neutral
        signals.append(f'VIX neutral ({vix_level:.1f})')
    elif vix_level < 25:
        score -= 1
        signals.append(f'VIX elevated ({vix_level:.1f}) ⚠️')
    else:
        score -= 2
        signals.append(f'VIX high ({vix_level:.1f}) 🚨')

    # Sector rotation direction
    rot = rotation.get('rotation_signal', 'NEUTRAL')
    if rot == 'BULLISH':
        score += 1
        signals.append('Rotation: Risk-ON ✅')
    elif rot == 'BEARISH':
        score -= 1
        signals.append('Rotation: Risk-OFF ⚠️')
    else:
        signals.append('Rotation: Neutral')

    # Majority of indices above 50MA
    indices_above_50 = sum(1 for t in INDICES if indices.get(t, {}).get('above_50ma', False))
    if indices_above_50 >= 3:
        score += 1
        signals.append(f'{indices_above_50}/4 indices above 50MA ✅')
    elif indices_above_50 <= 1:
        score -= 1
        signals.append(f'{indices_above_50}/4 indices above 50MA ⚠️')

    # Classify
    if score >= 7:
        regime = 'STRONG BULL'
    elif score >= 4:
        regime = 'BULL'
    elif score >= 1:
        regime = 'NEUTRAL'
    elif score >= -2:
        regime = 'CAUTION'
    else:
        regime = 'BEAR'

    result = {
        'regime': regime,
        'score': score,
        'max_score': 10,
        'signals': signals,
    }

    emoji_map = {
        'STRONG BULL': '🟢🟢',
        'BULL': '🟢',
        'NEUTRAL': '🟡',
        'CAUTION': '🟠',
        'BEAR': '🔴',
    }
    print(f"  Regime: {emoji_map.get(regime, '')} {regime} (score: {score}/10)")
    for s in signals:
        print(f"    • {s}")

    return result


# ---------------------------------------------------------------------------
# 6. Market Alerts
# ---------------------------------------------------------------------------
def generate_alerts(indices, vix, breadth, rotation):
    """Generate market alerts based on unusual conditions."""
    print("\n🚨 Checking for alerts...")
    alerts = []

    # VIX spike
    if vix.get('spiked'):
        alerts.append({
            'type': 'VIX_SPIKE',
            'severity': 'HIGH',
            'message': f"VIX spiked {vix.get('daily_change_pct', 0):+.1f}% to {vix.get('level', 0):.1f}",
            'emoji': '🚨',
        })

    # VIX extreme
    if vix.get('level', 0) > 30:
        alerts.append({
            'type': 'VIX_EXTREME',
            'severity': 'HIGH',
            'message': f"VIX at EXTREME FEAR level: {vix.get('level', 0):.1f}",
            'emoji': '🤯',
        })

    # Index broke below key MAs
    for ticker in INDICES:
        idx = indices.get(ticker, {})
        if idx.get('above_50ma') is False:
            # Check if it recently crossed (daily change was negative while near MA)
            alerts.append({
                'type': 'BELOW_50MA',
                'severity': 'MEDIUM',
                'message': f"{ticker} ({INDICES[ticker]}) trading below 50-day MA",
                'emoji': '⚠️',
            })
        if idx.get('above_200ma') is False:
            alerts.append({
                'type': 'BELOW_200MA',
                'severity': 'HIGH',
                'message': f"{ticker} ({INDICES[ticker]}) trading below 200-day MA",
                'emoji': '🚨',
            })

    # Breadth deterioration
    if breadth.get('breadth_label') in ('WEAKENING', 'POOR'):
        alerts.append({
            'type': 'BREADTH_WEAK',
            'severity': 'MEDIUM',
            'message': f"Market breadth is {breadth.get('breadth_label')}: only {breadth.get('pct_above_50ma', 0)}% above 50MA",
            'emoji': '📉',
        })

    # Risk-off rotation
    if rotation.get('rotation_signal') == 'BEARISH':
        alerts.append({
            'type': 'RISK_OFF',
            'severity': 'MEDIUM',
            'message': 'Money rotating from offensive to defensive sectors (risk-off)',
            'emoji': '🛡️',
        })

    # High new lows
    if breadth.get('new_lows', 0) > breadth.get('new_highs', 0) * 2:
        alerts.append({
            'type': 'NEW_LOWS',
            'severity': 'MEDIUM',
            'message': f"New lows ({breadth.get('new_lows')}) significantly exceed new highs ({breadth.get('new_highs')})",
            'emoji': '📉',
        })

    if not alerts:
        print("  ✅ No active alerts")
    else:
        for a in alerts:
            print(f"  {a['emoji']} [{a['severity']}] {a['message']}")

    return alerts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_market_health():
    """Run full market health analysis."""
    print("=" * 60)
    print("  🌍 MARKET HEALTH SCANNER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. Indices
    indices = analyze_indices()

    # 2. VIX
    vix = analyze_vix()

    # 3. Breadth
    breadth = analyze_breadth()

    # 4. Sector Rotation
    rotation = analyze_sector_rotation()

    # 5. Market Regime
    regime = classify_regime(indices, vix, breadth, rotation)

    # 6. Alerts
    alerts = generate_alerts(indices, vix, breadth, rotation)

    # Compile output
    output = {
        'timestamp': datetime.now().isoformat(),
        'indices': indices,
        'vix': vix,
        'breadth': breadth,
        'sector_rotation': rotation,
        'regime': regime,
        'alerts': alerts,
    }

    # Save JSON
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n💾 Saved to {OUTPUT_FILE}")

    # Print summary
    print("\n" + "=" * 60)
    print("  📋 MARKET HEALTH SUMMARY")
    print("=" * 60)

    # Regime
    regime_emoji = {
        'STRONG BULL': '🟢🟢', 'BULL': '🟢', 'NEUTRAL': '🟡',
        'CAUTION': '🟠', 'BEAR': '🔴',
    }
    r = regime['regime']
    print(f"\n  {'='*40}")
    print(f"  MARKET REGIME:  {regime_emoji.get(r, '')}  {r}")
    print(f"  Score: {regime['score']}/10")
    print(f"  {'='*40}")

    # Indices table
    print(f"\n  {'Idx':<5} {'Price':>10} {'Daily':>8} {'Week':>8} {'Month':>8} {'50MA':>6} {'200MA':>6} {'From Hi':>8}")
    print(f"  {'-'*65}")
    for ticker, data in indices.items():
        ma50_str = '✅' if data.get('above_50ma') else '❌'
        ma200_str = '✅' if data.get('above_200ma') else '❌'
        daily = f"{data.get('daily_change_pct', 0):+.1f}%" if data.get('daily_change_pct') is not None else '—'
        weekly = f"{data.get('weekly_change_pct', 0):+.1f}%" if data.get('weekly_change_pct') is not None else '—'
        monthly = f"{data.get('monthly_change_pct', 0):+.1f}%" if data.get('monthly_change_pct') is not None else '—'
        from_hi = f"{data.get('dist_from_high_pct', 0):.1f}%" if data.get('dist_from_high_pct') is not None else '—'
        print(f"  {ticker:<5} ${data['price']:>8.2f} {daily:>8} {weekly:>8} {monthly:>8} {ma50_str:>6} {ma200_str:>6} {from_hi:>8}")

    # VIX
    if vix:
        print(f"\n  VIX: {vix.get('level', '?'):.1f}  {vix.get('emoji', '')} {vix.get('label', '')}  (trend: {vix.get('trend', '?')})")

    # Breadth
    if breadth:
        print(f"\n  Breadth: {breadth.get('breadth_label', '?')} ({breadth.get('breadth_score', 0)}/100)")
        print(f"    A/D: {breadth.get('ad_ratio', '?'):.2f}  |  >50MA: {breadth.get('pct_above_50ma', '?')}%  |  >200MA: {breadth.get('pct_above_200ma', '?')}%")
        print(f"    New Highs: {breadth.get('new_highs', 0)}  |  New Lows: {breadth.get('new_lows', 0)}")

    # Rotation
    if rotation:
        print(f"\n  Rotation: {rotation.get('rotation_direction', '?')} ({rotation.get('rotation_signal', '?')})")
        if rotation.get('leading'):
            print(f"    Leading: {', '.join(s['sector'] for s in rotation['leading'][:3])}")
        if rotation.get('lagging'):
            print(f"    Lagging: {', '.join(s['sector'] for s in rotation['lagging'][:3])}")

    # Alerts
    if alerts:
        print(f"\n  🚨 ALERTS ({len(alerts)}):")
        for a in alerts:
            print(f"    {a['emoji']} {a['message']}")
    else:
        print("\n  ✅ No active alerts")

    print("\n" + "=" * 60)
    return output


if __name__ == '__main__':
    run_market_health()
