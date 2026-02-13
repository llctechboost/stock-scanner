#!/usr/bin/env python3
"""
Position Calculator - Calculate exact shares based on account size and risk
"""
import argparse
from colorama import Fore, Style, init

init(autoreset=True)

def calculate_position(account_size, entry_price, stop_loss, risk_pct=2.0):
    """Calculate position size based on risk."""
    
    # Risk per trade (dollars)
    risk_dollars = account_size * (risk_pct / 100)
    
    # Risk per share
    risk_per_share = entry_price - stop_loss
    
    if risk_per_share <= 0:
        print(f"{Fore.RED}✗ Error: Stop loss must be below entry price{Style.RESET_ALL}")
        return None
    
    # Shares to buy
    shares = int(risk_dollars / risk_per_share)
    
    # Total cost
    total_cost = shares * entry_price
    
    # Actual risk
    actual_risk = shares * risk_per_share
    actual_risk_pct = (actual_risk / account_size) * 100
    
    # Stop loss price
    stop_loss_pct = ((entry_price - stop_loss) / entry_price) * 100
    
    return {
        'shares': shares,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'total_cost': total_cost,
        'risk_dollars': actual_risk,
        'risk_pct': actual_risk_pct,
        'stop_pct': stop_loss_pct
    }

def main():
    parser = argparse.ArgumentParser(description='Position Size Calculator')
    parser.add_argument('--account', type=float, required=True, help='Account size')
    parser.add_argument('--entry', type=float, required=True, help='Entry price')
    parser.add_argument('--stop', type=float, required=True, help='Stop loss price')
    parser.add_argument('--risk', type=float, default=2.0, help='Risk % per trade (default: 2.0)')
    
    args = parser.parse_args()
    
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📊 POSITION SIZE CALCULATOR")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
    
    result = calculate_position(args.account, args.entry, args.stop, args.risk)
    
    if result:
        print(f"{Fore.WHITE}{Style.BRIGHT}Account Size:{Style.RESET_ALL} ${args.account:,.2f}")
        print(f"{Fore.WHITE}{Style.BRIGHT}Entry Price:{Style.RESET_ALL}  ${result['entry_price']:.2f}")
        print(f"{Fore.WHITE}{Style.BRIGHT}Stop Loss:{Style.RESET_ALL}    ${result['stop_loss']:.2f} ({Fore.RED}-{result['stop_pct']:.1f}%{Style.RESET_ALL})")
        print()
        print(f"{Fore.GREEN}{Style.BRIGHT}BUY {result['shares']} SHARES{Style.RESET_ALL}")
        print()
        print(f"Total Cost:   ${result['total_cost']:,.2f}")
        print(f"Risk Amount:  ${result['risk_dollars']:,.2f} ({result['risk_pct']:.2f}% of account)")
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")

if __name__ == '__main__':
    main()
