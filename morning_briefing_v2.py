#!/usr/bin/env python3
"""
Morning Briefing v2.0 - Integrated with Screener v3
Includes: 200W MA, Pattern Recognition, Fundamentals scoring
"""

import json
import os
import sys
from datetime import datetime
import yfinance as yf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════════════════════════
# SCREENER FUNCTIONS (from screener_v3)
# ═══════════════════════════════════════════════════════════════

def get_200w_ma_data(ticker):
    """Get 200W MA proximity for a ticker"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5y", interval="1wk")
        
        if len(hist) < 200:
            return None, None
        
        hist['SMA_200W'] = hist['Close'].rolling(window=200).mean()
        current = hist['Close'].iloc[-1]
        sma = hist['SMA_200W'].iloc[-1]
        
        if sma and not pd.isna(sma):
            pct = ((current - sma) / sma) * 100
            return sma, pct
        return None, None
    except:
        return None, None


def load_screener_results():
    """Load most recent screener results"""
    import glob
    
    pattern = os.path.join(SCRIPT_DIR, 'screener_results_*.json')
    files = sorted(glob.glob(pattern), reverse=True)
    
    if files:
        with open(files[0]) as f:
            return json.load(f), files[0]
    return None, None


def run_quick_scan(tickers):
    """Run quick scan on specific tickers"""
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from screener_v3 import screen_stock
        
        results = []
        for ticker in tickers:
            try:
                result = screen_stock(ticker)
                results.append(result)
            except:
                pass
        return results
    except:
        return []


# ═══════════════════════════════════════════════════════════════
# MAIN BRIEFING
# ═══════════════════════════════════════════════════════════════

def main():
    import pandas as pd
    
    now = datetime.now()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           ☀️  MORNING BRIEFING v2.0  ☀️                      ║
║           {now.strftime('%A, %B %d, %Y  %I:%M %p'):^48}║
╚══════════════════════════════════════════════════════════════╝
""")

    # ━━━ MARKET CONTEXT ━━━
    print("━━━ 📊 MARKET CONTEXT ━━━")
    try:
        spy = yf.download('^GSPC', period='3mo', progress=False)
        vix = yf.download('^VIX', period='1mo', progress=False)
        
        # Handle multi-index
        if hasattr(spy.columns, 'levels') and len(spy.columns.levels) > 1:
            spy.columns = spy.columns.get_level_values(0)
        if hasattr(vix.columns, 'levels') and len(vix.columns.levels) > 1:
            vix.columns = vix.columns.get_level_values(0)
        
        spy_price = spy['Close'].iloc[-1]
        spy_ma200 = spy['Close'].rolling(200).mean().iloc[-1]
        spy_chg = ((spy['Close'].iloc[-1] / spy['Close'].iloc[-2]) - 1) * 100
        vix_val = vix['Close'].iloc[-1]
        
        # SPY vs 200 day
        spy_200_pct = ((spy_price - spy_ma200) / spy_ma200) * 100
        
        trend = "🟢 BULLISH" if spy_price > spy_ma200 else "🔴 BEARISH"
        vix_label = "Low" if vix_val < 15 else "Moderate" if vix_val < 20 else "Elevated" if vix_val < 30 else "HIGH"
        
        print(f"  SPY: ${spy_price:,.2f} ({'+' if spy_chg > 0 else ''}{spy_chg:.1f}%) | {trend}")
        print(f"  SPY vs 200D MA: {spy_200_pct:+.1f}%")
        print(f"  VIX: {vix_val:.1f} ({vix_label})")
        
    except Exception as e:
        print(f"  Market data error: {e}")
    
    print()

    # ━━━ SCREENER TOP PICKS ━━━
    print("━━━ 🎯 SCREENER TOP PICKS (v3 Scoring) ━━━")
    
    screener_data, screener_file = load_screener_results()
    
    if screener_data:
        # Top 10 by total score
        top10 = sorted(screener_data, key=lambda x: x.get('total_score', 0), reverse=True)[:10]
        
        print(f"  {'Rank':<5} {'Ticker':<7} {'Score':<8} {'Pattern':<8} {'Fund':<8} {'200W MA':<10} {'Setup'}")
        print(f"  {'-'*70}")
        
        for i, r in enumerate(top10, 1):
            pct = r.get('pct_from_200w')
            pct_str = f"{pct:+.1f}%" if pct else "N/A"
            patterns = ', '.join(r.get('patterns', []))[:20] if r.get('patterns') else 'None'
            
            # Highlight if tight to 200W MA
            tight = "✅" if pct and abs(pct) <= 5 else ""
            
            print(f"  {i:<5} {r['ticker']:<7} {r['total_score']:<8.1f} {r.get('pattern_score', 0):.0f}/50{'':<3} {r.get('fundamentals_score', 0):.0f}/50{'':<3} {pct_str:<10} {patterns} {tight}")
        
        print(f"\n  Source: {os.path.basename(screener_file)}")
    else:
        print("  No screener results found. Run: python3 screener_v3.py")
    
    print()

    # ━━━ TIGHT TO 200W MA ━━━
    print("━━━ 📍 TIGHT TO 200W MA (±5%) ━━━")
    
    if screener_data:
        tight_200w = [r for r in screener_data 
                      if r.get('pct_from_200w') is not None 
                      and abs(r['pct_from_200w']) <= 5
                      and r.get('total_score', 0) >= 50]
        
        tight_200w = sorted(tight_200w, key=lambda x: abs(x['pct_from_200w']))[:8]
        
        if tight_200w:
            for r in tight_200w:
                pct = r['pct_from_200w']
                emoji = "🎯" if abs(pct) <= 2 else "📍"
                print(f"  {emoji} {r['ticker']:<7} {r['total_score']:.1f}/100 | {pct:+.1f}% from 200W MA | {r.get('patterns', ['None'])}")
        else:
            print("  No stocks tight to 200W MA with score >= 50")
    
    print()

    # ━━━ PATTERN ALERTS ━━━
    print("━━━ 📈 PATTERN ALERTS ━━━")
    
    if screener_data:
        # Cup & Handle
        cup_handle = [r for r in screener_data if 'Cup & Handle' in str(r.get('patterns', []))]
        cup_handle = sorted(cup_handle, key=lambda x: x.get('total_score', 0), reverse=True)[:5]
        
        # VCP
        vcp = [r for r in screener_data if 'VCP' in str(r.get('patterns', []))]
        vcp = sorted(vcp, key=lambda x: x.get('total_score', 0), reverse=True)[:5]
        
        if cup_handle:
            print("  🏆 CUP & HANDLE:")
            for r in cup_handle:
                pct = r.get('pct_from_200w')
                pct_str = f"{pct:+.1f}%" if pct else "N/A"
                print(f"     {r['ticker']:<7} {r['total_score']:.1f}/100 | 200W: {pct_str}")
        
        if vcp:
            print("  📊 VCP (Volatility Contraction):")
            for r in vcp:
                pct = r.get('pct_from_200w')
                pct_str = f"{pct:+.1f}%" if pct else "N/A"
                vcp_type = [p for p in r.get('patterns', []) if 'VCP' in p]
                print(f"     {r['ticker']:<7} {r['total_score']:.1f}/100 | 200W: {pct_str} | {vcp_type}")
        
        if not cup_handle and not vcp:
            print("  No Cup & Handle or VCP patterns detected")
    
    print()

    # ━━━ WATCHLIST CHECK ━━━
    print("━━━ 👀 WATCHLIST QUICK CHECK ━━━")
    
    watchlist = ['GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'AAPL', 'MSFT']
    
    if screener_data:
        watchlist_dict = {r['ticker']: r for r in screener_data if r['ticker'] in watchlist}
        
        for ticker in watchlist:
            if ticker in watchlist_dict:
                r = watchlist_dict[ticker]
                pct = r.get('pct_from_200w')
                pct_str = f"{pct:+.1f}%" if pct else "N/A"
                patterns = r.get('patterns', ['None'])
                print(f"  {ticker:<7} {r['total_score']:.1f}/100 | 200W: {pct_str} | {patterns}")
    
    print()

    # ━━━ ACTION ITEMS ━━━
    print("━━━ 🎯 TODAY'S ACTION ━━━")
    
    if screener_data:
        top_tight = [r for r in screener_data 
                     if r.get('pct_from_200w') is not None 
                     and abs(r['pct_from_200w']) <= 5
                     and r.get('total_score', 0) >= 60]
        
        if top_tight:
            best = sorted(top_tight, key=lambda x: x['total_score'], reverse=True)[0]
            print(f"  1. 🎯 FOCUS: {best['ticker']} — {best['total_score']:.1f}/100, {best['pct_from_200w']:+.1f}% from 200W MA")
            print(f"  2. Verify options flow on Unusual Whales")
            print(f"  3. Check for earnings dates before entry")
        else:
            print("  No high-conviction setups tight to 200W MA")
            print("  Be patient — cash is a position")
    
    print()

    # ━━━ COMMANDS ━━━
    print("""━━━ ⚡ QUICK COMMANDS ━━━
  Run full screener:  python3 screener_v3.py
  Check single stock: python3 screener_v3.py TICKER
  Run old system:     python3 system.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    # Save briefing
    brief = {
        'timestamp': now.isoformat(),
        'top_picks': screener_data[:10] if screener_data else [],
        'tight_200w': [r for r in screener_data if r.get('pct_from_200w') and abs(r['pct_from_200w']) <= 5][:10] if screener_data else []
    }
    
    brief_file = os.path.join(SCRIPT_DIR, f"briefing_v2_{now.strftime('%Y%m%d_%H%M')}.json")
    with open(brief_file, 'w') as f:
        json.dump(brief, f, indent=2, default=str)
    
    print(f"  Briefing saved: {brief_file}")


if __name__ == '__main__':
    import pandas as pd
    main()
