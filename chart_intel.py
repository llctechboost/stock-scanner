#!/usr/bin/env python3
"""
Chart Intel — Generates TradingView screenshots with full trade intel cards.
Pulls data from all scanners and sends via Telegram.

Usage:
    python3 chart_intel.py                    # All stocks scoring 7+/12
    python3 chart_intel.py GOOGL AMD NU       # Specific tickers
    python3 chart_intel.py --min-score 8      # Custom threshold
    python3 chart_intel.py --send             # Also send to Telegram
"""

import os
import sys
import re
import glob
import json
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(SCRIPT_DIR, 'charts')
os.makedirs(CHARTS_DIR, exist_ok=True)


def load_json(filename):
    path = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
        return None


def get_scanner_data():
    """Parse latest scan results into a dict of {ticker: data}."""
    stocks = {}
    txt_files = sorted(glob.glob(os.path.join(SCRIPT_DIR, 'scan_results_*.txt')), reverse=True)
    if not txt_files:
        return stocks
    
    with open(txt_files[0], 'r') as f:
        text = f.read()
    
    lines = text.split('\n')
    current = None
    
    # Also grab market timing
    market = {}
    for line in lines:
        ls = line.strip()
        if 'S&P 500:' in ls:
            m = re.search(r'\$([\d,.]+)', ls)
            if m: market['sp500'] = m.group(1)
        if 'Distribution Days:' in ls:
            m = re.search(r'(\d+)', ls)
            if m: market['dist_days'] = m.group(1)
        if 'VIX:' in ls:
            m = re.search(r'([\d.]+)\s*\((\w+)\)', ls)
            if m: market['vix'] = m.group(1); market['vix_level'] = m.group(2)
        if 'Caution' in ls: market['signal'] = 'CAUTION'
        elif 'Green' in ls.lower() and 'light' in ls.lower(): market['signal'] = 'GREEN LIGHT'
        elif 'Red' in ls.lower() and 'light' in ls.lower(): market['signal'] = 'RED LIGHT'
    
    for line in lines:
        ls = line.strip()
        
        ticker_match = re.match(r'^([A-Z]{1,5})\s*-\s*Score:\s*(\d+)/12\s*-\s*\$([\d,.]+)', ls)
        if ticker_match:
            t = ticker_match.group(1)
            if t in stocks:
                continue  # Skip duplicates
            current = {
                'ticker': t,
                'score': int(ticker_match.group(2)),
                'price': float(ticker_match.group(3).replace(',', '')),
                'rs_rating': None,
                'patterns': [],
                'pattern_details': [],
                'buy_point': None,
                'eps_growth': None,
                'roe': None,
                'volume_ratio': None,
                'earnings_warning': False,
                'earnings_days': None,
                'earnings_date': None,
            }
            stocks[t] = current
            continue
        
        if current and ls.startswith('RS Rating:'):
            m = re.search(r'RS Rating:\s*(\d+)', ls)
            if m: current['rs_rating'] = int(m.group(1))
        
        if current and '✓' in ls:
            detail = ls.split('✓', 1)[1].strip() if '✓' in ls else ls
            
            if 'Flat Base' in ls:
                current['patterns'].append('Flat Base')
                current['pattern_details'].append(detail)
            elif 'Cup with Handle' in ls:
                current['patterns'].append('Cup with Handle')
                current['pattern_details'].append(detail)
            elif 'High Tight Flag' in ls:
                current['patterns'].append('High Tight Flag')
                current['pattern_details'].append(detail)
            elif 'Ascending Base' in ls:
                current['patterns'].append('Ascending Base')
                current['pattern_details'].append(detail)
            elif 'Pocket Pivot' in ls:
                current['patterns'].append('Pocket Pivot')
                current['pattern_details'].append(detail)
            elif 'Volume Breakout' in ls:
                m = re.search(r'([\d.]+)x', ls)
                if m: current['volume_ratio'] = f"{m.group(1)}x"
            elif 'EPS Growth' in ls:
                m = re.search(r'EPS Growth\s*([\d.]+)%', ls)
                if m: current['eps_growth'] = f"{m.group(1)}%"
            elif 'ROE' in ls:
                m = re.search(r'ROE\s*([\d.]+)%', ls)
                if m: current['roe'] = f"{m.group(1)}%"
            elif 'EARNINGS' in ls.upper():
                current['earnings_warning'] = True
                dm = re.search(r'EARNINGS IN (\d+) DAYS', ls)
                if dm: current['earnings_days'] = int(dm.group(1))
                dt = re.search(r'\((\d{4}-\d{2}-\d{2})\)', ls)
                if dt: current['earnings_date'] = dt.group(1)
        
        if current and '→ Buy point:' in ls:
            m = re.search(r'\$([\d,.]+)', ls)
            if m: current['buy_point'] = float(m.group(1).replace(',', ''))
    
    return stocks, market


