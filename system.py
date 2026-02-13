#!/usr/bin/env python3
"""
TRADING SYSTEM v1.1 — Backtested & Optimized

Entry Rules (from 5yr backtest, 64-stock universe):
  - Pattern detected: Breakout, Cup w/ Handle, VCP, Flat Base, Pocket Pivot
  - SPY > 200-day MA (bull regime only)
  - Volume ≥ 1.5x avg for Breakout (other patterns don't require high vol)
  - Priority: Breakout+Cup (2.56x PF) > Cup alone (2.18x) > Breakout (1.74x)

Position Rules:
  - 10% hard stop loss
  - 20% fixed profit target
  - 60-day max hold
  - 2% risk per trade (default)
  - Max 5 open positions

Results (backtest 2021-2026):
  - 52% win rate | 3.95% avg return | 1.88x PF | 2.06 Sharpe
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys
import os

# ── Config ──────────────────────────────────────────────

UNIVERSE = [
    # Major Tech
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO', 'CRM',
    # Semis (added TSM, MU, INTC, SNDK)
    'TSM', 'MU', 'ASML', 'LRCX', 'KLAC', 'AMAT', 'MRVL', 'QCOM', 'INTC', 'SNDK',
    # AI / Cloud / Software
    'PLTR', 'NET', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'MDB', 'PANW', 'NOW', 'SHOP',
    'SMCI', 'ARM', 'APP', 'HIMS', 'DUOL', 'CELH', 'TOST', 'CAVA',
    'ORCL', 'ADBE', 'NFLX', 'LITE',
    # Finance / Crypto (added IBIT, MSTR)
    'GS', 'JPM', 'V', 'MA', 'AXP', 'COIN', 'HOOD', 'SOFI', 'NU',
    'IBIT', 'MSTR',
    # Healthcare
    'LLY', 'NVO', 'UNH', 'ISRG', 'DXCM', 'PODD', 'VRTX',
    # Consumer / Travel (added BABA, MELI)
    'UBER', 'ABNB', 'DASH', 'RKLB', 'AXON', 'DECK', 'GWW', 'URI',
    'COST', 'TJX', 'LULU', 'NKE', 'HD', 'LOW', 'BABA', 'MELI', 'CVNA',
    # Energy / Materials (added AA)
    'XOM', 'CVX', 'EOG', 'FCX', 'NUE', 'AA',
    # ETFs - added for flow tracking
    'SPY', 'QQQ', 'IWM', 'SMH', 'SLV', 'GLD', 'XLE', 'XLF',
    # Other high-flow names from Quant Data
    'CAH', 'VRT', 'NBIS', 'MCK', 'GEV',
]

STOP_LOSS = 0.10        # 10%
PROFIT_TARGET = 0.20    # 20%
MAX_HOLD_DAYS = 60
RISK_PER_TRADE = 0.02   # 2% of account
MAX_POSITIONS = 5
BREAKOUT_VOL_THRESHOLD = 1.5  # only for Breakout pattern

STATE_FILE = os.path.join(os.path.dirname(__file__), 'system_state.json')
SIGNALS_FILE = os.path.join(os.path.dirname(__file__), 'system_signals.json')


# ── Pattern Detection ──────────────────────────────────

class PatternDetector:
    """Pattern detection — same algos validated by 5yr backtest."""

    @staticmethod
    def scan(df):
        """Detect all patterns on latest bar. Returns list of pattern dicts."""
        close = df['Close'].values
        volume = df['Volume'].values
        high = df['High'].values
        low = df['Low'].values
        opn = df['Open'].values
        n = len(close)
        i = n - 1

        if n < 200:
            return []

        patterns = []
        vol_50 = np.mean(volume[max(0, i-49):i+1])
        vol_ratio = volume[i] / vol_50 if vol_50 > 0 else 0
        ma50 = np.mean(close[i-49:i+1])

        # ── Pocket Pivot ──
        # Up day, volume > max down-day vol in last 10 days, above 10MA
        if close[i] > opn[i]:
            max_dv = 0
            for k in range(max(0, i-10), i):
                if close[k] < opn[k]:
                    max_dv = max(max_dv, volume[k])
            if max_dv > 0 and volume[i] > max_dv:
                ma10 = np.mean(close[i-9:i+1])
                if close[i] > ma10:
                    patterns.append({
                        'name': 'Pocket Pivot',
                        'tier': 3,
                        'detail': f"Vol {volume[i]/max_dv:.1f}x max down-day vol"
                    })

        # ── Flat Base ──
        # 7-18% range over ~40 days, price near top, near 52wk high
        h40 = np.max(close[max(0, i-40):i+1])
        l40 = np.min(close[max(0, i-40):i+1])
        if l40 > 0:
            rng = (h40 - l40) / l40
            if 0.07 <= rng <= 0.18:
                pos_in_range = (close[i] - l40) / (h40 - l40) if h40 > l40 else 0
                if pos_in_range > 0.90:
                    h252 = np.max(close[max(0, i-252):i+1])
                    if h40 >= h252 * 0.92:
                        patterns.append({
                            'name': 'Flat Base',
                            'tier': 2,
                            'detail': f"{rng*100:.1f}% range, {pos_in_range*100:.0f}% position, near 52wk high"
                        })

        # ── VCP (Volatility Contraction) ──
        # Progressive tightening of price ranges + volume decline
        if i > 60 and close[i-40] > 0 and close[i-20] > 0:
            r1 = (np.max(close[i-60:i-30]) - np.min(close[i-60:i-30])) / close[i-40]
            r2 = (np.max(close[i-30:i-10]) - np.min(close[i-30:i-10])) / close[i-20]
            r3 = (np.max(close[i-10:i+1]) - np.min(close[i-10:i+1])) / close[i]
            if r1 > 0.05 and r2 < r1 * 0.8 and r3 < r2 * 0.8:
                v1 = np.mean(volume[i-30:i-10])
                v2 = np.mean(volume[i-10:i+1])
                if v2 < v1:
                    patterns.append({
                        'name': 'VCP',
                        'tier': 2,
                        'detail': f"Contractions: {r1*100:.0f}% → {r2*100:.0f}% → {r3*100:.0f}%, vol declining"
                    })

        # ── Breakout ──
        # Price above 20-day high, volume ≥ 1.5x, above 50MA
        if not np.isnan(ma50):
            prev_high = np.max(close[i-21:i])
            if close[i] > prev_high and vol_ratio > BREAKOUT_VOL_THRESHOLD and close[i] > ma50:
                patterns.append({
                    'name': 'Breakout',
                    'tier': 1,
                    'detail': f"Above 20d high on {vol_ratio:.1f}x volume"
                })

        # ── Cup with Handle ──
        if i > 80:
            left_high = np.max(close[i-80:i-50])
            cup_low = np.min(close[i-50:i-15])
            right_side = np.max(close[i-15:i-5])
            if left_high > 0:
                depth = (left_high - cup_low) / left_high
                recovery = right_side / left_high
                if 0.12 <= depth <= 0.35 and recovery >= 0.90:
                    handle_high = np.max(close[i-15:i-3])
                    handle_low = np.min(close[i-10:i+1])
                    if handle_high > 0:
                        hd = (handle_high - handle_low) / handle_high
                        if 0.03 <= hd <= 0.15:
                            hv = np.mean(volume[i-10:i+1])
                            bv = np.mean(volume[i-50:i-10])
                            if hv < bv:
                                patterns.append({
                                    'name': 'Cup w/ Handle',
                                    'tier': 1,
                                    'detail': f"Depth {depth*100:.0f}%, handle {hd*100:.0f}%, vol drying up"
                                })

        return patterns

    @staticmethod
    def watchlist_scan(df):
        """
        Detect stocks that are CLOSE to forming patterns or have structural strength.
        Returns list of near-miss patterns with what's needed to trigger.
        """
        close = df['Close'].values
        volume = df['Volume'].values
        high = df['High'].values
        low = df['Low'].values
        opn = df['Open'].values
        n = len(close)
        i = n - 1

        if n < 200:
            return []

        near_misses = []
        vol_50 = np.mean(volume[max(0, i-49):i+1])
        vol_ratio = volume[i] / vol_50 if vol_50 > 0 else 0
        ma50 = np.mean(close[i-49:i+1])
        ma200 = np.mean(close[max(0, i-199):i+1]) if n >= 200 else ma50
        h252 = np.max(close[max(0, i-252):i+1])
        pct_from_high = (h252 - close[i]) / h252
        perf_3m = (close[i] / close[i-63] - 1) if i >= 63 else 0

        # Only watch stocks within 15% of high and above at least one MA
        if pct_from_high > 0.15 or (close[i] < ma50 and close[i] < ma200):
            return []

        # ── Near Flat Base ──
        h40 = np.max(close[max(0, i-40):i+1])
        l40 = np.min(close[max(0, i-40):i+1])
        if l40 > 0:
            rng = (h40 - l40) / l40
            pos_in_range = (close[i] - l40) / (h40 - l40) if h40 > l40 else 0
            near_high = h40 / h252 if h252 > 0 else 0
            if 0.05 <= rng <= 0.25 and near_high >= 0.85:
                needs = []
                if rng > 0.18:
                    needs.append(f"range tighten ({rng*100:.0f}%→<18%)")
                if pos_in_range < 0.90:
                    needs.append(f"price to top ({pos_in_range*100:.0f}%→>90%)")
                if near_high < 0.92:
                    needs.append(f"closer to high ({near_high*100:.0f}%→>92%)")
                if not needs:
                    needs.append("already qualifies")
                near_misses.append({
                    'name': 'Flat Base' if not needs or needs == ['already qualifies'] else 'Near Flat Base',
                    'needs': needs,
                    'progress': f"{rng*100:.0f}% range, {pos_in_range*100:.0f}% pos, {near_high*100:.0f}% of high"
                })

        # ── Near VCP ──
        if i > 60 and close[i-40] > 0 and close[i-20] > 0:
            r1 = (np.max(close[i-60:i-30]) - np.min(close[i-60:i-30])) / close[i-40]
            r2 = (np.max(close[i-30:i-10]) - np.min(close[i-30:i-10])) / close[i-20]
            r3 = (np.max(close[i-10:i+1]) - np.min(close[i-10:i+1])) / close[i]
            v1 = np.mean(volume[i-30:i-10])
            v2 = np.mean(volume[i-10:i+1])
            if r1 > 0.05 and r2 < r1:  # at least first contraction exists
                needs = []
                if r2 >= r1 * 0.8:
                    needs.append(f"2nd tighten ({r2*100:.0f}%→<{r1*0.8*100:.0f}%)")
                if r3 >= r2 * 0.8:
                    needs.append(f"3rd tighten ({r3*100:.0f}%→<{r2*0.8*100:.0f}%)")
                if v2 >= v1:
                    needs.append("vol decline")
                if not needs:
                    needs.append("already qualifies")
                near_misses.append({
                    'name': 'VCP' if not needs or needs == ['already qualifies'] else 'Near VCP',
                    'needs': needs,
                    'progress': f"{r1*100:.0f}%→{r2*100:.0f}%→{r3*100:.0f}%"
                })

        # ── Near Breakout ──
        prev_high = np.max(close[i-21:i])
        if close[i] > ma50:
            pct_to_bo = (prev_high - close[i]) / close[i]
            if 0 < pct_to_bo <= 0.05:  # within 5% of breakout
                needs = [f"${prev_high:.2f} ({pct_to_bo*100:.1f}% away)"]
                if vol_ratio < BREAKOUT_VOL_THRESHOLD:
                    needs.append(f"vol ({vol_ratio:.1f}x→>{BREAKOUT_VOL_THRESHOLD}x)")
                near_misses.append({
                    'name': 'Near Breakout',
                    'needs': needs,
                    'progress': f"${close[i]:.2f} vs 20d high ${prev_high:.2f}"
                })

        # ── Strong Momentum (worth watching even without a pattern) ──
        if pct_from_high <= 0.08 and close[i] > ma50 and close[i] > ma200 and perf_3m > 0.08:
            if not any(p['name'] in ['Flat Base', 'VCP'] for p in near_misses):
                near_misses.append({
                    'name': 'Momentum',
                    'needs': ['pattern to form'],
                    'progress': f"{pct_from_high*100:.1f}% from high, +{perf_3m*100:.0f}% 3M"
                })

        return near_misses


# ── Market Regime ──────────────────────────────────────

def check_market_regime():
    """Check if SPY is above 200MA."""
    try:
        spy = yf.download('SPY', period='1y', progress=False)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)
        close = spy['Close']
        ma200 = close.rolling(200).mean().iloc[-1]
        price = close.iloc[-1]
        return price > ma200, float(price), float(ma200)
    except:
        return True, 0, 0


# ── Position Sizing ───────────────────────────────────

def calculate_position(account_size, entry_price, stop_pct=STOP_LOSS, risk_pct=RISK_PER_TRADE):
    """Calculate shares based on fixed-risk sizing."""
    risk_dollars = account_size * risk_pct
    stop_price = entry_price * (1 - stop_pct)
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return 0, 0, 0
    shares = int(risk_dollars / risk_per_share)
    cost = shares * entry_price
    return shares, cost, stop_price


# ── Signal Scoring ────────────────────────────────────

def score_signal(patterns, vol_ratio, num_patterns):
    """Score a signal 1-100 based on pattern quality."""
    score = 0

    tier_scores = {1: 30, 2: 20, 3: 10}
    best_tier = min(p['tier'] for p in patterns)
    score += tier_scores.get(best_tier, 10)

    if num_patterns >= 3:
        score += 25
    elif num_patterns >= 2:
        score += 15

    names = set(p['name'] for p in patterns)
    if 'Breakout' in names and 'Cup w/ Handle' in names:
        score += 20  # 2.56x PF combo
    elif 'VCP' in names and 'Flat Base' in names:
        score += 15  # 1.91x PF combo

    if vol_ratio >= 3.0:
        score += 10
    elif vol_ratio >= 2.0:
        score += 7
    elif vol_ratio >= 1.5:
        score += 5

    return min(100, score)


# ── State Management ──────────────────────────────────

def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            'positions': [],
            'closed_trades': [],
            'account_size': 25000,
            'last_scan': None,
            'regime': 'bull'
        }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)


# ── Core Scanner ──────────────────────────────────────

def scan(quiet=False):
    """Full system scan. Returns ranked signals."""
    if not quiet:
        print(f"\n{'='*60}")
        print(f"  SYSTEM SCAN — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}\n")

    is_bull, spy_price, spy_ma200 = check_market_regime()
    state = load_state()

    if not quiet:
        regime = "BULL" if is_bull else "BEAR"
        print(f"  Market: {regime} (SPY ${spy_price:.2f} vs 200MA ${spy_ma200:.2f})")

    if not is_bull:
        state['regime'] = 'bear'
        save_state(state)
        if not quiet:
            print(f"\n  SPY below 200MA — NO NEW ENTRIES")
            print(f"  Defensive mode. Manage existing positions only.\n")
        return [], []

    state['regime'] = 'bull'

    open_pos = len(state.get('positions', []))
    slots = MAX_POSITIONS - open_pos
    if not quiet:
        print(f"  Positions: {open_pos}/{MAX_POSITIONS} ({slots} slot{'s' if slots != 1 else ''} open)")
        print(f"  Account: ${state.get('account_size', 25000):,.0f}")
        print()

    if not quiet:
        print(f"  Scanning {len(UNIVERSE)} stocks...\n")

    signals = []
    watchlist = []

    for idx, ticker in enumerate(UNIVERSE):
        try:
            df = yf.download(ticker, period='2y', progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) < 200:
                continue

            close = df['Close'].values
            volume = df['Volume'].values
            price = float(close[-1])
            vol_50 = float(np.mean(volume[-50:]))
            vol_ratio = float(volume[-1] / vol_50) if vol_50 > 0 else 0
            ma50 = float(np.mean(close[-50:]))
            ma200 = float(np.mean(close[-200:])) if len(close) >= 200 else ma50
            h252 = float(np.max(close[-252:]))
            pct_from_high = (h252 - price) / h252 if h252 > 0 else 1

            # Detect patterns (no volume gate — patterns themselves validate)
            patterns = PatternDetector.scan(df)

            if patterns:
                score = score_signal(patterns, vol_ratio, len(patterns))
                shares, cost, stop_price = calculate_position(
                    state.get('account_size', 25000), price)
                target_price = price * (1 + PROFIT_TARGET)

                signals.append({
                    'ticker': ticker,
                    'price': round(price, 2),
                    'score': score,
                    'patterns': [p['name'] for p in patterns],
                    'pattern_details': [p['detail'] for p in patterns],
                    'vol_ratio': round(vol_ratio, 2),
                    'num_patterns': len(patterns),
                    'shares': shares,
                    'cost': round(cost, 2),
                    'stop_price': round(stop_price, 2),
                    'target_price': round(target_price, 2),
                    'pct_from_high': round(pct_from_high * 100, 1),
                    'above_ma50': price > ma50,
                    'above_ma200': price > ma200,
                    'scan_time': datetime.now().isoformat()
                })
            else:
                # Check watchlist (near-miss patterns)
                near = PatternDetector.watchlist_scan(df)
                if near:
                    watchlist.append({
                        'ticker': ticker,
                        'price': round(price, 2),
                        'pct_from_high': round(pct_from_high * 100, 1),
                        'above_ma50': price > ma50,
                        'above_ma200': price > ma200,
                        'vol_ratio': round(vol_ratio, 2),
                        'near_patterns': near
                    })

            if not quiet:
                sys.stdout.write(f"\r  {idx+1}/{len(UNIVERSE)}: {ticker}          ")
                sys.stdout.flush()

        except Exception as e:
            continue

    if not quiet:
        sys.stdout.write(f"\r{'':60}\r")

    signals.sort(key=lambda x: x['score'], reverse=True)

    # Save
    output = {
        'timestamp': datetime.now().isoformat(),
        'regime': 'bull',
        'spy': {'price': spy_price, 'ma200': spy_ma200},
        'signals': signals,
        'watchlist': watchlist,
        'open_slots': slots
    }
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    state['last_scan'] = datetime.now().isoformat()
    save_state(state)

    # ── Print Signals ──
    if not quiet:
        print(f"  ACTIONABLE SIGNALS: {len(signals)}")
        if signals:
            print(f"\n  {'#':>3} {'Ticker':<7} {'Price':>8} {'Score':>5} {'Patterns':<28} {'Vol':>5} {'From Hi':>7} {'Stop':>8} {'Target':>8}")
            print(f"  {'─'*3} {'─'*7} {'─'*8} {'─'*5} {'─'*28} {'─'*5} {'─'*7} {'─'*8} {'─'*8}")
            for i, s in enumerate(signals[:10], 1):
                pats = '+'.join(s['patterns'][:3])
                print(f"  {i:>3} {s['ticker']:<7} ${s['price']:>7.2f} {s['score']:>4} {pats:<28} {s['vol_ratio']:>4.1f}x {s['pct_from_high']:>5.1f}% ${s['stop_price']:>7.2f} ${s['target_price']:>7.2f}")

            # Top pick detail
            top = signals[0]
            print(f"\n  TOP PICK: {top['ticker']}")
            print(f"  Score: {top['score']}/100 | Patterns: {', '.join(top['patterns'])}")
            for d in top['pattern_details']:
                print(f"    -> {d}")
            print(f"  Entry: ${top['price']:.2f} | Stop: ${top['stop_price']:.2f} (-10%) | Target: ${top['target_price']:.2f} (+20%)")
            print(f"  Shares: {top['shares']} (${top['cost']:,.2f} / 2% risk) | Max hold: {MAX_HOLD_DAYS}d")

        # ── Print Watchlist ──
        print(f"\n  {'─'*60}")
        print(f"  WATCHLIST ({len(watchlist)} stocks near pattern completion):")
        if watchlist:
            # Sort: fewer needs = closer to triggering
            watchlist.sort(key=lambda w: sum(len(p['needs']) for p in w['near_patterns']))
            print()
            for w in watchlist[:15]:
                ma_str = ""
                if w['above_ma50'] and w['above_ma200']:
                    ma_str = ">50&200MA"
                elif w['above_ma50']:
                    ma_str = ">50MA"
                elif w['above_ma200']:
                    ma_str = ">200MA"
                else:
                    ma_str = "<MAs"

                print(f"  {w['ticker']:<7} ${w['price']:>8.2f} | {w['pct_from_high']:>5.1f}% from high | {ma_str:<10} | vol {w['vol_ratio']:.1f}x")
                for p in w['near_patterns']:
                    needs_str = ' + '.join(p['needs'])
                    print(f"          {p['name']}: {p['progress']}")
                    print(f"          Needs: {needs_str}")
                print()
        else:
            print("  None\n")

    return signals, watchlist


# ── Position Management ───────────────────────────────

def add_position(ticker, entry_price, shares, patterns=None):
    """Add a new position to track."""
    state = load_state()
    pos = {
        'ticker': ticker,
        'entry_price': entry_price,
        'shares': shares,
        'entry_date': datetime.now().strftime('%Y-%m-%d'),
        'stop_price': round(entry_price * (1 - STOP_LOSS), 2),
        'target_price': round(entry_price * (1 + PROFIT_TARGET), 2),
        'max_exit_date': (datetime.now() + timedelta(days=MAX_HOLD_DAYS)).strftime('%Y-%m-%d'),
        'patterns': patterns or [],
        'status': 'open'
    }
    state['positions'].append(pos)
    save_state(state)
    print(f"  Added {ticker}: {shares} shares @ ${entry_price:.2f}")
    print(f"  Stop: ${pos['stop_price']:.2f} | Target: ${pos['target_price']:.2f} | Exit by: {pos['max_exit_date']}")
    return pos


def check_positions():
    """Check all open positions against stops/targets/time."""
    state = load_state()
    positions = state.get('positions', [])
    if not positions:
        print("  No open positions.")
        return []

    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n  {'='*65}")
    print(f"  POSITION CHECK — {today}")
    print(f"  {'='*65}\n")

    alerts = []
    for pos in positions:
        ticker = pos['ticker']
        try:
            df = yf.download(ticker, period='5d', progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            price = float(df['Close'].iloc[-1])
        except:
            price = pos['entry_price']

        pnl = (price - pos['entry_price']) / pos['entry_price']
        days_held = (datetime.now() - datetime.strptime(pos['entry_date'], '%Y-%m-%d')).days

        status = 'HOLD'
        emoji = '  '
        if price <= pos['stop_price']:
            status = 'STOP HIT — SELL'
            emoji = '!!'
            alerts.append(f"!! {ticker} hit stop at ${pos['stop_price']:.2f}")
        elif price >= pos['target_price']:
            status = 'TARGET HIT — SELL'
            emoji = '>>'
            alerts.append(f">> {ticker} hit target at ${pos['target_price']:.2f}")
        elif today >= pos['max_exit_date']:
            status = 'TIME EXIT — SELL'
            emoji = '>>'
            alerts.append(f">> {ticker} max hold reached ({MAX_HOLD_DAYS}d)")
        elif pnl < -0.05:
            status = 'WATCH'
            emoji = '?'

        pnl_str = f"{'+' if pnl >= 0 else ''}{pnl*100:.1f}%"
        pnl_dollar = pnl * pos['shares'] * pos['entry_price']

        print(f"  {emoji} {ticker:<6} | ${price:>8.2f} | {pnl_str:>7} (${pnl_dollar:>+8.2f}) | {days_held}d/{MAX_HOLD_DAYS}d | {status}")

    if alerts:
        print(f"\n  ALERTS:")
        for a in alerts:
            print(f"    {a}")
    print()
    return alerts


def close_position(ticker, exit_price, reason='manual'):
    """Close a position and record the trade."""
    state = load_state()
    pos = None
    for p in state['positions']:
        if p['ticker'].upper() == ticker.upper():
            pos = p
            break

    if not pos:
        print(f"  No open position for {ticker}")
        return None

    pnl = (exit_price - pos['entry_price']) / pos['entry_price']
    pnl_dollar = pnl * pos['shares'] * pos['entry_price']
    days = (datetime.now() - datetime.strptime(pos['entry_date'], '%Y-%m-%d')).days

    trade = {
        **pos,
        'exit_price': exit_price,
        'exit_date': datetime.now().strftime('%Y-%m-%d'),
        'return_pct': round(pnl * 100, 2),
        'return_dollar': round(pnl_dollar, 2),
        'days_held': days,
        'exit_reason': reason
    }

    state['positions'] = [p for p in state['positions'] if p['ticker'].upper() != ticker.upper()]
    state['closed_trades'].append(trade)
    state['account_size'] = state.get('account_size', 25000) + pnl_dollar
    save_state(state)

    win = pnl >= 0
    print(f"  {'WIN' if win else 'LOSS'}: {ticker} {pnl*100:+.1f}% (${pnl_dollar:+.2f}) in {days}d — {reason}")
    return trade


def performance():
    """Show trading performance summary."""
    state = load_state()
    trades = state.get('closed_trades', [])

    if not trades:
        print("  No closed trades yet.")
        return

    returns = [t['return_pct'] / 100 for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gw = sum(wins) if wins else 0
    gl = abs(sum(losses)) if losses else 0.001

    print(f"\n  {'='*50}")
    print(f"  PERFORMANCE SUMMARY")
    print(f"  {'='*50}\n")
    print(f"  Total trades:    {len(trades)}")
    print(f"  Win rate:        {len(wins)/len(trades)*100:.1f}%")
    print(f"  Avg return:      {np.mean(returns)*100:+.2f}%")
    if wins:
        print(f"  Avg win:         {np.mean(wins)*100:+.2f}%")
    if losses:
        print(f"  Avg loss:        {np.mean(losses)*100:.2f}%")
    print(f"  Profit factor:   {gw/gl:.2f}x")
    print(f"  Account:         ${state.get('account_size', 25000):,.2f}")

    total_pnl = sum(t['return_dollar'] for t in trades)
    print(f"  Total P&L:       ${total_pnl:+,.2f}")
    print()

    print(f"  Last 5 trades:")
    for t in trades[-5:]:
        win = t['return_pct'] > 0
        print(f"    {'W' if win else 'L'} {t['ticker']} {t['return_pct']:+.1f}% (${t['return_dollar']:+.2f}) — {t['exit_reason']} — {t['days_held']}d")
    print()


def set_account(size):
    """Set account size."""
    state = load_state()
    state['account_size'] = size
    save_state(state)
    print(f"  Account size set to ${size:,.2f}")


# ── CLI ───────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Trading System v1.1')
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('scan', help='Full scan: signals + watchlist')
    sub.add_parser('watchlist', help='Watchlist only (faster)')
    sub.add_parser('check', help='Check open positions')

    p_add = sub.add_parser('add', help='Add position')
    p_add.add_argument('ticker')
    p_add.add_argument('price', type=float)
    p_add.add_argument('shares', type=int)
    p_add.add_argument('--patterns', nargs='*', default=[])

    p_close = sub.add_parser('close', help='Close position')
    p_close.add_argument('ticker')
    p_close.add_argument('price', type=float)
    p_close.add_argument('--reason', default='manual')

    sub.add_parser('perf', help='Performance summary')

    p_acct = sub.add_parser('account', help='Set account size')
    p_acct.add_argument('size', type=float)

    sub.add_parser('status', help='Quick status')

    args = parser.parse_args()

    if args.command == 'scan':
        scan()
    elif args.command == 'watchlist':
        # Just show last saved watchlist
        try:
            with open(SIGNALS_FILE, 'r') as f:
                data = json.load(f)
            wl = data.get('watchlist', [])
            print(f"\n  Watchlist ({len(wl)} stocks) — from {data['timestamp'][:16]}\n")
            for w in wl[:15]:
                print(f"  {w['ticker']:<7} ${w['price']:>8.2f} | {w['pct_from_high']:>5.1f}% from high")
                for p in w['near_patterns']:
                    print(f"          {p['name']}: {p['progress']}")
                    print(f"          Needs: {' + '.join(p['needs'])}")
                print()
        except:
            print("  No watchlist data. Run 'scan' first.")
    elif args.command == 'check':
        check_positions()
    elif args.command == 'add':
        add_position(args.ticker.upper(), args.price, args.shares, args.patterns)
    elif args.command == 'close':
        close_position(args.ticker.upper(), args.price, args.reason)
    elif args.command == 'perf':
        performance()
    elif args.command == 'account':
        set_account(args.size)
    elif args.command == 'status':
        state = load_state()
        is_bull, spy_p, spy_ma = check_market_regime()
        regime = "BULL" if is_bull else "BEAR"
        n_pos = len(state.get('positions', []))
        n_trades = len(state.get('closed_trades', []))
        print(f"\n  System v1.1 Status")
        print(f"  Market: {regime} (SPY ${spy_p:.2f} vs 200MA ${spy_ma:.2f})")
        print(f"  Account: ${state.get('account_size', 25000):,.2f}")
        print(f"  Open: {n_pos}/{MAX_POSITIONS} | Closed: {n_trades}")
        print(f"  Last scan: {state.get('last_scan', 'never')}")
        print(f"  Rules: 10% stop | 20% target | 60d max | 2% risk\n")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
