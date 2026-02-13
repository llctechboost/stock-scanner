#!/usr/bin/env python3
"""
Price Alert Checker
Checks price alerts and outputs triggered alerts
Run via cron every 15-30 minutes during market hours
"""

import json
import os
import yfinance as yf
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALERTS_FILE = os.path.join(SCRIPT_DIR, 'price_alerts.json')

def load_alerts():
    try:
        with open(ALERTS_FILE) as f:
            return json.load(f)
    except:
        return {"alerts": []}

def save_alerts(data):
    with open(ALERTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if len(data) > 0:
            return data['Close'].iloc[-1]
    except:
        pass
    return None

def check_alerts():
    data = load_alerts()
    triggered = []
    
    # Group alerts by ticker
    tickers = set(a['ticker'] for a in data['alerts'] if a.get('active', True))
    
    for ticker in tickers:
        price = get_price(ticker)
        if price is None:
            continue
        
        for alert in data['alerts']:
            if alert['ticker'] != ticker or not alert.get('active', True):
                continue
            
            target = alert['price']
            alert_type = alert['type']
            
            # Check if triggered
            if alert_type == 'above' and price >= target:
                triggered.append({
                    'ticker': ticker,
                    'current_price': price,
                    'alert_price': target,
                    'message': alert['message']
                })
                alert['active'] = False  # Deactivate after trigger
                alert['triggered_at'] = datetime.now().isoformat()
                alert['triggered_price'] = price
                
            elif alert_type == 'below' and price <= target:
                triggered.append({
                    'ticker': ticker,
                    'current_price': price,
                    'alert_price': target,
                    'message': alert['message']
                })
                alert['active'] = False
                alert['triggered_at'] = datetime.now().isoformat()
                alert['triggered_price'] = price
    
    # Save updated alerts
    save_alerts(data)
    
    return triggered

def main():
    triggered = check_alerts()
    
    if triggered:
        print("🚨 PRICE ALERTS TRIGGERED:")
        print("=" * 50)
        for t in triggered:
            print(f"\n{t['message']}")
            print(f"   Current: ${t['current_price']:.2f} | Alert: ${t['alert_price']:.2f}")
        return triggered
    else:
        # Just output current prices for active alerts
        data = load_alerts()
        active = [a for a in data['alerts'] if a.get('active', True)]
        if active:
            tickers = set(a['ticker'] for a in active)
            print("📊 Active Alerts Status:")
            for ticker in tickers:
                price = get_price(ticker)
                ticker_alerts = [a for a in active if a['ticker'] == ticker]
                print(f"\n{ticker}: ${price:.2f}")
                for a in ticker_alerts:
                    direction = "↓" if a['type'] == 'below' else "↑"
                    distance = ((a['price'] - price) / price * 100)
                    print(f"   {direction} ${a['price']:.2f} ({distance:+.1f}%)")
        return None

if __name__ == '__main__':
    main()
