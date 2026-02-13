#!/usr/bin/env python3
"""
Stock Screener v3.0
- Pattern Recognition (50 pts scaled): 200W MA, Cup & Handle, VCP, Flat Base
- Fundamentals (50 pts scaled): EPS Growth, ROE, Rev Growth, D/E, P/E
- Options Activity: Coming later (Unusual Whales API)

Run on S&P 500 + Russell 1000
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import json
warnings.filterwarnings('ignore')

# ============================================================
# PATTERN DETECTION
# ============================================================

def get_200w_ma_score(hist_weekly):
    """Calculate 200W MA proximity score"""
    if len(hist_weekly) < 200:
        return 0, None, None
    
    hist_weekly['SMA_200W'] = hist_weekly['Close'].rolling(window=200).mean()
    current_price = hist_weekly['Close'].iloc[-1]
    sma_200w = hist_weekly['SMA_200W'].iloc[-1]
    
    if pd.isna(sma_200w):
        return 0, None, None
    
    pct_from_ma = ((current_price - sma_200w) / sma_200w) * 100
    
    # Score based on proximity
    abs_pct = abs(pct_from_ma)
    if abs_pct <= 2:
        score = 22  # Full 200W MA score (standalone)
    elif abs_pct <= 5:
        score = 18
    elif abs_pct <= 10:
        score = 12
    elif abs_pct <= 15:
        score = 6
    else:
        score = 0
    
    return score, sma_200w, pct_from_ma


def detect_cup_and_handle(hist_daily):
    """
    Detect Cup & Handle pattern
    - U-shape base: 30-65% depth
    - Duration: 7-65 weeks (35-325 trading days)
    - Handle: pullback <15% from right rim
    """
    if len(hist_daily) < 100:
        return False, 0
    
    closes = hist_daily['Close'].values
    highs = hist_daily['High'].values
    
    # Look for swing high in last 6 months
    lookback = min(252, len(closes))
    recent = closes[-lookback:]
    
    # Find the highest point (left rim of cup)
    peak_idx = np.argmax(recent)
    peak_price = recent[peak_idx]
    
    if peak_idx < 20:  # Need enough data after peak
        return False, 0
    
    # Find lowest point after peak (bottom of cup)
    after_peak = recent[peak_idx:]
    if len(after_peak) < 20:
        return False, 0
    
    trough_idx = np.argmin(after_peak) + peak_idx
    trough_price = recent[trough_idx]
    
    # Calculate depth
    depth = (peak_price - trough_price) / peak_price * 100
    
    # Check if depth is in valid range (15-50% for more sensitivity)
    if not (15 <= depth <= 50):
        return False, 0
    
    # Check if price has recovered (right side of cup)
    current_price = closes[-1]
    recovery = (current_price - trough_price) / (peak_price - trough_price) * 100
    
    if recovery < 70:  # Need at least 70% recovery
        return False, 0
    
    # Check for handle (small pullback in last 2-4 weeks)
    last_20 = closes[-20:]
    recent_high = np.max(last_20)
    recent_low = np.min(last_20[-10:])  # Last 10 days
    handle_depth = (recent_high - recent_low) / recent_high * 100
    
    # Handle should be small pullback
    has_handle = 2 <= handle_depth <= 15
    
    if has_handle:
        return True, 30  # Cup & Handle standalone = 30 pts
    elif recovery > 85:
        return True, 25  # Cup forming, no handle yet
    
    return False, 0


def detect_vcp(hist_daily):
    """
    Detect Volatility Contraction Pattern (VCP)
    - 2+ contractions
    - Each contraction tighter than previous
    - Decreasing volume
    """
    if len(hist_daily) < 60:
        return False, 0, "tight"
    
    closes = hist_daily['Close'].values[-60:]
    highs = hist_daily['High'].values[-60:]
    lows = hist_daily['Low'].values[-60:]
    
    # Calculate rolling volatility (ATR proxy)
    ranges = highs - lows
    
    # Split into 3 periods of 20 days
    period1_range = np.mean(ranges[:20])
    period2_range = np.mean(ranges[20:40])
    period3_range = np.mean(ranges[40:])
    
    # Check for contraction (each period tighter than last)
    contracting = period1_range > period2_range > period3_range
    
    if not contracting:
        return False, 0, None
    
    # Calculate contraction ratio
    contraction_ratio = period3_range / period1_range
    
    # Tight VCP: final range < 40% of initial
    # Loose VCP: final range 40-60% of initial
    if contraction_ratio < 0.4:
        return True, 27, "tight"  # Tight VCP = 27 pts
    elif contraction_ratio < 0.6:
        return True, 20, "loose"  # Loose VCP = 20 pts
    
    return False, 0, None


def detect_flat_base(hist_daily):
    """
    Detect Flat Base pattern
    - Price range < 15% over 5+ weeks
    - Near highs (within 25% of 52w high)
    """
    if len(hist_daily) < 50:
        return False, 0
    
    # Last 5 weeks
    recent = hist_daily.tail(25)
    high = recent['High'].max()
    low = recent['Low'].min()
    
    price_range = (high - low) / low * 100
    
    # Check 52w high
    yearly = hist_daily.tail(252)
    yearly_high = yearly['High'].max()
    current = hist_daily['Close'].iloc[-1]
    from_high = (yearly_high - current) / yearly_high * 100
    
    if price_range < 15 and from_high < 25:
        return True, 18  # Flat Base = 18 pts
    
    return False, 0


def get_pattern_score(ticker):
    """Get combined pattern score for a ticker"""
    try:
        stock = yf.Ticker(ticker)
        
        # Get weekly data for 200W MA
        hist_weekly = stock.history(period="5y", interval="1wk")
        
        # Get daily data for patterns
        hist_daily = stock.history(period="2y", interval="1d")
        
        if len(hist_weekly) < 200 or len(hist_daily) < 100:
            return 0, {}
        
        # Calculate 200W MA
        ma_score, sma_200w, pct_from_ma = get_200w_ma_score(hist_weekly)
        
        # Detect patterns
        cup_handle, cup_score = detect_cup_and_handle(hist_daily)
        vcp, vcp_score, vcp_type = detect_vcp(hist_daily)
        flat_base, flat_score = detect_flat_base(hist_daily)
        
        # Determine best pattern combo
        patterns_found = []
        best_score = 0
        
        # Check combos (200W MA + pattern)
        near_200w = abs(pct_from_ma) <= 5 if pct_from_ma else False
        
        if near_200w and cup_handle:
            best_score = 35  # Best combo
            patterns_found = ["200W MA", "Cup & Handle"]
        elif near_200w and vcp:
            best_score = 33
            patterns_found = ["200W MA", f"VCP ({vcp_type})"]
        elif cup_handle:
            best_score = cup_score
            patterns_found = ["Cup & Handle"]
        elif near_200w and flat_base:
            best_score = 28
            patterns_found = ["200W MA", "Flat Base"]
        elif vcp:
            best_score = vcp_score
            patterns_found = [f"VCP ({vcp_type})"]
        elif ma_score > 0:
            best_score = ma_score
            patterns_found = [f"200W MA ({pct_from_ma:+.1f}%)"]
        elif flat_base:
            best_score = flat_score
            patterns_found = ["Flat Base"]
        
        current_price = hist_daily['Close'].iloc[-1]
        
        details = {
            "price": round(current_price, 2),
            "sma_200w": round(sma_200w, 2) if sma_200w else None,
            "pct_from_200w": round(pct_from_ma, 2) if pct_from_ma else None,
            "patterns": patterns_found,
            "pattern_score_raw": best_score
        }
        
        return best_score, details
        
    except Exception as e:
        return 0, {"error": str(e)}


# ============================================================
# FUNDAMENTALS
# ============================================================

def get_fundamentals_score(ticker):
    """Get fundamentals score (max 35 pts raw, scaled to 50)"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        score = 0
        details = {}
        
        # EPS Growth (9 pts)
        eps_growth = info.get('earningsGrowth', 0) or 0
        if eps_growth > 0.20:
            score += 9
            details['eps_growth'] = f"{eps_growth*100:.1f}% ⭐"
        elif eps_growth > 0.10:
            score += 6
            details['eps_growth'] = f"{eps_growth*100:.1f}%"
        elif eps_growth > 0:
            score += 3
            details['eps_growth'] = f"{eps_growth*100:.1f}%"
        else:
            details['eps_growth'] = f"{eps_growth*100:.1f}%"
        
        # ROE (8 pts)
        roe = info.get('returnOnEquity', 0) or 0
        if roe > 0.20:
            score += 8
            details['roe'] = f"{roe*100:.1f}% ⭐"
        elif roe > 0.15:
            score += 6
            details['roe'] = f"{roe*100:.1f}%"
        elif roe > 0.10:
            score += 4
            details['roe'] = f"{roe*100:.1f}%"
        else:
            details['roe'] = f"{roe*100:.1f}%"
        
        # Revenue Growth (7 pts)
        rev_growth = info.get('revenueGrowth', 0) or 0
        if rev_growth > 0.15:
            score += 7
            details['rev_growth'] = f"{rev_growth*100:.1f}% ⭐"
        elif rev_growth > 0.10:
            score += 5
            details['rev_growth'] = f"{rev_growth*100:.1f}%"
        elif rev_growth > 0.05:
            score += 3
            details['rev_growth'] = f"{rev_growth*100:.1f}%"
        else:
            details['rev_growth'] = f"{rev_growth*100:.1f}%"
        
        # Debt/Equity (6 pts)
        de = info.get('debtToEquity', None)
        if de is not None:
            de = de / 100 if de > 10 else de  # Normalize if in percentage
            if de < 0.3:
                score += 6
                details['debt_equity'] = f"{de:.2f} ⭐"
            elif de < 0.5:
                score += 4
                details['debt_equity'] = f"{de:.2f}"
            elif de < 1.0:
                score += 2
                details['debt_equity'] = f"{de:.2f}"
            else:
                details['debt_equity'] = f"{de:.2f}"
        else:
            details['debt_equity'] = "N/A"
        
        # P/E (5 pts)
        pe = info.get('trailingPE', 0) or 0
        if 10 <= pe <= 25:
            score += 5
            details['pe'] = f"{pe:.1f} ⭐"
        elif 5 <= pe <= 35:
            score += 3
            details['pe'] = f"{pe:.1f}"
        elif pe > 0:
            score += 1
            details['pe'] = f"{pe:.1f}"
        else:
            details['pe'] = "N/A"
        
        details['fundamentals_score_raw'] = score
        details['company_name'] = info.get('shortName', ticker)
        details['market_cap'] = info.get('marketCap', 0)
        details['sector'] = info.get('sector', 'Unknown')
        
        return score, details
        
    except Exception as e:
        return 0, {"error": str(e)}


