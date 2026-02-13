#!/usr/bin/env python3
"""
Real-Time Options Flow Scanner
Detects unusual options activity and smart money positioning
"""
import json
import yfinance as yf
from datetime import datetime, timedelta
from colorama import Fore, Style, init

init(autoreset=True)

# Universe (from scanner_v3.py)
# Universe - expanded with high-flow tickers from Quant Data
UNIVERSE = [
    # Major Tech
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO', 'CRM',
    # Semis
    'TSM', 'MU', 'ASML', 'LRCX', 'KLAC', 'AMAT', 'MRVL', 'QCOM', 'INTC', 'SNDK',
    # AI / Cloud / Software
    'PLTR', 'NET', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'MDB', 'PANW', 'NOW', 'SHOP',
    'SMCI', 'ARM', 'IONQ', 'RGTI', 'APP', 'HIMS', 'DUOL', 'CELH', 'TOST', 'CAVA',
    'ORCL', 'ADBE', 'NFLX', 'LITE',
    # Finance / Crypto
    'GS', 'JPM', 'V', 'MA', 'AXP', 'COIN', 'HOOD', 'SOFI', 'NU',
    'IBIT', 'MSTR',  # Bitcoin plays
    # Healthcare
    'LLY', 'NVO', 'UNH', 'ISRG', 'DXCM', 'PODD', 'VRTX',
    # Consumer / Travel
    'UBER', 'ABNB', 'DASH', 'RKLB', 'AXON', 'DECK', 'GWW', 'URI',
    'COST', 'TJX', 'LULU', 'NKE', 'HD', 'LOW', 'BABA', 'MELI',
    # Energy / Materials
    'XOM', 'CVX', 'EOG', 'FCX', 'NUE', 'AA',
    # ETFs - Index & Commodities
    'SPY', 'QQQ', 'IWM', 'SMH',  # Index
    'SLV', 'GLD', 'AGQ',  # Precious metals
    'XLE', 'XLF', 'XLK',  # Sector ETFs
    # Other high-flow names
    'CVNA', 'CAH', 'VRT', 'NBIS', 'MCK', 'GEV',
]

FLOW_FILE = 'options_flow_latest.json'

def analyze_options_flow(ticker):
    """Analyze unusual options activity."""
    try:
        stock = yf.Ticker(ticker)
        
        # Get current price
        hist = stock.history(period='1d')
        if hist.empty:
            return None
        current_price = hist['Close'].iloc[-1]
        
        # Get options dates
        dates = stock.options
        if not dates or len(dates) < 2:
            return None
        
        # Analyze near-term options (first 2 expirations)
        signals = []
        
        for exp_date in dates[:2]:
            try:
                opt = stock.option_chain(exp_date)
                
                # Analyze calls
                if not opt.calls.empty:
                    calls = opt.calls
                    calls = calls[calls['volume'] > 0]  # Filter active
                    
                    if not calls.empty:
                        # Calculate metrics
                        total_call_volume = calls['volume'].sum()
                        avg_call_volume = calls['volume'].mean()
                        max_call_volume = calls['volume'].max()
                        
                        # Find unusual strikes (high volume)
                        unusual_calls = calls[calls['volume'] > calls['volume'].quantile(0.85)]
                        
                        for _, row in unusual_calls.iterrows():
                            volume = row['volume']
                            oi = row.get('openInterest', 0)
                            strike = row['strike']
                            premium = row['lastPrice']
                            iv = row.get('impliedVolatility', 0)
                            
                            # Volume/OI ratio (high = fresh positioning)
                            vol_oi_ratio = volume / oi if oi > 0 else 0
                            
                            # Premium flow (dollars spent)
                            premium_flow = volume * premium * 100
                            
                            # Distance from current price
                            dist_pct = ((strike - current_price) / current_price) * 100
                            
                            # Score the signal (0-100)
                            score = 0
                            
                            # High volume
                            if volume > 1000:
                                score += 30
                            elif volume > 500:
                                score += 20
                            elif volume > 100:
                                score += 10
                            
                            # Fresh positioning (vol > OI)
                            if vol_oi_ratio > 0.5:
                                score += 25
                            elif vol_oi_ratio > 0.25:
                                score += 15
                            
                            # Large premium flow
                            if premium_flow > 500000:
                                score += 25
                            elif premium_flow > 100000:
                                score += 15
                            elif premium_flow > 50000:
                                score += 10
                            
                            # Strike proximity (ATM or slightly OTM)
                            if abs(dist_pct) < 5:
                                score += 20
                            elif abs(dist_pct) < 10:
                                score += 10
                            
                            if score >= 50:  # Only record significant signals
                                signals.append({
                                    'type': 'CALL',
                                    'strike': strike,
                                    'expiry': exp_date,
                                    'volume': int(volume),
                                    'oi': int(oi),
                                    'premium': premium,
                                    'premium_flow': premium_flow,
                                    'iv': iv,
                                    'vol_oi_ratio': vol_oi_ratio,
                                    'dist_pct': dist_pct,
                                    'score': score
                                })
                
                # Analyze puts (similar logic)
                if not opt.puts.empty:
                    puts = opt.puts
                    puts = puts[puts['volume'] > 0]
                    
                    if not puts.empty:
                        unusual_puts = puts[puts['volume'] > puts['volume'].quantile(0.85)]
                        
                        for _, row in unusual_puts.iterrows():
                            volume = row['volume']
                            oi = row.get('openInterest', 0)
                            strike = row['strike']
                            premium = row['lastPrice']
                            
                            vol_oi_ratio = volume / oi if oi > 0 else 0
                            premium_flow = volume * premium * 100
                            dist_pct = ((strike - current_price) / current_price) * 100
                            
                            score = 0
                            if volume > 1000:
                                score += 30
                            elif volume > 500:
                                score += 20
                            elif volume > 100:
                                score += 10
                            
                            if vol_oi_ratio > 0.5:
                                score += 25
                            elif vol_oi_ratio > 0.25:
                                score += 15
                            
                            if premium_flow > 500000:
                                score += 25
                            elif premium_flow > 100000:
                                score += 15
                            
                            if abs(dist_pct) < 5:
                                score += 20
                            elif abs(dist_pct) < 10:
                                score += 10
                            
                            if score >= 50:
                                signals.append({
                                    'type': 'PUT',
                                    'strike': strike,
                                    'expiry': exp_date,
                                    'volume': int(volume),
                                    'oi': int(oi),
                                    'premium': premium,
                                    'premium_flow': premium_flow,
                                    'iv': row.get('impliedVolatility', 0),
                                    'vol_oi_ratio': vol_oi_ratio,
                                    'dist_pct': dist_pct,
                                    'score': score
                                })
            
            except Exception as e:
                continue
        
        if signals:
            # Sort by score
            signals.sort(key=lambda x: x['score'], reverse=True)
            
            # Take top 3
            top_signals = signals[:3]
            
            # Overall flow bias
            call_signals = [s for s in top_signals if s['type'] == 'CALL']
            put_signals = [s for s in top_signals if s['type'] == 'PUT']
            
            call_flow = sum(s['premium_flow'] for s in call_signals)
            put_flow = sum(s['premium_flow'] for s in put_signals)
            
            bias = 'BULLISH' if call_flow > put_flow else 'BEARISH' if put_flow > call_flow else 'NEUTRAL'
            
            return {
                'ticker': ticker,
                'price': current_price,
                'signals': top_signals,
                'bias': bias,
                'call_flow': call_flow,
                'put_flow': put_flow,
                'timestamp': datetime.now().isoformat()
            }
        
        return None
    
    except Exception as e:
        return None

