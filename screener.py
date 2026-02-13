#!/usr/bin/env python3
"""
Stock Screener - Finds setups for VCP, Cup & Handle, Munger 200-day
Runs daily to surface trade candidates
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from datetime import datetime, timedelta
from config import ALPACA_KEY, ALPACA_SECRET

# Watchlist of quality stocks to scan
UNIVERSE = [
    # Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "CRM", "ADBE",
    # Quality/Munger style
    "COST", "V", "MA", "JNJ", "PG", "KO", "PEP", "WMT", "HD", "MCD",
    # Growth
    "NFLX", "SHOP", "SQ", "SNOW", "PLTR", "NET", "DDOG", "CRWD", "ZS", "PANW",
    # Financials
    "JPM", "BAC", "GS", "MS", "BRK.B", "BLK", "SCHW",
    # Healthcare
    "UNH", "LLY", "ABBV", "MRK", "TMO", "DHR", "ISRG",
    # Industrials
    "CAT", "DE", "UNP", "HON", "GE", "RTX", "LMT"
]

headers = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

def get_bars(symbol: str, days: int = 250) -> list:
    """Get daily bars for a symbol"""
    end = datetime.now()
    start = end - timedelta(days=days + 50)  # buffer for trading days
    
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    params = {
        "timeframe": "1Day",
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "limit": days
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json().get("bars", [])
    except Exception as e:
        return []

def calc_sma(bars: list, period: int) -> float:
    """Calculate simple moving average"""
    if len(bars) < period:
        return 0
    closes = [b["c"] for b in bars[-period:]]
    return sum(closes) / len(closes)

def calc_atr(bars: list, period: int = 14) -> float:
    """Calculate average true range"""
    if len(bars) < period + 1:
        return 0
    
    trs = []
    for i in range(-period, 0):
        high = bars[i]["h"]
        low = bars[i]["l"]
        prev_close = bars[i-1]["c"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    
    return sum(trs) / len(trs)

def scan_vcp(symbol: str, bars: list) -> dict:
    """
    VCP: Volatility Contraction Pattern
    - Price above 50 & 200 SMA (uptrend)
    - Recent volatility contracting (ATR decreasing)
    - Tight consolidation (last 5 days range < 5%)
    """
    if len(bars) < 200:
        return None
    
    current = bars[-1]["c"]
    sma50 = calc_sma(bars, 50)
    sma200 = calc_sma(bars, 200)
    
    # Must be in uptrend
    if current < sma50 or current < sma200:
        return None
    
    # Check volatility contraction
    atr_20 = calc_atr(bars[:-10], 20)  # ATR 20 days ago
    atr_now = calc_atr(bars, 10)       # Recent ATR
    
    if atr_20 == 0 or atr_now >= atr_20:
        return None  # No contraction
    
    # Check tight range (last 5 days)
    recent = bars[-5:]
    high5 = max(b["h"] for b in recent)
    low5 = min(b["l"] for b in recent)
    range_pct = (high5 - low5) / low5 * 100
    
    if range_pct > 6:
        return None  # Not tight enough
    
    contraction = (1 - atr_now / atr_20) * 100
    
    return {
        "symbol": symbol,
        "strategy": "VCP",
        "price": current,
        "sma50": sma50,
        "sma200": sma200,
        "range_pct": range_pct,
        "contraction": contraction,
        "score": contraction  # Higher contraction = better
    }

def scan_cup_handle(symbol: str, bars: list) -> dict:
    """
    Cup & Handle:
    - Was down 15-35% from high (cup depth)
    - Recovered most of the drop
    - Recent small pullback (handle)
    """
    if len(bars) < 60:
        return None
    
    current = bars[-1]["c"]
    
    # Find 52-week high
    high_52w = max(b["h"] for b in bars[-252:]) if len(bars) >= 252 else max(b["h"] for b in bars)
    
    # Find lowest point in last 60 days (cup bottom)
    lows_60 = [(i, b["l"]) for i, b in enumerate(bars[-60:])]
    cup_bottom_idx, cup_bottom = min(lows_60, key=lambda x: x[1])
    
    # Cup depth should be 15-35%
    depth = (high_52w - cup_bottom) / high_52w * 100
    if depth < 12 or depth > 40:
        return None
    
    # Should have recovered (within 10% of high)
    recovery = (current - cup_bottom) / (high_52w - cup_bottom) * 100 if high_52w != cup_bottom else 0
    if recovery < 70:
        return None  # Not recovered enough
    
    # Handle: small recent pullback (2-10%)
    recent_high = max(b["h"] for b in bars[-15:])
    handle_depth = (recent_high - current) / recent_high * 100
    
    if handle_depth < 1 or handle_depth > 12:
        return None  # No handle or too deep
    
    return {
        "symbol": symbol,
        "strategy": "CUP",
        "price": current,
        "high_52w": high_52w,
        "cup_depth": depth,
        "recovery": recovery,
        "handle_depth": handle_depth,
        "score": recovery - handle_depth  # Good recovery, small handle = better
    }

def scan_munger_200(symbol: str, bars: list) -> dict:
    """
    Munger 200-day:
    - Quality stock (we assume our universe is quality)
    - Trading within 5% of 200 SMA
    - Oversold opportunity
    """
    if len(bars) < 200:
        return None
    
    current = bars[-1]["c"]
    sma200 = calc_sma(bars, 200)
    sma50 = calc_sma(bars, 50)
    
    # Distance from 200 SMA
    distance = (current - sma200) / sma200 * 100
    
    # Want stocks near or below 200 SMA (within -5% to +3%)
    if distance < -10 or distance > 5:
        return None
    
    # Prefer if recently pulled back
    high_20 = max(b["h"] for b in bars[-20:])
    pullback = (high_20 - current) / high_20 * 100
    
    if pullback < 3:
        return None  # Not enough pullback
    
    return {
        "symbol": symbol,
        "strategy": "M200",
        "price": current,
        "sma200": sma200,
        "distance_pct": distance,
        "pullback_pct": pullback,
        "score": pullback - abs(distance)  # Good pullback, close to 200 = better
    }

def run_scan():
    """Run all scans and return results"""
    results = {"VCP": [], "CUP": [], "M200": []}
    
    print(f"🔍 Scanning {len(UNIVERSE)} stocks...")
    
    for i, symbol in enumerate(UNIVERSE):
        bars = get_bars(symbol)
        if not bars:
            continue
        
        # Run each strategy scan
        vcp = scan_vcp(symbol, bars)
        if vcp:
            results["VCP"].append(vcp)
        
        cup = scan_cup_handle(symbol, bars)
        if cup:
            results["CUP"].append(cup)
        
        m200 = scan_munger_200(symbol, bars)
        if m200:
            results["M200"].append(m200)
        
        # Progress
        if (i + 1) % 10 == 0:
            print(f"  Scanned {i + 1}/{len(UNIVERSE)}...")
    
    # Sort by score
    for strat in results:
        results[strat].sort(key=lambda x: x["score"], reverse=True)
    
    return results

def format_results(results: dict) -> str:
    """Format results for display"""
    lines = [f"📊 SCAN RESULTS — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    
    # VCP
    lines.append("🔷 VCP (Volatility Contraction)")
    if results["VCP"]:
        for r in results["VCP"][:5]:
            lines.append(f"  • {r['symbol']:5} ${r['price']:.2f} — range {r['range_pct']:.1f}%, contraction {r['contraction']:.0f}%")
    else:
        lines.append("  No setups found")
    
    lines.append("")
    
    # Cup & Handle
    lines.append("☕ CUP & HANDLE")
    if results["CUP"]:
        for r in results["CUP"][:5]:
            lines.append(f"  • {r['symbol']:5} ${r['price']:.2f} — cup {r['cup_depth']:.0f}%, handle {r['handle_depth']:.1f}%")
    else:
        lines.append("  No setups found")
    
    lines.append("")
    
    # Munger 200
    lines.append("📏 MUNGER 200-DAY")
    if results["M200"]:
        for r in results["M200"][:5]:
            lines.append(f"  • {r['symbol']:5} ${r['price']:.2f} — {r['distance_pct']:+.1f}% from 200 SMA, pulled back {r['pullback_pct']:.1f}%")
    else:
        lines.append("  No setups found")
    
    return "\n".join(lines)

if __name__ == "__main__":
    results = run_scan()
    print(format_results(results))