# ============================================================
# MAIN SCREENER
# ============================================================

def screen_stock(ticker):
    """Full screen for a single stock"""
    pattern_score, pattern_details = get_pattern_score(ticker)
    fund_score, fund_details = get_fundamentals_score(ticker)
    
    # Scale scores (Pattern: 35 → 50, Fundamentals: 35 → 50)
    pattern_scaled = round((pattern_score / 35) * 50, 1)
    fund_scaled = round((fund_score / 35) * 50, 1)
    
    total_score = pattern_scaled + fund_scaled
    
    return {
        "ticker": ticker,
        "total_score": round(total_score, 1),
        "pattern_score": pattern_scaled,
        "pattern_score_raw": pattern_score,
        "fundamentals_score": fund_scaled,
        "fundamentals_score_raw": fund_score,
        "patterns": pattern_details.get("patterns", []),
        "price": pattern_details.get("price"),
        "sma_200w": pattern_details.get("sma_200w"),
        "pct_from_200w": pattern_details.get("pct_from_200w"),
        "company_name": fund_details.get("company_name", ticker),
        "sector": fund_details.get("sector"),
        "market_cap": fund_details.get("market_cap"),
        "eps_growth": fund_details.get("eps_growth"),
        "roe": fund_details.get("roe"),
        "rev_growth": fund_details.get("rev_growth"),
        "debt_equity": fund_details.get("debt_equity"),
        "pe": fund_details.get("pe"),
    }


