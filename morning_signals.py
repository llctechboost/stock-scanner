#!/usr/bin/env python3
"""
Morning Signals - Pre-market entry orders from yesterday's scan
"""
import json
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

def load_scan_results():
    """Load latest scan results."""
    try:
        with open('money_scan_latest.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{Fore.RED}✗ No scan results found. Run money_scanner.py first.{Style.RESET_ALL}")
        return None

def generate_signals():
    """Generate morning entry signals."""
    data = load_scan_results()
    if not data:
        return
    
    results = data['results']
    scan_time = data['timestamp']
    
    # Top 5 high-probability setups
    top5 = [r for r in results if r['score'] >= 70][:5]
    
    if not top5:
        print(f"{Fore.YELLOW}⚠ No high-probability setups (score >= 70) found.{Style.RESET_ALL}")
        return
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📈 MORNING ENTRY SIGNALS")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M')} (Pre-Market)")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    print(f"Based on scan: {scan_time[:10]}\n")
    
    print(f"{Fore.WHITE}{Style.BRIGHT}TOP 5 SETUPS:{Style.RESET_ALL}\n")
    
    for i, stock in enumerate(top5, 1):
        ticker = stock['ticker']
        price = stock['price']
        score = stock['score']
        
        # Calculate buy point (1% above current)
        buy_point = price * 1.01
        
        # Calculate stop loss (8% below entry)
        stop_loss = buy_point * 0.92
        
        print(f"{Fore.GREEN}{Style.BRIGHT}{i}. {ticker}{Style.RESET_ALL} (Score: {score}/100)")
        print(f"   Buy Point:  ${buy_point:.2f}")
        print(f"   Stop Loss:  ${stop_loss:.2f} ({Fore.RED}-8%{Style.RESET_ALL})")
        print(f"   Risk/Reward: 8% risk for ~25% target")
        print()
    
    print(f"{Fore.CYAN}{'─'*60}{Style.RESET_ALL}")
    print(f"\n{Fore.YELLOW}💡 TIP:{Style.RESET_ALL} Place limit orders at buy point before market open")
    print(f"   Use position_calc.py to determine exact shares\n")

if __name__ == '__main__':
    generate_signals()
