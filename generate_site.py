#!/usr/bin/env python3
"""
Generate static index.html for GitHub Pages
Runs scanner on 200 S&P 500 stocks and updates the site
"""
import os
import sys
import json
import subprocess
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Top 200 S&P 500 by market cap
UNIVERSE = [
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


def scan_stock(ticker):
    """Scan a single stock and return data."""
    try:
        df = yf.download(ticker, period='2y', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 200:
            return None
        
        close = df['Close']
        volume = df['Volume']
        high = df['High']
        low = df['Low']
        price = float(close.iloc[-1])
        
        # 200 WMA (Weekly Moving Average approximation using 200 days)
        weights = np.arange(1, 201)
        wma_200 = close.rolling(200).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True).iloc[-1]
        wma_pct = ((price - wma_200) / wma_200) * 100
        
        # 50 and 200 SMA
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1]
        
        # Score calculation
        score = 0
        signals = []
        
        # RS (3-month performance)
        perf_3m = (price / close.iloc[-63] - 1) * 100 if len(close) > 63 else 0
        if perf_3m > 20:
            score += 25
        elif perf_3m > 10:
            score += 15
        elif perf_3m > 0:
            score += 5
        
        # Price vs MAs
        if price > ma50:
            score += 10
        if price > ma200:
            score += 10
        if ma50 > ma200:
            score += 5
        
        # Volume
        avg_vol = volume.rolling(50).mean().iloc[-1]
        recent_vol = volume.iloc[-5:].mean()
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
        if vol_ratio > 1.5:
            score += 15
        elif vol_ratio > 1.2:
            score += 10
        
        # Volatility contraction (VCP)
        recent_range = (close.iloc[-20:].max() - close.iloc[-20:].min()) / price
        prior_range = (close.iloc[-60:-20].max() - close.iloc[-60:-20].min()) / close.iloc[-40] if len(close) > 60 else recent_range
        vcp_score = 0
        if recent_range < prior_range * 0.5:
            score += 15
            vcp_score = 9
        elif recent_range < prior_range * 0.7:
            score += 10
            vcp_score = 7
        
        # 52-week high proximity
        high_52w = close.iloc[-252:].max() if len(close) >= 252 else close.max()
        pct_from_high = ((high_52w - price) / high_52w) * 100
        if pct_from_high < 3:
            score += 15
            signals.append('BREAKOUT')
        elif pct_from_high < 10:
            score += 10
            signals.append('AT PIVOT')
        
        # 200 WMA zone (Munger buy zone: within 10% of 200 WMA)
        in_wma_zone = abs(wma_pct) < 10
        if in_wma_zone:
            signals.append('200-WMA')
            score += 10
        
        # Determine signal type
        if 'BREAKOUT' in signals:
            signal_type = 'BREAKOUT'
        elif vcp_score >= 7:
            signal_type = 'VCP'
        elif 'AT PIVOT' in signals:
            signal_type = 'AT PIVOT'
        elif in_wma_zone:
            signal_type = '200-WMA'
        else:
            signal_type = 'WATCH'
        
        # Calculate entry, stop, target
        entry = round(price * 1.005, 2)
        stop = round(price * 0.92, 2)
        target = round(price * 1.20, 2)
        
        # Munger stars (fundamental proxy based on stability)
        munger = '⭐⭐⭐' if score >= 80 else '⭐⭐' if score >= 60 else '⭐'
        
        return {
            'ticker': ticker,
            'price': price,
            'score': min(100, score),
            'signal_type': signal_type,
            'entry': entry,
            'stop': stop,
            'target': target,
            'wma_pct': wma_pct,
            'in_wma_zone': in_wma_zone,
            'vcp_score': vcp_score,
            'pct_from_high': pct_from_high,
            'vol_ratio': vol_ratio,
            'perf_3m': perf_3m,
            'munger': munger
        }
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")
        return None


