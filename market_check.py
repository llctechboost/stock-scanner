#!/usr/bin/env python3
"""
Quick market data fetcher for cron jobs.
Uses yfinance (reliable) instead of Yahoo API (blocked).
Usage: python3 market_check.py
"""
import yfinance as yf
import json
import sys

def get_market():
    data = {}
    for sym in ['SPY', 'QQQ', 'DIA', 'IWM', 'VIX']:
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            price = info['lastPrice']
            prev = info['previousClose']
            chg = ((price / prev) - 1) * 100
            data[sym] = {
                'price': round(price, 2),
                'prev_close': round(prev, 2),
                'change_pct': round(chg, 2)
            }
        except:
            pass

    # Save for other tools
    with open('market_check_latest.json', 'w') as f:
        json.dump(data, f, indent=2)

    # Print summary
    for sym, d in data.items():
        arrow = '+' if d['change_pct'] >= 0 else ''
        print(f"{sym}: ${d['price']:.2f} ({arrow}{d['change_pct']:.2f}%)")

    return data

if __name__ == '__main__':
    get_market()
