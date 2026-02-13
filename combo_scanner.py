#!/usr/bin/env python3
"""
Combo Scanner - Stocks + Options + VCP Combined
Shows 🔥 when stock pattern AND unusual options activity align
Shows 📐 VCP (Volatility Contraction Pattern) detection section
"""
import json
import sys
import yfinance as yf
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

# Import VCP detector
try:
    from vcp_detector import analyze_vcp, VCPResult
    VCP_AVAILABLE = True
except ImportError:
    VCP_AVAILABLE = False

def load_money_scan():
    """Load latest money scanner results."""
    try:
        with open('money_scan_latest.json', 'r') as f:
            data = json.load(f)
            return data['results']
    except:
        return []

def check_options_flow(ticker):
    """Check for unusual options activity."""
    try:
        stock = yf.Ticker(ticker)
        dates = stock.options
        
        if not dates:
            return False
        
        opt = stock.option_chain(dates[0])
        
        # Check for high volume calls (bullish signal)
        if not opt.calls.empty:
            calls = opt.calls
            high_vol = calls[calls['volume'] > calls['volume'].quantile(0.75)]
            if len(high_vol) >= 2:
                return True
        
        return False
    except:
        return False

def run_combo_scan():
    """Run combined scanner."""
    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"{Fore.CYAN}{Style.BRIGHT}🔥 COMBO SCANNER - Stocks + Options")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{Fore.CYAN}{'='*65}{Style.RESET_ALL}\n")
    
    # Load stock scanner results
    stock_results = load_money_scan()
    
    if not stock_results:
        print(f"{Fore.RED}✗ No stock scan data. Run money_scanner.py first.{Style.RESET_ALL}\n")
        return
    
    # Check top stocks for options activity
    print(f"{Fore.YELLOW}Analyzing top stocks + options flow...{Style.RESET_ALL}\n")
    
    opportunities = []
    
    for stock in stock_results[:20]:  # Check top 20
        ticker = stock['ticker']
        has_options = check_options_flow(ticker)
        
        stock['has_options_flow'] = has_options
        stock['fire'] = stock['score'] >= 75 and has_options
        
        if stock['score'] >= 60:  # Show stocks with decent scores
            opportunities.append(stock)
    
    # Sort by score
    opportunities.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"{Fore.WHITE}{Style.BRIGHT}TOP OPPORTUNITIES:{Style.RESET_ALL}\n")
    print(f"{'Ticker':<8}{'Score':<8}{'Price':>10}{'Stock':<10}{'Options':<10}{'Signal':<8}")
    print(f"{'─'*65}")
    
    for opp in opportunities[:15]:
        ticker = opp['ticker']
        score = opp['score']
        price = opp['price']
        
        # Score color
        if score >= 80:
            score_color = Fore.GREEN
        elif score >= 60:
            score_color = Fore.YELLOW
        else:
            score_color = Fore.RED
        
        # Stock signal
        stock_signal = f"{Fore.GREEN}✓ Pattern{Style.RESET_ALL}" if score >= 70 else f"{Fore.YELLOW}○ Watch{Style.RESET_ALL}"
        
        # Options signal
        options_signal = f"{Fore.GREEN}✓ Flow{Style.RESET_ALL}" if opp['has_options_flow'] else f"{Fore.WHITE}—{Style.RESET_ALL}"
        
        # Fire signal
        fire = f"{Fore.RED}🔥 HOT{Style.RESET_ALL}" if opp['fire'] else ""
        
        print(f"{Fore.CYAN}{ticker:<8}{Style.RESET_ALL}{score_color}{score:>3}/100{Style.RESET_ALL}  ${price:>8.2f} {stock_signal:<18}{options_signal:<18}{fire}")
    
    print()
    
    # Summary
    fire_count = sum(1 for o in opportunities if o['fire'])
    
    if fire_count > 0:
        print(f"{Fore.RED}🔥 {fire_count} HOT SIGNAL{'S' if fire_count > 1 else ''}{Style.RESET_ALL} - Strong stock pattern + unusual options flow")
    else:
        print(f"{Fore.YELLOW}💡 No combined signals right now. Monitor for alignment.{Style.RESET_ALL}")
    
    print()
    print(f"{Fore.CYAN}{'─'*65}{Style.RESET_ALL}")
    print(f"\n{Fore.YELLOW}Legend:{Style.RESET_ALL}")
    print(f"  {Fore.RED}🔥{Style.RESET_ALL} = Stock score 75+ AND unusual options flow (highest conviction)")
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} = Signal present")
    print(f"  {Fore.YELLOW}○{Style.RESET_ALL} = Watch (score 60-74)")
    print(f"  — = No unusual options activity\n")

    # ── VCP SECTION ─────────────────────────────────────────────
    if VCP_AVAILABLE:
        run_vcp_scan(stock_results)
    else:
        print(f"{Fore.RED}⚠ VCP detector not available (import failed){Style.RESET_ALL}\n")


