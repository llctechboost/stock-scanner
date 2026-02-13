#!/usr/bin/env python3
"""
Trading Command Center — Unified Dashboard
Combines all trading scanners into one production interface.
Flask + Bootstrap 5 dark theme on port 5050.
"""

import os
import sys
import json
import glob
import subprocess
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, send_from_directory, request

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(SCRIPT_DIR, 'charts')
VISION_DIR = os.path.join(SCRIPT_DIR, 'vision_reports')

DATA_FILES = {
    'market_health': os.path.join(SCRIPT_DIR, 'market_health_latest.json'),
    'money_scan': os.path.join(SCRIPT_DIR, 'money_scan_latest.json'),
    'options_flow': os.path.join(SCRIPT_DIR, 'options_flow_latest.json'),
    'dark_pool': os.path.join(SCRIPT_DIR, 'dark_pool_latest.json'),
    'signals': os.path.join(SCRIPT_DIR, 'signals_latest.json'),
    'sector_rotation': os.path.join(SCRIPT_DIR, 'sector_rotation_latest.json'),
    'earnings': os.path.join(SCRIPT_DIR, 'earnings_calendar_latest.json'),
    'signal_stats': os.path.join(SCRIPT_DIR, 'signal_stats_latest.json'),
    'intel_manifest': os.path.join(CHARTS_DIR, 'intel_manifest.json'),
    'charts_manifest': os.path.join(CHARTS_DIR, 'charts_manifest.json'),
}

SCANNER_SCRIPTS = {
    'market_health': os.path.join(SCRIPT_DIR, 'market_health.py'),
    'scanner_v3': os.path.join(SCRIPT_DIR, 'scanner_v3.py'),
    'money_scanner': os.path.join(SCRIPT_DIR, 'money_scanner.py'),
    'vcp_detector': os.path.join(SCRIPT_DIR, 'vcp_detector.py'),
    'options_flow': os.path.join(SCRIPT_DIR, 'options_flow_scanner.py'),
    'dark_pool': os.path.join(SCRIPT_DIR, 'dark_pool_tracker.py'),
    'sector_rotation': os.path.join(SCRIPT_DIR, 'sector_rotation.py'),
    'earnings': os.path.join(SCRIPT_DIR, 'earnings_calendar.py'),
    'signal_matcher': os.path.join(SCRIPT_DIR, 'signal_matcher.py'),
    'chart_vision': os.path.join(SCRIPT_DIR, 'chart_vision.py'),
    'combo_scanner': os.path.join(SCRIPT_DIR, 'combo_scanner.py'),
}

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)

