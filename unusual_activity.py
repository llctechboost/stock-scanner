#!/usr/bin/env python3
"""
Unusual Options Activity Scanner
Finds unusual options flow (simplified version - uses yfinance options data)
"""
import yfinance as yf
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

WATCHLIST = ['NVDA', 'AAPL', 'MSFT', 'TSLA', 'AMD', 'GOOGL', 'META', 'AMZN', 'SPY', 'QQQ']

def scan_unusual_options():
    """Scan for unusual options activity."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}⚡ UNUSUAL OPTIONS ACTIVITY SCANNER")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}Scanning {len(WATCHLIST)} tickers for unusual options...{Style.RESET_ALL}\n")
    
    unusual_options = []
    
    for ticker in WATCHLIST:
        try:
            stock = yf.Ticker(ticker)
            
            # Get options dates
            dates = stock.options
            if not dates:
                continue
            
            # Check nearest expiry
            opt = stock.option_chain(dates[0])
            
            calls = opt.calls
            puts = opt.puts
            
            # Find high volume calls
            if not calls.empty:
                high_vol_calls = calls[calls['volume'] > calls['volume'].quantile(0.8)]
                
                for _, row in high_vol_calls.head(2).iterrows():
                    unusual_options.append({
                        'ticker': ticker,
                        'type': 'CALL',
                        'strike': row['strike'],
                        'expiry': dates[0],
                        'volume': row['volume'],
                        'oi': row.get('openInterest', 0),
                        'iv': row.get('impliedVolatility', 0)
                    })
            
            # Find high volume puts
            if not puts.empty:
                high_vol_puts = puts[puts['volume'] > puts['volume'].quantile(0.8)]
                
                for _, row in high_vol_puts.head(2).iterrows():
                    unusual_options.append({
                        'ticker': ticker,
                        'type': 'PUT',
                        'strike': row['strike'],
                        'expiry': dates[0],
                        'volume': row['volume'],
                        'oi': row.get('openInterest', 0),
                        'iv': row.get('impliedVolatility', 0)
                    })
        
        except Exception as e:
            continue
    
    if not unusual_options:
        print(f"{Fore.YELLOW}⚠ No unusual options activity detected right now.{Style.RESET_ALL}\n")
        return
    
    # Sort by volume
    unusual_options.sort(key=lambda x: x['volume'], reverse=True)
    
    print(f"{Fore.WHITE}{Style.BRIGHT}HIGH VOLUME OPTIONS:{Style.RESET_ALL}\n")
    print(f"{'Ticker':<8}{'Type':<6}{'Strike':>8}{'Expiry':<12}{'Volume':>10}{'OI':>10}")
    print(f"{'─'*60}")
    
    for opt in unusual_options[:15]:
        type_color = Fore.GREEN if opt['type'] == 'CALL' else Fore.RED
        print(f"{Fore.CYAN}{opt['ticker']:<8}{Style.RESET_ALL}{type_color}{opt['type']:<6}{Style.RESET_ALL}${opt['strike']:>7.2f}  {opt['expiry']:<12}{opt['volume']:>10,}{opt['oi']:>10,}")
    
    print()
    print(f"{Fore.YELLOW}💡 TIP:{Style.RESET_ALL} Look for high volume + low open interest = fresh positioning")
    print(f"   {Fore.GREEN}CALLS{Style.RESET_ALL} = Bullish bias | {Fore.RED}PUTS{Style.RESET_ALL} = Bearish/hedge\n")

if __name__ == '__main__':
    scan_unusual_options()
