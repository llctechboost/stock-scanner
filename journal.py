#!/usr/bin/env python3
"""
Trade Journal - Full P&L tracking with stats
"""
import json
import argparse
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

TRADES_FILE = 'trades.json'

def load_trades():
    """Load trades from JSON."""
    try:
        with open(TRADES_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_trades(trades):
    """Save trades to JSON."""
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)

def add_trade(ticker, entry, exit, pattern='Unknown'):
    """Add a new trade."""
    trades = load_trades()
    
    pnl = exit - entry
    pnl_pct = (pnl / entry) * 100
    
    trade = {
        'id': len(trades) + 1,
        'date': datetime.now().isoformat()[:10],
        'ticker': ticker,
        'pattern': pattern,
        'entry': entry,
        'exit': exit,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'win': pnl > 0
    }
    
    trades.append(trade)
    save_trades(trades)
    
    color = Fore.GREEN if trade['win'] else Fore.RED
    print(f"\n{color}✓ Trade added:{Style.RESET_ALL}")
    print(f"  {ticker} @ ${entry:.2f} → ${exit:.2f}")
    print(f"  P&L: {color}${pnl:.2f} ({pnl_pct:+.1f}%){Style.RESET_ALL}\n")

def list_trades():
    """List all trades."""
    trades = load_trades()
    
    if not trades:
        print(f"\n{Fore.YELLOW}No trades recorded yet.{Style.RESET_ALL}\n")
        return
    
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📊 TRADE JOURNAL")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
    
    print(f"{'ID':<4}{'Date':<12}{'Ticker':<8}{'Entry':>8}{'Exit':>8}{'P&L':>10}{'Return':>8}{'Pattern':<15}")
    print(f"{'─'*70}")
    
    for t in trades[-20:]:  # Last 20 trades
        color = Fore.GREEN if t['win'] else Fore.RED
        print(f"{t['id']:<4}{t['date']:<12}{t['ticker']:<8}${t['entry']:>7.2f}${t['exit']:>7.2f}{color}${t['pnl']:>9.2f}{t['pnl_pct']:>+7.1f}%{Style.RESET_ALL} {t.get('pattern', 'N/A'):<15}")
    
    print()

def show_stats():
    """Show trade statistics."""
    trades = load_trades()
    
    if not trades:
        print(f"\n{Fore.YELLOW}No trades to analyze.{Style.RESET_ALL}\n")
        return
    
    total_trades = len(trades)
    winners = [t for t in trades if t['win']]
    losers = [t for t in trades if not t['win']]
    
    win_rate = len(winners) / total_trades * 100
    
    total_pnl = sum(t['pnl'] for t in trades)
    avg_win = sum(t['pnl'] for t in winners) / len(winners) if winners else 0
    avg_loss = sum(t['pnl'] for t in losers) / len(losers) if losers else 0
    
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📈 PERFORMANCE STATS")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
    
    print(f"Total Trades:     {total_trades}")
    print(f"Winners:          {Fore.GREEN}{len(winners)}{Style.RESET_ALL}")
    print(f"Losers:           {Fore.RED}{len(losers)}{Style.RESET_ALL}")
    print(f"Win Rate:         {Fore.GREEN if win_rate >= 50 else Fore.RED}{win_rate:.1f}%{Style.RESET_ALL}")
    print()
    print(f"Total P&L:        {Fore.GREEN if total_pnl > 0 else Fore.RED}${total_pnl:,.2f}{Style.RESET_ALL}")
    print(f"Avg Win:          {Fore.GREEN}${avg_win:.2f}{Style.RESET_ALL}")
    print(f"Avg Loss:         {Fore.RED}${avg_loss:.2f}{Style.RESET_ALL}")
    
    if avg_loss != 0:
        profit_factor = abs(avg_win * len(winners) / (avg_loss * len(losers)))
        print(f"Profit Factor:    {Fore.GREEN if profit_factor > 1.5 else Fore.YELLOW}{profit_factor:.2f}{Style.RESET_ALL}")
    
    print()

def main():
    parser = argparse.ArgumentParser(description='Trade Journal')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Add trade
    add_parser = subparsers.add_parser('add', help='Add a trade')
    add_parser.add_argument('ticker', help='Stock ticker')
    add_parser.add_argument('entry', type=float, help='Entry price')
    add_parser.add_argument('exit', type=float, help='Exit price')
    add_parser.add_argument('--pattern', default='Unknown', help='Pattern name')
    
    # List trades
    subparsers.add_parser('list', help='List recent trades')
    
    # Show stats
    subparsers.add_parser('stats', help='Show statistics')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        add_trade(args.ticker, args.entry, args.exit, args.pattern)
    elif args.command == 'list':
        list_trades()
    elif args.command == 'stats':
        show_stats()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
