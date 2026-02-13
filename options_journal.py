#!/usr/bin/env python3
"""
Options Journal - Track options trades separately
"""
import json
import argparse
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

OPTIONS_FILE = 'options_trades.json'

def load_options():
    try:
        with open(OPTIONS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_options(trades):
    with open(OPTIONS_FILE, 'w') as f:
        json.dump(trades, f, indent=2)

def add_option(ticker, option_type, strike, expiry, entry, exit=None, contracts=1):
    """Add options trade."""
    trades = load_options()
    
    trade = {
        'id': len(trades) + 1,
        'date': datetime.now().isoformat()[:10],
        'ticker': ticker.upper(),
        'type': option_type.upper(),
        'strike': strike,
        'expiry': expiry,
        'contracts': contracts,
        'entry_premium': entry,
        'exit_premium': exit,
        'status': 'closed' if exit else 'open'
    }
    
    if exit:
        trade['pnl'] = (exit - entry) * 100 * contracts
        trade['pnl_pct'] = ((exit - entry) / entry) * 100
        trade['win'] = trade['pnl'] > 0
    
    trades.append(trade)
    save_options(trades)
    
    if exit:
        color = Fore.GREEN if trade['win'] else Fore.RED
        print(f"\n{color}✓ Options trade closed:{Style.RESET_ALL}")
        print(f"  {ticker.upper()} ${strike} {option_type.upper()} {expiry}")
        print(f"  ${entry:.2f} → ${exit:.2f}")
        print(f"  P&L: {color}${trade['pnl']:.2f} ({trade['pnl_pct']:+.1f}%){Style.RESET_ALL}\n")
    else:
        print(f"\n{Fore.GREEN}✓ Options position opened:{Style.RESET_ALL}")
        print(f"  {ticker.upper()} ${strike} {option_type.upper()} {expiry}")
        print(f"  Entry: ${entry:.2f} x {contracts} contract{'s' if contracts > 1 else ''}\n")

def list_options():
    """List options trades."""
    trades = load_options()
    
    if not trades:
        print(f"\n{Fore.YELLOW}No options trades yet.{Style.RESET_ALL}\n")
        return
    
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📊 OPTIONS JOURNAL")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
    
    print(f"{'ID':<4}{'Date':<12}{'Ticker':<8}{'Type':<6}{'Strike':>8}{'Entry':>8}{'Exit':>8}{'P&L':>10}{'Status':<8}")
    print(f"{'─'*80}")
    
    for t in trades[-20:]:
        exit_str = f"${t['exit_premium']:.2f}" if t.get('exit_premium') else '-'
        pnl_str = f"${t.get('pnl', 0):.2f}" if t.get('pnl') else '-'
        
        if t['status'] == 'closed':
            color = Fore.GREEN if t.get('win') else Fore.RED
        else:
            color = Fore.YELLOW
        
        print(f"{t['id']:<4}{t['date']:<12}{t['ticker']:<8}{t['type']:<6}${t['strike']:>7.2f}${t['entry_premium']:>7.2f}{exit_str:>8}{color}{pnl_str:>10}{Style.RESET_ALL} {t['status']:<8}")
    
    print()

def stats_options():
    """Show options stats."""
    trades = load_options()
    
    closed = [t for t in trades if t['status'] == 'closed']
    
    if not closed:
        print(f"\n{Fore.YELLOW}No closed options trades to analyze.{Style.RESET_ALL}\n")
        return
    
    total = len(closed)
    winners = [t for t in closed if t.get('win')]
    losers = [t for t in closed if not t.get('win')]
    
    win_rate = len(winners) / total * 100
    total_pnl = sum(t.get('pnl', 0) for t in closed)
    avg_win = sum(t['pnl'] for t in winners) / len(winners) if winners else 0
    avg_loss = sum(t['pnl'] for t in losers) / len(losers) if losers else 0
    
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📈 OPTIONS PERFORMANCE")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
    
    print(f"Total Trades:     {total}")
    print(f"Winners:          {Fore.GREEN}{len(winners)}{Style.RESET_ALL}")
    print(f"Losers:           {Fore.RED}{len(losers)}{Style.RESET_ALL}")
    print(f"Win Rate:         {Fore.GREEN if win_rate >= 50 else Fore.RED}{win_rate:.1f}%{Style.RESET_ALL}")
    print()
    print(f"Total P&L:        {Fore.GREEN if total_pnl > 0 else Fore.RED}${total_pnl:,.2f}{Style.RESET_ALL}")
    print(f"Avg Win:          {Fore.GREEN}${avg_win:.2f}{Style.RESET_ALL}")
    print(f"Avg Loss:         {Fore.RED}${avg_loss:.2f}{Style.RESET_ALL}")
    print()

def main():
    parser = argparse.ArgumentParser(description='Options Journal')
    subparsers = parser.add_subparsers(dest='command')
    
    # Add
    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('ticker')
    add_parser.add_argument('type', choices=['call', 'put'])
    add_parser.add_argument('strike', type=float)
    add_parser.add_argument('expiry')
    add_parser.add_argument('entry', type=float)
    add_parser.add_argument('--exit', type=float)
    add_parser.add_argument('--contracts', type=int, default=1)
    
    # List/Stats
    subparsers.add_parser('list')
    subparsers.add_parser('stats')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        add_option(args.ticker, args.type, args.strike, args.expiry, args.entry, args.exit, args.contracts)
    elif args.command == 'list':
        list_options()
    elif args.command == 'stats':
        stats_options()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