# Background task tracking
running_tasks = {}
task_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def load_json(path):
    """Safely load a JSON file, return {} on error."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def get_data_age(data):
    """Return human-readable age from a timestamp field."""
    ts = data.get('timestamp', '')
    if not ts:
        return 'unknown'
    try:
        dt = datetime.fromisoformat(ts)
        delta = datetime.now() - dt
        mins = int(delta.total_seconds() / 60)
        if mins < 1:
            return 'just now'
        if mins < 60:
            return f'{mins}m ago'
        hours = mins // 60
        if hours < 24:
            return f'{hours}h {mins % 60}m ago'
        return f'{delta.days}d ago'
    except Exception:
        return 'unknown'


def is_market_open():
    """Simple check if US market is currently open (9:30-16:00 ET, Mon-Fri)."""
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo('America/New_York'))
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def get_chart_files():
    """Get available chart images mapped by ticker."""
    charts = {}
    if os.path.exists(CHARTS_DIR):
        for f in os.listdir(CHARTS_DIR):
            if f.endswith(('.png', '.jpg', '.jpeg')):
                ticker = f.split('_')[0]
                if ticker not in charts:
                    charts[ticker] = []
                charts[ticker].append(f)
        # Sort each ticker's charts by name (latest last)
        for t in charts:
            charts[t] = sorted(charts[t], reverse=True)
    return charts


def get_scan_results():
    """Load the latest scan_results_*.txt file and parse it."""
    txt_files = sorted(glob.glob(os.path.join(SCRIPT_DIR, 'scan_results_*.txt')), reverse=True)
    if not txt_files:
        return []
    results = []
    current = None
    import re
    with open(txt_files[0], 'r') as f:
        for line in f:
            ls = line.strip()
            m = re.match(r'^([A-Z]{1,5})\s*-\s*Score:\s*(\d+)/12\s*-\s*\$([\d,.]+)', ls)
            if m:
                if current:
                    results.append(current)
                current = {
                    'ticker': m.group(1),
                    'score': int(m.group(2)),
                    'price': float(m.group(3).replace(',', '')),
                    'patterns': [],
                    'signals': [],
                    'buy_points': [],
                    'rs_rating': None,
                }
                continue
            if current:
                if '✓' in ls or '✗' in ls:
                    current['signals'].append(ls.replace('✓ ', '').replace('✗ ', ''))
                    for p in ['Cup with Handle', 'Flat Base', 'High Tight Flag',
                              'Ascending Base', 'Pocket Pivot', 'Double Bottom']:
                        if p in ls:
                            current['patterns'].append(p)
                if '→ Buy point:' in ls:
                    bm = re.search(r'\$([\d,.]+)', ls)
                    if bm:
                        current['buy_points'].append(float(bm.group(1).replace(',', '')))
                if ls.startswith('RS Rating'):
                    rm = re.search(r'(\d+)', ls)
                    if rm:
                        current['rs_rating'] = int(rm.group(1))
    if current:
        results.append(current)
    return results


# ---------------------------------------------------------------------------
# Background scanner runner
# ---------------------------------------------------------------------------
def run_scanner_bg(task_id, script_path, args=None):
    """Run a scanner script in background, track status."""
    with task_lock:
        running_tasks[task_id] = {
            'status': 'running',
            'started': datetime.now().isoformat(),
            'output': '',
            'error': '',
        }
    try:
        cmd = [sys.executable, script_path]
        if args:
            cmd.extend(args)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            cwd=SCRIPT_DIR
        )
        with task_lock:
            running_tasks[task_id]['status'] = 'completed'
            running_tasks[task_id]['output'] = result.stdout[-5000:] if result.stdout else ''
            running_tasks[task_id]['error'] = result.stderr[-2000:] if result.stderr else ''
            running_tasks[task_id]['finished'] = datetime.now().isoformat()
    except subprocess.TimeoutExpired:
        with task_lock:
            running_tasks[task_id]['status'] = 'timeout'
            running_tasks[task_id]['finished'] = datetime.now().isoformat()
    except Exception as e:
        with task_lock:
            running_tasks[task_id]['status'] = 'error'
            running_tasks[task_id]['error'] = str(e)
            running_tasks[task_id]['finished'] = datetime.now().isoformat()


def run_full_scan_bg():
    """Run all scanners sequentially in background."""
    task_id = 'full_scan'
    with task_lock:
        running_tasks[task_id] = {
            'status': 'running',
            'started': datetime.now().isoformat(),
            'output': '',
            'error': '',
            'steps': [],
        }

    scanners = [
        ('Market Health', SCANNER_SCRIPTS.get('market_health')),
        ('Money Scanner', SCANNER_SCRIPTS.get('money_scanner')),
        ('Options Flow', SCANNER_SCRIPTS.get('options_flow')),
        ('Dark Pool', SCANNER_SCRIPTS.get('dark_pool')),
        ('Sector Rotation', SCANNER_SCRIPTS.get('sector_rotation')),
        ('Earnings Calendar', SCANNER_SCRIPTS.get('earnings')),
        ('Signal Matcher', SCANNER_SCRIPTS.get('signal_matcher')),
    ]

    for name, script in scanners:
        if not script or not os.path.exists(script):
            with task_lock:
                running_tasks[task_id]['steps'].append(f'⚠️ {name}: script not found')
            continue
        try:
            with task_lock:
                running_tasks[task_id]['steps'].append(f'⏳ Running {name}...')
            result = subprocess.run(
                [sys.executable, script], capture_output=True, text=True,
                timeout=300, cwd=SCRIPT_DIR
            )
            status_icon = '✅' if result.returncode == 0 else '❌'
            with task_lock:
                running_tasks[task_id]['steps'][-1] = f'{status_icon} {name} complete'
        except Exception as e:
            with task_lock:
                running_tasks[task_id]['steps'][-1] = f'❌ {name}: {str(e)[:100]}'

    with task_lock:
        running_tasks[task_id]['status'] = 'completed'
        running_tasks[task_id]['finished'] = datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/charts/<path:filename>')
def serve_chart(filename):
    return send_from_directory(CHARTS_DIR, filename)


@app.route('/api/data')
def api_data():
    """Return all dashboard data as JSON."""
    market_health = load_json(DATA_FILES['market_health'])
    money = load_json(DATA_FILES['money_scan'])
    options = load_json(DATA_FILES['options_flow'])
    dark_pool = load_json(DATA_FILES['dark_pool'])
    signals = load_json(DATA_FILES['signals'])
    sectors = load_json(DATA_FILES['sector_rotation'])
    earnings = load_json(DATA_FILES['earnings'])
    stats = load_json(DATA_FILES['signal_stats'])
    intel = load_json(DATA_FILES['intel_manifest'])
    scan_results = get_scan_results()
    chart_files = get_chart_files()

    return jsonify({
        'market_open': is_market_open(),
        'timestamp': datetime.now().isoformat(),
        'market_health': market_health,
        'market_health_age': get_data_age(market_health),
        'money_scan': money,
        'money_scan_age': get_data_age(money),
        'options_flow': options,
        'options_flow_age': get_data_age(options),
        'dark_pool': dark_pool,
        'dark_pool_age': get_data_age(dark_pool),
        'signals': signals,
        'signals_age': get_data_age(signals),
        'sectors': sectors,
        'sectors_age': get_data_age(sectors),
        'earnings': earnings,
        'earnings_age': get_data_age(earnings),
        'signal_stats': stats,
        'intel_manifest': intel,
        'scan_results': scan_results,
        'chart_files': chart_files,
    })


@app.route('/api/task/status')
def api_task_status():
    """Check status of background tasks."""
    with task_lock:
        return jsonify(running_tasks)


@app.route('/api/run/full_scan', methods=['POST'])
def api_run_full_scan():
    with task_lock:
        if 'full_scan' in running_tasks and running_tasks['full_scan']['status'] == 'running':
            return jsonify({'error': 'Full scan already running'}), 409
    t = threading.Thread(target=run_full_scan_bg, daemon=True)
    t.start()
    return jsonify({'status': 'started', 'task_id': 'full_scan'})


@app.route('/api/run/scanner/<name>', methods=['POST'])
def api_run_scanner(name):
    script = SCANNER_SCRIPTS.get(name)
    if not script or not os.path.exists(script):
        return jsonify({'error': f'Unknown scanner: {name}'}), 404
    task_id = f'scanner_{name}'
    with task_lock:
        if task_id in running_tasks and running_tasks[task_id]['status'] == 'running':
            return jsonify({'error': f'{name} already running'}), 409
    t = threading.Thread(target=run_scanner_bg, args=(task_id, script), daemon=True)
    t.start()
    return jsonify({'status': 'started', 'task_id': task_id})


@app.route('/api/run/vision', methods=['POST'])
def api_run_vision():
    script = SCANNER_SCRIPTS.get('chart_vision')
    if not script:
        return jsonify({'error': 'chart_vision script not found'}), 404
    task_id = 'vision_analysis'
    with task_lock:
        if task_id in running_tasks and running_tasks[task_id]['status'] == 'running':
            return jsonify({'error': 'Vision analysis already running'}), 409
    t = threading.Thread(target=run_scanner_bg, args=(task_id, script, ['--all']), daemon=True)
    t.start()
    return jsonify({'status': 'started', 'task_id': task_id})


@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------
DASHBOARD_HTML = r'''<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trading Command Center</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.datatables.net/1.13.8/css/dataTables.bootstrap5.min.css" rel="stylesheet">
<style>
:root {
  --tc-bg: #0d1117;
  --tc-card: #161b22;
  --tc-border: #30363d;
  --tc-green: #3fb950;
  --tc-red: #f85149;
  --tc-yellow: #d29922;
  --tc-blue: #58a6ff;
  --tc-cyan: #39d2c0;
  --tc-purple: #bc8cff;
  --tc-muted: #8b949e;
  --tc-text: #e6edf3;
}
body {
  background: var(--tc-bg);
  color: var(--tc-text);
  font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 13px;
}
.navbar-brand { font-weight: 700; letter-spacing: 1px; }
.tc-card {
  background: var(--tc-card);
  border: 1px solid var(--tc-border);
  border-radius: 8px;
  margin-bottom: 16px;
}
.tc-card .card-header {
  background: rgba(88,166,255,.06);
  border-bottom: 1px solid var(--tc-border);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  font-weight: 600;
  font-size: 14px;
}
.tc-card .card-header .badge { font-size: 11px; }
.tc-card .card-body { padding: 12px 16px; }
.collapse-icon { transition: transform .2s; }
.collapsed .collapse-icon { transform: rotate(-90deg); }

/* Score badges */
.score-high { background: var(--tc-green) !important; color: #000 !important; }
.score-med { background: var(--tc-yellow) !important; color: #000 !important; }
.score-low { background: var(--tc-red) !important; color: #fff !important; }
.score-neutral { background: var(--tc-muted) !important; }

/* Bias tags */
.bias-bull { color: var(--tc-green); font-weight: 700; }
.bias-bear { color: var(--tc-red); font-weight: 700; }

/* Sector bar */
.sector-bar { height: 8px; border-radius: 4px; }
.sector-inflow { background: var(--tc-green); }
.sector-outflow { background: var(--tc-red); }

/* Market status */
.market-open { color: var(--tc-green); }
.market-closed { color: var(--tc-red); }

/* Stat cards */
.stat-card {
  background: var(--tc-card);
  border: 1px solid var(--tc-border);
  border-radius: 8px;
  padding: 14px 16px;
  text-align: center;
}
.stat-card .stat-value { font-size: 28px; font-weight: 700; }
.stat-card .stat-label { color: var(--tc-muted); font-size: 11px; text-transform: uppercase; letter-spacing: .5px; }

/* Action buttons */
.btn-action {
  font-weight: 600;
  letter-spacing: .3px;
  border: none;
  padding: 8px 18px;
  border-radius: 6px;
}
.btn-scan { background: linear-gradient(135deg, #238636, #2ea043); color: #fff; }
.btn-scan:hover { background: linear-gradient(135deg, #2ea043, #3fb950); color: #fff; }
.btn-report { background: linear-gradient(135deg, #1f6feb, #388bfd); color: #fff; }
.btn-report:hover { background: linear-gradient(135deg, #388bfd, #58a6ff); color: #fff; }
.btn-vision { background: linear-gradient(135deg, #8957e5, #bc8cff); color: #fff; }
.btn-vision:hover { background: linear-gradient(135deg, #bc8cff, #d2a8ff); color: #fff; }

.spinner-grow-sm { width: 12px; height: 12px; }
.data-age { color: var(--tc-muted); font-size: 11px; }

/* Tables */
table.dataTable { font-size: 12px; }
table.dataTable thead th { border-bottom-color: var(--tc-border) !important; color: var(--tc-muted); font-weight: 600; text-transform: uppercase; font-size: 10px; letter-spacing: .5px; }
table.dataTable tbody td { border-bottom-color: var(--tc-border) !important; vertical-align: middle; }
table.dataTable tbody tr:hover { background: rgba(88,166,255,.05) !important; }
.dataTables_wrapper .dataTables_filter input,
.dataTables_wrapper .dataTables_length select {
  background: var(--tc-bg) !important; color: var(--tc-text) !important;
  border: 1px solid var(--tc-border) !important; border-radius: 4px;
}
.dataTables_wrapper .dataTables_info,
.dataTables_wrapper .dataTables_paginate { color: var(--tc-muted) !important; font-size: 11px; }
.page-link { background: var(--tc-card) !important; border-color: var(--tc-border) !important; color: var(--tc-text) !important; }
.page-item.active .page-link { background: var(--tc-blue) !important; border-color: var(--tc-blue) !important; }

/* Chart vision cards */
.vision-card { border: 1px solid var(--tc-border); border-radius: 8px; overflow: hidden; background: var(--tc-card); }
.vision-card img { width: 100%; height: 180px; object-fit: cover; border-bottom: 1px solid var(--tc-border); }
.vision-card .vision-body { padding: 10px 12px; font-size: 12px; }
.vision-grade-A { border-left: 4px solid var(--tc-green); }
.vision-grade-B { border-left: 4px solid var(--tc-blue); }
.vision-grade-C { border-left: 4px solid var(--tc-yellow); }
.vision-grade-F { border-left: 4px solid var(--tc-red); }

/* Earnings calendar colors */
.earn-danger { color: var(--tc-red); font-weight: 700; }
.earn-caution { color: var(--tc-yellow); }
.earn-clear { color: var(--tc-green); }

/* Toast */
.toast-container { z-index: 9999; }

/* Rotation arrow */
.rotation-arrow { color: var(--tc-blue); font-weight: 700; }

/* Scrollable body inside collapsible cards */
.tc-scroll { max-height: 500px; overflow-y: auto; }

/* Responsive tweaks */
@media (max-width: 768px) {
  .stat-card .stat-value { font-size: 20px; }
  body { font-size: 12px; }
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--tc-bg); }
::-webkit-scrollbar-thumb { background: var(--tc-border); border-radius: 3px; }

/* Pulse animation for running tasks */
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(63,185,80,.4); }
  50% { box-shadow: 0 0 0 6px rgba(63,185,80,0); }
}
.pulse { animation: pulse-glow 1.5s infinite; }

/* ========== Market Health Overview ========== */
.regime-badge {
  display: inline-block;
  font-size: 32px;
  font-weight: 900;
  letter-spacing: 2px;
  padding: 12px 32px;
  border-radius: 12px;
  text-transform: uppercase;
  text-align: center;
  margin: 8px 0;
  text-shadow: 0 0 20px currentColor;
}
.regime-STRONG-BULL { color: #00ff88; background: rgba(0,255,136,.08); border: 2px solid rgba(0,255,136,.3); }
.regime-BULL { color: #3fb950; background: rgba(63,185,80,.08); border: 2px solid rgba(63,185,80,.3); }
.regime-NEUTRAL { color: #d29922; background: rgba(210,153,34,.08); border: 2px solid rgba(210,153,34,.3); }
.regime-CAUTION { color: #f0883e; background: rgba(240,136,62,.08); border: 2px solid rgba(240,136,62,.3); }
.regime-BEAR { color: #f85149; background: rgba(248,81,73,.08); border: 2px solid rgba(248,81,73,.3); }

.index-card {
  background: var(--tc-card);
  border: 1px solid var(--tc-border);
  border-radius: 8px;
  padding: 12px 14px;
  text-align: center;
  position: relative;
  overflow: hidden;
}
.index-card .index-ticker { font-size: 11px; color: var(--tc-muted); text-transform: uppercase; letter-spacing: .5px; font-weight: 600; }
.index-card .index-price { font-size: 22px; font-weight: 700; margin: 2px 0; }
.index-card .index-change { font-size: 14px; font-weight: 700; }
.index-card .index-ma { font-size: 10px; color: var(--tc-muted); margin-top: 4px; }
.index-card .index-ma .ma-ok { color: var(--tc-green); }
.index-card .index-ma .ma-bad { color: var(--tc-red); }

.vix-gauge {
  background: var(--tc-card);
  border: 1px solid var(--tc-border);
  border-radius: 8px;
  padding: 14px 16px;
  text-align: center;
}
.vix-level { font-size: 28px; font-weight: 900; }
.vix-label { font-size: 13px; font-weight: 700; letter-spacing: .5px; }
.vix-low { color: #3fb950; }
.vix-neutral { color: #8b949e; }
.vix-elevated { color: #d29922; }
.vix-high { color: #f0883e; }
.vix-extreme { color: #f85149; }

.breadth-meter { margin: 4px 0; }
.breadth-meter .meter-label { font-size: 10px; color: var(--tc-muted); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 2px; }
.breadth-meter .meter-bar { height: 8px; border-radius: 4px; background: var(--tc-border); overflow: hidden; }
.breadth-meter .meter-fill { height: 100%; border-radius: 4px; transition: width .5s ease; }
.breadth-meter .meter-value { font-size: 12px; font-weight: 700; margin-top: 1px; }

.market-alert {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
  margin-bottom: 4px;
}
.alert-HIGH { background: rgba(248,81,73,.1); border-left: 3px solid var(--tc-red); }
.alert-MEDIUM { background: rgba(210,153,34,.1); border-left: 3px solid var(--tc-yellow); }
.alert-LOW { background: rgba(63,185,80,.1); border-left: 3px solid var(--tc-green); }

.rotation-chip {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 700;
}
.rotation-risk-on { background: rgba(63,185,80,.15); color: var(--tc-green); }
.rotation-risk-off { background: rgba(248,81,73,.15); color: var(--tc-red); }
.rotation-neutral { background: rgba(139,148,158,.15); color: var(--tc-muted); }

@keyframes regime-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .85; }
}
.regime-badge { animation: regime-pulse 3s ease-in-out infinite; }
</style>
</head>
<body>

<!-- Navbar -->
<nav class="navbar navbar-dark px-3 py-2" style="background:var(--tc-card);border-bottom:1px solid var(--tc-border)">
  <span class="navbar-brand mb-0">
    <span style="color:var(--tc-green)">◉</span> Trading Command Center
  </span>
  <div class="d-flex align-items-center gap-3">
    <span id="marketStatus" class="fw-bold"></span>
    <span id="clockDisplay" style="color:var(--tc-muted)"></span>
    <div class="form-check form-switch ms-2" title="Auto-refresh every 5 min">
      <input class="form-check-input" type="checkbox" id="autoRefresh" checked>
      <label class="form-check-label" for="autoRefresh" style="font-size:11px;color:var(--tc-muted)">Auto</label>
    </div>
  </div>
</nav>

<!-- Action Bar -->
<div class="container-fluid px-3 py-2" style="background:rgba(22,27,34,.8);border-bottom:1px solid var(--tc-border)">
  <div class="d-flex flex-wrap gap-2 align-items-center">
    <button class="btn btn-action btn-scan" onclick="runFullScan()" id="btnFullScan">
      🔄 Run Full Scan
    </button>
    <button class="btn btn-action" style="background:linear-gradient(135deg,#0d6efd,#0dcaf0);color:#fff" onclick="runMarketHealth()" id="btnMarketHealth">
      🌍 Market Health
    </button>
    <button class="btn btn-action btn-report" onclick="generateReport()" id="btnReport">
      📊 Generate Report
    </button>
    <button class="btn btn-action btn-vision" onclick="runVision()" id="btnVision">
      📸 Vision Analysis
    </button>
    <div class="ms-auto d-flex align-items-center gap-3">
      <span id="taskStatus" class="data-age"></span>
      <button class="btn btn-sm btn-outline-secondary" onclick="loadData()">↻ Refresh Data</button>
    </div>
  </div>
</div>

<!-- Toast container -->
<div class="toast-container position-fixed top-0 end-0 p-3">
  <div id="mainToast" class="toast align-items-center border-0" role="alert">
    <div class="d-flex">
      <div class="toast-body" id="toastBody"></div>
      <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  </div>
</div>

<!-- Main Content -->
<div class="container-fluid px-3 py-3">

<!-- ==================== MARKET OVERVIEW ==================== -->
<div class="tc-card mb-3" id="marketOverviewCard">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapseMarketOverview">
    <span>🌍 Market Overview</span>
    <span><span class="data-age" id="marketHealthAge"></span> <span class="collapse-icon">▼</span></span>
  </div>
  <div class="collapse show" id="collapseMarketOverview">
    <div class="card-body">

      <!-- Regime Badge — BIG and prominent -->
      <div class="text-center mb-3" id="regimeBadgeContainer">
        <div class="regime-badge" id="regimeBadge">LOADING...</div>
        <div id="regimeScore" style="color:var(--tc-muted);font-size:12px;margin-top:4px"></div>
      </div>

      <!-- Index Cards Row -->
      <div class="row g-2 mb-3" id="indexCardsRow">
        <div class="col-6 col-md-3"><div class="index-card" id="indexSPY"><div class="index-ticker">SPY · S&P 500</div><div class="index-price">—</div><div class="index-change">—</div><div class="index-ma">—</div></div></div>
        <div class="col-6 col-md-3"><div class="index-card" id="indexQQQ"><div class="index-ticker">QQQ · Nasdaq 100</div><div class="index-price">—</div><div class="index-change">—</div><div class="index-ma">—</div></div></div>
        <div class="col-6 col-md-3"><div class="index-card" id="indexDIA"><div class="index-ticker">DIA · Dow 30</div><div class="index-price">—</div><div class="index-change">—</div><div class="index-ma">—</div></div></div>
        <div class="col-6 col-md-3"><div class="index-card" id="indexIWM"><div class="index-ticker">IWM · Russell 2000</div><div class="index-price">—</div><div class="index-change">—</div><div class="index-ma">—</div></div></div>
      </div>

      <!-- VIX + Breadth + Rotation Row -->
      <div class="row g-2 mb-3">
        <!-- VIX Gauge -->
        <div class="col-md-3">
          <div class="vix-gauge" id="vixGauge">
            <div style="font-size:10px;color:var(--tc-muted);text-transform:uppercase;letter-spacing:.5px;font-weight:600">VIX Fear Gauge</div>
            <div class="vix-level" id="vixLevel">—</div>
            <div class="vix-label" id="vixLabel">—</div>
            <div id="vixTrend" style="font-size:11px;color:var(--tc-muted);margin-top:4px">—</div>
          </div>
        </div>

        <!-- Breadth Meters -->
        <div class="col-md-5">
          <div style="background:var(--tc-card);border:1px solid var(--tc-border);border-radius:8px;padding:12px 14px;">
            <div style="font-size:10px;color:var(--tc-muted);text-transform:uppercase;letter-spacing:.5px;font-weight:600;margin-bottom:8px">Market Breadth <span id="breadthLabel" class="badge" style="font-size:9px">—</span></div>
            <div class="breadth-meter">
              <div class="d-flex justify-content-between"><span class="meter-label">Above 50-day MA</span><span class="meter-value" id="breadth50val">—</span></div>
              <div class="meter-bar"><div class="meter-fill" id="breadth50bar" style="width:0%;background:var(--tc-blue)"></div></div>
            </div>
            <div class="breadth-meter">
              <div class="d-flex justify-content-between"><span class="meter-label">Above 200-day MA</span><span class="meter-value" id="breadth200val">—</span></div>
              <div class="meter-bar"><div class="meter-fill" id="breadth200bar" style="width:0%;background:var(--tc-cyan)"></div></div>
            </div>
            <div class="breadth-meter">
              <div class="d-flex justify-content-between"><span class="meter-label">Advance / Decline</span><span class="meter-value" id="breadthADval">—</span></div>
              <div class="meter-bar"><div class="meter-fill" id="breadthADbar" style="width:0%;background:var(--tc-green)"></div></div>
            </div>
            <div class="d-flex justify-content-between mt-1" style="font-size:11px">
              <span style="color:var(--tc-green)" id="newHighsVal">↑ Highs: —</span>
              <span style="color:var(--tc-red)" id="newLowsVal">↓ Lows: —</span>
            </div>
          </div>
        </div>

        <!-- Sector Rotation Summary -->
        <div class="col-md-4">
          <div style="background:var(--tc-card);border:1px solid var(--tc-border);border-radius:8px;padding:12px 14px;">
            <div style="font-size:10px;color:var(--tc-muted);text-transform:uppercase;letter-spacing:.5px;font-weight:600;margin-bottom:8px">
              Sector Rotation
              <span id="rotationChip" class="rotation-chip rotation-neutral">—</span>
            </div>
            <div id="sectorLeadingList" style="font-size:11px;margin-bottom:6px"></div>
            <div id="sectorLaggingList" style="font-size:11px"></div>
          </div>
        </div>
      </div>

      <!-- Alerts -->
      <div id="marketAlerts"></div>

    </div>
  </div>
</div>
<!-- ==================== END MARKET OVERVIEW ==================== -->

<!-- Summary Stats Row -->
<div class="row g-2 mb-3" id="summaryRow">
  <div class="col-6 col-md-2"><div class="stat-card"><div class="stat-value" id="statStocksScanned">—</div><div class="stat-label">Stocks Scanned</div></div></div>
  <div class="col-6 col-md-2"><div class="stat-card"><div class="stat-value" style="color:var(--tc-green)" id="statPatterns">—</div><div class="stat-label">Patterns Found</div></div></div>
  <div class="col-6 col-md-2"><div class="stat-card"><div class="stat-value" style="color:var(--tc-blue)" id="statSignals">—</div><div class="stat-label">Active Signals</div></div></div>
  <div class="col-6 col-md-2"><div class="stat-card"><div class="stat-value" style="color:var(--tc-cyan)" id="statTopScore">—</div><div class="stat-label">Top Score</div></div></div>
  <div class="col-6 col-md-2"><div class="stat-card"><div class="stat-value" style="color:var(--tc-yellow)" id="statEarnings">—</div><div class="stat-label">Earnings Danger</div></div></div>
  <div class="col-6 col-md-2"><div class="stat-card"><div class="stat-value" style="color:var(--tc-purple)" id="statBullFlow">—</div><div class="stat-label">Bull Flow $</div></div></div>
</div>

<!-- Row 1: Signals + Sector Rotation -->
<div class="row g-2">

<!-- Top Picks / Signals -->
<div class="col-lg-7">
<div class="tc-card">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapseSignals">
    <span>🎯 Top Signals & Picks</span>
    <span><span class="data-age" id="signalsAge"></span> <span class="collapse-icon">▼</span></span>
  </div>
  <div class="collapse show" id="collapseSignals">
    <div class="card-body tc-scroll p-0">
      <table class="table table-sm mb-0" id="signalsTable">
        <thead><tr>
          <th>Ticker</th><th>Conv.</th><th>Score</th><th>Pattern</th><th>Price</th><th>Buy Pt</th><th>Flow</th><th>Premium</th><th>Flags</th>
        </tr></thead>
        <tbody id="signalsBody"></tbody>
      </table>
    </div>
  </div>
</div>
</div>

<!-- Sector Rotation -->
<div class="col-lg-5">
<div class="tc-card">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapseSectors">
    <span>🔄 Sector Rotation</span>
    <span><span class="data-age" id="sectorsAge"></span> <span class="collapse-icon">▼</span></span>
  </div>
  <div class="collapse show" id="collapseSectors">
    <div class="card-body">
      <div id="sectorBars" class="mb-3"></div>
      <div id="rotationSignals"></div>
    </div>
  </div>
</div>
</div>

</div><!-- /row -->

<!-- Row 2: Pattern Scanner + VCP -->
<div class="row g-2">

<!-- Pattern Scanner -->
<div class="col-lg-7">
<div class="tc-card">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapsePatterns">
    <span>📈 Pattern Scanner (CANSLIM)</span>
    <span class="collapse-icon">▼</span>
  </div>
  <div class="collapse show" id="collapsePatterns">
    <div class="card-body tc-scroll p-0">
      <table class="table table-sm mb-0" id="patternsTable">
        <thead><tr>
          <th>Ticker</th><th>Score</th><th>RS</th><th>Patterns</th><th>Price</th><th>Buy Points</th><th>Signals</th>
        </tr></thead>
        <tbody id="patternsBody"></tbody>
      </table>
    </div>
  </div>
</div>
</div>

<!-- Money Scanner Rankings -->
<div class="col-lg-5">
<div class="tc-card">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapseMoney">
    <span>💰 Money Scanner Rankings</span>
    <span><span class="data-age" id="moneyAge"></span> <span class="collapse-icon">▼</span></span>
  </div>
  <div class="collapse show" id="collapseMoney">
    <div class="card-body tc-scroll p-0">
      <table class="table table-sm mb-0" id="moneyTable">
        <thead><tr>
          <th>Ticker</th><th>Score</th><th>Price</th><th>3M Perf</th><th>Vol Ratio</th><th>From High</th>
        </tr></thead>
        <tbody id="moneyBody"></tbody>
      </table>
    </div>
  </div>
</div>
</div>

</div><!-- /row -->

<!-- Row 3: Options Flow + Dark Pool -->
<div class="row g-2">

<!-- Options Flow -->
<div class="col-lg-7">
<div class="tc-card">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapseOptions">
    <span>📊 Options Flow — Unusual Activity</span>
    <span><span class="data-age" id="optionsAge"></span> <span class="collapse-icon">▼</span></span>
  </div>
  <div class="collapse show" id="collapseOptions">
    <div class="card-body tc-scroll p-0">
      <table class="table table-sm mb-0" id="optionsTable">
        <thead><tr>
          <th>Ticker</th><th>Bias</th><th>Call Flow</th><th>Put Flow</th><th>Top Strike</th><th>Expiry</th><th>Vol/OI</th><th>Premium</th>
        </tr></thead>
        <tbody id="optionsBody"></tbody>
      </table>
    </div>
  </div>
</div>
</div>

<!-- Dark Pool + Earnings -->
<div class="col-lg-5">

<!-- Dark Pool -->
<div class="tc-card">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapseDarkPool">
    <span>🌑 Dark Pool / Institutional Activity</span>
    <span><span class="data-age" id="darkPoolAge"></span> <span class="collapse-icon">▼</span></span>
  </div>
  <div class="collapse show" id="collapseDarkPool">
    <div class="card-body tc-scroll p-0">
      <table class="table table-sm mb-0" id="darkPoolTable">
        <thead><tr>
          <th>Ticker</th><th>Price</th><th>Inst%</th><th>Short%</th><th>Short Δ</th><th>Acc Score</th><th>Assessment</th>
        </tr></thead>
        <tbody id="darkPoolBody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- Earnings Calendar -->
<div class="tc-card">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapseEarnings">
    <span>📅 Earnings Calendar</span>
    <span><span class="data-age" id="earningsAge"></span> <span class="collapse-icon">▼</span></span>
  </div>
  <div class="collapse show" id="collapseEarnings">
    <div class="card-body tc-scroll p-0">
      <table class="table table-sm mb-0">
        <thead><tr><th>Ticker</th><th>Date</th><th>Days</th><th>Status</th><th>Price</th></tr></thead>
        <tbody id="earningsBody"></tbody>
      </table>
    </div>
  </div>
</div>

</div><!-- /col -->
</div><!-- /row -->

<!-- Row 4: Chart Vision -->
<div class="row g-2">
<div class="col-12">
<div class="tc-card">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapseVision">
    <span>🧠 Computer Vision Analysis</span>
    <span class="collapse-icon">▼</span>
  </div>
  <div class="collapse show" id="collapseVision">
    <div class="card-body">
      <div class="row g-2" id="visionGrid"></div>
    </div>
  </div>
</div>
</div>
</div>

<!-- Row 5: Signal History -->
<div class="row g-2">
<div class="col-12">
<div class="tc-card">
  <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapseHistory">
    <span>📜 Signal History & Stats</span>
    <span class="collapse-icon">▼</span>
  </div>
  <div class="collapse show" id="collapseHistory">
    <div class="card-body">
      <div class="row g-3">
        <div class="col-md-4" id="historyStats"></div>
        <div class="col-md-8">
          <div class="tc-scroll p-0">
            <table class="table table-sm mb-0">
              <thead><tr><th>Pattern</th><th>Total</th><th>Wins</th><th>Losses</th><th>Win Rate</th></tr></thead>
              <tbody id="historyPatterns"></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
</div>
</div>

</div><!-- /container -->

<!-- Scripts -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.8/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.8/js/dataTables.bootstrap5.min.js"></script>
<script>
// ========== Globals ==========
let DATA = {};
let refreshInterval = null;
let dtSignals, dtPatterns, dtMoney, dtOptions, dtDarkPool;

// ========== Utility ==========
function fmt$(n) {
  if (n == null) return '—';
  if (Math.abs(n) >= 1e6) return '$' + (n/1e6).toFixed(1) + 'M';
  if (Math.abs(n) >= 1e3) return '$' + (n/1e3).toFixed(0) + 'K';
  return '$' + n.toFixed(2);
}
function fmtPct(n) { return n == null ? '—' : (n >= 0 ? '+' : '') + n.toFixed(1) + '%'; }
function fmtNum(n) { return n == null ? '—' : n.toLocaleString(); }
function scoreClass(score, max) {
  let pct = score / max;
  if (pct >= 0.7) return 'score-high';
  if (pct >= 0.4) return 'score-med';
  return 'score-low';
}
function scoreBadge(score, max) {
  return `<span class="badge ${scoreClass(score, max)}">${score}/${max}</span>`;
}
function biasTag(bias) {
  if (!bias) return '';
  return bias === 'BULLISH'
    ? '<span class="bias-bull">🟢 BULL</span>'
    : '<span class="bias-bear">🔴 BEAR</span>';
}

function showToast(msg, bg) {
  const t = document.getElementById('mainToast');
  t.className = 'toast align-items-center border-0 text-white ' + (bg || 'bg-success');
  document.getElementById('toastBody').textContent = msg;
  new bootstrap.Toast(t, {delay:3000}).show();
}

// ========== Clock ==========
function updateClock() {
  const now = new Date();
  document.getElementById('clockDisplay').textContent = now.toLocaleString('en-US', {
    timeZone:'America/New_York', weekday:'short', month:'short', day:'numeric',
    hour:'2-digit', minute:'2-digit', second:'2-digit'
  }) + ' ET';
}
setInterval(updateClock, 1000);
updateClock();

// ========== Data Loading ==========
function loadData() {
  fetch('/api/data')
    .then(r => r.json())
    .then(data => {
      DATA = data;
      renderAll();
    })
    .catch(e => showToast('Failed to load data: ' + e, 'bg-danger'));
}

function renderAll() {
  renderMarketStatus();
  renderMarketHealth();
  renderSummary();
  renderSignals();
  renderSectors();
  renderPatterns();
  renderMoney();
  renderOptions();
  renderDarkPool();
  renderEarnings();
  renderVision();
  renderHistory();
}

// ========== Market Status ==========
function renderMarketStatus() {
  const el = document.getElementById('marketStatus');
  if (DATA.market_open) {
    el.innerHTML = '<span class="market-open">● MARKET OPEN</span>';
  } else {
    el.innerHTML = '<span class="market-closed">● MARKET CLOSED</span>';
  }
}

// ========== Market Health Overview ==========
function renderMarketHealth() {
  const mh = DATA.market_health || {};
  document.getElementById('marketHealthAge').textContent = DATA.market_health_age || '';

  if (!mh.regime) {
    document.getElementById('regimeBadge').textContent = 'NO DATA — Run Market Health Scanner';
    document.getElementById('regimeBadge').className = 'regime-badge regime-NEUTRAL';
    return;
  }

  // --- Regime Badge ---
  const regime = mh.regime.regime || 'NEUTRAL';
  const regimeCls = regime.replace(' ', '-');
  const regimeEl = document.getElementById('regimeBadge');
  regimeEl.textContent = regime;
  regimeEl.className = 'regime-badge regime-' + regimeCls;
  document.getElementById('regimeScore').textContent = `Regime Score: ${mh.regime.score}/${mh.regime.max_score}`;

  // --- Index Cards ---
  const indexMap = {SPY:'S&P 500', QQQ:'Nasdaq 100', DIA:'Dow 30', IWM:'Russell 2000'};
  ['SPY','QQQ','DIA','IWM'].forEach(ticker => {
    const idx = (mh.indices || {})[ticker];
    const el = document.getElementById('index' + ticker);
    if (!el || !idx) return;

    const changeColor = (idx.daily_change_pct || 0) >= 0 ? 'var(--tc-green)' : 'var(--tc-red)';
    const changeSign = (idx.daily_change_pct || 0) >= 0 ? '+' : '';

    const ma50cls = idx.above_50ma ? 'ma-ok' : 'ma-bad';
    const ma200cls = idx.above_200ma ? 'ma-ok' : 'ma-bad';
    const ma50icon = idx.above_50ma ? '✅' : '❌';
    const ma200icon = idx.above_200ma ? '✅' : '❌';

    // Weekly & monthly pills
    const wkColor = (idx.weekly_change_pct || 0) >= 0 ? 'var(--tc-green)' : 'var(--tc-red)';
    const moColor = (idx.monthly_change_pct || 0) >= 0 ? 'var(--tc-green)' : 'var(--tc-red)';

    el.innerHTML = `
      <div class="index-ticker">${ticker} · ${indexMap[ticker]}</div>
      <div class="index-price">$${idx.price.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
      <div class="index-change" style="color:${changeColor}">${changeSign}${(idx.daily_change_pct||0).toFixed(2)}%</div>
      <div style="font-size:10px;color:var(--tc-muted);margin:2px 0">
        <span style="color:${wkColor}">1W ${(idx.weekly_change_pct||0)>=0?'+':''}${(idx.weekly_change_pct||0).toFixed(1)}%</span>
        &nbsp;|&nbsp;
        <span style="color:${moColor}">1M ${(idx.monthly_change_pct||0)>=0?'+':''}${(idx.monthly_change_pct||0).toFixed(1)}%</span>
      </div>
      <div class="index-ma">
        <span class="${ma50cls}">${ma50icon} 50MA</span> &nbsp;
        <span class="${ma200cls}">${ma200icon} 200MA</span>
      </div>
      <div style="font-size:10px;color:var(--tc-muted);margin-top:2px">From High: ${(idx.dist_from_high_pct||0).toFixed(1)}%</div>
    `;
  });

  // --- VIX Gauge ---
  const vix = mh.vix || {};
  if (vix.level) {
    const vixClsMap = {'LOW FEAR':'vix-low','NEUTRAL':'vix-neutral','ELEVATED':'vix-elevated','HIGH FEAR':'vix-high','EXTREME FEAR':'vix-extreme'};
    const vixCls = vixClsMap[vix.label] || 'vix-neutral';
    document.getElementById('vixLevel').textContent = vix.level.toFixed(1);
    document.getElementById('vixLevel').className = 'vix-level ' + vixCls;
    document.getElementById('vixLabel').textContent = (vix.emoji || '') + ' ' + (vix.label || '');
    document.getElementById('vixLabel').className = 'vix-label ' + vixCls;
    const trendArrow = vix.trend === 'RISING' ? '📈' : '📉';
    document.getElementById('vixTrend').innerHTML = `${trendArrow} ${vix.trend} &nbsp; <span style="font-size:10px">10d avg: ${vix.avg_10d||'—'}</span>`;

    // Color the gauge border
    const gaugeEl = document.getElementById('vixGauge');
    const borderColors = {'LOW FEAR':'rgba(63,185,80,.4)','NEUTRAL':'rgba(139,148,158,.3)','ELEVATED':'rgba(210,153,34,.4)','HIGH FEAR':'rgba(240,136,62,.5)','EXTREME FEAR':'rgba(248,81,73,.5)'};
    gaugeEl.style.borderColor = borderColors[vix.label] || 'var(--tc-border)';
  }

  // --- Breadth Meters ---
  const breadth = mh.breadth || {};
  if (breadth.pct_above_50ma != null) {
    const b50 = breadth.pct_above_50ma;
    const b200 = breadth.pct_above_200ma;
    const ad = breadth.ad_ratio;
    const adPct = Math.min((ad / 3) * 100, 100); // normalize A/D ratio to 0-100 (3.0 = 100%)

    document.getElementById('breadth50val').textContent = b50 + '%';
    document.getElementById('breadth50bar').style.width = b50 + '%';
    document.getElementById('breadth50bar').style.background = b50 > 60 ? 'var(--tc-green)' : b50 > 40 ? 'var(--tc-yellow)' : 'var(--tc-red)';

    document.getElementById('breadth200val').textContent = b200 + '%';
    document.getElementById('breadth200bar').style.width = b200 + '%';
    document.getElementById('breadth200bar').style.background = b200 > 60 ? 'var(--tc-green)' : b200 > 40 ? 'var(--tc-yellow)' : 'var(--tc-red)';

    document.getElementById('breadthADval').textContent = ad.toFixed(2);
    document.getElementById('breadthADbar').style.width = adPct + '%';
    document.getElementById('breadthADbar').style.background = ad > 1.2 ? 'var(--tc-green)' : ad > 0.8 ? 'var(--tc-yellow)' : 'var(--tc-red)';

    document.getElementById('newHighsVal').textContent = '↑ Highs: ' + (breadth.new_highs || 0);
    document.getElementById('newLowsVal').textContent = '↓ Lows: ' + (breadth.new_lows || 0);

    // Breadth label badge
    const blEl = document.getElementById('breadthLabel');
    const blColors = {'STRONG':'score-high','HEALTHY':'score-high','MIXED':'score-med','WEAKENING':'score-low','POOR':'score-low'};
    blEl.textContent = breadth.breadth_label || '—';
    blEl.className = 'badge ' + (blColors[breadth.breadth_label] || 'score-neutral');
  }

  // --- Sector Rotation ---
  const rot = mh.sector_rotation || {};
  if (rot.rotation_direction) {
    const chipEl = document.getElementById('rotationChip');
    chipEl.textContent = rot.rotation_direction;
    const chipCls = rot.rotation_direction === 'RISK-ON' ? 'rotation-risk-on' : rot.rotation_direction === 'RISK-OFF' ? 'rotation-risk-off' : 'rotation-neutral';
    chipEl.className = 'rotation-chip ' + chipCls;

    const leadEl = document.getElementById('sectorLeadingList');
    const lagEl = document.getElementById('sectorLaggingList');

    if (rot.leading && rot.leading.length) {
      leadEl.innerHTML = '<span style="color:var(--tc-green);font-weight:700">▲ Leading:</span> ' +
        rot.leading.map(s => `<span style="color:var(--tc-green)">${s.sector}</span>`).join(', ');
    }
    if (rot.lagging && rot.lagging.length) {
      lagEl.innerHTML = '<span style="color:var(--tc-red);font-weight:700">▼ Lagging:</span> ' +
        rot.lagging.map(s => `<span style="color:var(--tc-red)">${s.sector}</span>`).join(', ');
    }
  }

  // --- Alerts ---
  const alerts = mh.alerts || [];
  const alertsDiv = document.getElementById('marketAlerts');
  if (alerts.length === 0) {
    alertsDiv.innerHTML = '<div style="font-size:12px;color:var(--tc-green);text-align:center;padding:6px">✅ No active market alerts</div>';
  } else {
    alertsDiv.innerHTML = '<div style="font-size:10px;color:var(--tc-muted);text-transform:uppercase;letter-spacing:.5px;font-weight:600;margin-bottom:6px">⚠️ Market Alerts</div>' +
      alerts.map(a => `<div class="market-alert alert-${a.severity}">${a.emoji} <span>${a.message}</span></div>`).join('');
  }
}

// ========== Summary Stats ==========
function renderSummary() {
  const money = DATA.money_scan?.results || [];
  const signals = DATA.signals?.all || [];
  const scan = DATA.scan_results || [];
  const earnings = DATA.earnings?.results || [];
  const options = DATA.options_flow?.results || [];

  document.getElementById('statStocksScanned').textContent = money.length || scan.length || '—';

  // Count patterns
  let patternCount = 0;
  scan.forEach(s => { patternCount += (s.patterns || []).length; });
  signals.forEach(s => { if (s.pattern) patternCount++; });
  document.getElementById('statPatterns').textContent = patternCount || '—';

  document.getElementById('statSignals').textContent = signals.length || '—';

  // Top score
  let topScore = 0;
  money.forEach(m => { if (m.score > topScore) topScore = m.score; });
  document.getElementById('statTopScore').textContent = topScore || '—';

  // Earnings danger
  let danger = earnings.filter(e => e.category === 'DANGER').length;
  document.getElementById('statEarnings').textContent = danger || '0';

  // Bull flow
  let totalBull = 0;
  options.forEach(o => { if (o.bias === 'BULLISH') totalBull += (o.call_flow || 0); });
  document.getElementById('statBullFlow').textContent = totalBull > 0 ? fmt$(totalBull) : '—';
}

// ========== Signals ==========
function renderSignals() {
  const all = DATA.signals?.all || [];
  document.getElementById('signalsAge').textContent = DATA.signals_age || '';
  const tbody = document.getElementById('signalsBody');
  tbody.innerHTML = '';

  // Sort by conviction desc
  const sorted = [...all].sort((a,b) => b.conviction - a.conviction);

  sorted.forEach(s => {
    let flags = [];
    if (s.earnings_warning) flags.push(`<span class="earn-danger">⚠️ EARN ${s.earnings_days}d</span>`);
    if ((s.premium_flow || 0) > 1000000) flags.push(`<span style="color:var(--tc-purple)">💎 BIG</span>`);

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${s.ticker}</strong></td>
      <td>${scoreBadge(s.conviction, 100)}</td>
      <td>${scoreBadge(s.stock_score, 100)}</td>
      <td>${s.pattern || '<span style="color:var(--tc-muted)">—</span>'}</td>
      <td>$${(s.price||0).toFixed(2)}</td>
      <td>${s.buy_point ? '$' + s.buy_point.toFixed(2) : '—'}</td>
      <td>${biasTag(s.flow_bias)}</td>
      <td>${s.premium_flow ? fmt$(s.premium_flow) : '—'}</td>
      <td>${flags.join(' ') || '—'}</td>
    `;
    tbody.appendChild(tr);
  });

  // Init DataTable
  if (dtSignals) dtSignals.destroy();
  dtSignals = $('#signalsTable').DataTable({
    pageLength: 15, order: [[1, 'desc']], dom: 'ftip',
    language: { search: '🔍' }
  });
}

// ========== Sectors ==========
function renderSectors() {
  document.getElementById('sectorsAge').textContent = DATA.sectors_age || '';
  const sectors = DATA.sectors?.sectors || [];
  const rotations = DATA.sectors?.rotation_signals || [];
  const summary = DATA.sectors?.summary || {};

  // Sector bars
  const barsDiv = document.getElementById('sectorBars');
  barsDiv.innerHTML = '';

  // Sort by mf_score
  const sorted = [...sectors].sort((a,b) => b.mf_score - a.mf_score);
  const maxAbs = Math.max(...sorted.map(s => Math.abs(s.mf_score)), 1);

  sorted.forEach(s => {
    const pct = Math.abs(s.mf_score) / maxAbs * 100;
    const cls = s.mf_score >= 0 ? 'sector-inflow' : 'sector-outflow';
    const rsiTag = s.rsi_label === 'OVERBOUGHT' ? ' <span class="badge bg-warning text-dark" style="font-size:9px">OB</span>' : '';

    barsDiv.innerHTML += `
      <div class="d-flex align-items-center mb-1" style="font-size:11px">
        <span style="width:100px;color:var(--tc-muted)">${s.sector}</span>
        <div class="flex-grow-1 mx-2">
          <div class="sector-bar ${cls}" style="width:${Math.max(pct,4)}%"></div>
        </div>
        <span style="width:60px;text-align:right;${s.mf_score>=0?'color:var(--tc-green)':'color:var(--tc-red)'}">${s.mf_score>=0?'+':''}${s.mf_score.toFixed(1)}</span>
        <span style="width:50px;text-align:right;color:var(--tc-muted)">RSI ${s.rsi.toFixed(0)}</span>
        ${rsiTag}
      </div>
    `;
  });

  // Rotation signals
  const rotDiv = document.getElementById('rotationSignals');
  rotDiv.innerHTML = '<div style="font-size:11px;color:var(--tc-muted);margin-bottom:6px"><strong>Money Flow Rotations:</strong></div>';
  rotations.slice(0, 5).forEach(r => {
    rotDiv.innerHTML += `
      <div style="font-size:11px;margin-bottom:3px">
        <span style="color:var(--tc-red)">${r.from_sector}</span>
        <span class="rotation-arrow"> → </span>
        <span style="color:var(--tc-green)">${r.to_sector}</span>
        <span style="color:var(--tc-muted);margin-left:8px">(${r.strength.toFixed(0)})</span>
      </div>
    `;
  });
}

// ========== Pattern Scanner ==========
function renderPatterns() {
  const results = DATA.scan_results || [];
  const tbody = document.getElementById('patternsBody');
  tbody.innerHTML = '';

  results.forEach(r => {
    const tr = document.createElement('tr');
    const patterns = (r.patterns || []).join(', ') || '<span style="color:var(--tc-muted)">—</span>';
    const bps = (r.buy_points || []).map(b => '$' + b.toFixed(2)).join(', ') || '—';
    const signals = (r.signals || []).slice(0, 3).join('<br>');

    tr.innerHTML = `
      <td><strong>${r.ticker}</strong></td>
      <td>${scoreBadge(r.score, 12)}</td>
      <td>${r.rs_rating != null ? r.rs_rating : '—'}</td>
      <td>${patterns}</td>
      <td>$${(r.price||0).toFixed(2)}</td>
      <td>${bps}</td>
      <td style="font-size:11px">${signals}</td>
    `;
    tbody.appendChild(tr);
  });

  if (dtPatterns) dtPatterns.destroy();
  dtPatterns = $('#patternsTable').DataTable({
    pageLength: 10, order: [[1, 'desc']], dom: 'ftip',
    language: { search: '🔍' }
  });
}

// ========== Money Scanner ==========
function renderMoney() {
  const results = DATA.money_scan?.results || [];
  document.getElementById('moneyAge').textContent = DATA.money_scan_age || '';
  const tbody = document.getElementById('moneyBody');
  tbody.innerHTML = '';

  results.forEach(r => {
    const tr = document.createElement('tr');
    const perfColor = r.perf_3m >= 0 ? 'var(--tc-green)' : 'var(--tc-red)';
    const fromHigh = r.from_high;
    const fhColor = fromHigh < 10 ? 'var(--tc-green)' : fromHigh < 25 ? 'var(--tc-yellow)' : 'var(--tc-red)';

    tr.innerHTML = `
      <td><strong>${r.ticker}</strong></td>
      <td>${scoreBadge(r.score, 100)}</td>
      <td>$${r.price.toFixed(2)}</td>
      <td style="color:${perfColor}">${fmtPct(r.perf_3m)}</td>
      <td>${r.vol_ratio.toFixed(2)}x</td>
      <td style="color:${fhColor}">${r.from_high.toFixed(1)}%</td>
    `;
    tbody.appendChild(tr);
  });

  if (dtMoney) dtMoney.destroy();
  dtMoney = $('#moneyTable').DataTable({
    pageLength: 15, order: [[1, 'desc']], dom: 'ftip',
    language: { search: '🔍' }
  });
}

// ========== Options Flow ==========
function renderOptions() {
  const results = DATA.options_flow?.results || [];
  document.getElementById('optionsAge').textContent = DATA.options_flow_age || '';
  const tbody = document.getElementById('optionsBody');
  tbody.innerHTML = '';

  // Sort by total flow
  const sorted = [...results].sort((a,b) => ((b.call_flow||0)+(b.put_flow||0)) - ((a.call_flow||0)+(a.put_flow||0)));

  sorted.forEach(r => {
    const topSignal = r.signals && r.signals.length > 0 ? r.signals[0] : {};
    const totalFlow = (r.call_flow || 0) + (r.put_flow || 0);
    const isBig = totalFlow > 5000000;

    const tr = document.createElement('tr');
    if (isBig) tr.style.background = 'rgba(188,140,255,.06)';

    tr.innerHTML = `
      <td><strong>${r.ticker}</strong> ${isBig ? '💎' : ''}</td>
      <td>${biasTag(r.bias)}</td>
      <td style="color:var(--tc-green)">${fmt$(r.call_flow)}</td>
      <td style="color:var(--tc-red)">${fmt$(r.put_flow)}</td>
      <td>${topSignal.strike ? '$' + topSignal.strike : '—'}</td>
      <td>${topSignal.expiry || '—'}</td>
      <td>${topSignal.vol_oi_ratio ? topSignal.vol_oi_ratio.toFixed(1) + 'x' : '—'}</td>
      <td>${topSignal.premium_flow ? fmt$(topSignal.premium_flow) : '—'}</td>
    `;
    tbody.appendChild(tr);
  });

  if (dtOptions) dtOptions.destroy();
  dtOptions = $('#optionsTable').DataTable({
    pageLength: 15, order: [[2, 'desc']], dom: 'ftip',
    language: { search: '🔍' }
  });
}

// ========== Dark Pool ==========
function renderDarkPool() {
  const results = DATA.dark_pool?.results || [];
  document.getElementById('darkPoolAge').textContent = DATA.dark_pool_age || '';
  const tbody = document.getElementById('darkPoolBody');
  tbody.innerHTML = '';

  // Sort by acc_score desc
  const sorted = [...results].sort((a,b) => (b.acc_score||0) - (a.acc_score||0));

  sorted.forEach(r => {
    const tr = document.createElement('tr');
    const assessColor = r.assessment === 'ACCUMULATING' ? 'var(--tc-green)'
                      : r.assessment === 'DISTRIBUTING' ? 'var(--tc-red)' : 'var(--tc-muted)';
    const shortColor = (r.short_change_pct || 0) < 0 ? 'var(--tc-green)' : 'var(--tc-red)';

    tr.innerHTML = `
      <td><strong>${r.ticker}</strong></td>
      <td>$${(r.price||0).toFixed(2)}</td>
      <td>${(r.inst_ownership_pct||0).toFixed(1)}%</td>
      <td>${(r.short_float_pct||0).toFixed(1)}%</td>
      <td style="color:${shortColor}">${fmtPct(r.short_change_pct)}</td>
      <td>${scoreBadge(r.acc_score || 0, 10)}</td>
      <td style="color:${assessColor};font-weight:600">${r.assessment || '—'}</td>
    `;
    tbody.appendChild(tr);
  });

  if (dtDarkPool) dtDarkPool.destroy();
  dtDarkPool = $('#darkPoolTable').DataTable({
    pageLength: 10, order: [[5, 'desc']], dom: 'ftip',
    language: { search: '🔍' }
  });
}

// ========== Earnings Calendar ==========
function renderEarnings() {
  const results = DATA.earnings?.results || [];
  document.getElementById('earningsAge').textContent = DATA.earnings_age || '';
  const tbody = document.getElementById('earningsBody');
  tbody.innerHTML = '';

  // Filter out PASSED, sort by days_until
  const upcoming = results.filter(e => e.category !== 'PASSED').sort((a,b) => (a.days_until||999) - (b.days_until||999));

  upcoming.forEach(e => {
    const cls = e.category === 'DANGER' ? 'earn-danger'
              : e.category === 'CAUTION' ? 'earn-caution' : 'earn-clear';
    const icon = e.category === 'DANGER' ? '🚨' : e.category === 'CAUTION' ? '⚠️' : '✅';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${e.ticker}</strong></td>
      <td>${e.earnings_date || '—'}</td>
      <td class="${cls}">${e.days_until != null ? e.days_until + 'd' : '—'}</td>
      <td class="${cls}">${icon} ${e.category}</td>
      <td>$${(e.price||0).toFixed(2)}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ========== Chart Vision ==========
function renderVision() {
  const intel = DATA.intel_manifest || {};
  const chartFiles = DATA.chart_files || {};
  const grid = document.getElementById('visionGrid');
  grid.innerHTML = '';

  const charts = intel.charts || [];
  const market = intel.market || {};

  if (charts.length === 0) {
    // Show available chart images even without intel
    const tickers = Object.keys(chartFiles).slice(0, 10);
    if (tickers.length === 0) {
      grid.innerHTML = '<div class="text-center p-4" style="color:var(--tc-muted)">No chart data available. Click "📸 Vision Analysis" to generate.</div>';
      return;
    }
    tickers.forEach(ticker => {
      const imgFile = chartFiles[ticker][0];
      grid.innerHTML += `
        <div class="col-md-4 col-lg-3">
          <div class="vision-card">
            <img src="/charts/${imgFile}" alt="${ticker}" loading="lazy">
            <div class="vision-body">
              <div class="d-flex justify-content-between">
                <strong>${ticker}</strong>
                <span style="color:var(--tc-muted)">No analysis</span>
              </div>
            </div>
          </div>
        </div>
      `;
    });
    return;
  }

  // Market context
  if (market.sp500) {
    grid.innerHTML += `
      <div class="col-12 mb-2">
        <div class="d-flex gap-3 flex-wrap" style="font-size:12px">
          <span>S&P 500: <strong>$${market.sp500}</strong></span>
          <span>VIX: <strong>${market.vix}</strong> (${market.vix_level})</span>
          <span>Dist Days: <strong>${market.dist_days}</strong></span>
          <span>Signal: <strong style="color:${market.signal==='CAUTION'?'var(--tc-yellow)':market.signal==='BULLISH'?'var(--tc-green)':'var(--tc-red)'}">${market.signal}</strong></span>
        </div>
      </div>
    `;
  }

  charts.forEach(c => {
    const imgPath = c.path ? '/charts/' + c.path.split('/').pop() : '';
    const scoreGrade = c.score >= 8 ? 'A' : c.score >= 6 ? 'B' : c.score >= 4 ? 'C' : 'F';
    const intelLines = (c.intel || '').split('\n').filter(l => l.trim()).slice(0, 8);

    grid.innerHTML += `
      <div class="col-md-6 col-lg-4">
        <div class="vision-card vision-grade-${scoreGrade}">
          ${imgPath ? `<img src="${imgPath}" alt="${c.ticker}" loading="lazy">` : '<div style="height:180px;background:var(--tc-bg);display:flex;align-items:center;justify-content:center;color:var(--tc-muted)">No chart</div>'}
          <div class="vision-body">
            <div class="d-flex justify-content-between mb-1">
              <strong>${c.ticker}</strong>
              <span>${scoreBadge(c.score, 12)}</span>
            </div>
            <div style="font-size:11px;white-space:pre-line;color:var(--tc-muted);max-height:120px;overflow-y:auto">${intelLines.join('\n')}</div>
          </div>
        </div>
      </div>
    `;
  });
}

// ========== Signal History ==========
function renderHistory() {
  const stats = DATA.signal_stats || {};
  const overall = stats.overall || {};
  const byPattern = stats.by_pattern || {};
  const byFlow = stats.by_flow_bias || {};

  // Stats summary
  document.getElementById('historyStats').innerHTML = `
    <div class="stat-card mb-2"><div class="stat-value">${overall.total || 0}</div><div class="stat-label">Total Signals</div></div>
    <div class="row g-2">
      <div class="col-4"><div class="stat-card"><div class="stat-value" style="color:var(--tc-green);font-size:18px">${overall.wins || 0}</div><div class="stat-label">Wins</div></div></div>
      <div class="col-4"><div class="stat-card"><div class="stat-value" style="color:var(--tc-red);font-size:18px">${overall.losses || 0}</div><div class="stat-label">Losses</div></div></div>
      <div class="col-4"><div class="stat-card"><div class="stat-value" style="color:var(--tc-cyan);font-size:18px">${overall.win_rate || 0}%</div><div class="stat-label">Win Rate</div></div></div>
    </div>
    <div class="mt-2" style="font-size:11px;color:var(--tc-muted)">
      Pending: ${overall.pending || 0} | Resolved: ${overall.resolved || 0}
    </div>
    <div class="mt-2">
      <div style="font-size:11px;color:var(--tc-muted);margin-bottom:4px"><strong>By Flow Bias:</strong></div>
      ${Object.entries(byFlow).map(([k,v]) =>
        `<div style="font-size:11px"><span class="${k==='BULLISH'?'bias-bull':'bias-bear'}">${k}</span>: ${v.total} signals, ${v.win_rate}% win</div>`
      ).join('')}
    </div>
  `;

  // By pattern
  const tbody = document.getElementById('historyPatterns');
  tbody.innerHTML = '';
  Object.entries(byPattern).forEach(([pat, v]) => {
    tbody.innerHTML += `
      <tr>
        <td>${pat}</td>
        <td>${v.total || 0}</td>
        <td style="color:var(--tc-green)">${v.wins || 0}</td>
        <td style="color:var(--tc-red)">${v.losses || 0}</td>
        <td>${v.win_rate || 0}%</td>
      </tr>
    `;
  });
  if (Object.keys(byPattern).length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:var(--tc-muted);text-align:center">No pattern data yet</td></tr>';
  }
}

// ========== Action Buttons ==========
function runFullScan() {
  const btn = document.getElementById('btnFullScan');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-grow spinner-grow-sm"></span> Scanning...';
  fetch('/api/run/full_scan', {method:'POST'})
    .then(r => r.json())
    .then(d => {
      showToast('Full scan started — this may take a few minutes');
      pollTask('full_scan', () => {
        btn.disabled = false;
        btn.innerHTML = '🔄 Run Full Scan';
        loadData();
        showToast('Full scan complete!');
      });
    })
    .catch(e => {
      btn.disabled = false;
      btn.innerHTML = '🔄 Run Full Scan';
      showToast('Error: ' + e, 'bg-danger');
    });
}

function generateReport() {
  const btn = document.getElementById('btnReport');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-grow spinner-grow-sm"></span> Generating...';
  // Generate an HTML report from current data
  fetch('/api/report', {method:'POST'})
    .then(r => r.json())
    .then(d => {
      btn.disabled = false;
      btn.innerHTML = '📊 Generate Report';
      if (d.path) {
        showToast('Report generated!');
        window.open(d.path, '_blank');
      }
    })
    .catch(e => {
      btn.disabled = false;
      btn.innerHTML = '📊 Generate Report';
      showToast('Report generated from current data');
      // Fallback: open print dialog
      window.print();
    });
}

function runMarketHealth() {
  const btn = document.getElementById('btnMarketHealth');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-grow spinner-grow-sm"></span> Scanning...';
  fetch('/api/run/scanner/market_health', {method:'POST'})
    .then(r => r.json())
    .then(d => {
      showToast('Market Health scanner started');
      pollTask('scanner_market_health', () => {
        btn.disabled = false;
        btn.innerHTML = '🌍 Market Health';
        loadData();
        showToast('Market Health updated!');
      });
    })
    .catch(e => {
      btn.disabled = false;
      btn.innerHTML = '🌍 Market Health';
      showToast('Error: ' + e, 'bg-danger');
    });
}

function runVision() {
  const btn = document.getElementById('btnVision');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-grow spinner-grow-sm"></span> Analyzing...';
  fetch('/api/run/vision', {method:'POST'})
    .then(r => r.json())
    .then(d => {
      showToast('Vision analysis started');
      pollTask('vision_analysis', () => {
        btn.disabled = false;
        btn.innerHTML = '📸 Vision Analysis';
        loadData();
        showToast('Vision analysis complete!');
      });
    })
    .catch(e => {
      btn.disabled = false;
      btn.innerHTML = '📸 Vision Analysis';
      showToast('Error: ' + e, 'bg-danger');
    });
}

function pollTask(taskId, onComplete) {
  const poll = setInterval(() => {
    fetch('/api/task/status')
      .then(r => r.json())
      .then(tasks => {
        const task = tasks[taskId];
        if (!task) { clearInterval(poll); return; }
        // Update status display
        let statusText = taskId + ': ' + task.status;
        if (task.steps) statusText = task.steps[task.steps.length - 1] || statusText;
        document.getElementById('taskStatus').textContent = statusText;

        if (task.status !== 'running') {
          clearInterval(poll);
          document.getElementById('taskStatus').textContent = '';
          if (onComplete) onComplete();
        }
      });
  }, 3000);
}

// ========== Auto Refresh ==========
function setupAutoRefresh() {
  const cb = document.getElementById('autoRefresh');
  if (cb.checked) {
    refreshInterval = setInterval(loadData, 300000); // 5 min
  }
  cb.addEventListener('change', () => {
    if (refreshInterval) clearInterval(refreshInterval);
    if (cb.checked) refreshInterval = setInterval(loadData, 300000);
  });
}

// ========== Init ==========
document.addEventListener('DOMContentLoaded', () => {
  loadData();
  setupAutoRefresh();
});
</script>
</body>
</html>
'''


# ---------------------------------------------------------------------------
# Report endpoint
# ---------------------------------------------------------------------------
@app.route('/api/report', methods=['POST'])
def api_generate_report():
    """Generate an HTML report from current data."""
    money = load_json(DATA_FILES['money_scan'])
    options = load_json(DATA_FILES['options_flow'])
    dark_pool = load_json(DATA_FILES['dark_pool'])
    signals = load_json(DATA_FILES['signals'])
    sectors = load_json(DATA_FILES['sector_rotation'])
    earnings = load_json(DATA_FILES['earnings'])
    intel = load_json(DATA_FILES['intel_manifest'])

    now = datetime.now()
    all_signals = signals.get('all', [])
    hot = signals.get('hot', [])
    strong = signals.get('strong', [])
    watch = signals.get('watch', [])

    # Top 5 picks
    top5 = sorted(all_signals, key=lambda x: x.get('conviction', 0), reverse=True)[:5]

    # Earnings danger
    earn_danger = [e for e in earnings.get('results', []) if e.get('category') == 'DANGER']

    # Sector summary
    sector_data = sectors.get('sectors', [])
    inflow = sectors.get('summary', {}).get('inflow_sectors', [])
    outflow = sectors.get('summary', {}).get('outflow_sectors', [])

    report_html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Trading Report {now.strftime("%Y-%m-%d")}</title>
<style>
body {{ font-family: system-ui; background: #0d1117; color: #e6edf3; max-width: 900px; margin: 0 auto; padding: 20px; }}
h1 {{ color: #58a6ff; border-bottom: 2px solid #30363d; padding-bottom: 10px; }}
h2 {{ color: #3fb950; margin-top: 30px; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }}
th {{ background: #161b22; color: #8b949e; padding: 8px; text-align: left; border: 1px solid #30363d; }}
td {{ padding: 8px; border: 1px solid #30363d; }}
.green {{ color: #3fb950; }} .red {{ color: #f85149; }} .yellow {{ color: #d29922; }} .blue {{ color: #58a6ff; }}
.box {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 10px 0; }}
</style></head><body>
<h1>📊 Trading Command Center Report</h1>
<p>{now.strftime("%A, %B %d, %Y %I:%M %p ET")}</p>

<div class="box">
<h2>📋 Summary</h2>
<table>
<tr><td>Stocks Scanned</td><td><strong>{len(money.get("results", []))}</strong></td></tr>
<tr><td>Active Signals</td><td><strong>{len(all_signals)}</strong></td></tr>
<tr><td>🔥 Hot Signals</td><td><strong class="green">{len(hot)}</strong></td></tr>
<tr><td>💪 Strong Signals</td><td><strong class="blue">{len(strong)}</strong></td></tr>
<tr><td>👀 Watch Signals</td><td><strong class="yellow">{len(watch)}</strong></td></tr>
<tr><td>⚠️ Earnings Danger</td><td><strong class="red">{len(earn_danger)}</strong></td></tr>
</table>
</div>

<div class="box">
<h2>🎯 Top 5 Actionable Picks</h2>
<table>
<tr><th>Ticker</th><th>Conviction</th><th>Score</th><th>Pattern</th><th>Price</th><th>Buy Point</th><th>Flow</th><th>Notes</th></tr>
'''
    for s in top5:
        flags = []
        if s.get('earnings_warning'):
            flags.append(f'⚠️ EARNINGS {s.get("earnings_days", "?")}d')
        if (s.get('premium_flow') or 0) > 1000000:
            flags.append('💎 BIG FLOW')
        report_html += f'''<tr>
<td><strong>{s["ticker"]}</strong></td>
<td class="{"green" if s["conviction"]>=70 else "yellow" if s["conviction"]>=50 else "red"}">{s["conviction"]}/100</td>
<td>{s.get("stock_score", "—")}/100</td>
<td>{s.get("pattern") or "—"}</td>
<td>${s.get("price", 0):.2f}</td>
<td>{"$" + str(round(s["buy_point"], 2)) if s.get("buy_point") else "—"}</td>
<td>{s.get("flow_bias", "—")}</td>
<td>{" ".join(flags) or "—"}</td>
</tr>'''

    report_html += f'''</table></div>

<div class="box">
<h2>🔄 Sector Rotation</h2>
<p><span class="green">Inflow:</span> {", ".join(inflow)}</p>
<p><span class="red">Outflow:</span> {", ".join(outflow)}</p>
</div>

<div class="box">
<h2>🚨 Risk Alerts — Upcoming Earnings</h2>
<table><tr><th>Ticker</th><th>Date</th><th>Days</th><th>Price</th></tr>'''

    for e in earn_danger:
        report_html += f'<tr><td class="red"><strong>{e["ticker"]}</strong></td><td>{e.get("earnings_date","—")}</td><td>{e.get("days_until","—")}d</td><td>${e.get("price",0):.2f}</td></tr>'

    report_html += '''</table></div>
<div class="box">
<h2>💰 Top Money Scanner Stocks</h2>
<table><tr><th>Ticker</th><th>Score</th><th>Price</th><th>3M Perf</th><th>From High</th></tr>'''

    for m in sorted(money.get('results', []), key=lambda x: x['score'], reverse=True)[:15]:
        perf_cls = "green" if m['perf_3m'] >= 0 else "red"
        report_html += f'<tr><td><strong>{m["ticker"]}</strong></td><td>{m["score"]}/100</td><td>${m["price"]:.2f}</td><td class="{perf_cls}">{m["perf_3m"]:+.1f}%</td><td>{m["from_high"]:.1f}%</td></tr>'

    report_html += '''</table></div>
<p style="color:#8b949e;font-size:11px;margin-top:40px;text-align:center">Generated by Trading Command Center</p>
</body></html>'''

    # Save report
    report_dir = os.path.join(SCRIPT_DIR, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    filename = f'report_{now.strftime("%Y%m%d_%H%M")}.html'
    filepath = os.path.join(report_dir, filename)
    with open(filepath, 'w') as f:
        f.write(report_html)

    return jsonify({'status': 'ok', 'path': f'/reports/{filename}'})


@app.route('/reports/<path:filename>')
def serve_report(filename):
    report_dir = os.path.join(SCRIPT_DIR, 'reports')
    return send_from_directory(report_dir, filename)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  📊 Trading Command Center")
    print(f"  http://localhost:5050")
    print("=" * 60 + "\n")
    app.run(host='0.0.0.0', port=5050, debug=False)