def get_universe():
    """Get S&P 500 + Russell 1000 tickers"""
    import requests
    import csv
    from io import StringIO
    
    # S&P 500 from GitHub CSV
    try:
        url = 'https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv'
        r = requests.get(url, timeout=10)
        reader = csv.DictReader(StringIO(r.text))
        sp500 = [row['Symbol'].replace('.', '-') for row in reader]
    except:
        sp500 = []
    
    # Additional growth/tech stocks not in S&P 500
    additions = [
        'MSTR', 'PLTR', 'HOOD', 'SOFI', 'COIN', 'RBLX', 'U', 'SNOW', 'DDOG', 
        'NET', 'CRWD', 'ZS', 'OKTA', 'MDB', 'CFLT', 'PATH', 'DOCN', 'GTLB',
        'BILL', 'TOST', 'DUOL', 'IOT', 'ESTC', 'MNDY', 'PCOR', 'APP', 'SHOP',
        'SQ', 'AFRM', 'UPST', 'NU', 'GRAB', 'SE', 'MELI', 'BABA', 'JD', 'PDD'
    ]
    
    universe = list(set(sp500 + additions))
    print(f"Universe: {len(universe)} tickers ({len(sp500)} S&P 500 + {len(additions)} additions)")
    return universe


def run_screener(limit=None):
    """Run full screener on universe"""
    universe = get_universe()
    if limit:
        universe = universe[:limit]
    
    print(f"Screening {len(universe)} stocks...")
    print("=" * 60)
    
    results = []
    
    for i, ticker in enumerate(universe):
        try:
            result = screen_stock(ticker)
            results.append(result)
            
            if result['total_score'] >= 50:
                print(f"[{i+1}/{len(universe)}] {ticker}: {result['total_score']:.1f} pts - {result['patterns']}")
            
        except Exception as e:
            print(f"[{i+1}/{len(universe)}] {ticker}: ERROR - {e}")
        
        # Progress update every 50
        if (i + 1) % 50 == 0:
            print(f"... processed {i+1}/{len(universe)}")
    
    # Sort by total score
    results = sorted(results, key=lambda x: x['total_score'], reverse=True)
    
    return results


