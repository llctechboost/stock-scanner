#!/usr/bin/env python3
"""
Morning Briefing - Daily summary for trading
Run at market open for actionable intel
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from datetime import datetime
from config import ALPACA_KEY, ALPACA_SECRET
from alpaca_client import client
from tracker import tracker
from screener import run_scan, format_results

headers = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

def get_market_status():
    """Check if market is open and get calendar"""
    resp = requests.get("https://paper-api.alpaca.markets/v2/clock", headers=headers)
    clock = resp.json()
    return clock

def get_major_indices():
    """Get SPY, QQQ, IWM for market direction"""
    indices = {}
    for symbol in ["SPY", "QQQ", "IWM"]:
        try:
            url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?timeframe=1Day&limit=2"
            resp = requests.get(url, headers=headers)
            bars = resp.json().get("bars", [])
            if len(bars) >= 2:
                prev = bars[-2]["c"]
                curr = bars[-1]["c"]
                change = (curr - prev) / prev * 100
                indices[symbol] = {"price": curr, "change": change}
        except:
            pass
    return indices

def generate_briefing() -> str:
    """Generate the full morning briefing"""
    lines = []
    lines.append(f"☀️ MORNING BRIEFING — {datetime.now().strftime('%A %b %d, %Y')}")
    lines.append("=" * 40)
    
    # Market Status
    clock = get_market_status()
    if clock["is_open"]:
        lines.append("🟢 Market: OPEN")
    else:
        next_open = clock["next_open"][:10]
        lines.append(f"🔴 Market: CLOSED (opens {next_open})")
    
    lines.append("")
    
    # Account Status
    try:
        acct = client.get_account()
        equity = float(acct["equity"])
        cash = float(acct["cash"])
        bp = float(acct["buying_power"])
        lines.append("💰 ACCOUNT")
        lines.append(f"  Equity: ${equity:,.2f}")
        lines.append(f"  Cash: ${cash:,.2f}")
        lines.append(f"  Buying Power: ${bp:,.2f}")
    except Exception as e:
        lines.append(f"  ⚠️ Could not fetch account: {e}")
    
    lines.append("")
    
    # Open Positions
    positions = tracker.get_open_trades()
    if positions:
        lines.append(f"📈 OPEN POSITIONS ({len(positions)})")
        for t in positions:
            lines.append(f"  • {t.symbol} ({t.strategy}) — {t.qty} @ ${t.entry_price:.2f}")
            if t.stop_loss:
                lines.append(f"    Stop: ${t.stop_loss:.2f} | Target: ${t.target:.2f}")
    else:
        lines.append("📈 No open positions")
    
    lines.append("")
    
    # Strategy Stats
    stats = tracker.get_stats()
    if stats["trades"] > 0:
        lines.append("📊 STRATEGY PERFORMANCE")
        lines.append(f"  Total: {stats['trades']} trades | {stats['win_rate']:.0f}% win | ${stats['total_pnl']:+,.2f}")
    
    lines.append("")
    
    # Scan Results
    lines.append("🔍 TODAY'S SETUPS")
    try:
        results = run_scan()
        total = len(results["VCP"]) + len(results["CUP"]) + len(results["M200"])
        
        if total == 0:
            lines.append("  No setups matching criteria")
        else:
            if results["VCP"]:
                lines.append(f"  VCP: {', '.join(r['symbol'] for r in results['VCP'][:3])}")
            if results["CUP"]:
                lines.append(f"  Cup&Handle: {', '.join(r['symbol'] for r in results['CUP'][:3])}")
            if results["M200"]:
                lines.append(f"  Munger 200: {', '.join(r['symbol'] for r in results['M200'][:3])}")
    except Exception as e:
        lines.append(f"  ⚠️ Scan failed: {e}")
    
    lines.append("")
    lines.append("=" * 40)
    lines.append("Ready to trade. What's the move?")
    
    return "\n".join(lines)

if __name__ == "__main__":
    print(generate_briefing())
