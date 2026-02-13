#!/usr/bin/env python3
"""
Morning Briefing - One command, complete pre-market intelligence
Runs all scans, matches signals, generates actionable summary
"""

import subprocess
import json
import os
import sys
from datetime import datetime

# Colors
G = '\033[92m'  # Green
R = '\033[91m'  # Red
Y = '\033[93m'  # Yellow
B = '\033[94m'  # Blue
W = '\033[97m'  # White
D = '\033[90m'  # Dim
FIRE = '\033[91m🔥'
RESET = '\033[0m'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_scan(script, label):
    """Run a scanner script and return success status"""
    print(f"  {D}Running {label}...{RESET}", end='', flush=True)
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, script)],
            capture_output=True, text=True, timeout=300,
            cwd=SCRIPT_DIR
        )
        if result.returncode == 0:
            print(f" {G}✓{RESET}")
            return True
        else:
            print(f" {R}✗{RESET}")
            if result.stderr:
                print(f"    {D}{result.stderr[:200]}{RESET}")
            return False
    except subprocess.TimeoutExpired:
        print(f" {Y}timeout{RESET}")
        return False
    except Exception as e:
        print(f" {R}error: {e}{RESET}")
        return False


def load_json(filename):
    """Load a JSON file from script directory"""
    path = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
        return None


def format_currency(val):
    """Format large numbers nicely"""
    if val >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    elif val >= 1_000:
        return f"${val/1_000:.0f}K"
    return f"${val:.0f}"