def generate_html(results):
    """Generate the full index.html with scan results."""
    
    # Sort and categorize
    actionable = [r for r in results if r['signal_type'] in ['BREAKOUT', 'VCP', 'AT PIVOT', '200-WMA'] and r['score'] >= 70]
    actionable.sort(key=lambda x: x['score'], reverse=True)
    
    wma_zone = [r for r in results if r['in_wma_zone']]
    vcps = [r for r in results if r['vcp_score'] >= 7]
    watchlist = [r for r in results if r['score'] >= 50 and r not in actionable]
    watchlist.sort(key=lambda x: x['score'], reverse=True)
    
    timestamp = datetime.now().strftime("%B %d, %Y • %I:%M %p EST")
    
    # Generate stock rows
    def make_row(s, row_class=''):
        score_class = 'score-a' if s['score'] >= 80 else 'score-b' if s['score'] >= 60 else 'score-c'
        tag_class = {
            'BREAKOUT': 'tag-breakout',
            'VCP': 'tag-vcp',
            'AT PIVOT': 'tag-pivot',
            '200-WMA': 'tag-200wma',
            'WATCH': 'tag-forming'
        }.get(s['signal_type'], 'tag-forming')
        
        wma_display = f"+{s['wma_pct']:.0f}%" if s['wma_pct'] > 0 else f"{s['wma_pct']:.0f}%"
        wma_class = 'cyan' if s['in_wma_zone'] else ''
        
        signal_display = s['signal_type']
        if s['signal_type'] == 'VCP' and s['vcp_score'] >= 8:
            signal_display = 'VCP ⭐'
        elif s['signal_type'] == '200-WMA':
            signal_display = '200-WMA 🧠'
        
        action = 'BUY' if s['score'] >= 70 else 'WATCH'
        action_class = 'action-buy' if action == 'BUY' else 'action-watch'
        
        return f'''<tr class="{row_class}" onclick="loadChart('{s['ticker']}')">
                    <td class="ticker">{s['ticker']}</td>
                    <td><span class="pattern-tag {tag_class}">{signal_display}</span></td>
                    <td><span class="score-pill {score_class}">{s['score']}</span></td>
                    <td>${s['price']:,.2f}</td>
                    <td class="positive">${s['entry']:,.2f}</td>
                    <td class="negative">${s['stop']:,.2f}</td>
                    <td class="positive">${s['target']:,.2f}</td>
                    <td class="{wma_class}">{wma_display}</td>
                    <td class="munger-stars">{s['munger']}</td>
                    <td><span class="action-badge {action_class}">{action}</span></td>
                </tr>'''
    
    actionable_rows = '\n'.join([make_row(s, 'actionable' if s['signal_type'] != '200-WMA' else 'wma-buy-zone') for s in actionable[:20]])
    watchlist_rows = '\n'.join([make_row(s) for s in watchlist[:30]])
    
    # Generate stockData for chart
    stock_data_js = ',\n'.join([
        f"'{s['ticker']}': {{ price: {s['price']:.2f}, entry: {s['entry']:.2f}, stop: {s['stop']:.0f}, target: {s['target']:.0f}, pattern: '{s['signal_type']}', vcp: {s['vcp_score']}, rs: '+{s['perf_3m']:.0f}%', high: '{s['pct_from_high']:.1f}%', wma: '{s['wma_pct']:+.0f}%', munger: '{s['munger']}' }}"
        for s in results[:50]
    ])
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Scanner Command Center</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; }}
        .container {{ max-width: 1600px; margin: 0 auto; padding: 15px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; background: linear-gradient(90deg, rgba(88,166,255,0.1), rgba(163,113,247,0.1)); border-radius: 12px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.1); }}
        .header h1 {{ font-size: 1.6em; background: linear-gradient(90deg, #58a6ff, #a371f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header .timestamp {{ color: #8b949e; font-size: 0.85em; }}
        .header .status {{ display: flex; gap: 15px; align-items: center; }}
        .status-badge {{ padding: 5px 12px; border-radius: 20px; font-size: 0.8em; font-weight: 600; }}
        .status-live {{ background: rgba(63,185,80,0.2); color: #3fb950; }}
        .status-market {{ background: rgba(88,166,255,0.2); color: #58a6ff; }}
        .main-grid {{ display: grid; grid-template-columns: 1fr 420px; gap: 20px; }}
        .section {{ background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); overflow: hidden; margin-bottom: 20px; }}
        .section-header {{ padding: 12px 16px; background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; justify-content: space-between; align-items: center; }}
        .section-title {{ font-size: 1em; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
        .section-count {{ background: rgba(88,166,255,0.2); color: #58a6ff; padding: 2px 10px; border-radius: 12px; font-size: 0.75em; }}
        .section-body {{ padding: 0; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
        th {{ padding: 10px 12px; text-align: left; font-weight: 600; color: #8b949e; font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.5px; background: rgba(255,255,255,0.02); }}
        td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        tr:hover {{ background: rgba(255,255,255,0.03); }}
        tr.actionable {{ background: rgba(63,185,80,0.08); }}
        tr.actionable:hover {{ background: rgba(63,185,80,0.12); }}
        tr.wma-buy-zone {{ background: rgba(0,212,255,0.08); }}
        tr.wma-buy-zone:hover {{ background: rgba(0,212,255,0.12); }}
        .ticker {{ font-weight: 700; color: #e6edf3; cursor: pointer; }}
        .ticker:hover {{ color: #58a6ff; text-decoration: underline; }}
        .positive {{ color: #3fb950; }}
        .negative {{ color: #f85149; }}
        .cyan {{ color: #00d4ff; }}
        .score-pill {{ padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.85em; }}
        .score-a {{ background: rgba(63,185,80,0.2); color: #3fb950; }}
        .score-b {{ background: rgba(254,202,87,0.2); color: #d29922; }}
        .score-c {{ background: rgba(248,81,73,0.2); color: #f85149; }}
        .pattern-tag {{ padding: 2px 8px; border-radius: 4px; font-size: 0.75em; font-weight: 600; }}
        .tag-breakout {{ background: rgba(63,185,80,0.15); color: #3fb950; }}
        .tag-vcp {{ background: rgba(255,107,107,0.15); color: #ff6b6b; }}
        .tag-pivot {{ background: rgba(88,166,255,0.15); color: #58a6ff; }}
        .tag-forming {{ background: rgba(139,148,158,0.15); color: #8b949e; }}
        .tag-200wma {{ background: rgba(0,212,255,0.15); color: #00d4ff; }}
        .action-badge {{ padding: 4px 10px; border-radius: 4px; font-size: 0.75em; font-weight: 700; }}
        .action-buy {{ background: #238636; color: #fff; }}
        .action-watch {{ background: rgba(210,153,34,0.2); color: #d29922; }}
        .munger-stars {{ color: #ffc107; }}
        .quick-stats {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 20px; }}
        .stat-card {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 15px; text-align: center; border: 1px solid rgba(255,255,255,0.08); }}
        .stat-value {{ font-size: 1.8em; font-weight: 700; }}
        .stat-label {{ color: #8b949e; font-size: 0.75em; margin-top: 5px; }}
        .chart-panel {{ position: sticky; top: 15px; }}
        .chart-container {{ background: #1e222d; border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); }}
        .chart-header {{ padding: 10px 15px; background: rgba(255,255,255,0.03); display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.08); }}
        .chart-ticker {{ font-weight: 700; font-size: 1.1em; color: #58a6ff; }}
        .chart-price {{ color: #3fb950; font-weight: 600; }}
        .tradingview-widget-container {{ height: 350px; }}
        .trade-box {{ margin: 15px; padding: 15px; background: rgba(63,185,80,0.1); border-radius: 8px; border: 1px solid rgba(63,185,80,0.2); }}
        .trade-box h4 {{ color: #3fb950; margin-bottom: 10px; font-size: 0.9em; }}
        .trade-row {{ display: flex; justify-content: space-between; margin: 8px 0; }}
        .trade-label {{ color: #8b949e; font-size: 0.85em; }}
        .trade-value {{ font-weight: 700; font-size: 0.95em; }}
        .trade-value.entry {{ color: #3fb950; }}
        .trade-value.stop {{ color: #f85149; }}
        .trade-value.target {{ color: #58a6ff; }}
        .footer {{ text-align: center; padding: 20px; color: #6e7681; font-size: 0.8em; border-top: 1px solid rgba(255,255,255,0.05); margin-top: 20px; }}
        @media (max-width: 1200px) {{ .main-grid {{ grid-template-columns: 1fr; }} .chart-panel {{ position: static; }} .quick-stats {{ grid-template-columns: repeat(3, 1fr); }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>📊 Stock Scanner Command Center</h1>
                <div class="timestamp">Last scan: {timestamp}</div>
            </div>
            <div class="status">
                <span class="status-badge status-live">● Data Live</span>
                <span class="status-badge status-market">Auto-updates every 6h</span>
            </div>
        </div>
        
        <div class="quick-stats">
            <div class="stat-card">
                <div class="stat-value" style="color:#3fb950">{len(actionable)}</div>
                <div class="stat-label">🎯 Actionable Now</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#00d4ff">{len(wma_zone)}</div>
                <div class="stat-label">🧠 200-WMA Zone</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#ff6b6b">{len(vcps)}</div>
                <div class="stat-label">⭐ VCPs</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#d29922">{len(watchlist)}</div>
                <div class="stat-label">👀 Watch List</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#a371f7">{len(UNIVERSE)}</div>
                <div class="stat-label">📊 Total Universe</div>
            </div>
        </div>
        
        <div class="main-grid">
            <div class="tables-column">
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">🎯 ACTIONABLE NOW <span class="section-count">{len(actionable)} setups</span></div>
                    </div>
                    <div class="section-body">
                        <table>
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th>Signal</th>
                                    <th>Score</th>
                                    <th>Price</th>
                                    <th>Entry</th>
                                    <th>Stop</th>
                                    <th>Target</th>
                                    <th>200-WMA</th>
                                    <th>Munger</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
{actionable_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">👀 WATCH LIST <span class="section-count">{len(watchlist[:30])} stocks</span></div>
                    </div>
                    <div class="section-body">
                        <table>
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th>Signal</th>
                                    <th>Score</th>
                                    <th>Price</th>
                                    <th>Entry</th>
                                    <th>Stop</th>
                                    <th>Target</th>
                                    <th>200-WMA</th>
                                    <th>Munger</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
{watchlist_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="chart-panel">
                <div class="chart-container">
                    <div class="chart-header">
                        <span class="chart-ticker" id="chart-ticker">NVDA</span>
                        <span class="chart-price" id="chart-price">$185.41</span>
                    </div>
                    <div class="tradingview-widget-container" id="tv-chart"></div>
                    <div class="trade-box" id="trade-box">
                        <h4>📊 Trade Setup</h4>
                        <div class="trade-row"><span class="trade-label">Entry:</span><span class="trade-value entry" id="trade-entry">$186.00</span></div>
                        <div class="trade-row"><span class="trade-label">Stop Loss:</span><span class="trade-value stop" id="trade-stop">$170.00</span></div>
                        <div class="trade-row"><span class="trade-label">Target:</span><span class="trade-value target" id="trade-target">$222.00</span></div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            Stock Scanner Command Center • Auto-updates every 6 hours • Top 200 S&P 500 stocks
        </div>
    </div>
    
    <script>
        const stockData = {{
            {stock_data_js}
        }};
        
        function loadChart(ticker) {{
            document.getElementById('chart-ticker').textContent = ticker;
            const data = stockData[ticker] || stockData['NVDA'];
            document.getElementById('chart-price').textContent = '$' + data.price.toFixed(2);
            document.getElementById('trade-entry').textContent = '$' + data.entry.toFixed(2);
            document.getElementById('trade-stop').textContent = '$' + data.stop.toFixed(0);
            document.getElementById('trade-target').textContent = '$' + data.target.toFixed(0);
            
            document.getElementById('tv-chart').innerHTML = '';
            new TradingView.widget({{
                "container_id": "tv-chart",
                "symbol": ticker,
                "interval": "D",
                "timezone": "America/New_York",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "toolbar_bg": "#1e222d",
                "enable_publishing": false,
                "hide_top_toolbar": true,
                "hide_legend": true,
                "save_image": false,
                "height": 350,
                "width": "100%"
            }});
        }}
        
        // Load TradingView widget script
        var script = document.createElement('script');
        script.src = 'https://s3.tradingview.com/tv.js';
        script.onload = function() {{ loadChart('NVDA'); }};
        document.head.appendChild(script);
    </script>
</body>
</html>'''
    
    return html


def main():
    print(f"\n{'='*60}")
    print(f"📊 GENERATING STOCK SCANNER SITE")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")
    
    print(f"Scanning {len(UNIVERSE)} stocks...")
    
    results = []
    for i, ticker in enumerate(UNIVERSE):
        sys.stdout.write(f"\r  {ticker}... ({i+1}/{len(UNIVERSE)})")
        sys.stdout.flush()
        r = scan_stock(ticker)
        if r:
            results.append(r)
    
    print(f"\r\n✓ Scanned {len(results)} stocks successfully\n")
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # Generate HTML
    html = generate_html(results)
    
    # Write to file
    output_path = os.path.join(SCRIPT_DIR, 'index.html')
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✓ Generated index.html")
    
    # Git commit and push
    try:
        os.chdir(SCRIPT_DIR)
        subprocess.run(['git', 'add', 'index.html'], check=True)
        subprocess.run(['git', 'commit', '-m', f'Auto-update scan {datetime.now().strftime("%Y-%m-%d %H:%M")}'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print(f"✓ Pushed to GitHub\n")
    except subprocess.CalledProcessError as e:
        print(f"⚠ Git push failed: {e}\n")
    
    # Summary
    actionable = [r for r in results if r['signal_type'] in ['BREAKOUT', 'VCP', 'AT PIVOT', '200-WMA'] and r['score'] >= 70]
    print(f"{'='*60}")
    print(f"SUMMARY:")
    print(f"  Total stocks: {len(results)}")
    print(f"  Actionable: {len(actionable)}")
    print(f"  Top 3: {', '.join([r['ticker'] for r in results[:3]])}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
