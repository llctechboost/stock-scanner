#!/usr/bin/env python3
"""
Stock Scanner Dashboard (Port 5000)
CANSLIM stock analysis with market timing, breakouts, bases, and pocket pivots.
Dark theme, auto-refresh, mobile responsive.
"""
from flask import Flask, render_template_string, jsonify, request
import json
import glob
import os
from datetime import datetime

app = Flask(__name__)
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📊 Stock Scanner Dashboard</title>
<meta http-equiv="refresh" content="60">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #fff; padding: 20px; min-height: 100vh; }
a { color: #00ff88; text-decoration: none; }
a:hover { text-decoration: underline; }

/* Header */
.header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; border-bottom: 1px solid #222; padding-bottom: 16px; }
.header h1 { color: #00ff88; font-size: 1.8em; }
.header .meta { color: #888; font-size: 0.85em; }
.header .meta span { color: #00ff88; }

/* Market Timing Panel */
.market-panel { background: #111; border: 1px solid #222; border-radius: 12px; padding: 20px; margin-bottom: 24px; }
.market-panel h2 { color: #00ff88; font-size: 1.2em; margin-bottom: 14px; }
.market-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }
.market-card { background: #1a1a1a; border-radius: 8px; padding: 14px; text-align: center; }
.market-card .label { color: #888; font-size: 0.8em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.market-card .value { font-size: 1.4em; font-weight: 700; }
.market-card .value.green { color: #00ff88; }
.market-card .value.red { color: #ff4444; }
.market-card .value.yellow { color: #ffaa44; }
.market-card .sub { color: #666; font-size: 0.75em; margin-top: 4px; }

/* Signal light */
.signal-light { display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.signal-light.green-light { background: #00ff88; box-shadow: 0 0 8px #00ff88; }
.signal-light.yellow-light { background: #ffaa44; box-shadow: 0 0 8px #ffaa44; }
.signal-light.red-light { background: #ff4444; box-shadow: 0 0 8px #ff4444; }

/* Filters */
.filters { background: #111; border: 1px solid #222; border-radius: 12px; padding: 16px; margin-bottom: 24px; display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
.filter-group { display: flex; flex-direction: column; gap: 4px; }
.filter-group label { color: #888; font-size: 0.75em; text-transform: uppercase; letter-spacing: 1px; }
.filter-group select, .filter-group input[type=range] { background: #1a1a1a; color: #fff; border: 1px solid #333; border-radius: 6px; padding: 6px 10px; font-size: 0.9em; }
.filter-group select { min-width: 150px; }
.filter-group input[type=range] { width: 160px; accent-color: #00ff88; }
.filter-group .range-val { color: #00ff88; font-size: 0.85em; font-weight: 600; }
.checkbox-group { display: flex; flex-wrap: wrap; gap: 10px; }
.checkbox-group label { color: #ccc; font-size: 0.85em; cursor: pointer; display: flex; align-items: center; gap: 4px; }
.checkbox-group input[type=checkbox] { accent-color: #00ff88; }

/* Section */
.section { margin-bottom: 32px; }
.section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.section-header h2 { font-size: 1.3em; }
.section-header .count { background: #00ff88; color: #0a0a0a; font-size: 0.75em; font-weight: 700; padding: 2px 8px; border-radius: 10px; }
.section-header.breakout h2 { color: #ff4444; }
.section-header.breakout .count { background: #ff4444; color: #fff; }
.section-header.base h2 { color: #ffaa44; }
.section-header.base .count { background: #ffaa44; color: #0a0a0a; }
.section-header.pivot h2 { color: #44aaff; }
.section-header.pivot .count { background: #44aaff; color: #0a0a0a; }

/* Stock Cards Grid */
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }
.card { background: #1a1a1a; border: 1px solid #222; border-radius: 10px; padding: 16px; transition: border-color 0.2s, transform 0.15s; }
.card:hover { border-color: #00ff88; transform: translateY(-2px); }
.card .top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.card .ticker { font-size: 1.3em; font-weight: 700; color: #00ff88; }
.card .score { font-size: 1em; font-weight: 700; padding: 3px 10px; border-radius: 6px; }
.card .score.high { background: #00ff8822; color: #00ff88; }
.card .score.mid { background: #ffaa4422; color: #ffaa44; }
.card .score.low { background: #ff444422; color: #ff4444; }
.card .price-row { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; font-size: 0.9em; }
.card .price-row span { color: #ccc; }
.card .price-row strong { color: #fff; }
.card .patterns { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.card .pattern-tag { background: #222; color: #aaa; font-size: 0.75em; padding: 2px 8px; border-radius: 4px; }
.card .pattern-tag.cup { border-left: 3px solid #ff4444; }
.card .pattern-tag.flat { border-left: 3px solid #ffaa44; }
.card .pattern-tag.htf { border-left: 3px solid #ff66aa; }
.card .pattern-tag.ascending { border-left: 3px solid #ffaa44; }
.card .pattern-tag.pivot { border-left: 3px solid #44aaff; }
.card .fundamentals { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; font-size: 0.8em; }
.card .fundamentals .stat { text-align: center; padding: 4px; background: #111; border-radius: 4px; }
.card .fundamentals .stat .lbl { color: #666; font-size: 0.85em; }
.card .fundamentals .stat .val { color: #fff; font-weight: 600; }
.card .sector-tag { color: #666; font-size: 0.75em; margin-top: 6px; }

/* Empty state */
.empty { text-align: center; padding: 40px; color: #555; }
.empty .icon { font-size: 2.5em; margin-bottom: 8px; }

/* Footer */
.footer { text-align: center; color: #444; font-size: 0.75em; margin-top: 40px; padding-top: 16px; border-top: 1px solid #1a1a1a; }

/* Responsive */
@media (max-width: 768px) {
    body { padding: 10px; }
    .header h1 { font-size: 1.3em; }
    .cards { grid-template-columns: 1fr; }
    .market-grid { grid-template-columns: repeat(2, 1fr); }
    .filters { flex-direction: column; }
}
</style>
</head>
<body>
{% macro stock_card(stock) %}
<div class="card" data-ticker="{{ stock.ticker }}" data-sector="{{ stock.sector }}" data-score="{{ stock.score }}" data-patterns="{{ stock.pattern_keys|join(',') }}">
    <div class="top">
        <span class="ticker">{{ stock.ticker }}</span>
        <span class="score {{ 'high' if stock.score >= 9 else ('mid' if stock.score >= 6 else 'low') }}">{{ stock.score }}/12</span>
    </div>
    <div class="price-row">
        <span>Price: <strong>${{ "%.2f"|format(stock.price) }}</strong></span>
        {% if stock.buy_point %}<span>Buy: <strong>${{ "%.2f"|format(stock.buy_point) }}</strong></span>{% endif %}
        {% if stock.rs_rating %}<span>RS: <strong>{{ stock.rs_rating }}</strong></span>{% endif %}
    </div>
    <div class="patterns">
        {% for p in stock.patterns %}
        <span class="pattern-tag {{ p.cls }}">{{ p.name }}</span>
        {% endfor %}
    </div>
    <div class="fundamentals">
        <div class="stat"><div class="lbl">EPS Growth</div><div class="val">{{ stock.eps_growth }}</div></div>
        <div class="stat"><div class="lbl">ROE</div><div class="val">{{ stock.roe }}</div></div>
        <div class="stat"><div class="lbl">Volume</div><div class="val">{{ stock.volume_ratio }}</div></div>
    </div>
    {% if stock.sector %}<div class="sector-tag">{{ stock.sector }}</div>{% endif %}
</div>
{% endmacro %}

<div class="header">
    <h1>📊 Stock Scanner</h1>
    <div class="meta">
        Updated: <span>{{ timestamp }}</span> &nbsp;|&nbsp;
        Stocks scanned: <span>{{ total_stocks }}</span> &nbsp;|&nbsp;
        Results: <span>{{ total_results }}</span>
    </div>
</div>

<!-- Market Timing -->
<div class="market-panel">
    <h2>🎯 Market Timing</h2>
    <div class="market-grid">
        <div class="market-card">
            <div class="label">S&P 500 Trend</div>
            <div class="value {{ 'green' if market.sp500_trend == 'Uptrend' else ('red' if market.sp500_trend == 'Downtrend' else 'yellow') }}">
                {{ market.sp500_trend }}
            </div>
            <div class="sub">{{ market.sp500_detail }}</div>
        </div>
        <div class="market-card">
            <div class="label">VIX (Volatility)</div>
            <div class="value {{ 'green' if market.vix_level == 'Low' else ('yellow' if market.vix_level == 'Moderate' else 'red') }}">
                {{ market.vix_value }}
            </div>
            <div class="sub">{{ market.vix_level }}</div>
        </div>
        <div class="market-card">
            <div class="label">Distribution Days</div>
            <div class="value {{ 'green' if market.dist_days < 4 else ('yellow' if market.dist_days < 6 else 'red') }}">
                {{ market.dist_days }}
            </div>
            <div class="sub">of 25 trading days</div>
        </div>
        <div class="market-card">
            <div class="label">Overall Signal</div>
            <div class="value">
                <span class="signal-light {{ 'green-light' if market.signal == 'Green Light' else ('yellow-light' if market.signal == 'Caution' else 'red-light') }}"></span>
                {{ market.signal }}
            </div>
            <div class="sub">{{ market.recommendation }}</div>
        </div>
    </div>
</div>

<!-- Filters -->
<div class="filters">
    <div class="filter-group">
        <label>Sector</label>
        <select id="sectorFilter" onchange="applyFilters()">
            <option value="all">All Sectors</option>
            {% for s in sectors %}
            <option value="{{ s }}">{{ s }}</option>
            {% endfor %}
        </select>
    </div>
    <div class="filter-group">
        <label>Min Score: <span class="range-val" id="scoreVal">0</span>/12</label>
        <input type="range" id="scoreFilter" min="0" max="12" value="0" oninput="document.getElementById('scoreVal').textContent=this.value; applyFilters()">
    </div>
    <div class="filter-group">
        <label>Patterns</label>
        <div class="checkbox-group">
            <label><input type="checkbox" class="patternCb" value="cup" checked onchange="applyFilters()"> Cup & Handle</label>
            <label><input type="checkbox" class="patternCb" value="flat" checked onchange="applyFilters()"> Flat Base</label>
            <label><input type="checkbox" class="patternCb" value="htf" checked onchange="applyFilters()"> High Tight Flag</label>
            <label><input type="checkbox" class="patternCb" value="ascending" checked onchange="applyFilters()"> Ascending Base</label>
            <label><input type="checkbox" class="patternCb" value="pivot" checked onchange="applyFilters()"> Pocket Pivot</label>
        </div>
    </div>
</div>

<!-- Breakouts Now -->
<div class="section" id="breakoutsSection">
    <div class="section-header breakout">
        <h2>🔥 Breakouts Now</h2>
        <span class="count" id="breakoutCount">{{ breakouts|length }}</span>
    </div>
    <div class="cards" id="breakoutCards">
        {% for stock in breakouts %}
        {{ stock_card(stock) }}
        {% endfor %}
        {% if not breakouts %}
        <div class="empty"><div class="icon">📭</div>No breakouts detected</div>
        {% endif %}
    </div>
</div>

<!-- Bases Forming -->
<div class="section" id="basesSection">
    <div class="section-header base">
        <h2>📐 Bases Forming</h2>
        <span class="count" id="baseCount">{{ bases|length }}</span>
    </div>
    <div class="cards" id="baseCards">
        {% for stock in bases %}
        {{ stock_card(stock) }}
        {% endfor %}
        {% if not bases %}
        <div class="empty"><div class="icon">📭</div>No bases forming</div>
        {% endif %}
    </div>
</div>

<!-- Pocket Pivots -->
<div class="section" id="pivotsSection">
    <div class="section-header pivot">
        <h2>⚡ Pocket Pivots</h2>
        <span class="count" id="pivotCount">{{ pivots|length }}</span>
    </div>
    <div class="cards" id="pivotCards">
        {% for stock in pivots %}
        {{ stock_card(stock) }}
        {% endfor %}
        {% if not pivots %}
        <div class="empty"><div class="icon">📭</div>No pocket pivots detected</div>
        {% endif %}
    </div>
</div>

<div class="footer">
    Stock Scanner Dashboard &bull; CANSLIM Analysis &bull; Auto-refreshes every 60s
</div>

<script>
function applyFilters() {
    const sector = document.getElementById('sectorFilter').value;
    const minScore = parseInt(document.getElementById('scoreFilter').value);
    const checkedPatterns = Array.from(document.querySelectorAll('.patternCb:checked')).map(cb => cb.value);

    document.querySelectorAll('.card[data-ticker]').forEach(card => {
        const cardSector = card.dataset.sector || '';
        const cardScore = parseInt(card.dataset.score) || 0;
        const cardPatterns = (card.dataset.patterns || '').split(',');

        let show = true;
        if (sector !== 'all' && cardSector !== sector) show = false;
        if (cardScore < minScore) show = false;
        const allPatternCbs = document.querySelectorAll('.patternCb');
        const anyChecked = checkedPatterns.length > 0 && checkedPatterns.length < allPatternCbs.length;
        if (anyChecked) {
            const cardPats = (card.dataset.patterns || '').split(',').map(p => p.trim()).filter(p => p);
            if (cardPats.length === 0 || !cardPats.some(p => checkedPatterns.includes(p))) show = false;
        }
        card.style.display = show ? '' : 'none';
    });

    // Update counts
    ['breakout', 'base', 'pivot'].forEach(section => {
        const cards = document.querySelectorAll('#' + section + 'Cards .card[data-ticker]');
        let visible = 0;
        cards.forEach(c => { if (c.style.display !== 'none') visible++; });
        const counter = document.getElementById(section + 'Count');
        if (counter) counter.textContent = visible;
    });
}
</script>
</body>
</html>


'''


def load_scan_results():
    """Load the most recent scan results from JSON or text files."""
    results = {
        'market': {
            'sp500_trend': 'Unknown',
            'sp500_detail': 'No data loaded',
            'vix_value': '--',
            'vix_level': 'Unknown',
            'dist_days': 0,
            'signal': 'Unknown',
            'recommendation': 'Load scan data'
        },
        'breakouts': [],
        'bases': [],
        'pivots': [],
        'sectors': set(),
        'total_stocks': 0,
        'total_results': 0
    }

    # Try JSON first
    json_files = sorted(glob.glob(os.path.join(DATA_DIR, 'scan_results*.json')), reverse=True)
    if json_files:
        try:
            with open(json_files[0], 'r') as f:
                data = json.load(f)
            return _parse_json_results(data)
        except Exception:
            pass

    # Try text files
    txt_files = sorted(glob.glob(os.path.join(DATA_DIR, 'scan_results*.txt')), reverse=True)
    if txt_files:
        try:
            with open(txt_files[0], 'r') as f:
                text = f.read()
            return _parse_text_results(text)
        except Exception:
            pass

    # Try loading demo/sample data
    sample_path = os.path.join(DATA_DIR, 'sample_scan.json')
    if os.path.exists(sample_path):
        try:
            with open(sample_path, 'r') as f:
                data = json.load(f)
            return _parse_json_results(data)
        except Exception:
            pass

    return results


def _classify_pattern(pattern_name):
    """Return CSS class and filter key for a pattern."""
    p = pattern_name.lower()
    if 'cup' in p or 'handle' in p:
        return 'cup', 'cup'
    elif 'flat' in p:
        return 'flat', 'flat'
    elif 'high tight' in p or 'htf' in p:
        return 'htf', 'htf'
    elif 'ascending' in p:
        return 'ascending', 'ascending'
    elif 'pocket' in p or 'pivot' in p:
        return 'pivot', 'pivot'
    return '', ''


def _categorize_stock(stock):
    """Categorize into breakout, base, or pivot based on patterns."""
    patterns_lower = [p.lower() for p in stock.get('patterns_raw', [])]
    for p in patterns_lower:
        if 'cup' in p or 'handle' in p or 'high tight' in p or 'htf' in p:
            return 'breakout'
    for p in patterns_lower:
        if 'flat' in p or 'ascending' in p:
            return 'base'
    for p in patterns_lower:
        if 'pocket' in p or 'pivot' in p:
            return 'pivot'
    return 'breakout'


def _build_stock(raw):
    """Normalize a raw stock dict into template-friendly format."""
    patterns_raw = raw.get('patterns', raw.get('patterns_detected', []))
    if isinstance(patterns_raw, str):
        patterns_raw = [p.strip() for p in patterns_raw.split(',') if p.strip()]

    patterns = []
    pattern_keys = []
    for p in patterns_raw:
        cls, key = _classify_pattern(p)
        patterns.append({'name': p, 'cls': cls})
        if key:
            pattern_keys.append(key)

    score = raw.get('score', raw.get('total_score', 0))
    try:
        score = int(score)
    except (ValueError, TypeError):
        score = 0

    price = raw.get('price', 0)
    try:
        price = float(price)
    except (ValueError, TypeError):
        price = 0.0

    buy_point = raw.get('buy_point', raw.get('buypoint', None))
    if buy_point:
        try:
            buy_point = float(buy_point)
        except (ValueError, TypeError):
            buy_point = None

    rs = raw.get('rs_rating', raw.get('rs', '--'))
    eps = raw.get('eps_growth', raw.get('eps', '--'))
    roe = raw.get('roe', '--')
    vol = raw.get('volume_ratio', raw.get('vol_ratio', '--'))
    if isinstance(eps, (int, float)):
        eps = f"{eps}%"
    if isinstance(roe, (int, float)):
        roe = f"{roe}%"
    if isinstance(vol, (int, float)):
        vol = f"{vol:.1f}x"

    return {
        'ticker': raw.get('ticker', raw.get('symbol', '???')),
        'score': score,
        'price': price,
        'buy_point': buy_point,
        'rs_rating': rs,
        'eps_growth': eps,
        'roe': roe,
        'volume_ratio': vol,
        'patterns': patterns,
        'pattern_keys': pattern_keys,
        'patterns_raw': patterns_raw,
        'sector': raw.get('sector', raw.get('industry', ''))
    }


def _parse_json_results(data):
    """Parse JSON scan results."""
    result = {
        'market': {
            'sp500_trend': 'Unknown', 'sp500_detail': '', 'vix_value': '--',
            'vix_level': 'Unknown', 'dist_days': 0, 'signal': 'Unknown', 'recommendation': ''
        },
        'breakouts': [], 'bases': [], 'pivots': [],
        'sectors': set(), 'total_stocks': 0, 'total_results': 0
    }

    # Market timing
    mt = data.get('market_timing', data.get('market', {}))
    if mt:
        result['market']['sp500_trend'] = mt.get('sp500_trend', mt.get('trend', 'Unknown'))
        result['market']['sp500_detail'] = mt.get('detail', mt.get('sp500_detail', ''))
        result['market']['vix_value'] = mt.get('vix', mt.get('vix_value', '--'))
        result['market']['vix_level'] = mt.get('vix_signal', mt.get('vix_level', 'Unknown'))
        result['market']['dist_days'] = mt.get('distribution_days', mt.get('dist_days', 0))
        result['market']['signal'] = mt.get('recommendation', mt.get('signal', 'Unknown'))
        result['market']['recommendation'] = mt.get('detail', mt.get('recommendation', ''))

    # Stocks
    stocks_raw = data.get('results', data.get('stocks', []))
    if isinstance(stocks_raw, dict):
        # Might be segmented already
        for key in ['breakouts', 'breakouts_now']:
            for s in stocks_raw.get(key, []):
                stock = _build_stock(s)
                result['breakouts'].append(stock)
                if stock['sector']:
                    result['sectors'].add(stock['sector'])
        for key in ['bases', 'bases_forming']:
            for s in stocks_raw.get(key, []):
                stock = _build_stock(s)
                result['bases'].append(stock)
                if stock['sector']:
                    result['sectors'].add(stock['sector'])
        for key in ['pivots', 'pocket_pivots']:
            for s in stocks_raw.get(key, []):
                stock = _build_stock(s)
                result['pivots'].append(stock)
                if stock['sector']:
                    result['sectors'].add(stock['sector'])
    else:
        for raw in stocks_raw:
            stock = _build_stock(raw)
            cat = _categorize_stock(stock)
            if cat == 'breakout':
                result['breakouts'].append(stock)
            elif cat == 'base':
                result['bases'].append(stock)
            else:
                result['pivots'].append(stock)
            if stock['sector']:
                result['sectors'].add(stock['sector'])

    result['total_stocks'] = data.get('total_scanned', data.get('total_stocks', 0))
    result['total_results'] = len(result['breakouts']) + len(result['bases']) + len(result['pivots'])
    result['sectors'] = sorted(result['sectors'])

    # Sort by score descending
    for key in ['breakouts', 'bases', 'pivots']:
        result[key].sort(key=lambda x: x['score'], reverse=True)

    return result


def _parse_text_results(text):
    """Parse text-based scan results from scanner_v3.py output."""
    import re

    result = {
        'market': {
            'sp500_trend': 'Unknown', 'sp500_detail': '', 'vix_value': '--',
            'vix_level': 'Unknown', 'dist_days': 0, 'signal': 'Unknown', 'recommendation': ''
        },
        'breakouts': [], 'bases': [], 'pivots': [],
        'sectors': set(), 'total_stocks': 0, 'total_results': 0
    }

    lines = text.strip().split('\n')
    current_section = None
    current_stock = None
    seen_tickers = {}  # track per section to avoid dupes

    for i, line in enumerate(lines):
        ls = line.strip()
        ll = ls.lower()

        # ── Market timing ──
        sp_match = re.search(r'S&P 500:\s*\$?([\d,]+\.?\d*)', ls)
        if sp_match:
            result['market']['sp500_detail'] = f"S&P 500: ${sp_match.group(1)}"

        if 'above 21-day' in ll and '✓' in ls:
            result['market']['sp500_trend'] = 'Above 21-MA'
        if 'above 50-day' in ll and '✓' in ls:
            result['market']['sp500_trend'] = 'Uptrend'

        dist_match = re.search(r'Distribution Days:\s*(\d+)', ls)
        if dist_match:
            result['market']['dist_days'] = int(dist_match.group(1))

        vix_match = re.search(r'VIX:\s*([\d.]+)\s*\((\w+)\)', ls)
        if vix_match:
            result['market']['vix_value'] = vix_match.group(1)
            result['market']['vix_level'] = vix_match.group(2)

        if '⚠️ caution' in ll:
            result['market']['signal'] = 'Caution'
            result['market']['recommendation'] = 'Reduce position sizes'
        elif 'green light' in ll or '✅ green' in ll:
            result['market']['signal'] = 'Green Light'
            result['market']['recommendation'] = 'Full position sizes'
        elif 'red light' in ll or '🔴 red' in ll:
            result['market']['signal'] = 'Red Light'
            result['market']['recommendation'] = 'Avoid new positions'

        # ── Section detection ──
        if '🚀 BREAKOUTS NOW' in ls or 'BREAKOUTS NOW' in ls.upper():
            _save_stock(current_stock, current_section, result, seen_tickers)
            current_stock = None
            current_section = 'breakouts'
            continue
        elif '📈 BASES FORMING' in ls or 'BASES FORMING' in ls.upper():
            _save_stock(current_stock, current_section, result, seen_tickers)
            current_stock = None
            current_section = 'bases'
            continue
        elif 'POCKET PIVOT' in ls.upper():
            _save_stock(current_stock, current_section, result, seen_tickers)
            current_stock = None
            current_section = 'pivots'
            continue
        elif '=' * 10 in ls and current_stock:
            _save_stock(current_stock, current_section, result, seen_tickers)
            current_stock = None
            continue

        if not current_section:
            continue

        # ── Ticker line: "GOOGL - Score: 10/12 - $338.00" ──
        ticker_match = re.match(r'^([A-Z]{1,5})\s*-\s*Score:\s*(\d+)/12\s*-\s*\$([\d,.]+)', ls)
        if ticker_match:
            _save_stock(current_stock, current_section, result, seen_tickers)
            current_stock = {
                'ticker': ticker_match.group(1),
                'score': int(ticker_match.group(2)),
                'price': float(ticker_match.group(3).replace(',', '')),
                'buy_point': None,
                'rs_rating': '--',
                'eps_growth': '--',
                'roe': '--',
                'volume_ratio': '--',
                'patterns': [],
                'pattern_keys': [],
                'patterns_raw': [],
                'sector': '',
                'earnings_warning': False
            }
            continue

        # ── Detail lines (belong to current_stock) ──
        if current_stock and ls.startswith('RS Rating:'):
            rs_m = re.search(r'RS Rating:\s*(\d+)', ls)
            if rs_m:
                current_stock['rs_rating'] = rs_m.group(1)

        if current_stock and '✓' in ls:
            # Pattern detection
            if 'Flat Base' in ls:
                current_stock['patterns_raw'].append(ls.split('✓')[1].strip())
                current_stock['patterns'].append({'name': 'Flat Base', 'cls': 'flat'})
                current_stock['pattern_keys'].append('flat')
            elif 'Cup with Handle' in ls or 'Cup' in ls and 'Handle' in ls:
                current_stock['patterns_raw'].append(ls.split('✓')[1].strip())
                current_stock['patterns'].append({'name': 'Cup & Handle', 'cls': 'cup'})
                current_stock['pattern_keys'].append('cup')
            elif 'High Tight Flag' in ls:
                current_stock['patterns_raw'].append(ls.split('✓')[1].strip())
                current_stock['patterns'].append({'name': 'High Tight Flag', 'cls': 'htf'})
                current_stock['pattern_keys'].append('htf')
            elif 'Ascending Base' in ls:
                current_stock['patterns_raw'].append(ls.split('✓')[1].strip())
                current_stock['patterns'].append({'name': 'Ascending Base', 'cls': 'ascending'})
                current_stock['pattern_keys'].append('ascending')
            elif 'Pocket Pivot' in ls:
                current_stock['patterns_raw'].append(ls.split('✓')[1].strip())
                current_stock['patterns'].append({'name': 'Pocket Pivot', 'cls': 'pivot'})
                current_stock['pattern_keys'].append('pivot')
            elif 'Volume Breakout' in ls:
                vol_m = re.search(r'([\d.]+)x', ls)
                if vol_m:
                    current_stock['volume_ratio'] = f"{vol_m.group(1)}x"
            elif 'EPS Growth' in ls:
                eps_m = re.search(r'EPS Growth\s*([\d.]+)%', ls)
                if eps_m:
                    current_stock['eps_growth'] = f"{eps_m.group(1)}%"
            elif 'ROE' in ls:
                roe_m = re.search(r'ROE\s*([\d.]+)%', ls)
                if roe_m:
                    current_stock['roe'] = f"{roe_m.group(1)}%"
            elif 'EARNINGS' in ls.upper():
                current_stock['earnings_warning'] = True

        if current_stock and '→ Buy point:' in ls:
            bp_m = re.search(r'\$([\d,.]+)', ls)
            if bp_m:
                current_stock['buy_point'] = float(bp_m.group(1).replace(',', ''))

        # Total stocks scanned
        total_match = re.search(r'Total stocks scanned:\s*(\d+)', ls)
        if total_match:
            result['total_stocks'] = int(total_match.group(1))

    # Save last stock
    _save_stock(current_stock, current_section, result, seen_tickers)

    result['total_results'] = len(result['breakouts']) + len(result['bases']) + len(result['pivots'])
    result['sectors'] = sorted(result['sectors'])

    # Sort by score descending
    for key in ['breakouts', 'bases', 'pivots']:
        result[key].sort(key=lambda x: x['score'], reverse=True)

    return result


def _save_stock(stock, section, result, seen_tickers):
    """Save a parsed stock to the appropriate section, avoiding duplicates."""
    if stock and section:
        key = f"{section}:{stock['ticker']}"
        if key not in seen_tickers:
            seen_tickers[key] = True
            result[section].append(stock)
            if stock.get('sector'):
                result['sectors'].add(stock['sector'])


@app.route('/')
def index():
    data = load_scan_results()
    return render_template_string(
        TEMPLATE,
        market=data['market'],
        breakouts=data['breakouts'],
        bases=data['bases'],
        pivots=data['pivots'],
        sectors=data['sectors'],
        total_stocks=data['total_stocks'],
        total_results=data['total_results'],
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )


@app.route('/api/scan')
def api_scan():
    data = load_scan_results()
    data['sectors'] = list(data['sectors']) if isinstance(data['sectors'], set) else data['sectors']
    return jsonify(data)


if __name__ == '__main__':
    print("\n📊 Stock Scanner Dashboard starting at http://localhost:5003\n")
    app.run(debug=False, host='0.0.0.0', port=5003)
