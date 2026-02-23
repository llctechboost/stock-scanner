#!/usr/bin/env python3
"""
Enhanced Stock Scanner - Generates comprehensive market analysis dashboard

Integrates:
- Original scanner functionality (squeeze, VCP, cup & handle)
- Sector & Industry Analysis with heatmap
- Timeframe Continuity (Strat style)
- Market Breadth Dashboard
- Actionable Summaries

Run: python generate_site_enhanced.py
"""
import os
import sys
import json
from datetime import datetime

# Import from original generate_site
from generate_site import (
    UNIVERSE, scan_stock, main as scanner_main
)

# Import market outlook
from market_outlook import (
    run_market_outlook, get_vix_info, get_spy_levels,
    calculate_breadth_metrics, load_sector_cache, save_sector_cache,
    get_stock_sector_info, normalize_sector, get_timeframe_scenarios,
    download_with_cache
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def generate_enhanced_html(scan_results, outlook_data):
    """Generate enhanced HTML with all dashboard sections."""
    
    timestamp = datetime.now().strftime("%B %d, %Y • %I:%M %p EST")
    
    # Extract data
    sectors = outlook_data.get('sectors', {})
    breadth = outlook_data.get('breadth', {})
    vix = outlook_data.get('vix', {})
    spy = outlook_data.get('spy', {})
    stocks = outlook_data.get('stocks', [])
    summary = outlook_data.get('summary', {})
    full_continuity = outlook_data.get('full_continuity', {})
    top_setups = outlook_data.get('top_setups', [])
    
    # Categorize scan results (from original)
    actionable = [r for r in scan_results if r['is_actionable']]
    wma_zone = [r for r in scan_results if r['in_wma_zone']]
    vcps = [r for r in scan_results if r['is_vcp']]
    cup_handles = [r for r in scan_results if r.get('is_cup_handle', False)]
    high_squeeze = [r for r in scan_results if r.get('is_high_squeeze', False)]
    daily_squeeze = [r for r in scan_results if r.get('is_daily_high_squeeze', False)]
    weekly_squeeze = [r for r in scan_results if r.get('is_weekly_high_squeeze', False)]
    watchlist = [r for r in scan_results if r['is_watchlist']]
    
    # Sort
    actionable.sort(key=lambda x: x['score'], reverse=True)
    scan_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Overall market bias
    total_bullish = summary.get('bullish_count', 0)
    total_stocks = summary.get('total_stocks', 1)
    bullish_pct = (total_bullish / total_stocks) * 100 if total_stocks > 0 else 50
    
    if bullish_pct >= 60 and vix.get('label', '') not in ('HIGH', 'EXTREME'):
        overall_bias = 'BULLISH'
        bias_color = '#22c55e'
    elif bullish_pct >= 45:
        overall_bias = 'NEUTRAL'
        bias_color = '#eab308'
    else:
        overall_bias = 'BEARISH'
        bias_color = '#ef4444'
    
    # Build sector heatmap HTML
    sorted_sectors = sorted(sectors.values(), key=lambda x: x.get('bullish_pct', 0), reverse=True)
    
    sector_cards_html = ''
    for sec in sorted_sectors:
        bp = sec.get('bullish_pct', 50)
        if bp >= 65:
            color = '#22c55e'
        elif bp >= 50:
            color = '#84cc16'
        elif bp >= 35:
            color = '#eab308'
        elif bp >= 20:
            color = '#f97316'
        else:
            color = '#ef4444'
        
        sector_cards_html += f'''
            <div class="sector-card" style="border-left-color: {color};">
                <div class="sector-name">{sec.get('sector', 'Unknown')}</div>
                <div class="sector-bullish" style="color: {color};">{bp:.0f}% bullish</div>
                <div class="sector-info">{sec.get('weekly_squeeze_count', 0)}W / {sec.get('daily_squeeze_count', 0)}D squeeze</div>
                <div class="sector-perf">1M: {sec.get('avg_perf_1m', 0):+.1f}%</div>
            </div>
        '''
    
    # Full continuity lists
    bullish_cont_tickers = full_continuity.get('bullish', [])[:20]
    bearish_cont_tickers = full_continuity.get('bearish', [])[:20]
    
    bullish_cont_html = ', '.join([f'<span class="cont-ticker" onclick="loadChart(\'{t}\')">{t}</span>' for t in bullish_cont_tickers]) if bullish_cont_tickers else 'None'
    bearish_cont_html = ', '.join([f'<span class="cont-ticker" onclick="loadChart(\'{t}\')">{t}</span>' for t in bearish_cont_tickers]) if bearish_cont_tickers else 'None'
    
    # Top setups list
    top_setups_html = ''
    for i, s in enumerate(top_setups[:10], 1):
        setup_tags = []
        if s.get('weekly_squeeze_on'):
            setup_tags.append('WSQ')
        if s.get('daily_squeeze_on'):
            setup_tags.append('DSQ')
        if s.get('full_continuity'):
            setup_tags.append(f"FC-{s.get('continuity_direction', '?')[:1]}")
        
        tags_str = ' | '.join(setup_tags) if setup_tags else '-'
        top_setups_html += f'''
            <div class="setup-item" onclick="loadChart('{s.get('ticker', '')}')">
                <span class="setup-rank">{i}</span>
                <span class="setup-ticker">{s.get('ticker', '')}</span>
                <span class="setup-tags">{tags_str}</span>
                <span class="setup-sector">{s.get('sector', '')}</span>
                <span class="setup-perf">{s.get('perf_3m', 0):+.1f}%</span>
            </div>
        '''
    
    # Generate stock table rows (from original)
    def make_row(s):
        score_class = 'score-a' if s['score'] >= 80 else 'score-b' if s['score'] >= 60 else 'score-c'
        tag_class = {
            'BREAKOUT': 'tag-breakout', 'VCP': 'tag-vcp', 'AT PIVOT': 'tag-pivot',
            '200-WMA': 'tag-200wma', 'WATCH': 'tag-forming', 'CUP & HANDLE': 'tag-cup'
        }.get(s['signal_type'], 'tag-forming')
        
        wma_display = f"+{s['wma_pct']:.0f}%" if s['wma_pct'] > 0 else f"{s['wma_pct']:.0f}%"
        wma_class = 'cyan' if s['in_wma_zone'] else ''
        
        signal_display = s['signal_type']
        if s['signal_type'] == 'VCP' and s['vcp_score'] >= 8:
            signal_display = 'VCP ⭐'
        elif s['signal_type'] == '200-WMA':
            signal_display = '200-WMA 🧠'
        elif s['signal_type'] == 'CUP & HANDLE':
            signal_display = 'CUP & HANDLE ☕'
        
        action = 'BUY' if s['score'] >= 70 else 'WATCH'
        action_class = 'action-buy' if action == 'BUY' else 'action-watch'
        
        cats = []
        if s['is_actionable']: cats.append('actionable')
        if s['in_wma_zone']: cats.append('wma')
        if s['is_vcp']: cats.append('vcp')
        if s.get('is_cup_handle', False): cats.append('cup')
        if s.get('is_high_squeeze', False): cats.append('squeeze')
        if s.get('is_daily_high_squeeze', False): cats.append('squeeze_daily')
        if s.get('is_weekly_high_squeeze', False): cats.append('squeeze_weekly')
        if s['is_watchlist']: cats.append('watchlist')
        cats.append('all')
        
        row_class = 'actionable' if s['is_actionable'] and s['signal_type'] not in ['200-WMA'] else ''
        if s['in_wma_zone']: row_class = 'wma-buy-zone'
        if s.get('is_cup_handle', False): row_class = 'cup-handle'
        if s.get('is_high_squeeze', False): row_class = 'high-squeeze'
        
        return f'''<tr class="stock-row {row_class}" data-categories="{' '.join(cats)}" data-ticker="{s['ticker']}" data-score="{s['score']}" onclick="loadChart('{s['ticker']}')">
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
    
    all_rows = '\n'.join([make_row(s) for s in scan_results])
    
    # Stock data for charts (from original)
    stock_data_js = ',\n            '.join([
        f"'{s['ticker']}': {{ price: {s['price']:.2f}, entry: {s['entry']:.2f}, stop: {s['stop']:.0f}, target: {s['target']:.0f}, pattern: '{s['signal_type']}', vcp: {s['vcp_score']}, rs: '{s['perf_3m']:+.0f}%', high: '{s['pct_from_high']:.1f}%', wma: '{s['wma_pct']:+.0f}%', munger: '{s['munger']}', dailySq: {s.get('daily_squeeze_score', 0)}, weeklySq: {s.get('weekly_squeeze_score', 0)} }}"
        for s in scan_results
    ])
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Market Analysis Command Center</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; }}
        .container {{ max-width: 1800px; margin: 0 auto; padding: 15px; }}
        
        /* Header */
        .header {{ display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; background: linear-gradient(90deg, rgba(88,166,255,0.1), rgba(163,113,247,0.1)); border-radius: 12px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.1); }}
        .header h1 {{ font-size: 1.6em; background: linear-gradient(90deg, #58a6ff, #a371f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header .timestamp {{ color: #8b949e; font-size: 0.85em; }}
        .status {{ display: flex; gap: 15px; align-items: center; }}
        .status-badge {{ padding: 5px 12px; border-radius: 20px; font-size: 0.8em; font-weight: 600; }}
        .status-live {{ background: rgba(63,185,80,0.2); color: #3fb950; }}
        .market-bias {{ background: {bias_color}33; color: {bias_color}; padding: 5px 15px; border-radius: 20px; font-weight: 700; }}
        
        /* Market Overview Banner */
        .market-overview {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 15px; margin-bottom: 20px; }}
        .overview-card {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 15px; text-align: center; border: 1px solid rgba(255,255,255,0.08); }}
        .overview-label {{ color: #8b949e; font-size: 0.75em; margin-bottom: 5px; }}
        .overview-value {{ font-size: 1.4em; font-weight: 700; }}
        .overview-value.positive {{ color: #3fb950; }}
        .overview-value.negative {{ color: #f85149; }}
        .overview-value.neutral {{ color: #eab308; }}
        .overview-sub {{ font-size: 0.75em; color: #8b949e; margin-top: 3px; }}
        
        /* Sector Heatmap */
        .sector-section {{ margin-bottom: 20px; }}
        .section-title {{ font-size: 1.1em; font-weight: 600; margin-bottom: 12px; color: #e6edf3; }}
        .sector-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }}
        .sector-card {{ background: rgba(255,255,255,0.03); border-radius: 8px; padding: 12px; border-left: 4px solid #666; }}
        .sector-name {{ font-weight: 600; font-size: 0.9em; margin-bottom: 4px; }}
        .sector-bullish {{ font-size: 1.1em; font-weight: 700; }}
        .sector-info {{ font-size: 0.75em; color: #8b949e; margin-top: 4px; }}
        .sector-perf {{ font-size: 0.75em; color: #8b949e; }}
        
        /* Continuity Section */
        .continuity-section {{ background: rgba(255,255,255,0.02); border-radius: 12px; padding: 15px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.08); }}
        .cont-row {{ display: flex; align-items: flex-start; margin: 10px 0; }}
        .cont-label {{ font-weight: 600; min-width: 100px; }}
        .cont-label.bullish {{ color: #22c55e; }}
        .cont-label.bearish {{ color: #ef4444; }}
        .cont-tickers {{ flex: 1; line-height: 1.8; }}
        .cont-ticker {{ display: inline-block; padding: 2px 8px; background: rgba(255,255,255,0.05); border-radius: 4px; margin: 2px 4px 2px 0; cursor: pointer; font-size: 0.85em; }}
        .cont-ticker:hover {{ background: rgba(88,166,255,0.2); }}
        
        /* Top Setups */
        .top-setups {{ background: rgba(255,255,255,0.02); border-radius: 12px; padding: 15px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.08); }}
        .setup-item {{ display: flex; align-items: center; padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); cursor: pointer; }}
        .setup-item:hover {{ background: rgba(255,255,255,0.05); }}
        .setup-rank {{ width: 25px; color: #8b949e; font-size: 0.85em; }}
        .setup-ticker {{ width: 70px; font-weight: 700; color: #58a6ff; }}
        .setup-tags {{ flex: 1; font-size: 0.8em; color: #a371f7; }}
        .setup-sector {{ width: 120px; font-size: 0.8em; color: #8b949e; }}
        .setup-perf {{ width: 60px; text-align: right; font-size: 0.85em; color: #3fb950; }}
        
        /* Quick Stats */
        .quick-stats {{ display: grid; grid-template-columns: repeat(8, 1fr); gap: 10px; margin-bottom: 20px; }}
        .stat-card {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 15px; text-align: center; border: 2px solid rgba(255,255,255,0.08); cursor: pointer; transition: all 0.2s; }}
        .stat-card:hover {{ border-color: rgba(255,255,255,0.3); transform: translateY(-2px); }}
        .stat-card.active {{ border-color: #58a6ff; background: rgba(88,166,255,0.1); }}
        .stat-value {{ font-size: 1.8em; font-weight: 700; }}
        .stat-label {{ color: #8b949e; font-size: 0.75em; margin-top: 5px; }}
        
        /* Main Grid */
        .main-grid {{ display: grid; grid-template-columns: 1fr 420px; gap: 20px; }}
        .section {{ background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); overflow: hidden; }}
        .section-header {{ padding: 12px 16px; background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; justify-content: space-between; align-items: center; }}
        .section-header .section-title {{ margin-bottom: 0; }}
        .section-count {{ background: rgba(88,166,255,0.2); color: #58a6ff; padding: 2px 10px; border-radius: 12px; font-size: 0.75em; }}
        .section-body {{ padding: 0; max-height: 600px; overflow-y: auto; }}
        
        /* Table Styles */
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
        th {{ padding: 10px 12px; text-align: left; font-weight: 600; color: #8b949e; font-size: 0.7em; text-transform: uppercase; background: rgba(255,255,255,0.02); position: sticky; top: 0; z-index: 1; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        tr.stock-row {{ cursor: pointer; }}
        tr.stock-row:hover {{ background: rgba(255,255,255,0.05); }}
        tr.stock-row.actionable {{ background: rgba(63,185,80,0.08); }}
        tr.stock-row.wma-buy-zone {{ background: rgba(0,212,255,0.08); }}
        tr.stock-row.cup-handle {{ background: rgba(255,165,0,0.12); }}
        tr.stock-row.high-squeeze {{ background: rgba(255,0,255,0.12); }}
        tr.stock-row.hidden {{ display: none; }}
        
        .ticker {{ font-weight: 700; color: #e6edf3; }}
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
        .tag-cup {{ background: rgba(255,165,0,0.2); color: #ffa500; }}
        
        .action-badge {{ padding: 4px 10px; border-radius: 4px; font-size: 0.75em; font-weight: 700; }}
        .action-buy {{ background: #238636; color: #fff; }}
        .action-watch {{ background: rgba(210,153,34,0.2); color: #d29922; }}
        .munger-stars {{ color: #ffc107; }}
        
        /* Chart Panel */
        .chart-panel {{ position: sticky; top: 15px; }}
        .chart-container {{ background: #1e222d; border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); }}
        .chart-header {{ padding: 10px 15px; background: rgba(255,255,255,0.03); display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.08); }}
        .chart-ticker {{ font-weight: 700; font-size: 1.1em; color: #58a6ff; }}
        .chart-price {{ color: #3fb950; font-weight: 600; }}
        .tradingview-widget-container {{ height: 400px; }}
        
        .trade-box {{ margin: 15px; padding: 15px; background: rgba(63,185,80,0.1); border-radius: 8px; border: 1px solid rgba(63,185,80,0.2); }}
        .trade-box h4 {{ color: #3fb950; margin-bottom: 10px; font-size: 0.9em; }}
        .trade-row {{ display: flex; justify-content: space-between; margin: 8px 0; }}
        .trade-label {{ color: #8b949e; font-size: 0.85em; }}
        .trade-value {{ font-weight: 700; font-size: 0.95em; }}
        .trade-value.entry {{ color: #3fb950; }}
        .trade-value.stop {{ color: #f85149; }}
        .trade-value.target {{ color: #58a6ff; }}
        
        .tv-button {{ display: block; margin: 15px; padding: 12px 20px; background: linear-gradient(90deg, #2962FF, #2979FF); color: #fff; text-align: center; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 0.9em; transition: all 0.2s; }}
        .tv-button:hover {{ background: linear-gradient(90deg, #1E88E5, #2196F3); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(41,98,255,0.3); }}
        
        .stock-details {{ padding: 15px; border-top: 1px solid rgba(255,255,255,0.08); }}
        .detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
        .detail-item {{ display: flex; justify-content: space-between; }}
        .detail-label {{ color: #8b949e; font-size: 0.8em; }}
        .detail-value {{ font-weight: 600; font-size: 0.85em; }}
        
        .footer {{ text-align: center; padding: 20px; color: #6e7681; font-size: 0.8em; margin-top: 20px; }}
        
        /* Responsive */
        @media (max-width: 1400px) {{
            .quick-stats {{ grid-template-columns: repeat(4, 1fr); }}
            .market-overview {{ grid-template-columns: repeat(3, 1fr); }}
        }}
        @media (max-width: 1200px) {{
            .main-grid {{ grid-template-columns: 1fr; }}
            .chart-panel {{ position: static; }}
        }}
        @media (max-width: 800px) {{
            .quick-stats {{ grid-template-columns: repeat(2, 1fr); }}
            .market-overview {{ grid-template-columns: repeat(2, 1fr); }}
            .sector-grid {{ grid-template-columns: 1fr 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div>
                <h1>📊 Market Analysis Command Center</h1>
                <div class="timestamp">Last scan: {timestamp}</div>
            </div>
            <div class="status">
                <span class="market-bias">{overall_bias}</span>
                <span class="status-badge status-live">● Data Live</span>
            </div>
        </div>
        
        <!-- Market Overview Banner -->
        <div class="market-overview">
            <div class="overview-card">
                <div class="overview-label">VIX Level</div>
                <div class="overview-value {'negative' if vix.get('level', 20) > 25 else 'positive' if vix.get('level', 20) < 18 else 'neutral'}">{vix.get('level', 0):.1f}</div>
                <div class="overview-sub">{vix.get('label', 'N/A')} | {vix.get('trend', 'N/A')}</div>
            </div>
            <div class="overview-card">
                <div class="overview-label">SPY</div>
                <div class="overview-value">${spy.get('price', 0):.2f}</div>
                <div class="overview-sub">{spy.get('pct_from_high', 0):+.1f}% from high</div>
            </div>
            <div class="overview-card">
                <div class="overview-label">A/D Ratio</div>
                <div class="overview-value {'positive' if breadth.get('ad_ratio', 1) > 1.2 else 'negative' if breadth.get('ad_ratio', 1) < 0.8 else 'neutral'}">{breadth.get('ad_ratio', 1):.2f}</div>
                <div class="overview-sub">{breadth.get('advancing', 0)}↑ / {breadth.get('declining', 0)}↓</div>
            </div>
            <div class="overview-card">
                <div class="overview-label">Above 50MA</div>
                <div class="overview-value {'positive' if breadth.get('pct_above_50sma', 50) > 60 else 'negative' if breadth.get('pct_above_50sma', 50) < 40 else 'neutral'}">{breadth.get('pct_above_50sma', 0):.0f}%</div>
                <div class="overview-sub">of S&P 500</div>
            </div>
            <div class="overview-card">
                <div class="overview-label">New Highs/Lows</div>
                <div class="overview-value">{breadth.get('new_highs', 0)}/{breadth.get('new_lows', 0)}</div>
                <div class="overview-sub">Ratio: {breadth.get('hl_ratio', 1):.1f}</div>
            </div>
            <div class="overview-card">
                <div class="overview-label">Continuity</div>
                <div class="overview-value positive">{len(bullish_cont_tickers)}</div>
                <div class="overview-sub">Full Bullish Cont.</div>
            </div>
        </div>
        
        <!-- Sector Heatmap -->
        <div class="sector-section">
            <div class="section-title">🔥 Sector Rotation Heatmap</div>
            <div class="sector-grid">
                {sector_cards_html}
            </div>
        </div>
        
        <!-- Timeframe Continuity -->
        <div class="continuity-section">
            <div class="section-title">🎯 Full Timeframe Continuity (Monthly + Weekly + Daily Aligned)</div>
            <div class="cont-row">
                <span class="cont-label bullish">🟢 BULLISH:</span>
                <div class="cont-tickers">{bullish_cont_html}</div>
            </div>
            <div class="cont-row">
                <span class="cont-label bearish">🔴 BEARISH:</span>
                <div class="cont-tickers">{bearish_cont_html}</div>
            </div>
        </div>
        
        <!-- Top Setups -->
        <div class="top-setups">
            <div class="section-title">⚡ Top Setups (Continuity + Squeeze)</div>
            {top_setups_html}
        </div>
        
        <!-- Quick Stats (Original) -->
        <div class="quick-stats">
            <div class="stat-card active" data-filter="actionable" onclick="filterStocks('actionable')">
                <div class="stat-value" style="color:#3fb950">{len(actionable)}</div>
                <div class="stat-label">🎯 Actionable</div>
            </div>
            <div class="stat-card" data-filter="squeeze_weekly" onclick="filterStocks('squeeze_weekly')">
                <div class="stat-value" style="color:#ff00ff">{len(weekly_squeeze)}</div>
                <div class="stat-label">🔥 Weekly Sq</div>
            </div>
            <div class="stat-card" data-filter="squeeze_daily" onclick="filterStocks('squeeze_daily')">
                <div class="stat-value" style="color:#ff66ff">{len(daily_squeeze)}</div>
                <div class="stat-label">⚡ Daily Sq</div>
            </div>
            <div class="stat-card" data-filter="cup" onclick="filterStocks('cup')">
                <div class="stat-value" style="color:#ffa500">{len(cup_handles)}</div>
                <div class="stat-label">☕ Cup & Handle</div>
            </div>
            <div class="stat-card" data-filter="vcp" onclick="filterStocks('vcp')">
                <div class="stat-value" style="color:#ff6b6b">{len(vcps)}</div>
                <div class="stat-label">⭐ VCPs</div>
            </div>
            <div class="stat-card" data-filter="wma" onclick="filterStocks('wma')">
                <div class="stat-value" style="color:#00d4ff">{len(wma_zone)}</div>
                <div class="stat-label">🧠 200-WMA</div>
            </div>
            <div class="stat-card" data-filter="watchlist" onclick="filterStocks('watchlist')">
                <div class="stat-value" style="color:#d29922">{len(watchlist)}</div>
                <div class="stat-label">👀 Watch</div>
            </div>
            <div class="stat-card" data-filter="all" onclick="filterStocks('all')">
                <div class="stat-value" style="color:#a371f7">{len(scan_results)}</div>
                <div class="stat-label">📊 All</div>
            </div>
        </div>
        
        <!-- Main Grid -->
        <div class="main-grid">
            <div class="tables-column">
                <div class="section">
                    <div class="section-header">
                        <div class="section-title" id="section-title">🎯 ACTIONABLE NOW</div>
                        <span class="section-count" id="section-count">{len(actionable)} stocks</span>
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
                            <tbody id="stocks-table">
{all_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <!-- Chart Panel -->
            <div class="chart-panel">
                <div class="chart-container">
                    <div class="chart-header">
                        <span class="chart-ticker" id="chart-ticker">Select a stock</span>
                        <span class="chart-price" id="chart-price">—</span>
                    </div>
                    <div class="tradingview-widget-container" id="tv-chart">
                        <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#8b949e;">
                            Click a stock to view chart
                        </div>
                    </div>
                    <div class="trade-box" id="trade-box" style="display:none;">
                        <h4>📊 Trade Setup</h4>
                        <div class="trade-row"><span class="trade-label">Entry:</span><span class="trade-value entry" id="trade-entry">—</span></div>
                        <div class="trade-row"><span class="trade-label">Stop Loss:</span><span class="trade-value stop" id="trade-stop">—</span></div>
                        <div class="trade-row"><span class="trade-label">Target:</span><span class="trade-value target" id="trade-target">—</span></div>
                    </div>
                    <div class="stock-details" id="stock-details" style="display:none;">
                        <div class="detail-grid">
                            <div class="detail-item"><span class="detail-label">Pattern:</span><span class="detail-value" id="detail-pattern">—</span></div>
                            <div class="detail-item"><span class="detail-label">RS:</span><span class="detail-value" id="detail-rs">—</span></div>
                            <div class="detail-item"><span class="detail-label">From High:</span><span class="detail-value" id="detail-high">—</span></div>
                            <div class="detail-item"><span class="detail-label">200-WMA:</span><span class="detail-value" id="detail-wma">—</span></div>
                        </div>
                    </div>
                    <a href="#" id="tv-link" class="tv-button" target="_blank" style="display:none;">Open in TradingView</a>
                </div>
            </div>
        </div>
        
        <div class="footer">
            Market Analysis Command Center • S&P 500 • {timestamp}
        </div>
    </div>
    
    <script src="https://s3.tradingview.com/tv.js"></script>
    <script>
        const stockData = {{
            {stock_data_js}
        }};
        
        const filterLabels = {{
            'actionable': '🎯 ACTIONABLE NOW',
            'squeeze_weekly': '🔥 WEEKLY SQUEEZE',
            'squeeze_daily': '⚡ DAILY SQUEEZE',
            'cup': '☕ CUP & HANDLE',
            'wma': '🧠 200-WMA ZONE',
            'vcp': '⭐ VCP PATTERNS',
            'watchlist': '👀 WATCH LIST',
            'all': '📊 ALL STOCKS'
        }};
        
        let currentFilter = 'actionable';
        
        function filterStocks(category) {{
            currentFilter = category;
            const rows = Array.from(document.querySelectorAll('.stock-row'));
            let visibleCount = 0;
            
            rows.forEach(row => {{
                const cats = row.dataset.categories.split(' ');
                if (cats.includes(category)) {{
                    row.classList.remove('hidden');
                    visibleCount++;
                }} else {{
                    row.classList.add('hidden');
                }}
            }});
            
            document.querySelectorAll('.stat-card').forEach(card => {{
                card.classList.remove('active');
                if (card.dataset.filter === category) card.classList.add('active');
            }});
            
            document.getElementById('section-title').textContent = filterLabels[category];
            document.getElementById('section-count').textContent = visibleCount + ' stocks';
        }}
        
        function loadChart(ticker) {{
            const data = stockData[ticker];
            if (!data) return;
            
            document.getElementById('chart-ticker').textContent = ticker;
            document.getElementById('chart-price').textContent = '$' + data.price.toFixed(2);
            document.getElementById('trade-entry').textContent = '$' + data.entry.toFixed(2);
            document.getElementById('trade-stop').textContent = '$' + data.stop.toFixed(0);
            document.getElementById('trade-target').textContent = '$' + data.target.toFixed(0);
            document.getElementById('detail-pattern').textContent = data.pattern;
            document.getElementById('detail-rs').textContent = data.rs;
            document.getElementById('detail-high').textContent = data.high;
            document.getElementById('detail-wma').textContent = data.wma;
            
            document.getElementById('trade-box').style.display = 'block';
            document.getElementById('stock-details').style.display = 'block';
            
            const tvLink = document.getElementById('tv-link');
            tvLink.style.display = 'block';
            tvLink.href = 'https://www.tradingview.com/chart/?symbol=' + ticker;
            
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
                "save_image": false,
                "height": 400,
                "width": "100%"
            }});
            
            document.querySelectorAll('.stock-row').forEach(r => r.style.outline = 'none');
            const selectedRow = document.querySelector(`[data-ticker="${{ticker}}"]`);
            if (selectedRow) {{
                selectedRow.style.outline = '2px solid #58a6ff';
                selectedRow.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
            }}
        }}
        
        filterStocks('actionable');
    </script>
</body>
</html>'''
    
    return html


def main():
    """Run enhanced scanner with market outlook."""
    print("=" * 60)
    print("  📊 ENHANCED MARKET ANALYSIS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Run market outlook analysis
    print("\n🔍 Running market outlook analysis...")
    outlook_data, _ = run_market_outlook(quick_mode=False)
    
    # Run original scanner
    print("\n🔍 Running pattern scanner...")
    from generate_site import main as scanner_main, UNIVERSE, scan_stock
    
    scan_results = []
    for i, ticker in enumerate(UNIVERSE):
        result = scan_stock(ticker)
        if result:
            scan_results.append(result)
        if (i + 1) % 50 == 0:
            print(f"  Scanned {i + 1}/{len(UNIVERSE)} stocks...")
    
    print(f"✅ Scanned {len(scan_results)} stocks")
    
    # Generate enhanced HTML
    print("\n📝 Generating enhanced dashboard...")
    html = generate_enhanced_html(scan_results, outlook_data)
    
    # Save HTML
    output_path = os.path.join(SCRIPT_DIR, 'index.html')
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✅ Generated {output_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("  📊 SUMMARY")
    print("=" * 60)
    
    summary = outlook_data.get('summary', {})
    print(f"  Total Stocks: {summary.get('total_stocks', 0)}")
    print(f"  Bullish: {summary.get('bullish_count', 0)}")
    print(f"  Bearish: {summary.get('bearish_count', 0)}")
    print(f"  Daily Squeeze: {summary.get('in_daily_squeeze', 0)}")
    print(f"  Weekly Squeeze: {summary.get('in_weekly_squeeze', 0)}")
    print(f"  Full Continuity Bullish: {summary.get('full_continuity_bullish', 0)}")
    print(f"  Full Continuity Bearish: {summary.get('full_continuity_bearish', 0)}")
    
    return scan_results, outlook_data


if __name__ == '__main__':
    main()
