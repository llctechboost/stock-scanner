#!/usr/bin/env python3
"""
Flow Dashboard - Simple web interface for monitoring signals
"""
from flask import Flask, render_template_string
import json
from datetime import datetime

app = Flask(__name__)

TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🔥 Trading Dashboard</title>
    <meta http-equiv="refresh" content="60">
    <style>
        body { font-family: Arial; background: #0a0a0a; color: #fff; padding: 20px; }
        h1 { color: #00ff88; }
        .signal { background: #1a1a1a; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid; }
        .hot { border-color: #ff4444; }
        .strong { border-color: #44ff44; }
        .watch { border-color: #ffaa44; }
        .meta { color: #888; font-size: 0.9em; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 10px; text-align: left; }
        th { background: #222; }
        tr:nth-child(even) { background: #111; }
        .green { color: #44ff44; }
        .red { color: #ff4444; }
        .yellow { color: #ffaa44; }
    </style>
</head>
<body>
    <h1>🔥 Trading Dashboard</h1>
    <p class="meta">Last updated: {{ timestamp }}</p>
    
    {% if hot %}
    <h2 style="color: #ff4444;">🔥 HOT SIGNALS ({{ hot|length }})</h2>
    {% for s in hot %}
    <div class="signal hot">
        <h3>{{ s.ticker }} - {{ s.conviction }}/100</h3>
        <p><strong>Pattern:</strong> {{ s.pattern }} ({{ s.stock_score }}/100)</p>
        <p><strong>Price:</strong> ${{ "%.2f"|format(s.price) }}
        {% if s.buy_point %} | <strong>Buy:</strong> ${{ "%.2f"|format(s.buy_point) }}{% endif %}
        {% if s.stop %} | <strong>Stop:</strong> ${{ "%.2f"|format(s.stop) }}{% endif %}</p>
        {% if s.has_flow %}
        <p><strong>Options:</strong> {{ s.flow_bias }} flow, ${{ "{:,.0f}".format(s.premium_flow) }}</p>
        {% endif %}
        <p class="meta">Reasons: {{ s.reasons|join(', ') }}</p>
    </div>
    {% endfor %}
    {% endif %}
    
    {% if strong %}
    <h2 style="color: #44ff44;">🟢 STRONG SIGNALS ({{ strong|length }})</h2>
    {% for s in strong[:5] %}
    <div class="signal strong">
        <h3>{{ s.ticker }} - {{ s.conviction }}/100</h3>
        <p><strong>Pattern:</strong> {{ s.pattern }} | <strong>Price:</strong> ${{ "%.2f"|format(s.price) }}</p>
        {% if s.has_flow %}<p><strong>Flow:</strong> {{ s.flow_bias }}</p>{% endif %}
    </div>
    {% endfor %}
    {% endif %}
    
    {% if positions %}
    <h2>📊 Open Positions</h2>
    <table>
        <tr><th>Ticker</th><th>Shares</th><th>Entry</th><th>Current</th><th>P&L</th></tr>
        {% for p in positions %}
        <tr>
            <td>{{ p.ticker }}</td>
            <td>{{ p.shares }}</td>
            <td>${{ "%.2f"|format(p.entry) }}</td>
            <td>${{ "%.2f"|format(p.current) }}</td>
            <td class="{{ 'green' if p.pnl > 0 else 'red' }}">${{ "%.2f"|format(p.pnl) }} ({{ "%+.1f"|format(p.pnl_pct) }}%)</td>
        </tr>
        {% endfor %}
    </table>
    {% endif %}
</body>
</html>
'''

@app.route('/')
def dashboard():
    # Load signals
    try:
        with open('signals_latest.json', 'r') as f:
            signals = json.load(f)
    except:
        signals = {'hot': [], 'strong': [], 'watch': []}
    
    # Load positions
    try:
        with open('positions.json', 'r') as f:
            all_pos = json.load(f)
            positions = [p for p in all_pos if p['status'] == 'open']
            
            # Add current prices (would need live data in production)
            for p in positions:
                p['current'] = p['entry']  # Placeholder
                p['pnl'] = 0
                p['pnl_pct'] = 0
    except:
        positions = []
    
    return render_template_string(
        TEMPLATE,
        hot=signals.get('hot', []),
        strong=signals.get('strong', []),
        positions=positions,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

if __name__ == '__main__':
    print("\n🌐 Starting dashboard at http://localhost:5000\n")
    app.run(debug=False, port=5000)
