#!/usr/bin/env python3
"""
Mock Portfolio Tracker — Track multiple paper portfolios in parallel.
Usage:
  python3 mock_tracker.py check          # Check all portfolios
  python3 mock_tracker.py check mock1    # Check specific portfolio
  python3 mock_tracker.py summary        # Performance summary
  python3 mock_tracker.py add mock3 GOOGL 338.00 14  # Add position
"""
import yfinance as yf
import numpy as np
import json
import sys
import os
from datetime import datetime, timedelta

MOCK_FILE = os.path.join(os.path.dirname(__file__), 'mock_portfolios.json')
STOP_PCT = 0.10
TARGET_PCT = 0.20
MAX_HOLD_DAYS = 60


def load():
    with open(MOCK_FILE, 'r') as f:
        return json.load(f)

def save(data):
    data['last_updated'] = datetime.now().isoformat()
    with open(MOCK_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def get_prices(tickers):
    """Batch fetch current prices."""
    prices = {}
    for t in tickers:
        try:
            df = yf.download(t, period='5d', progress=False)
            if hasattr(df.columns, 'levels'):
                df.columns = df.columns.get_level_values(0)
            prices[t] = float(df['Close'].iloc[-1])
        except:
            pass
    return prices


def check_portfolio(name, portfolio, prices):
    """Check a single portfolio and auto-close triggered positions."""
    print(f"\n  {'='*65}")
    print(f"  {portfolio['name']}")
    print(f"  Strategy: {portfolio['strategy']}")
    print(f"  {'='*65}\n")

    positions = portfolio.get('positions', [])
    closed = portfolio.get('closed', [])
    today = datetime.now().strftime('%Y-%m-%d')

    if not positions:
        print("  No open positions.\n")
    else:
        total_cost = 0
        total_value = 0
        alerts = []

        print(f"  {'Ticker':<7} {'Entry':>8} {'Now':>8} {'P&L':>7} {'P&L$':>9} {'Days':>5} {'Status':<20}")
        print(f"  {'─'*7} {'─'*8} {'─'*8} {'─'*7} {'─'*9} {'─'*5} {'─'*20}")

        for pos in positions:
            ticker = pos['ticker']
            price = prices.get(ticker, pos['entry_price'])
            pnl = (price - pos['entry_price']) / pos['entry_price']
            pnl_dollar = pnl * pos['shares'] * pos['entry_price']
            days = (datetime.now() - datetime.strptime(pos['entry_date'], '%Y-%m-%d')).days
            cost = pos['shares'] * pos['entry_price']
            value = pos['shares'] * price

            total_cost += cost
            total_value += value

            # Status check
            status = 'HOLD'
            if price <= pos['stop_price']:
                status = '!! STOP HIT'
                alerts.append(f"  !! {ticker} hit stop ${pos['stop_price']:.2f}")
            elif price >= pos['target_price']:
                status = '>> TARGET HIT'
                alerts.append(f"  >> {ticker} hit target ${pos['target_price']:.2f}")
            elif today >= pos['max_exit_date']:
                status = '>> TIME EXIT'
                alerts.append(f"  >> {ticker} max hold reached")
            elif pnl < -0.05:
                status = '? WATCH'
            elif pnl > 0.10:
                status = '+ STRONG'

            pnl_str = f"{pnl*100:+.1f}%"
            print(f"  {ticker:<7} ${pos['entry_price']:>7.2f} ${price:>7.2f} {pnl_str:>6} ${pnl_dollar:>+8.2f} {days:>4}d {status}")

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0
        print(f"\n  Portfolio: ${total_cost:,.0f} invested → ${total_value:,.0f} ({total_pnl_pct:+.1f}% / ${total_pnl:+,.2f})")

        if alerts:
            print(f"\n  ALERTS:")
            for a in alerts:
                print(f"  {a}")

    # Show watchlist if exists
    wl = portfolio.get('watchlist', [])
    if wl:
        print(f"\n  Watchlist: {', '.join(wl)}")

    # Closed trades
    if closed:
        wins = [t for t in closed if t.get('return_pct', 0) > 0]
        losses = [t for t in closed if t.get('return_pct', 0) <= 0]
        print(f"\n  Closed: {len(closed)} trades | {len(wins)}W / {len(losses)}L")
        total_closed_pnl = sum(t.get('return_dollar', 0) for t in closed)
        print(f"  Realized P&L: ${total_closed_pnl:+,.2f}")

    print()


def check_all(specific=None):
    """Check all or specific portfolio."""
    data = load()
    portfolios = data['portfolios']

    # Get all unique tickers
    all_tickers = set()
    for p in portfolios.values():
        for pos in p.get('positions', []):
            all_tickers.add(pos['ticker'])

    if not all_tickers:
        print("  No open positions across any portfolio.")
        return

    print(f"  Fetching prices for {len(all_tickers)} stocks...")
    prices = get_prices(all_tickers)

    if specific:
        if specific in portfolios:
            check_portfolio(specific, portfolios[specific], prices)
        else:
            print(f"  Portfolio '{specific}' not found. Available: {', '.join(portfolios.keys())}")
    else:
        for name, portfolio in portfolios.items():
            check_portfolio(name, portfolio, prices)


def summary():
    """Performance summary across all portfolios."""
    data = load()
    print(f"\n  {'='*65}")
    print(f"  MOCK PORTFOLIO SUMMARY — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  {'='*65}\n")

    all_tickers = set()
    for p in data['portfolios'].values():
        for pos in p.get('positions', []):
            all_tickers.add(pos['ticker'])

    prices = get_prices(all_tickers) if all_tickers else {}

    print(f"  {'Portfolio':<30} {'Open':>5} {'Closed':>7} {'Unrealized':>12} {'Realized':>10}")
    print(f"  {'─'*30} {'─'*5} {'─'*7} {'─'*12} {'─'*10}")

    for name, p in data['portfolios'].items():
        n_open = len(p.get('positions', []))
        n_closed = len(p.get('closed', []))

        unreal = 0
        for pos in p.get('positions', []):
            price = prices.get(pos['ticker'], pos['entry_price'])
            unreal += (price - pos['entry_price']) * pos['shares']

        real = sum(t.get('return_dollar', 0) for t in p.get('closed', []))

        print(f"  {p['name'][:30]:<30} {n_open:>5} {n_closed:>7} ${unreal:>+10,.2f} ${real:>+8,.2f}")

    print()


def add_position(portfolio_name, ticker, price, shares, patterns=None):
    """Add a position to a mock portfolio."""
    data = load()
    if portfolio_name not in data['portfolios']:
        print(f"  Portfolio '{portfolio_name}' not found.")
        return

    pos = {
        'ticker': ticker.upper(),
        'entry_price': price,
        'shares': shares,
        'entry_date': datetime.now().strftime('%Y-%m-%d'),
        'stop_price': round(price * (1 - STOP_PCT), 2),
        'target_price': round(price * (1 + TARGET_PCT), 2),
        'max_exit_date': (datetime.now() + timedelta(days=MAX_HOLD_DAYS)).strftime('%Y-%m-%d'),
        'patterns': patterns or [],
        'status': 'open'
    }
    data['portfolios'][portfolio_name]['positions'].append(pos)
    save(data)
    print(f"  Added {ticker} to {portfolio_name}: {shares} shares @ ${price:.2f}")
    print(f"  Stop: ${pos['stop_price']:.2f} | Target: ${pos['target_price']:.2f} | Exit by: {pos['max_exit_date']}")


def close_position(portfolio_name, ticker, exit_price, reason='manual'):
    """Close a position in a mock portfolio."""
    data = load()
    if portfolio_name not in data['portfolios']:
        print(f"  Portfolio '{portfolio_name}' not found.")
        return

    p = data['portfolios'][portfolio_name]
    pos = None
    for i, position in enumerate(p['positions']):
        if position['ticker'].upper() == ticker.upper():
            pos = position
            p['positions'].pop(i)
            break

    if not pos:
        print(f"  No open position for {ticker} in {portfolio_name}")
        return

    pnl = (exit_price - pos['entry_price']) / pos['entry_price']
    pnl_dollar = pnl * pos['shares'] * pos['entry_price']
    days = (datetime.now() - datetime.strptime(pos['entry_date'], '%Y-%m-%d')).days

    trade = {
        **pos,
        'exit_price': exit_price,
        'exit_date': datetime.now().strftime('%Y-%m-%d'),
        'return_pct': round(pnl * 100, 2),
        'return_dollar': round(pnl_dollar, 2),
        'days_held': days,
        'exit_reason': reason
    }
    p['closed'].append(trade)
    save(data)

    win = 'WIN' if pnl >= 0 else 'LOSS'
    print(f"  {win}: {ticker} {pnl*100:+.1f}% (${pnl_dollar:+.2f}) in {days}d — {reason}")


def main():
    if len(sys.argv) < 2:
        print("\nMock Portfolio Tracker")
        print("  check [name]           — Check positions")
        print("  summary                — All portfolios overview")
        print("  add <port> <ticker> <price> <shares>  — Add position")
        print("  close <port> <ticker> <price> [reason] — Close position")
        return

    cmd = sys.argv[1]

    if cmd == 'check':
        specific = sys.argv[2] if len(sys.argv) > 2 else None
        check_all(specific)
    elif cmd == 'summary':
        summary()
    elif cmd == 'add' and len(sys.argv) >= 5:
        add_position(sys.argv[2], sys.argv[3], float(sys.argv[4]), int(sys.argv[5]))
    elif cmd == 'close' and len(sys.argv) >= 5:
        reason = sys.argv[5] if len(sys.argv) > 5 else 'manual'
        close_position(sys.argv[2], sys.argv[3], float(sys.argv[4]), reason)
    else:
        print("  Invalid command. Run without args for help.")


if __name__ == '__main__':
    main()
