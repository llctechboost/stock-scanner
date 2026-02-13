#!/usr/bin/env python3
"""
Signal Matcher - Combines Stock Patterns + Options Flow
Generates high-conviction trade signals

Reads: money_scan_latest.json, options_flow_latest.json, scan_results (latest .txt)
Writes: signals_latest.json
"""
import json
import glob
import re
import os
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCAN_FILE = os.path.join(SCRIPT_DIR, 'money_scan_latest.json')
FLOW_FILE = os.path.join(SCRIPT_DIR, 'options_flow_latest.json')
SIGNALS_FILE = os.path.join(SCRIPT_DIR, 'signals_latest.json')

# Pattern win rates from backtest
PATTERN_WEIGHTS = {
    'Flat Base': 46.7,
    'Cup with Handle': 37.5,
    'Ascending Base': 42.0,
    'Pocket Pivot': 40.6,
    'High Tight Flag': 31.8
}


def load_stock_scan():
    """Load latest stock scanner results."""
    try:
        with open(SCAN_FILE, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, list) else data.get('results', [])
    except:
        return []


def load_scanner_patterns():
    """Load pattern data from latest scanner text output."""
    patterns = {}  # ticker -> {pattern, buy_point, earnings_warning, etc}
    
    txt_files = sorted(glob.glob(os.path.join(SCRIPT_DIR, 'scan_results_*.txt')), reverse=True)
    if not txt_files:
        return patterns
    
    try:
        with open(txt_files[0], 'r') as f:
            text = f.read()
    except:
        return patterns
    
    lines = text.split('\n')
    current_ticker = None
    current_data = None
    
    for line in lines:
        ls = line.strip()
        
        # Ticker line
        ticker_match = re.match(r'^([A-Z]{1,5})\s*-\s*Score:\s*(\d+)/12\s*-\s*\$([\d,.]+)', ls)
        if ticker_match:
            # Save previous
            if current_ticker and current_data:
                patterns[current_ticker] = current_data
            
            current_ticker = ticker_match.group(1)
            current_data = {
                'scanner_score': int(ticker_match.group(2)),
                'price': float(ticker_match.group(3).replace(',', '')),
                'patterns': [],
                'buy_point': None,
                'earnings_warning': False,
                'earnings_days': None,
                'earnings_date': None,
            }
            continue
        
        if current_data and '✓' in ls:
            if 'Flat Base' in ls:
                current_data['patterns'].append('Flat Base')
            elif 'Cup with Handle' in ls:
                current_data['patterns'].append('Cup with Handle')
            elif 'High Tight Flag' in ls:
                current_data['patterns'].append('High Tight Flag')
            elif 'Ascending Base' in ls:
                current_data['patterns'].append('Ascending Base')
            elif 'Pocket Pivot' in ls:
                current_data['patterns'].append('Pocket Pivot')
            
            if 'EARNINGS IN' in ls:
                current_data['earnings_warning'] = True
                days_m = re.search(r'EARNINGS IN (\d+) DAYS', ls)
                if days_m:
                    current_data['earnings_days'] = int(days_m.group(1))
                date_m = re.search(r'\((\d{4}-\d{2}-\d{2})\)', ls)
                if date_m:
                    current_data['earnings_date'] = date_m.group(1)
        
        if current_data and '→ Buy point:' in ls:
            bp_m = re.search(r'\$([\d,.]+)', ls)
            if bp_m:
                current_data['buy_point'] = float(bp_m.group(1).replace(',', ''))
    
    # Save last
    if current_ticker and current_data:
        patterns[current_ticker] = current_data
    
    return patterns


def load_options_flow():
    """Load latest options flow results."""
    try:
        with open(FLOW_FILE, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, list) else data.get('results', [])
    except:
        return []


def calculate_conviction(stock_data, flow_data, pattern_info):
    """
    Calculate conviction score (0-100).
    
    Scoring:
    - Stock score (money scanner): up to 40 pts
    - Options flow alignment: up to 30 pts
    - Pattern quality: up to 20 pts
    - Penalties: earnings proximity, bearish flow on bullish signal
    """
    score = 0
    reasons = []
    
    # 1. Stock score from money scanner (max 40 pts)
    stock_score = stock_data.get('score', 0)
    stock_contribution = (stock_score / 100) * 40
    score += stock_contribution
    
    # 2. Pattern quality (max 20 pts)
    best_pattern = ''
    best_weight = 0
    if pattern_info:
        for p in pattern_info.get('patterns', []):
            w = PATTERN_WEIGHTS.get(p, 30)
            if w > best_weight:
                best_weight = w
                best_pattern = p
        
        if best_pattern:
            pattern_pts = (best_weight / 47) * 20  # Normalize to max 20
            score += pattern_pts
            reasons.append(f"Pattern: {best_pattern} ({best_weight:.0f}% backtest win rate)")
    
    if stock_score >= 80:
        reasons.insert(0, f"Strong stock score ({stock_score}/100)")
    elif stock_score >= 60:
        reasons.insert(0, f"Good stock score ({stock_score}/100)")
    
    # 3. Options flow (max 30 pts)
    if flow_data:
        bias = flow_data.get('bias', 'NEUTRAL')
        
        if bias == 'BULLISH':
            score += 15
            reasons.append("Bullish options flow")
        elif bias == 'BEARISH':
            # Bearish flow on a stock we'd be buying = conflicting signal
            score -= 10
            reasons.append("⚠️ BEARISH flow — conflicting signal")
        
        # Premium size bonus
        premium = flow_data.get('total_premium', flow_data.get('call_flow', 0))
        if premium > 1_000_000:
            score += 10
            reasons.append(f"Large flow ${premium:,.0f}")
        elif premium > 500_000:
            score += 7
            reasons.append(f"Moderate flow ${premium:,.0f}")
        elif premium > 100_000:
            score += 3
        
        # Fresh positioning bonus
        signals = flow_data.get('signals', [])
        if signals and signals[0].get('vol_oi_ratio', 0) > 0.5:
            score += 5
            reasons.append("Fresh positioning")
    
    # 4. PENALTIES
    if pattern_info and pattern_info.get('earnings_warning'):
        days = pattern_info.get('earnings_days', 0)
        if days and days <= 7:
            score -= 25
            reasons.append(f"🚨 EARNINGS IN {days} DAYS — HIGH RISK")
        elif days and days <= 14:
            score -= 15
            reasons.append(f"⚠️ Earnings in {days} days — reduce size")
    
    # Cap between 0-100
    score = max(0, min(100, int(score)))
    
    return score, reasons, best_pattern