def get_flow_data():
    """Get options flow data per ticker."""
    flows = {}
    data = load_json('options_flow_latest.json')
    if not data:
        return flows
    results = data if isinstance(data, list) else data.get('results', [])
    for f in results:
        t = f.get('ticker')
        if t:
            flows[t] = {
                'bias': f.get('bias', 'N/A'),
                'premium': f.get('total_premium', f.get('call_flow', 0)),
                'top_strike': None,
                'top_type': None,
            }
            signals = f.get('signals', [])
            if signals:
                flows[t]['top_strike'] = signals[0].get('strike')
                flows[t]['top_type'] = signals[0].get('type', 'CALL')
    return flows


def get_dark_pool_data():
    """Get institutional data per ticker."""
    dp = {}
    data = load_json('dark_pool_latest.json')
    if not data:
        return dp
    results = data if isinstance(data, list) else data.get('results', data.get('stocks', []))
    if isinstance(results, list):
        for s in results:
            t = s.get('ticker')
            if t:
                dp[t] = {
                    'signal': s.get('signal', 'NEUTRAL'),
                    'inst_pct': s.get('institutional_pct', s.get('inst_ownership', None)),
                    'short_pct': s.get('short_pct', s.get('short_float', None)),
                }
    return dp


def get_sector_data():
    """Get sector rotation data."""
    sectors = {}
    data = load_json('sector_rotation_latest.json')
    if not data:
        return sectors
    results = data.get('sectors', data.get('results', []))
    if isinstance(results, list):
        for s in results:
            name = s.get('sector', s.get('name', ''))
            sectors[name.lower()] = {
                'flow': s.get('money_flow', s.get('flow_direction', 'NEUTRAL')),
                'rel_1m': s.get('rel_1m', s.get('relative_1m', 0)),
            }
    return sectors


def get_signal_data():
    """Get conviction scores per ticker."""
    signals = {}
    data = load_json('signals_latest.json')
    if not data:
        return signals
    for s in data.get('all', []):
        t = s.get('ticker')
        if t:
            signals[t] = {
                'conviction': s.get('conviction', 0),
                'reasons': s.get('reasons', []),
            }
    return signals


def format_currency(val):
    if val >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    elif val >= 1_000:
        return f"${val/1_000:.0f}K"
    return f"${val:.0f}"


