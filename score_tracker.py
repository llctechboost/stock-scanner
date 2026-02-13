#!/usr/bin/env python3
"""
Score Tracker — Monitors stocks scoring 80+ on the Money Scanner.
Tracks when stocks cross above/below the 80 threshold.
Sends alerts via Telegram when new stocks hit 80+.
"""
import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCAN_FILE = os.path.join(SCRIPT_DIR, 'money_scan_latest.json')
TRACKER_FILE = os.path.join(SCRIPT_DIR, 'score_tracker.json')
THRESHOLD = 80

def load_scan():
    with open(SCAN_FILE) as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get('results', [])

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE) as f:
            return json.load(f)
    return {"watchlist": {}, "history": [], "alerts": []}

def save_tracker(tracker):
    with open(TRACKER_FILE, 'w') as f:
        json.dump(tracker, f, indent=2, default=str)

def run():
    results = load_scan()
    tracker = load_tracker()
    now = datetime.now().isoformat()
    
    # Current 80+ stocks
    current_80 = {}
    for s in results:
        score = s.get('score', 0)
        ticker = s.get('ticker', '')
        if score >= THRESHOLD:
            current_80[ticker] = {
                'score': score,
                'price': s.get('price', 0),
                'perf_3m': s.get('perf_3m', s.get('3m_perf', 0)),
                'vol_ratio': s.get('vol_ratio', 0),
                'pct_from_high': s.get('pct_from_high', s.get('from_high', 0)),
                'last_seen': now
            }
    
    # Previous watchlist
    prev_watchlist = tracker.get('watchlist', {})
    
    # Detect new entries (crossed above 80)
    new_entries = []
    for ticker, data in current_80.items():
        if ticker not in prev_watchlist:
            new_entries.append({
                'ticker': ticker,
                'score': data['score'],
                'price': data['price'],
                'timestamp': now,
                'event': 'CROSSED_ABOVE_80'
            })
    
    # Detect exits (dropped below 80)
    exits = []
    for ticker in prev_watchlist:
        if ticker not in current_80:
            # Find current score
            current_score = 0
            for s in results:
                if s.get('ticker') == ticker:
                    current_score = s.get('score', 0)
                    break
            exits.append({
                'ticker': ticker,
                'prev_score': prev_watchlist[ticker].get('score', 0),
                'current_score': current_score,
                'timestamp': now,
                'event': 'DROPPED_BELOW_80'
            })
    
    # Detect score changes for existing 80+ stocks
    score_changes = []
    for ticker, data in current_80.items():
        if ticker in prev_watchlist:
            prev_score = prev_watchlist[ticker].get('score', 0)
            if data['score'] != prev_score:
                score_changes.append({
                    'ticker': ticker,
                    'prev_score': prev_score,
                    'new_score': data['score'],
                    'change': data['score'] - prev_score,
                    'timestamp': now
                })
    
    # Update tracker
    tracker['watchlist'] = current_80
    tracker['last_updated'] = now
    tracker['history'].extend(new_entries + exits)
    # Keep last 500 history entries
    tracker['history'] = tracker['history'][-500:]
    
    # Build alert
    alerts = []
    if new_entries:
        for e in new_entries:
            alerts.append(f"🟢 NEW 80+ | {e['ticker']} scored {e['score']} @ ${current_80[e['ticker']]['price']:.2f}")
    if exits:
        for e in exits:
            alerts.append(f"🔴 DROPPED | {e['ticker']} fell from {e['prev_score']} to {e['current_score']}")
    if score_changes:
        for c in score_changes:
            arrow = '📈' if c['change'] > 0 else '📉'
            alerts.append(f"{arrow} CHANGE | {c['ticker']}: {c['prev_score']} → {c['new_score']} ({c['change']:+.1f})")
    
    tracker['alerts'] = alerts
    save_tracker(tracker)
    
    # Print report
    print(f"\n{'='*60}")
    print(f"📊 SCORE TRACKER — Stocks Scoring {THRESHOLD}+")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    if current_80:
        print(f"\n🎯 CURRENT {THRESHOLD}+ WATCHLIST ({len(current_80)} stocks):\n")
        for ticker, data in sorted(current_80.items(), key=lambda x: x[1]['score'], reverse=True):
            status = "🆕" if ticker in [e['ticker'] for e in new_entries] else "  "
            print(f"  {status} {ticker:6s} | Score: {data['score']:5.1f} | ${data['price']:>8.2f} | 3M: {data['perf_3m']:>6.1f}% | Vol: {data['vol_ratio']:.2f}x | From High: {data['pct_from_high']:.1f}%")
    else:
        print(f"\n  No stocks currently scoring {THRESHOLD}+")
    
    if alerts:
        print(f"\n⚡ ALERTS:")
        for a in alerts:
            print(f"  {a}")
    
    # Near misses (75-79)
    near_misses = [(s.get('ticker'), s.get('score', 0), s.get('price', 0)) 
                   for s in results if 75 <= s.get('score', 0) < 80]
    near_misses.sort(key=lambda x: x[1], reverse=True)
    
    if near_misses:
        print(f"\n👀 NEAR MISSES (75-79):")
        for ticker, score, price in near_misses:
            print(f"  {ticker:6s} | Score: {score:5.1f} | ${price:>8.2f}")
    
    print(f"\n{'='*60}")
    
    return {
        'current_80': current_80,
        'new_entries': new_entries,
        'exits': exits,
        'score_changes': score_changes,
        'alerts': alerts,
        'near_misses': near_misses
    }

if __name__ == '__main__':
    run()
