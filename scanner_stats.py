#!/usr/bin/env python3
"""
Scanner Stats - Which patterns win most?
Analyzes journal.json for pattern performance
"""
import json
from colorama import Fore, Style, init

init(autoreset=True)

def load_trades():
    try:
        with open('trades.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{Fore.RED}✗ No trades found. Run journal.py first.{Style.RESET_ALL}")
        return []

def analyze_patterns():
    """Analyze pattern win rates."""
    trades = load_trades()
    
    if not trades:
        return
    
    # Only analyze closed trades with patterns
    closed = [t for t in trades if t.get('exit') and t.get('pattern')]
    
    if not closed:
        print(f"\n{Fore.YELLOW}No closed trades with pattern data yet.{Style.RESET_ALL}\n")
        return
    
    # Group by pattern
    patterns = {}
    for t in closed:
        pattern = t['pattern']
        if pattern not in patterns:
            patterns[pattern] = {'wins': 0, 'losses': 0, 'total_pnl': 0, 'trades': []}
        
        patterns[pattern]['trades'].append(t)
        if t.get('win'):
            patterns[pattern]['wins'] += 1
        else:
            patterns[pattern]['losses'] += 1
        
        patterns[pattern]['total_pnl'] += t.get('pnl', 0)
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}🎯 PATTERN PERFORMANCE ANALYSIS")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    # Sort by win rate
    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1]['wins'] / (x[1]['wins'] + x[1]['losses']), reverse=True)
    
    print(f"{'Pattern':<20}{'Trades':<8}{'Wins':<7}{'Win %':<8}{'Avg P&L':<12}{'Total P&L':<12}")
    print(f"{'─'*70}")
    
    for pattern, stats in sorted_patterns:
        total = stats['wins'] + stats['losses']
        win_rate = (stats['wins'] / total) * 100
        avg_pnl = stats['total_pnl'] / total
        
        # Color code win rate
        if win_rate >= 60:
            wr_color = Fore.GREEN
        elif win_rate >= 45:
            wr_color = Fore.YELLOW
        else:
            wr_color = Fore.RED
        
        # Color code P&L
        pnl_color = Fore.GREEN if stats['total_pnl'] > 0 else Fore.RED
        
        print(f"{pattern:<20}{total:<8}{stats['wins']:<7}{wr_color}{win_rate:>5.1f}%{Style.RESET_ALL}   ${avg_pnl:>8.2f}   {pnl_color}${stats['total_pnl']:>9.2f}{Style.RESET_ALL}")
    
    print()
    
    # Best performer
    if sorted_patterns:
        best = sorted_patterns[0]
        best_name = best[0]
        best_stats = best[1]
        best_wr = (best_stats['wins'] / (best_stats['wins'] + best_stats['losses'])) * 100
        
        print(f"{Fore.GREEN}🏆 Best Pattern: {best_name} ({best_wr:.1f}% win rate){Style.RESET_ALL}")
        print()

if __name__ == '__main__':
    analyze_patterns()
