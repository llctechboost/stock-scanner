#!/usr/bin/env python3
"""
Position Manager - Track open trades, P&L, and risk metrics
"""
import json
import argparse
import yfinance as yf
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

POSITIONS_FILE = 'positions.json'

def load_positions():
    """Load open positions."""
    try:
        with open(POSITIONS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_positions(positions):
    """Save positions."""
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions, f, indent=2)

def add_position(ticker, shares, entry, stop, pattern='', conviction=0):
    """Add new position."""
    positions = load_positions()
    
    position = {
        'id': len(positions) + 1,
        'ticker': ticker.upper(),
        'shares': shares,
        'entry': entry,
        'stop': stop,
        'pattern': pattern,
        'conviction': conviction,
        'entry_date': datetime.now().isoformat()[:10],
        'status': 'open'
    }
    
    positions.append(position)
    save_positions(positions)
    
    risk = (entry - stop) * shares
    print(f"\n{Fore.GREEN}✓ Position opened:{Style.RESET_ALL}")
    print(f"  {ticker.upper()}: {shares} shares @ ${entry:.2f}")
    print(f"  Stop: ${stop:.2f} (${risk:.2f} risk)\n")

def close_position(ticker, exit_price):
    """Close position."""
    positions = load_positions()
    
    for pos in positions:
        if pos['ticker'] == ticker.upper() and pos['status'] == 'open':
            pos['status'] = 'closed'
            pos['exit'] = exit_price
            pos['exit_date'] = datetime.now().isoformat()[:10]
            
            pnl = (exit_price - pos['entry']) * pos['shares']
            pnl_pct = ((exit_price - pos['entry']) / pos['entry']) * 100
            
            pos['pnl'] = pnl
            pos['pnl_pct'] = pnl_pct
            
            save_positions(positions)
            
            color = Fore.GREEN if pnl > 0 else Fore.RED
            print(f"\n{color}✓ Position closed:{Style.RESET_ALL}")
            print(f"  {ticker.upper()}: {pos['shares']} shares")
            print(f"  ${pos['entry']:.2f} → ${exit_price:.2f}")
            print(f"  P&L: {color}${pnl:.2f} ({pnl_pct:+.1f}%){Style.RESET_ALL}\n")
            return
    
    print(f"\n{Fore.RED}✗ No open position found for {ticker.upper()}{Style.RESET_ALL}\n")

def show_positions():
    """Display current positions with live P&L."""
    positions = load_positions()
    open_pos = [p for p in positions if p['status'] == 'open']
    
    if not open_pos:
        print(f"\n{Fore.YELLOW}No open positions.{Style.RESET_ALL}\n")
        return
    
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📊 OPEN POSITIONS")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
    
    total_value = 0
    total_pnl = 0
    
    print(f"{'Ticker':<8}{'Shares':>8}{'Entry':>10}{'Current':>10}{'Stop':>10}{'P&L':>12}{'Risk':>10}")
    print(f"{'─'*80}")
    
    for pos in open_pos:
        ticker = pos['ticker']
        
        try:
            stock = yf.Ticker(ticker)
            current = stock.history(period='1d')['Close'].iloc[-1]
        except:
            current = pos['entry']
        
        pnl = (current - pos['entry']) * pos['shares']
        pnl_pct = ((current - pos['entry']) / pos['entry']) * 100
        risk = (pos['entry'] - pos['stop']) * pos['shares']
        
        total_value += current * pos['shares']
        total_pnl += pnl
        
        color = Fore.GREEN if pnl > 0 else Fore.RED if pnl < 0 else Fore.YELLOW
        
        print(f"{Fore.CYAN}{ticker:<8}{Style.RESET_ALL}"
              f"{pos['shares']:>8}"
              f"${pos['entry']:>9.2f}"
              f"${current:>9.2f}"
              f"${pos['stop']:>9.2f}"
              f"{color}${pnl:>7.2f} ({pnl_pct:+.1f}%){Style.RESET_ALL}"
              f"${risk:>9.2f}")
    
    print(f"{'─'*80}")
    total_color = Fore.GREEN if total_pnl > 0 else Fore.RED
    print(f"\n{Fore.WHITE}Total Value: ${total_value:,.2f}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Total P&L: {total_color}${total_pnl:,.2f}{Style.RESET_ALL}\n")

def stats():
    """Show trading statistics."""
    positions = load_positions()
    closed = [p for p in positions if p['status'] == 'closed']
    
    if not closed:
        print(f"\n{Fore.YELLOW}No closed positions yet.{Style.RESET_ALL}\n")
        return
    
    total = len(closed)
    winners = [p for p in closed if p.get('pnl', 0) > 0]
    losers = [p for p in closed if p.get('pnl', 0) <= 0]
    
    win_rate = len(winners) / total * 100
    total_pnl = sum(p.get('pnl', 0) for p in closed)
    avg_win = sum(p['pnl'] for p in winners) / len(winners) if winners else 0
    avg_loss = sum(p['pnl'] for p in losers) / len(losers) if losers else 0
    
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📈 TRADING STATS")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
    
    print(f"Total Trades:   {total}")
    print(f"Winners:        {Fore.GREEN}{len(winners)}{Style.RESET_ALL}")
    print(f"Losers:         {Fore.RED}{len(losers)}{Style.RESET_ALL}")
    print(f"Win Rate:       {Fore.GREEN if win_rate >= 50 else Fore.RED}{win_rate:.1f}%{Style.RESET_ALL}")
    print()
    print(f"Total P&L:      {Fore.GREEN if total_pnl > 0 else Fore.RED}${total_pnl:,.2f}{Style.RESET_ALL}")
    print(f"Avg Win:        {Fore.GREEN}${avg_win:.2f}{Style.RESET_ALL}")
    print(f"Avg Loss:       {Fore.RED}${avg_loss:.2f}{Style.RESET_ALL}\n")

def main():
    parser = argparse.ArgumentParser(description='Position Manager')
    subparsers = parser.add_subparsers(dest='command')
    
    # Add position
    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('ticker')
    add_parser.add_argument('shares', type=int)
    add_parser.add_argument('entry', type=float)
    add_parser.add_argument('stop', type=float)
    add_parser.add_argument('--pattern', default='')
    add_parser.add_argument('--conviction', type=int, default=0)
    
    # Close position
    close_parser = subparsers.add_parser('close')
    close_parser.add_argument('ticker')
    close_parser.add_argument('exit', type=float)
    
    # List/Stats
    subparsers.add_parser('list')
    subparsers.add_parser('stats')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        add_position(args.ticker, args.shares, args.entry, args.stop, args.pattern, args.conviction)
    elif args.command == 'close':
        close_position(args.ticker, args.exit)
    elif args.command == 'list':
        show_positions()
    elif args.command == 'stats':
        stats()
    else:
        show_positions()

if __name__ == '__main__':
    main()
