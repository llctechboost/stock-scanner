#!/usr/bin/env python3
"""
TradingView Chart Screenshotter
Takes daily chart screenshots for stocks scoring 8+ from the scanner.

Usage:
    python3 chart_screenshotter.py                  # Screenshot all 8+ stocks from latest scan
    python3 chart_screenshotter.py GOOGL NVDA AMD   # Screenshot specific tickers
    python3 chart_screenshotter.py --min-score 6    # Lower threshold

Output: charts/ directory with timestamped PNG files
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


def get_tickers_from_scan(min_score=8):
    """Get tickers scoring above threshold from latest scan results."""
    tickers = []
    
    # Try scan results text files
    txt_files = sorted(glob.glob(os.path.join(SCRIPT_DIR, 'scan_results_*.txt')), reverse=True)
    if txt_files:
        with open(txt_files[0], 'r') as f:
            for line in f:
                match = re.match(r'^([A-Z]{1,5})\s*-\s*Score:\s*(\d+)/12', line.strip())
                if match:
                    ticker = match.group(1)
                    score = int(match.group(2))
                    if score >= min_score:
                        tickers.append((ticker, score))
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for t, s in tickers:
        if t not in seen:
            seen.add(t)
            unique.append((t, s))
    
    return sorted(unique, key=lambda x: x[1], reverse=True)


def screenshot_tradingview(ticker, timeframe='D'):
    """
    Take a screenshot of a TradingView chart for a ticker.
    
    Uses TradingView's widget/embed URL which doesn't require login.
    Timeframe: D=daily, W=weekly, M=monthly, 60=1hr, 240=4hr
    """
    from playwright.sync_api import sync_playwright
    
    # TradingView chart URL (public, no login needed)
    # Using the advanced chart widget
    url = f"https://www.tradingview.com/chart/?symbol={ticker}&interval={timeframe}"
    
    # Alternative: use the mini chart widget (cleaner, no login wall)
    widget_html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>
        html, body {{ margin:0; padding:0; background:#0a0a0a; width:100%; height:100%; overflow:hidden; }}
        .tradingview-widget-container {{ width:100%; height:100%; }}
        #tv-widget {{ width:100%; height:100%; }}
        iframe {{ width:100% !important; height:100% !important; }}
    </style></head>
    <body>
    <div class="tradingview-widget-container">
        <div id="tv-widget"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
            "width": "100%",
            "height": "100%",
            "symbol": "{ticker}",
            "interval": "{timeframe}",
            "timezone": "America/New_York",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "toolbar_bg": "#0a0a0a",
            "enable_publishing": false,
            "hide_top_toolbar": false,
            "hide_legend": false,
            "save_image": false,
            "container_id": "tv-widget",
            "studies": ["MASimple@tv-basicstudies", "MASimple@tv-basicstudies", "Volume@tv-basicstudies"],
            "studies_overrides": {{
                "moving average.length": 21,
                "moving average.color": "#2196F3",
                "moving average.linewidth": 2,
                "moving average #1.length": 50,
                "moving average #1.color": "#FF9800",
                "moving average #1.linewidth": 2
            }},
            "overrides": {{
                "mainSeriesProperties.candleStyle.upColor": "#00ff88",
                "mainSeriesProperties.candleStyle.downColor": "#ff4444",
                "mainSeriesProperties.candleStyle.borderUpColor": "#00ff88",
                "mainSeriesProperties.candleStyle.borderDownColor": "#ff4444",
                "mainSeriesProperties.candleStyle.wickUpColor": "#00ff88",
                "mainSeriesProperties.candleStyle.wickDownColor": "#ff4444",
                "paneProperties.background": "#0a0a0a",
                "paneProperties.vertGridProperties.color": "#1a1a1a",
                "paneProperties.horzGridProperties.color": "#1a1a1a"
            }}
        }});
        </script>
    </div>
    </body>
    </html>
    """
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{ticker}_{timestamp}.png"
    filepath = os.path.join(CHARTS_DIR, filename)
    
    # Write temp HTML
    temp_html = os.path.join(CHARTS_DIR, f'_temp_{ticker}.html')
    with open(temp_html, 'w') as f:
        f.write(widget_html)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1000, 'height': 600})
            
            # Load the widget
            page.goto(f'file://{temp_html}', wait_until='networkidle', timeout=30000)
            
            # Wait for TradingView widget to fully render
            time.sleep(3)
            
            # Wait for the chart iframe and canvas
            try:
                page.wait_for_selector('iframe', timeout=10000)
                time.sleep(2)
                # Wait for canvas inside iframe
                frame = page.frames[-1] if len(page.frames) > 1 else page
                frame.wait_for_selector('canvas', timeout=15000)
                time.sleep(4)  # Extra time for candles to draw
            except:
                time.sleep(8)  # Fallback — just wait
            
            # Screenshot
            page.screenshot(path=filepath, full_page=False)
            browser.close()
        
        # Cleanup temp file
        os.remove(temp_html)
        
        return filepath
    
    except Exception as e:
        # Cleanup
        if os.path.exists(temp_html):
            os.remove(temp_html)
        print(f"  ✗ Error screenshotting {ticker}: {e}")
        return None


def main():
    print(f"""
╔══════════════════════════════════════════════════╗
║  📸 TradingView Chart Screenshotter              ║
║  {datetime.now().strftime('%Y-%m-%d %H:%M'):^48}║
╚══════════════════════════════════════════════════╝
""")
    
    min_score = 8
    tickers = []
    
    # Parse args
    args = sys.argv[1:]
    manual_tickers = []
    for arg in args:
        if arg.startswith('--min-score'):
            if '=' in arg:
                min_score = int(arg.split('=')[1])
            elif args.index(arg) + 1 < len(args):
                min_score = int(args[args.index(arg) + 1])
        elif arg.isupper() and len(arg) <= 5:
            manual_tickers.append(arg)
    
    if manual_tickers:
        tickers = [(t, 0) for t in manual_tickers]
        print(f"  Screenshotting {len(tickers)} tickers: {', '.join(manual_tickers)}\n")
    else:
        tickers = get_tickers_from_scan(min_score)
        if tickers:
            print(f"  Found {len(tickers)} stocks scoring {min_score}+/12:")
            for t, s in tickers:
                print(f"    {t} — {s}/12")
            print()
        else:
            print(f"  No stocks scoring {min_score}+/12 in latest scan.\n")
            print(f"  Run: python3 scanner_v3.py first, or specify tickers:")
            print(f"  python3 chart_screenshotter.py GOOGL NVDA AMD\n")
            return
    
    # Screenshot each
    results = []
    for i, (ticker, score) in enumerate(tickers):
        print(f"  [{i+1}/{len(tickers)}] {ticker}...", end='', flush=True)
        filepath = screenshot_tradingview(ticker)
        if filepath:
            size_kb = os.path.getsize(filepath) / 1024
            print(f" ✓ ({size_kb:.0f}KB)")
            results.append({'ticker': ticker, 'score': score, 'path': filepath})
        else:
            print(f" ✗ failed")
    
    print(f"\n  Done! {len(results)}/{len(tickers)} charts saved to: {CHARTS_DIR}/")
    
    # Save manifest
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'min_score': min_score,
        'charts': results
    }
    manifest_path = os.path.join(CHARTS_DIR, 'charts_manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    return results


if __name__ == '__main__':
    main()
