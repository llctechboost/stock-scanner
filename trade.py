#!/usr/bin/env python3
"""
Quick Trade Logger - Fast trade entry
Usage: python trade.py TSLA 250 245 entry
"""
import sys
import json
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

TRADES_FILE = 'trades.json'

def load_trades():
    try:
        with open(TRADES_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_trades(trades):
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)

def log_trade(ticker, price1, price2, action):
    """Log a quick trade."""
    trades = load_trades()
    
    if action.lower() == 'entry':
        trade = {
            'id': len(trades) + 1,
            'date': datetime.now().isoformat()[:10],
            'ticker': ticker.upper(),
            'entry': price1,
            'stop': price2,
            'exit': None,
            'pnl': None,
            'status': 'open'
        }
        trades.append(trade)
        save_trades(trades)
        print(f"\n{Fore.GREEN}✓ Entry logged:{Style.RESET_ALL} {ticker.upper()} @ ${price1:.2f} (Stop: ${price2:.2f})\n")
    
    elif action.lower() == 'exit':
        # Find open trade
        open_trade = None
        for t in reversed(trades):
            if t['ticker'] == ticker.upper() and t.get('status') == 'open':
                open_trade = t
                break
        
        if open_trade:
            open_trade['exit'] = price1
            open_trade['status'] = 'closed'
            open_trade['pnl'] = price1 - open_trade['entry']
            open_trade['pnl_pct'] = (open_trade['pnl'] / open_trade['entry']) * 100
            open_trade['win'] = open_trade['pnl'] > 0
            
            save_trades(trades)
            
            color = Fore.GREEN if open_trade['win'] else Fore.RED
            print(f"\n{color}✓ Exit logged:{Style.RESET_ALL} {ticker.upper()} @ ${price1:.2f}")
            print(f"  P&L: {color}${open_trade['pnl']:.2f} ({open_trade['pnl_pct']:+.1f}%){Style.RESET_ALL}\n")
        else:
            print(f"\n{Fore.RED}✗ No open trade found for {ticker.upper()}{Style.RESET_ALL}\n")

def main():
    if len(sys.argv) != 5:
        print(f"\nUsage: {sys.argv[0]} TICKER PRICE1 PRICE2 entry|exit")
        print(f"\nExamples:")
        print(f"  Entry: {sys.argv[0]} TSLA 250 245 entry")
        print(f"  Exit:  {sys.argv[0]} TSLA 270 0 exit\n")
        sys.exit(1)
    
    ticker = sys.argv[1]
    price1 = float(sys.argv[2])
    price2 = float(sys.argv[3])
    action = sys.argv[4]
    
    log_trade(ticker, price1, price2, action)

if __name__ == '__main__':
    main()