def scan_all():
    """Scan entire universe."""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}{Style.BRIGHT}⚡ OPTIONS FLOW SCANNER")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}Scanning {len(UNIVERSE)} tickers for unusual options activity...{Style.RESET_ALL}\n")
    
    results = []
    
    for ticker in UNIVERSE:
        flow = analyze_options_flow(ticker)
        if flow and flow['signals']:
            results.append(flow)
            print(f"{Fore.GREEN}✓{Style.RESET_ALL} {ticker:<6} {flow['bias']:<10} {len(flow['signals'])} signals")
    
    # Sort by top signal score
    results.sort(key=lambda x: x['signals'][0]['score'], reverse=True)
    
    # Save to file
    output = {
        'timestamp': datetime.now().isoformat(),
        'scan_count': len(UNIVERSE),
        'results': results
    }
    
    with open(FLOW_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n{Fore.WHITE}{Style.BRIGHT}TOP UNUSUAL FLOW:{Style.RESET_ALL}\n")
    
    if results:
        print(f"{'Ticker':<8}{'Bias':<12}{'Type':<6}{'Strike':>9}{'Volume':>10}{'Flow':>12}{'Score':<6}")
        print(f"{'─'*70}")
        
        for r in results[:15]:
            ticker = r['ticker']
            bias = r['bias']
            
            for sig in r['signals'][:1]:  # Show top signal per stock
                type_color = Fore.GREEN if sig['type'] == 'CALL' else Fore.RED
                bias_color = Fore.GREEN if bias == 'BULLISH' else Fore.RED if bias == 'BEARISH' else Fore.YELLOW
                
                print(f"{Fore.CYAN}{ticker:<8}{Style.RESET_ALL}"
                      f"{bias_color}{bias:<12}{Style.RESET_ALL}"
                      f"{type_color}{sig['type']:<6}{Style.RESET_ALL}"
                      f"${sig['strike']:>8.2f}"
                      f"{sig['volume']:>10,}"
                      f"${sig['premium_flow']:>11,.0f}"
                      f" {sig['score']}/100")
    else:
        print(f"{Fore.YELLOW}⚠ No unusual options activity detected.{Style.RESET_ALL}")
    
    print(f"\n{Fore.WHITE}Results saved to: {FLOW_FILE}{Style.RESET_ALL}\n")
    
    return results

if __name__ == '__main__':
    scan_all()