def build_intel_card(ticker, stock, flow, dp, sector_map, signal):
    """Build a comprehensive text intel card for a stock."""
    lines = []
    
    # Header
    lines.append(f"📸 {ticker} — Daily Chart")
    lines.append("")
    
    # Pattern
    if stock['patterns']:
        pattern_name = stock['patterns'][0]
        detail = stock['pattern_details'][0] if stock['pattern_details'] else ''
        lines.append(f"📊 PATTERN: {pattern_name}")
        if detail:
            lines.append(f"   {detail}")
        lines.append(f"   Score: {stock['score']}/12 | RS Rating: {stock.get('rs_rating', '--')}")
    else:
        lines.append(f"📊 Score: {stock['score']}/12 | RS Rating: {stock.get('rs_rating', '--')}")
    
    lines.append("")
    
    # Trade Plan
    if stock['buy_point']:
        bp = stock['buy_point']
        stop = round(bp * 0.93, 2)  # 7% stop loss (O'Neil standard)
        target1 = round(bp * 1.10, 2)  # 10% target
        target2 = round(bp * 1.20, 2)  # 20% target
        risk = bp - stop
        reward = target1 - bp
        rr = round(reward / risk, 1) if risk > 0 else 0
        
        lines.append("💰 TRADE PLAN:")
        lines.append(f"   Buy Point:  ${bp:,.2f}")
        lines.append(f"   Stop Loss:  ${stop:,.2f} (-7%)")
        lines.append(f"   Target 1:   ${target1:,.2f} (+10%)")
        lines.append(f"   Target 2:   ${target2:,.2f} (+20%)")
        lines.append(f"   Risk/Reward: 1:{rr}")
        price = stock['price']
        if price >= bp:
            pos_txt = "ABOVE buy point"
        else:
            pct_below = ((bp - price) / price) * 100
            pos_txt = f"{pct_below:.1f}% below buy"
        lines.append(f"   Current:    ${price:,.2f} ({pos_txt})")
    else:
        lines.append(f"💰 Price: ${stock['price']:,.2f}")
    
    lines.append("")
    
    # Fundamentals
    fundies = []
    if stock['eps_growth']:
        fundies.append(f"EPS Growth: {stock['eps_growth']}")
    if stock['roe']:
        fundies.append(f"ROE: {stock['roe']}")
    if stock['volume_ratio']:
        fundies.append(f"Vol: {stock['volume_ratio']}")
    
    if fundies:
        lines.append(f"📈 FUNDAMENTALS: {' | '.join(fundies)}")
        lines.append("")
    
    # Options Flow
    if flow:
        bias = flow['bias']
        premium = flow['premium']
        emoji = "🟢" if bias == "BULLISH" else "🔴" if bias == "BEARISH" else "⚪"
        lines.append(f"💸 OPTIONS FLOW: {emoji} {bias} — {format_currency(premium)} premium")
        lines.append("")
    
    # Dark Pool / Institutional
    if dp:
        sig = dp.get('signal', 'NEUTRAL')
        inst = dp.get('inst_pct')
        short = dp.get('short_pct')
        if sig == 'ACCUMULATING':
            lines.append(f"🏦 INSTITUTIONS: 🟢 Accumulating")
        elif sig == 'DISTRIBUTING':
            lines.append(f"🏦 INSTITUTIONS: 🔴 Distributing")
        else:
            parts = []
            if inst: parts.append(f"Inst: {inst}%")
            if short: parts.append(f"Short: {short}%")
            if parts:
                lines.append(f"🏦 INSTITUTIONS: {' | '.join(parts)}")
        lines.append("")
    
    # Earnings
    if stock['earnings_warning']:
        days = stock['earnings_days']
        date = stock['earnings_date']
        if days and days <= 7:
            lines.append(f"🚨 EARNINGS: {date} ({days} days) — DO NOT ENTER")
            lines.append(f"   Wait for post-earnings reaction, then reassess")
        elif days and days <= 14:
            lines.append(f"⚠️ EARNINGS: {date} ({days} days) — REDUCE SIZE")
            lines.append(f"   Enter with half position or wait")
        lines.append("")
    else:
        lines.append("✅ EARNINGS: Clear (no upcoming)")
        lines.append("")
    
    # Conviction
    if signal:
        conv = signal['conviction']
        if conv >= 95:
            emoji = "🔥"
            label = "HOT — Maximum conviction"
        elif conv >= 85:
            emoji = "🟢"
            label = "STRONG — High conviction"
        elif conv >= 70:
            emoji = "🟡"
            label = "WATCH — Good conviction"
        else:
            emoji = "⚪"
            label = "LOW — Wait for better setup"
        lines.append(f"{emoji} CONVICTION: {conv}/100 — {label}")
    
    return '\n'.join(lines)


