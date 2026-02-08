#!/usr/bin/env python3
"""
Money Scanner - Ranks top 10 stocks by profit probability (0-100)
Uses CANSLIM methodology from scanner_v3.py
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import json
import sys
from colorama import Fore, Style, init

init(autoreset=True)

# Stock universe - Top 200 S&P 500 by market cap weight
UNIVERSE = [
    # Mag 7 + Mega Caps
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'GOOG', 'BRK-B', 'TSLA', 'UNH',
    'XOM', 'LLY', 'JPM', 'JNJ', 'V', 'PG', 'MA', 'AVGO', 'HD', 'CVX',
    'MRK', 'ABBV', 'COST', 'PEP', 'ADBE', 'KO', 'WMT', 'MCD', 'CSCO', 'CRM',
    'BAC', 'PFE', 'TMO', 'ACN', 'NFLX', 'AMD', 'ABT', 'LIN', 'ORCL', 'DIS',
    'CMCSA', 'DHR', 'VZ', 'PM', 'INTC', 'WFC', 'TXN', 'INTU', 'COP', 'NKE',
    'NEE', 'RTX', 'UNP', 'QCOM', 'HON', 'LOW', 'UPS', 'SPGI', 'IBM', 'BA',
    'CAT', 'GE', 'AMAT', 'ELV', 'PLD', 'SBUX', 'DE', 'NOW', 'ISRG', 'MS',
    'GS', 'BMY', 'BLK', 'BKNG', 'MDLZ', 'GILD', 'ADP', 'LMT', 'VRTX', 'AMT',
    'ADI', 'SYK', 'TJX', 'REGN', 'CVS', 'SCHW', 'MMC', 'TMUS', 'ZTS', 'CI',
    'PGR', 'LRCX', 'CB', 'MO', 'SO', 'ETN', 'EOG', 'BDX', 'SNPS', 'DUK',
    'SLB', 'PANW', 'BSX', 'CME', 'AON', 'KLAC', 'NOC', 'ITW', 'MU', 'CDNS',
    'CL', 'WM', 'ICE', 'CSX', 'SHW', 'HUM', 'EQIX', 'ORLY', 'GD', 'MCK',
    'FCX', 'PNC', 'APD', 'USB', 'PSX', 'MCO', 'MPC', 'EMR', 'MSI', 'NSC',
    'CTAS', 'CMG', 'MAR', 'MCHP', 'ROP', 'NXPI', 'AJG', 'AZO', 'TGT', 'PCAR',
    'TFC', 'AIG', 'AFL', 'HCA', 'KDP', 'CARR', 'OXY', 'SRE', 'AEP', 'PSA',
    'TRV', 'WMB', 'ADSK', 'NEM', 'MSCI', 'F', 'FDX', 'DXCM', 'KMB', 'FTNT',
    'D', 'EW', 'GM', 'IDXX', 'TEL', 'AMP', 'JCI', 'O', 'CCI', 'DVN',
    'SPG', 'PAYX', 'ROST', 'GIS', 'A', 'ALL', 'BIIB', 'IQV', 'LHX', 'CMI',
    'BK', 'YUM', 'PRU', 'CTVA', 'ODFL', 'WELL', 'DOW', 'HAL', 'KMI', 'MNST',
    'ANET', 'CPRT', 'EXC', 'PCG', 'FAST', 'KR', 'VRSK', 'EA', 'GEHC', 'ON'
]

def score_stock(ticker):
    """Score a stock 0-100 based on profit probability."""
    try:
        df = yf.download(ticker, period='1y', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 60:
            return None
        
        close = df['Close']
        volume = df['Volume']
        score = 0
        
        # 1. RS (Relative Strength) - 25 pts
        perf_3m = (close.iloc[-1] / close.iloc[-63] - 1) if len(close) > 63 else 0
        perf_6m = (close.iloc[-1] / close.iloc[-126] - 1) if len(close) > 126 else 0
        rs_raw = perf_3m * 0.6 + perf_6m * 0.4
        score += min(25, max(0, rs_raw * 100))
        
        # 2. Price vs Moving Averages - 20 pts
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) > 200 else ma50
        price = close.iloc[-1]
        if price > ma50:
            score += 10
        if price > ma200:
            score += 5
        if ma50 > ma200:
            score += 5
        
        # 3. Volume confirmation - 15 pts
        avg_vol = volume.rolling(50).mean().iloc[-1]
        recent_vol = volume.iloc[-5:].mean()
        if recent_vol > avg_vol * 1.5:
            score += 15
        elif recent_vol > avg_vol * 1.2:
            score += 10
        elif recent_vol > avg_vol:
            score += 5
        
        # 4. Volatility contraction (tight base) - 15 pts
        recent_range = (close.iloc[-20:].max() - close.iloc[-20:].min()) / close.iloc[-1]
        prior_range = (close.iloc[-60:-20].max() - close.iloc[-60:-20].min()) / close.iloc[-40] if len(close) > 60 else recent_range
        if recent_range < prior_range * 0.5:
            score += 15
        elif recent_range < prior_range * 0.7:
            score += 10
        elif recent_range < prior_range:
            score += 5
        
        # 5. Breakout proximity - 15 pts
        high_52w = close.iloc[-252:].max() if len(close) >= 252 else close.max()
        pct_from_high = (high_52w - price) / high_52w
        if pct_from_high < 0.03:
            score += 15
        elif pct_from_high < 0.10:
            score += 10
        elif pct_from_high < 0.20:
            score += 5
        
        # 6. Trend strength - 10 pts
        gains = close.diff().iloc[-20:]
        up_days = (gains > 0).sum()
        if up_days >= 14:
            score += 10
        elif up_days >= 12:
            score += 7
        elif up_days >= 10:
            score += 4
        
        return {
            'ticker': ticker,
            'score': min(100, int(score)),
            'price': float(price),
            'perf_3m': perf_3m * 100,
            'vol_ratio': recent_vol / avg_vol if avg_vol > 0 else 0,
            'from_high': pct_from_high * 100
        }
    except:
        return None

def run_scan():
    """Run money scanner on universe."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}💰 MONEY SCANNER - Profit Probability Rankings")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}Scanning {len(UNIVERSE)} stocks...{Style.RESET_ALL}\n")
    
    results = []
    for i, ticker in enumerate(UNIVERSE):
        sys.stdout.write(f"\r  {ticker}... ({i+1}/{len(UNIVERSE)})")
        sys.stdout.flush()
        r = score_stock(ticker)
        if r:
            results.append(r)
    
    results.sort(key=lambda x: x['score'], reverse=True)
    top10 = results[:10]
    
    print(f"\r{' '*50}\r")
    print(f"{Fore.WHITE}{Style.BRIGHT}TOP 10 STOCKS BY PROFIT PROBABILITY{Style.RESET_ALL}")
    print(f"{'─'*60}")
    print(f"{'Rank':<6}{'Ticker':<8}{'Score':<10}{'Price':>10}{'3M %':>8}{'Vol':>8}{'52W':>8}")
    print(f"{'─'*60}")
    
    for i, s in enumerate(top10):
        rank = i + 1
        sc = s['score']
        
        if sc >= 80:
            clr = Fore.GREEN
        elif sc >= 60:
            clr = Fore.YELLOW
        else:
            clr = Fore.RED
        
        bar = '█' * (sc // 10) + '░' * (10 - sc // 10)
        perf_clr = Fore.GREEN if s['perf_3m'] > 0 else Fore.RED
        
        print(f"{rank:<6}{Fore.CYAN}{s['ticker']:<8}{Style.RESET_ALL}{clr}{sc:>3}/100{Style.RESET_ALL}  {bar} ${s['price']:>8.2f} {perf_clr}{s['perf_3m']:>+6.1f}%{Style.RESET_ALL} {s['vol_ratio']:>5.1f}x {s['from_high']:>5.1f}%")
    
    print(f"{'─'*60}")
    print(f"\n  {Fore.GREEN}80+{Style.RESET_ALL} = High probability  {Fore.YELLOW}60-79{Style.RESET_ALL} = Watch  {Fore.RED}<60{Style.RESET_ALL} = Wait\n")
    
    # Save results
    output = {'timestamp': datetime.now().isoformat(), 'results': results}
    with open('money_scan_latest.json', 'w') as f:
        json.dump(output, f, indent=2)
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Saved to money_scan_latest.json\n")
    
    return results

if __name__ == '__main__':
    run_scan()