def main():
    print(f"""
{W}╔══════════════════════════════════════════════════════════════╗
║           ☀️  MORNING BRIEFING  ☀️                           ║
║           {datetime.now().strftime('%A, %B %d, %Y  %I:%M %p'):^48}║
╚══════════════════════════════════════════════════════════════╝{RESET}
""")

    # ── Step 1: Run all scans ──
    print(f"{B}━━━ RUNNING SCANS ━━━{RESET}")
    scan_ok = run_scan('money_scanner.py', 'Money Scanner (Top 10 stocks)')
    flow_ok = run_scan('options_flow_scanner.py', 'Options Flow Scanner')
    match_ok = run_scan('signal_matcher.py', 'Signal Matcher')

    print()

    # ── Step 2: Market Context ──
    print(f"{B}━━━ 📊 MARKET CONTEXT ━━━{RESET}")
    try:
        import yfinance as yf
        spy = yf.download('^GSPC', period='3mo', progress=False)
        vix = yf.download('^VIX', period='1mo', progress=False)
        qqq = yf.download('QQQ', period='3mo', progress=False)
        
        # Flatten multi-index if needed
        for df in [spy, vix, qqq]:
            if hasattr(df.columns, 'levels') and len(df.columns.levels) > 1:
                df.columns = df.columns.get_level_values(0)
        
        spy_price = spy['Close'].iloc[-1]
        spy_ma21 = spy['Close'].rolling(21).mean().iloc[-1]
        spy_ma50 = spy['Close'].rolling(50).mean().iloc[-1]
        spy_chg = ((spy['Close'].iloc[-1] / spy['Close'].iloc[-2]) - 1) * 100
        
        qqq_price = qqq['Close'].iloc[-1]
        qqq_chg = ((qqq['Close'].iloc[-1] / qqq['Close'].iloc[-2]) - 1) * 100
        
        vix_val = vix['Close'].iloc[-1]
        
        # Trend determination
        if spy_price > spy_ma21 > spy_ma50:
            trend = f"{G}UPTREND{RESET}"
            bias = "BULLISH"
        elif spy_price > spy_ma50:
            trend = f"{Y}CAUTIOUS{RESET}"
            bias = "MIXED"
        else:
            trend = f"{R}DOWNTREND{RESET}"
            bias = "BEARISH"
        
        # VIX interpretation
        if vix_val < 15:
            vix_label = f"{G}Low Fear{RESET}"
        elif vix_val < 20:
            vix_label = f"{Y}Moderate{RESET}"
        elif vix_val < 30:
            vix_label = f"{R}Elevated{RESET}"
        else:
            vix_label = f"{R}HIGH FEAR{RESET}"
        
        print(f"  S&P 500:  ${spy_price:,.2f} ({'+' if spy_chg > 0 else ''}{spy_chg:.1f}%)  |  Trend: {trend}")
        print(f"  QQQ:      ${qqq_price:,.2f} ({'+' if qqq_chg > 0 else ''}{qqq_chg:.1f}%)")
        print(f"  VIX:      {vix_val:.1f} — {vix_label}")
        print(f"  Bias:     {bias}")
        
        # Distribution days
        recent = spy.tail(25)
        dist_days = 0
        for i in range(1, len(recent)):
            if recent['Close'].iloc[i] < recent['Close'].iloc[i-1]:
                if recent['Volume'].iloc[i] > recent['Volume'].iloc[i-1]:
                    dist_days += 1
        
        if dist_days >= 5:
            print(f"  Dist Days: {R}{dist_days} ⚠️ High selling pressure{RESET}")
        else:
            print(f"  Dist Days: {dist_days}")
            
    except Exception as e:
        print(f"  {R}Could not load market data: {e}{RESET}")

    print()

    # ── Step 3: Top Stock Patterns ──
    print(f"{B}━━━ 📈 TOP STOCK SETUPS ━━━{RESET}")
    money = load_json('money_scan_latest.json')
    if money:
        top = money[:5] if isinstance(money, list) else []
        for s in top:
            ticker = s.get('ticker', '?')
            score = s.get('score', 0)
            price = s.get('price', 0)
            bar = '█' * int(score / 10) + '░' * (10 - int(score / 10))
            color = G if score >= 80 else Y if score >= 60 else D
            print(f"  {color}{ticker:6} {score:3}/100 {bar}  ${price:>10,.2f}{RESET}")
    else:
        print(f"  {D}No money scanner data{RESET}")

    print()

    # ── Step 4: Options Flow ──
    print(f"{B}━━━ 💰 OPTIONS FLOW HIGHLIGHTS ━━━{RESET}")
    flow = load_json('options_flow_latest.json')
    if flow:
        flow_list = flow if isinstance(flow, list) else flow.get('results', [])
        # Sort by premium/score
        bullish = [f for f in flow_list if f.get('bias') == 'BULLISH']
        bearish = [f for f in flow_list if f.get('bias') == 'BEARISH']
        
        if bullish:
            top_bull = sorted(bullish, key=lambda x: x.get('total_premium', 0), reverse=True)[:5]
            print(f"  {G}BULLISH:{RESET}")
            for f in top_bull:
                ticker = f.get('ticker', '?')
                premium = f.get('total_premium', 0)
                print(f"    {G}▲{RESET} {ticker:6} {format_currency(premium)} premium")
        
        if bearish:
            top_bear = sorted(bearish, key=lambda x: x.get('total_premium', 0), reverse=True)[:3]
            print(f"  {R}BEARISH:{RESET}")
            for f in top_bear:
                ticker = f.get('ticker', '?')
                premium = f.get('total_premium', 0)
                print(f"    {R}▼{RESET} {ticker:6} {format_currency(premium)} premium")
    else:
        print(f"  {D}No options flow data{RESET}")

    print()

    # ── Step 5: HOT Signals ──
    print(f"{B}━━━ 🔥 ACTIONABLE SIGNALS ━━━{RESET}")
    signals = load_json('signals_latest.json')
    if signals:
        hot = signals.get('hot', [])
        strong = signals.get('strong', [])
        
        if hot:
            for s in hot:
                ticker = s.get('ticker', '?')
                conv = s.get('conviction', 0)
                price = s.get('price', 0)
                pattern = s.get('pattern', '')
                flow_bias = s.get('flow_bias', '')
                premium = s.get('premium_flow', 0)
                buy_point = s.get('buy_point', 0)
                stop = s.get('stop', 0)
                reasons = s.get('reasons', [])
                
                print(f"""
  {FIRE} {ticker} — {conv}/100 CONVICTION{RESET}
  {W}{'─' * 50}{RESET}
  Price:     ${price:,.2f}
  Pattern:   {pattern}
  Flow:      {flow_bias} ({format_currency(premium)})
  Buy Point: ${buy_point:,.2f} {'← ACTIONABLE' if buy_point and price >= buy_point * 0.98 else ''}
  {D}Reasons: {', '.join(reasons[:3])}{RESET}""")
                
                # Earnings warning
                earnings_warn = s.get('earnings_warning', False)
                if earnings_warn:
                    print(f"  {R}⚠️  EARNINGS SOON — reduce size or skip{RESET}")
        else:
            print(f"  {Y}No 🔥 HOT signals today{RESET}")
        
        if strong:
            print(f"\n  {G}🟢 STRONG ({len(strong)}):{RESET}")
            for s in strong[:5]:
                ticker = s.get('ticker', '?')
                conv = s.get('conviction', 0)
                flow_bias = s.get('flow_bias', 'N/A')
                print(f"    {ticker:6} {conv}/100  {flow_bias}")
    else:
        print(f"  {D}No signal data{RESET}")

    print()

    # ── Step 6: Action Plan ──
    print(f"{B}━━━ 🎯 TODAY'S ACTION PLAN ━━━{RESET}")
    
    hot_count = len(signals.get('hot', [])) if signals else 0
    strong_count = len(signals.get('strong', [])) if signals else 0
    
    if hot_count > 0:
        print(f"  1. {W}Review {hot_count} 🔥 HOT signal(s) above{RESET}")
        print(f"  2. Calculate position sizes: python3 position_calc.py")
        print(f"  3. Set buy orders at buy points")
        print(f"  4. Set stop losses immediately after fill")
    elif strong_count > 0:
        print(f"  1. {W}Monitor {strong_count} 🟢 STRONG signals{RESET}")
        print(f"  2. Wait for upgrade to 🔥 (pattern + flow alignment)")
        print(f"  3. Don't force trades on 🟢 alone")
    else:
        print(f"  {Y}No high-conviction setups. Cash is a position.{RESET}")
        print(f"  Stay patient. The best trades come to you.")

    print()

    # ── Step 7: Risk Reminders ──
    print(f"{D}━━━ 💡 REMINDERS ━━━{RESET}")
    print(f"  {D}• 🔥 95+ = 15% position (stock + options)")
    print(f"  • 🟢 85-94 = 10% position (stock only)")
    print(f"  • 🟡 70-84 = 5% or paper trade")
    print(f"  • Never risk more than 1-2% per trade")
    print(f"  • Check earnings dates before entering!{RESET}")

    print(f"""
{W}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚡ Quick Commands:
  python3 position_calc.py --account 50000 --entry PRICE --stop STOP
  python3 position_manager.py add TICKER SHARES ENTRY STOP
  python3 alert_system.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
""")

    # ── Save briefing to file ──
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    brief = {
        'timestamp': timestamp,
        'hot_signals': signals.get('hot', []) if signals else [],
        'strong_signals': signals.get('strong', []) if signals else [],
        'top_stocks': money[:5] if money and isinstance(money, list) else [],
    }
    brief_file = os.path.join(SCRIPT_DIR, f'briefing_{timestamp}.json')
    with open(brief_file, 'w') as f:
        json.dump(brief, f, indent=2, default=str)
    print(f"  {D}Briefing saved: {brief_file}{RESET}")


if __name__ == '__main__':
    main()
