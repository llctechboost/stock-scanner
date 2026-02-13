#!/usr/bin/env python3
"""
Options Position Calculator
Calculate position size and risk for options trades
"""
import argparse
import yfinance as yf
from colorama import Fore, Style, init

init(autoreset=True)

def calculate_options_position(ticker, option_type, max_risk, strike=None):
    """Calculate options position."""
    try:
        stock = yf.Ticker(ticker)
        
        # Get options dates
        dates = stock.options
        if not dates:
            print(f"{Fore.RED}✗ No options data available for {ticker}{Style.RESET_ALL}")
            return
        
        # Use nearest expiry
        expiry = dates[0]
        opt = stock.option_chain(expiry)
        
        if option_type.lower() == 'call':
            chain = opt.calls
        else:
            chain = opt.puts
        
        if chain.empty:
            print(f"{Fore.RED}✗ No {option_type} options available{Style.RESET_ALL}")
            return
        
        # Find ATM or specified strike
        current_price = stock.history(period='1d')['Close'].iloc[-1]
        
        if strike:
            option = chain[chain['strike'] == strike]
            if option.empty:
                print(f"{Fore.RED}✗ Strike ${strike} not found{Style.RESET_ALL}")
                return
            option = option.iloc[0]
        else:
            # Find ATM
            chain['distance'] = abs(chain['strike'] - current_price)
            option = chain.loc[chain['distance'].idxmin()]
        
        premium = option['lastPrice']
        strike_price = option['strike']
        
        # Calculate contracts
        cost_per_contract = premium * 100
        contracts = int(max_risk / cost_per_contract)
        
        if contracts == 0:
            print(f"{Fore.RED}✗ Max risk too low. Premium: ${premium:.2f} per share (${cost_per_contract:.2f} per contract){Style.RESET_ALL}")
            return
        
        total_cost = contracts * cost_per_contract
        
        # Break-even
        if option_type.lower() == 'call':
            breakeven = strike_price + premium
        else:
            breakeven = strike_price - premium
        
        print(f"\n{Fore.CYAN}{'='*50}")
        print(f"{Fore.CYAN}{Style.BRIGHT}📊 OPTIONS POSITION CALCULATOR")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
        
        print(f"{Fore.WHITE}{Style.BRIGHT}Ticker:{Style.RESET_ALL}        {ticker.upper()}")
        print(f"{Fore.WHITE}{Style.BRIGHT}Current Price:{Style.RESET_ALL} ${current_price:.2f}")
        print(f"{Fore.WHITE}{Style.BRIGHT}Type:{Style.RESET_ALL}          {option_type.upper()}")
        print(f"{Fore.WHITE}{Style.BRIGHT}Strike:{Style.RESET_ALL}        ${strike_price:.2f}")
        print(f"{Fore.WHITE}{Style.BRIGHT}Expiry:{Style.RESET_ALL}        {expiry}")
        print(f"{Fore.WHITE}{Style.BRIGHT}Premium:{Style.RESET_ALL}       ${premium:.2f} per share")
        print()
        
        print(f"{Fore.GREEN}{Style.BRIGHT}BUY {contracts} CONTRACT{'S' if contracts > 1 else ''}{Style.RESET_ALL}")
        print()
        
        print(f"Total Cost:     ${total_cost:,.2f}")
        print(f"Max Loss:       ${total_cost:,.2f} (premium paid)")
        print(f"Break-Even:     ${breakeven:.2f}")
        print(f"Volume:         {int(option.get('volume', 0)):,}")
        print(f"Open Interest:  {int(option.get('openInterest', 0)):,}")
        
        iv = option.get('impliedVolatility', 0)
        if iv:
            print(f"Implied Vol:    {iv*100:.1f}%")
        
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
    
    except Exception as e:
        print(f"{Fore.RED}✗ Error: {e}{Style.RESET_ALL}")

def main():
    parser = argparse.ArgumentParser(description='Options Position Calculator')
    parser.add_argument('ticker', help='Stock ticker')
    parser.add_argument('type', choices=['call', 'put'], help='Option type')
    parser.add_argument('--max-risk', type=float, required=True, help='Maximum risk amount')
    parser.add_argument('--strike', type=float, help='Strike price (default: ATM)')
    
    args = parser.parse_args()
    
    calculate_options_position(args.ticker.upper(), args.type, args.max_risk, args.strike)

if __name__ == '__main__':
    main()