def match_signals():
    """Match stock patterns with options flow."""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}{Style.BRIGHT}🔥 SIGNAL MATCHER - Pattern + Flow Alignment")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
    
    stocks = load_stock_scan()
    flows = load_options_flow()
    pattern_data = load_scanner_patterns()
    
    if not stocks:
        print(f"{Fore.RED}✗ No stock scan data. Run money_scanner.py first.{Style.RESET_ALL}\n")
        return
    
    print(f"Loaded: {len(stocks)} stocks, {len(flows)} with options flow, "
          f"{len(pattern_data)} with pattern data\n")
    
    # Create flow lookup
    flow_map = {f['ticker']: f for f in flows}
    
    # Match and score
    signals = []
    
    for stock in stocks:
        ticker = stock['ticker']
        flow = flow_map.get(ticker)
        pinfo = pattern_data.get(ticker)
        
        conviction, reasons, pattern = calculate_conviction(stock, flow, pinfo)
        
        signal = {
            'ticker': ticker,
            'conviction': conviction,
            'stock_score': stock.get('score', 0),
            'pattern': pattern,
            'price': stock.get('price', 0),
            'buy_point': pinfo.get('buy_point') if pinfo else None,
            'has_flow': flow is not None,
            'flow_bias': flow.get('bias', 'N/A') if flow else 'N/A',
            'premium_flow': flow.get('total_premium', flow.get('call_flow', 0)) if flow else 0,
            'reasons': reasons,
            'earnings_warning': pinfo.get('earnings_warning', False) if pinfo else False,
            'earnings_days': pinfo.get('earnings_days') if pinfo else None,
            'timestamp': datetime.now().isoformat()
        }
        
        signals.append(signal)
    
    # Sort by conviction
    signals.sort(key=lambda x: x['conviction'], reverse=True)
    
    # Categorize
    hot = [s for s in signals if s['conviction'] >= 95]
    strong = [s for s in signals if 85 <= s['conviction'] < 95]
    watch = [s for s in signals if 70 <= s['conviction'] < 85]
    
    # Save
    output = {
        'timestamp': datetime.now().isoformat(),
        'hot': hot,
        'strong': strong,
        'watch': watch,
        'all': signals
    }
    
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    # Display
    print(f"{Fore.WHITE}{Style.BRIGHT}SIGNALS BY CONVICTION:{Style.RESET_ALL}\n")
    
    if hot:
        print(f"{Fore.RED}{Style.BRIGHT}🔥 HOT ({len(hot)}) - Maximum Conviction (95+):{Style.RESET_ALL}")
        for s in hot:
            flow_txt = f"+ {s['flow_bias']} flow" if s['has_flow'] else "no flow data"
            earnings_txt = f" ⚠️ EARNINGS {s['earnings_days']}d" if s.get('earnings_warning') else ""
            print(f"  {Fore.CYAN}{Style.BRIGHT}{s['ticker']:<6}{Style.RESET_ALL} "
                  f"{s['conviction']}/100 | {s['pattern']:<20} {flow_txt}{earnings_txt}")
            if s.get('buy_point'):
                print(f"    💰 Buy point: ${s['buy_point']:,.2f}  |  Price: ${s['price']:,.2f}")
            for reason in s['reasons']:
                print(f"    • {reason}")
        print()
    else:
        print(f"{Fore.YELLOW}  No 🔥 HOT signals (95+) right now{Style.RESET_ALL}\n")
    
    if strong:
        print(f"{Fore.GREEN}{Style.BRIGHT}🟢 STRONG ({len(strong)}) - High Conviction (85-94):{Style.RESET_ALL}")
        for s in strong[:5]:
            flow_txt = f"+ {s['flow_bias']} flow" if s['has_flow'] else ""
            earnings_txt = f" ⚠️ EARNINGS {s['earnings_days']}d" if s.get('earnings_warning') else ""
            print(f"  {Fore.CYAN}{s['ticker']:<6}{Style.RESET_ALL} "
                  f"{s['conviction']}/100 | {s['pattern']:<20} {flow_txt}{earnings_txt}")
        print()
    
    if watch:
        print(f"{Fore.YELLOW}🟡 WATCH ({len(watch)}) - Good Conviction (70-84){Style.RESET_ALL}")
        top3 = ', '.join(f"{s['ticker']}({s['conviction']})" for s in watch[:3])
        print(f"   Top 3: {top3}\n")
    
    total = len(hot) + len(strong) + len(watch)
    print(f"{Fore.WHITE}Total signals: {total} | "
          f"Saved to: {SIGNALS_FILE}{Style.RESET_ALL}\n")
    
    return output


if __name__ == '__main__':
    match_signals()
