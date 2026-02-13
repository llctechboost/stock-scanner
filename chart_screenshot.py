#!/usr/bin/env python3
"""
TradingView Chart Screenshot Utility
Captures chart images for stocks using TradingView's widget.
"""
import subprocess
import sys
import os
import time
import json

SCREENSHOT_DIR = os.path.expanduser("~/clawd/trading/charts")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def get_tradingview_snapshot_url(symbol, interval="D", width=800, height=400):
    """Generate a TradingView mini chart widget URL."""
    return (
        f"https://www.tradingview.com/widgetembed/?hideideas=1&overrides=%7B%7D"
        f"&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=en"
        f"&symbol={symbol}&interval={interval}&theme=dark"
        f"&style=1&timezone=America%2FNew_York&withdateranges=1"
        f"&studies=%5B%5D&width={width}&height={height}"
    )

def get_simple_chart_url(symbol):
    """Use TradingView's simple chart image URL."""
    return f"https://www.tradingview.com/symbols/{symbol}/"

if __name__ == "__main__":
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["NVDA"]
    for sym in symbols:
        print(f"Symbol: {sym}")
        print(f"  Chart URL: {get_simple_chart_url(sym)}")
        print(f"  Widget URL: {get_tradingview_snapshot_url(sym)}")