def run_vcp_scan(stock_results=None):
    """Run VCP scan on the stock universe."""
    print(f"\n{Fore.MAGENTA}{'='*65}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}📐 VCP SCANNER - Volatility Contraction Patterns")
    print(f"{Fore.MAGENTA}{'='*65}{Style.RESET_ALL}\n")

    # Get tickers to scan
    if stock_results:
        tickers = [s['ticker'] for s in stock_results[:30]]
    else:
        # Fallback universe
        tickers = [
            'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO', 'CRM',
            'PLTR', 'NET', 'CRWD', 'PANW', 'NOW', 'SHOP', 'APP', 'HIMS', 'COIN', 'AXON',
        ]

    print(f"{Fore.YELLOW}Scanning {len(tickers)} stocks for VCP patterns...{Style.RESET_ALL}\n")

    vcp_results = []
    for i, ticker in enumerate(tickers):
        sys.stdout.write(f"\r  Analyzing {ticker}... ({i + 1}/{len(tickers)})")
        sys.stdout.flush()
        r = analyze_vcp(ticker)
        if not r.error and r.score >= 2.0:
            vcp_results.append(r)

    vcp_results.sort(key=lambda x: x.score, reverse=True)

    print(f"\r{' ' * 55}\r")

    if not vcp_results:
        print(f"  {Fore.YELLOW}No VCP patterns detected in current scan.{Style.RESET_ALL}\n")
        return

    # Display header
    print(f"{Fore.WHITE}{Style.BRIGHT}VCP PATTERNS DETECTED:{Style.RESET_ALL}\n")
    print(f"{'Ticker':<7}{'Score':>6} {'Grd':>3} {'#C':>3}{'Tightness':>12}{'VolDry':>8}{'Pivot':>10}{'%High':>7}{'Depth':>7}  {'Flag'}")
    print(f"{'─' * 70}")

    for r in vcp_results[:15]:
        # Score color
        if r.score >= 7:
            sc = Fore.GREEN
        elif r.score >= 5:
            sc = Fore.YELLOW
        else:
            sc = Fore.WHITE

        # Tightness display
        if r.tightness_ratios:
            tight_str = '/'.join(f"{t:.0%}" for t in r.tightness_ratios[:3])
        else:
            tight_str = "—"

        # Volume dry-up
        if r.volume_ratios:
            vdry = f"{r.volume_ratios[-1]:.1f}x"
        else:
            vdry = "—"

        # Flag
        if r.is_textbook:
            flag = f"{Fore.GREEN}{Style.BRIGHT}⭐ TEXTBOOK{Style.RESET_ALL}"
        elif r.near_pivot:
            flag = f"{Fore.YELLOW}🎯 AT PIVOT{Style.RESET_ALL}"
        elif r.score >= 5:
            flag = f"{Fore.CYAN}📐 FORMING{Style.RESET_ALL}"
        else:
            flag = ""

        print(
            f"{Fore.CYAN}{r.ticker:<7}{Style.RESET_ALL}"
            f"{sc}{r.score:>5.1f}{Style.RESET_ALL}"
            f"{'':>1}{r.grade:>3}"
            f"{r.num_contractions:>4}"
            f"{tight_str:>12}"
            f"{vdry:>8}"
            f"  ${r.pivot_price:>7.2f}"
            f"{r.pct_from_high:>6.1f}%"
            f"{r.base_depth:>6.1f}%"
            f"  {flag}"
        )

    print(f"{'─' * 70}")

    # Summary
    textbook_count = sum(1 for r in vcp_results if r.is_textbook)
    pivot_count = sum(1 for r in vcp_results if r.near_pivot and not r.is_textbook)
    forming_count = sum(1 for r in vcp_results if r.score >= 5 and not r.is_textbook and not r.near_pivot)

    if textbook_count:
        print(f"\n  {Fore.GREEN}⭐ {textbook_count} TEXTBOOK VCP{'s' if textbook_count > 1 else ''}{Style.RESET_ALL} — Classic Minervini setup, highest conviction")
    if pivot_count:
        print(f"  {Fore.YELLOW}🎯 {pivot_count} AT PIVOT{Style.RESET_ALL} — Near breakout buy point, watch for volume surge")
    if forming_count:
        print(f"  {Fore.CYAN}📐 {forming_count} FORMING{Style.RESET_ALL} — Pattern developing, watch for tightening")

    print(f"\n{Fore.YELLOW}VCP Legend:{Style.RESET_ALL}")
    print(f"  Score = VCP quality 0-10  |  #C = contraction count  |  Grd = grade (A/B/C/D)")
    print(f"  Tightness = each contraction's range vs prior (lower = tighter)")
    print(f"  VolDry = last contraction volume vs 50d avg (lower = more dry-up)")
    print(f"  ⭐ TEXTBOOK = Score 7+, 3+ contractions, all tightening, near highs\n")


if __name__ == '__main__':
    run_combo_scan()