def screenshot_chart(ticker):
    """Take TradingView chart screenshot."""
    from playwright.sync_api import sync_playwright
    
    widget_html = f"""<!DOCTYPE html>
<html><head><style>
html,body{{margin:0;padding:0;background:#0a0a0a;width:100%;height:100%;overflow:hidden}}
.tradingview-widget-container{{width:100%;height:100%}}
#tv-widget{{width:100%;height:100%}}
iframe{{width:100%!important;height:100%!important}}
</style></head><body>
<div class="tradingview-widget-container"><div id="tv-widget"></div>
<script src="https://s3.tradingview.com/tv.js"></script>
<script>
new TradingView.widget({{
"width":"100%","height":"100%","symbol":"{ticker}","interval":"D",
"timezone":"America/New_York","theme":"dark","style":"1","locale":"en",
"toolbar_bg":"#0a0a0a","enable_publishing":false,"hide_top_toolbar":false,
"hide_legend":false,"save_image":false,"container_id":"tv-widget",
"studies":["MASimple@tv-basicstudies","MASimple@tv-basicstudies","Volume@tv-basicstudies"],
"studies_overrides":{{"moving average.length":21,"moving average.color":"#2196F3",
"moving average.linewidth":2,"moving average #1.length":50,
"moving average #1.color":"#FF9800","moving average #1.linewidth":2}},
"overrides":{{"mainSeriesProperties.candleStyle.upColor":"#00ff88",
"mainSeriesProperties.candleStyle.downColor":"#ff4444",
"mainSeriesProperties.candleStyle.borderUpColor":"#00ff88",
"mainSeriesProperties.candleStyle.borderDownColor":"#ff4444",
"mainSeriesProperties.candleStyle.wickUpColor":"#00ff88",
"mainSeriesProperties.candleStyle.wickDownColor":"#ff4444",
"paneProperties.background":"#0a0a0a",
"paneProperties.vertGridProperties.color":"#1a1a1a",
"paneProperties.horzGridProperties.color":"#1a1a1a"}}
}});
</script></div></body></html>"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filepath = os.path.join(CHARTS_DIR, f"{ticker}_{timestamp}.png")
    temp_html = os.path.join(CHARTS_DIR, f'_temp_{ticker}.html')
    
    with open(temp_html, 'w') as f:
        f.write(widget_html)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1000, 'height': 600})
            page.goto(f'file://{temp_html}', wait_until='networkidle', timeout=30000)
            time.sleep(3)
            try:
                page.wait_for_selector('iframe', timeout=10000)
                time.sleep(2)
                frame = page.frames[-1] if len(page.frames) > 1 else page
                frame.wait_for_selector('canvas', timeout=15000)
                time.sleep(4)
            except:
                time.sleep(8)
            page.screenshot(path=filepath, full_page=False)
            browser.close()
        os.remove(temp_html)
        return filepath
    except Exception as e:
        if os.path.exists(temp_html):
            os.remove(temp_html)
        print(f"  ✗ Error: {e}")
        return None


def main():
    print(f"\n{'='*55}")
    print(f"  📸 CHART INTEL — TradingView + Full Trade Analysis")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}\n")
    
    min_score = 7
    manual_tickers = []
    send_telegram = False
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--min-score' and i + 1 < len(args):
            min_score = int(args[i + 1]); i += 2
        elif args[i].startswith('--min-score='):
            min_score = int(args[i].split('=')[1]); i += 1
        elif args[i] == '--send':
            send_telegram = True; i += 1
        elif args[i].isupper() and len(args[i]) <= 5:
            manual_tickers.append(args[i]); i += 1
        else:
            i += 1
    
    # Load all data sources
    scanner_data, market = get_scanner_data()
    flow_data = get_flow_data()
    dp_data = get_dark_pool_data()
    sector_data = get_sector_data()
    signal_data = get_signal_data()
    
    print(f"  Data loaded: {len(scanner_data)} scanned, {len(flow_data)} flow, "
          f"{len(dp_data)} institutional, {len(signal_data)} signals\n")
    
    # Determine tickers to process
    if manual_tickers:
        tickers = manual_tickers
    else:
        tickers = [t for t, d in scanner_data.items() if d['score'] >= min_score]
        tickers.sort(key=lambda t: scanner_data[t]['score'], reverse=True)
    
    if not tickers:
        print(f"  No stocks scoring {min_score}+/12. Run scanner first.\n")
        return
    
    print(f"  Processing {len(tickers)} stocks: {', '.join(tickers)}\n")
    
    results = []
    
    for idx, ticker in enumerate(tickers):
        stock = scanner_data.get(ticker)
        if not stock:
            # Create minimal entry for manual tickers
            stock = {'ticker': ticker, 'score': 0, 'price': 0, 'patterns': [],
                     'pattern_details': [], 'buy_point': None, 'rs_rating': None,
                     'eps_growth': None, 'roe': None, 'volume_ratio': None,
                     'earnings_warning': False, 'earnings_days': None, 'earnings_date': None}
        
        flow = flow_data.get(ticker)
        dp = dp_data.get(ticker)
        signal = signal_data.get(ticker)
        
        # Build intel card
        intel = build_intel_card(ticker, stock, flow, dp, sector_data, signal)
        
        # Take screenshot
        print(f"  [{idx+1}/{len(tickers)}] {ticker}...", end='', flush=True)
        filepath = screenshot_chart(ticker)
        
        if filepath:
            size_kb = os.path.getsize(filepath) / 1024
            print(f" ✓ ({size_kb:.0f}KB)")
        else:
            print(f" ✗ screenshot failed")
            filepath = None
        
        # Print intel card
        print()
        for line in intel.split('\n'):
            print(f"  {line}")
        print(f"\n  {'─'*50}\n")
        
        results.append({
            'ticker': ticker,
            'chart_path': filepath,
            'intel': intel,
            'score': stock['score'],
        })
    
    # Save manifest
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'market': market,
        'charts': [{
            'ticker': r['ticker'],
            'path': r['chart_path'],
            'intel': r['intel'],
            'score': r['score'],
        } for r in results]
    }
    manifest_path = os.path.join(CHARTS_DIR, 'intel_manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"  Done! {len(results)} charts + intel cards generated.")
    print(f"  Saved to: {CHARTS_DIR}/\n")
    
    return results


if __name__ == '__main__':
    main()