def print_results(results, top_n=20):
    """Print top results"""
    print("\n" + "=" * 80)
    print(f"TOP {top_n} CANDIDATES")
    print("=" * 80)
    
    for i, r in enumerate(results[:top_n]):
        print(f"\n{i+1}. {r['ticker']} ({r['company_name']})")
        print(f"   TOTAL: {r['total_score']:.1f}/100")
        print(f"   Pattern: {r['pattern_score']:.1f}/50 (raw: {r['pattern_score_raw']}/35) — {r['patterns']}")
        print(f"   Fundamentals: {r['fundamentals_score']:.1f}/50 (raw: {r['fundamentals_score_raw']}/35)")
        print(f"   Price: ${r['price']} | 200W MA: ${r['sma_200w']} ({r['pct_from_200w']:+.1f}%)" if r['sma_200w'] else f"   Price: ${r['price']}")
        print(f"   EPS: {r['eps_growth']} | ROE: {r['roe']} | Rev: {r['rev_growth']} | D/E: {r['debt_equity']} | P/E: {r['pe']}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Single ticker mode
        ticker = sys.argv[1].upper()
        print(f"Analyzing {ticker}...")
        result = screen_stock(ticker)
        print(json.dumps(result, indent=2))
    else:
        # Full screener
        results = run_screener()
        print_results(results, top_n=30)
        
        # Save results
        output_file = f"/Users/rara/clawd/trading/screener_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_file}")
