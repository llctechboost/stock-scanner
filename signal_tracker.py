#!/usr/bin/env python3
"""
Signal Tracker - Win rate feedback loop.
Tracks every signal generated vs actual outcomes using SQLite.
Commands: record, update, stats, report
"""
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import json
import sys
import os
from colorama import Fore, Style, init

init(autoreset=True)

DB_FILE = 'signal_history.db'
STATS_FILE = 'signal_stats_latest.json'

WIN_THRESHOLD = 0.05   # 5% gain = win
LOSS_THRESHOLD = -0.05  # 5% loss = loss


def get_db():
    """Get database connection and ensure table exists."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            conviction TEXT,
            pattern TEXT,
            flow_bias TEXT,
            price_at_signal REAL,
            price_1w REAL,
            price_2w REAL,
            price_4w REAL,
            pnl_1w REAL,
            pnl_2w REAL,
            pnl_4w REAL,
            result TEXT,
            last_updated TEXT,
            UNIQUE(signal_date, ticker)
        )
    ''')
    conn.commit()
    return conn


def load_signals_file():
    """Load signals from signals_latest.json."""
    for path in ['signals_latest.json', '../completeinceptionmigrationeverything2026013101/signals_latest.json']:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                signals = data.get('all', data.get('signals', data.get('results', [])))
                if signals:
                    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Loaded {len(signals)} signals from {path}")
                    return signals, data.get('timestamp', datetime.now().isoformat())
            except Exception as e:
                print(f"  {Fore.RED}✗{Style.RESET_ALL} Error reading {path}: {e}")
    return [], None


def cmd_record():
    """Record current signals into the database."""
    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📝 SIGNAL TRACKER — Record Signals")
    print(f"{Fore.CYAN}{'='*65}{Style.RESET_ALL}\n")

    signals, timestamp = load_signals_file()
    if not signals:
        print(f"  {Fore.RED}No signals found! Run the signal generator first.{Style.RESET_ALL}\n")
        return

    conn = get_db()
    recorded = 0
    skipped = 0
    today = datetime.now().strftime('%Y-%m-%d')

    for sig in signals:
        ticker = sig.get('ticker')
        if not ticker:
            continue

        conviction = str(sig.get('conviction', sig.get('score', 'N/A')))
        pattern = sig.get('pattern', sig.get('type', 'UNKNOWN'))
        flow_bias = sig.get('flow_bias', sig.get('bias', 'UNKNOWN'))
        price = sig.get('price', sig.get('price_at_signal', 0))

        # If price is missing, fetch it
        if not price:
            try:
                hist = yf.Ticker(ticker).history(period='1d')
                if not hist.empty:
                    price = float(hist['Close'].iloc[-1])
            except:
                price = 0

        try:
            conn.execute('''
                INSERT INTO signals (signal_date, ticker, conviction, pattern, flow_bias, price_at_signal, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (today, ticker, conviction, pattern, flow_bias, price, datetime.now().isoformat()))
            recorded += 1
            print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Recorded {ticker} — {conviction} — ${price:.2f}")
        except sqlite3.IntegrityError:
            skipped += 1
            print(f"  {Fore.YELLOW}⤳{Style.RESET_ALL} Skipped {ticker} (already recorded for {today})")

    conn.commit()
    conn.close()

    print(f"\n  {Fore.WHITE}Recorded: {Fore.GREEN}{recorded}{Style.RESET_ALL}  Skipped: {Fore.YELLOW}{skipped}{Style.RESET_ALL}\n")


def cmd_update():
    """Update past signals with current prices and calculate P&L."""
    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"{Fore.CYAN}{Style.BRIGHT}🔄 SIGNAL TRACKER — Update Outcomes")
    print(f"{Fore.CYAN}{'='*65}{Style.RESET_ALL}\n")

    conn = get_db()
    rows = conn.execute('''
        SELECT * FROM signals WHERE result IS NULL OR result = '' ORDER BY signal_date
    ''').fetchall()

    if not rows:
        print(f"  {Fore.YELLOW}No pending signals to update.{Style.RESET_ALL}\n")
        conn.close()
        return

    print(f"  {Fore.YELLOW}Updating {len(rows)} signals...{Style.RESET_ALL}\n")

    updated = 0
    for row in rows:
        ticker = row['ticker']
        signal_date = row['signal_date']
        price_at = row['price_at_signal']

        if not price_at or price_at == 0:
            continue

        sig_dt = datetime.strptime(signal_date, '%Y-%m-%d')
        now = datetime.now()
        days_elapsed = (now - sig_dt).days

        try:
            # Fetch history from signal date
            start = sig_dt - timedelta(days=1)
            end = now + timedelta(days=1)
            hist = yf.download(ticker, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), progress=False)
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            if hist.empty:
                continue

            close = hist['Close']

            # Find prices at 1w, 2w, 4w marks
            def get_price_at_offset(offset_days):
                target = sig_dt + timedelta(days=offset_days)
                # Find closest available date
                available = close.index[close.index >= pd.Timestamp(target)]
                if len(available) > 0:
                    return float(close.loc[available[0]])
                return None

            price_1w = get_price_at_offset(7) if days_elapsed >= 7 else None
            price_2w = get_price_at_offset(14) if days_elapsed >= 14 else None
            price_4w = get_price_at_offset(28) if days_elapsed >= 28 else None

            # Current price for incomplete windows
            current = float(close.iloc[-1])

            # Calculate P&L
            pnl_1w = round((price_1w / price_at - 1) * 100, 2) if price_1w else None
            pnl_2w = round((price_2w / price_at - 1) * 100, 2) if price_2w else None
            pnl_4w = round((price_4w / price_at - 1) * 100, 2) if price_4w else None

            # Determine result
            result = None
            if days_elapsed >= 28 and pnl_4w is not None:
                # Full evaluation window
                best_pnl = max(filter(None, [pnl_1w, pnl_2w, pnl_4w]))
                worst_pnl = min(filter(None, [pnl_1w, pnl_2w, pnl_4w]))

                if best_pnl >= WIN_THRESHOLD * 100:
                    result = 'WIN'
                elif worst_pnl <= LOSS_THRESHOLD * 100:
                    result = 'LOSS'
                else:
                    result = 'FLAT'
            elif days_elapsed >= 7:
                # Partial — check if already hit thresholds
                available_pnls = [p for p in [pnl_1w, pnl_2w, pnl_4w] if p is not None]
                if available_pnls:
                    best = max(available_pnls)
                    worst = min(available_pnls)
                    if best >= WIN_THRESHOLD * 100:
                        result = 'WIN'
                    elif worst <= LOSS_THRESHOLD * 100:
                        result = 'LOSS'
                    # else still pending

            conn.execute('''
                UPDATE signals SET
                    price_1w = ?, price_2w = ?, price_4w = ?,
                    pnl_1w = ?, pnl_2w = ?, pnl_4w = ?,
                    result = ?, last_updated = ?
                WHERE id = ?
            ''', (price_1w, price_2w, price_4w, pnl_1w, pnl_2w, pnl_4w,
                  result, datetime.now().isoformat(), row['id']))
            updated += 1

            # Display
            result_clr = Fore.GREEN if result == 'WIN' else Fore.RED if result == 'LOSS' else Fore.YELLOW
            result_str = result or 'PENDING'
            pnl_str = f"{pnl_4w:>+.1f}%" if pnl_4w else (f"{pnl_2w:>+.1f}%" if pnl_2w else (f"{pnl_1w:>+.1f}%" if pnl_1w else 'N/A'))
            print(f"  {result_clr}{result_str:<8}{Style.RESET_ALL} {ticker:<8} Signal: {signal_date}  Entry: ${price_at:.2f}  P&L: {pnl_str}")

        except Exception as e:
            continue

    conn.commit()
    conn.close()
    print(f"\n  {Fore.GREEN}Updated {updated} signals{Style.RESET_ALL}\n")


def cmd_stats():
    """Show win rate statistics."""
    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📊 SIGNAL TRACKER — Win Rate Statistics")
    print(f"{Fore.CYAN}{'='*65}{Style.RESET_ALL}\n")

    conn = get_db()
    all_rows = conn.execute('SELECT * FROM signals').fetchall()
    resolved = conn.execute("SELECT * FROM signals WHERE result IN ('WIN', 'LOSS', 'FLAT')").fetchall()

    if not all_rows:
        print(f"  {Fore.YELLOW}No signals recorded yet. Run 'record' first.{Style.RESET_ALL}\n")
        conn.close()
        return

    total = len(all_rows)
    total_resolved = len(resolved)
    pending = total - total_resolved

    wins = len([r for r in resolved if r['result'] == 'WIN'])
    losses = len([r for r in resolved if r['result'] == 'LOSS'])
    flats = len([r for r in resolved if r['result'] == 'FLAT'])

    overall_wr = (wins / total_resolved * 100) if total_resolved > 0 else 0

    print(f"{Fore.WHITE}{Style.BRIGHT}OVERALL PERFORMANCE{Style.RESET_ALL}")
    print(f"{'─'*65}")
    wr_clr = Fore.GREEN if overall_wr >= 60 else Fore.YELLOW if overall_wr >= 40 else Fore.RED
    print(f"  Total Signals:  {total}")
    print(f"  Resolved:       {total_resolved}  (Pending: {pending})")
    print(f"  Win Rate:       {wr_clr}{overall_wr:.1f}%{Style.RESET_ALL}  ({wins}W / {losses}L / {flats}F)")

    # Average P&L
    pnls_4w = [r['pnl_4w'] for r in resolved if r['pnl_4w'] is not None]
    if pnls_4w:
        avg_pnl = np.mean(pnls_4w)
        pnl_clr = Fore.GREEN if avg_pnl > 0 else Fore.RED
        print(f"  Avg 4W P&L:     {pnl_clr}{avg_pnl:+.2f}%{Style.RESET_ALL}")
    print()

    stats_output = {
        'overall': {
            'total': total,
            'resolved': total_resolved,
            'pending': pending,
            'wins': wins,
            'losses': losses,
            'flats': flats,
            'win_rate': round(overall_wr, 1),
        },
        'by_conviction': {},
        'by_pattern': {},
        'by_flow_bias': {},
    }

    # --- By Conviction ---
    print(f"{Fore.WHITE}{Style.BRIGHT}BY CONVICTION LEVEL{Style.RESET_ALL}")
    print(f"{'─'*65}")

    convictions = set(r['conviction'] for r in all_rows if r['conviction'])
    conv_stats = []
    for conv in sorted(convictions):
        conv_resolved = [r for r in resolved if r['conviction'] == conv]
        conv_total = len([r for r in all_rows if r['conviction'] == conv])
        conv_wins = len([r for r in conv_resolved if r['result'] == 'WIN'])
        conv_losses = len([r for r in conv_resolved if r['result'] == 'LOSS'])
        conv_n = len(conv_resolved)
        wr = (conv_wins / conv_n * 100) if conv_n > 0 else 0
        conv_stats.append((conv, wr, conv_n, conv_wins, conv_losses, conv_total))
        stats_output['by_conviction'][conv] = {
            'win_rate': round(wr, 1), 'trades': conv_n, 'wins': conv_wins, 'losses': conv_losses, 'total': conv_total
        }

    # Sort by win rate descending
    conv_stats.sort(key=lambda x: x[1], reverse=True)
    for conv, wr, n, w, l, t in conv_stats:
        if wr >= 70:
            icon = '🔥'
            clr = Fore.GREEN
        elif wr >= 50:
            icon = '🟢'
            clr = Fore.GREEN
        elif wr >= 30:
            icon = '🟡'
            clr = Fore.YELLOW
        else:
            icon = '🔴'
            clr = Fore.RED
        bar = '█' * int(wr / 10) + '░' * (10 - int(wr / 10))
        print(f"  {icon} {conv:<12} {clr}{wr:>5.1f}%{Style.RESET_ALL} [{bar}] ({w}W/{l}L from {n} resolved, {t} total)")

    print()

    # --- By Pattern ---
    print(f"{Fore.WHITE}{Style.BRIGHT}BY PATTERN TYPE{Style.RESET_ALL}")
    print(f"{'─'*65}")

    patterns = set(r['pattern'] for r in all_rows if r['pattern'] and r['pattern'] != 'UNKNOWN')
    pat_stats = []
    for pat in sorted(patterns):
        pat_resolved = [r for r in resolved if r['pattern'] == pat]
        pat_total = len([r for r in all_rows if r['pattern'] == pat])
        pat_wins = len([r for r in pat_resolved if r['result'] == 'WIN'])
        pat_losses = len([r for r in pat_resolved if r['result'] == 'LOSS'])
        pat_n = len(pat_resolved)
        wr = (pat_wins / pat_n * 100) if pat_n > 0 else 0
        pat_stats.append((pat, wr, pat_n, pat_wins, pat_losses, pat_total))
        stats_output['by_pattern'][pat] = {
            'win_rate': round(wr, 1), 'trades': pat_n, 'wins': pat_wins, 'losses': pat_losses, 'total': pat_total
        }

    pat_stats.sort(key=lambda x: x[1], reverse=True)
    for pat, wr, n, w, l, t in pat_stats:
        clr = Fore.GREEN if wr >= 50 else Fore.RED
        print(f"  {pat:<20} {clr}{wr:>5.1f}%{Style.RESET_ALL} ({w}W/{l}L from {n} resolved, {t} total)")

    if pat_stats:
        best = pat_stats[0]
        worst = pat_stats[-1]
        print(f"\n  {Fore.GREEN}Best pattern:{Style.RESET_ALL}  {best[0]} ({best[1]:.0f}% win rate)")
        print(f"  {Fore.RED}Worst pattern:{Style.RESET_ALL} {worst[0]} ({worst[1]:.0f}% win rate)")

    print()

    # --- By Flow Bias ---
    print(f"{Fore.WHITE}{Style.BRIGHT}BY FLOW BIAS{Style.RESET_ALL}")
    print(f"{'─'*65}")

    biases = set(r['flow_bias'] for r in all_rows if r['flow_bias'] and r['flow_bias'] != 'UNKNOWN')
    for bias in sorted(biases):
        bias_resolved = [r for r in resolved if r['flow_bias'] == bias]
        bias_total = len([r for r in all_rows if r['flow_bias'] == bias])
        bias_wins = len([r for r in bias_resolved if r['result'] == 'WIN'])
        bias_losses = len([r for r in bias_resolved if r['result'] == 'LOSS'])
        bias_n = len(bias_resolved)
        wr = (bias_wins / bias_n * 100) if bias_n > 0 else 0
        clr = Fore.GREEN if wr >= 50 else Fore.RED
        print(f"  {bias:<12} {clr}{wr:>5.1f}%{Style.RESET_ALL} ({bias_wins}W/{bias_losses}L from {bias_n} resolved, {bias_total} total)")
        stats_output['by_flow_bias'][bias] = {
            'win_rate': round(wr, 1), 'trades': bias_n, 'wins': bias_wins, 'losses': bias_losses, 'total': bias_total
        }

    print()
    conn.close()

    # Save stats
    stats_output['timestamp'] = datetime.now().isoformat()
    with open(STATS_FILE, 'w') as f:
        json.dump(stats_output, f, indent=2)
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Saved to {STATS_FILE}\n")


def cmd_report():
    """Detailed report of all tracked signals."""
    print(f"\n{Fore.CYAN}{'='*85}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📋 SIGNAL TRACKER — Full Report")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{Fore.CYAN}{'='*85}{Style.RESET_ALL}\n")

    conn = get_db()
    rows = conn.execute('SELECT * FROM signals ORDER BY signal_date DESC, ticker').fetchall()

    if not rows:
        print(f"  {Fore.YELLOW}No signals recorded yet.{Style.RESET_ALL}\n")
        conn.close()
        return

    print(f"{Fore.WHITE}{Style.BRIGHT}ALL TRACKED SIGNALS ({len(rows)} total){Style.RESET_ALL}")
    print(f"{'─'*85}")
    print(f"{'Date':<12}{'Ticker':<8}{'Conv':<10}{'Pattern':<16}{'Entry':>8}{'1W P&L':>8}{'2W P&L':>8}{'4W P&L':>8}{'Result':>9}")
    print(f"{'─'*85}")

    for row in rows:
        result = row['result'] or 'PENDING'
        if result == 'WIN':
            res_clr = Fore.GREEN
            icon = '✅'
        elif result == 'LOSS':
            res_clr = Fore.RED
            icon = '❌'
        elif result == 'FLAT':
            res_clr = Fore.YELLOW
            icon = '➖'
        else:
            res_clr = Fore.WHITE
            icon = '⏳'

        pnl_1w = f"{row['pnl_1w']:>+.1f}%" if row['pnl_1w'] is not None else '    —'
        pnl_2w = f"{row['pnl_2w']:>+.1f}%" if row['pnl_2w'] is not None else '    —'
        pnl_4w = f"{row['pnl_4w']:>+.1f}%" if row['pnl_4w'] is not None else '    —'
        price = f"${row['price_at_signal']:.2f}" if row['price_at_signal'] else '   N/A'

        pnl1_clr = Fore.GREEN if row['pnl_1w'] and row['pnl_1w'] > 0 else Fore.RED if row['pnl_1w'] and row['pnl_1w'] < 0 else Fore.WHITE
        pnl2_clr = Fore.GREEN if row['pnl_2w'] and row['pnl_2w'] > 0 else Fore.RED if row['pnl_2w'] and row['pnl_2w'] < 0 else Fore.WHITE
        pnl4_clr = Fore.GREEN if row['pnl_4w'] and row['pnl_4w'] > 0 else Fore.RED if row['pnl_4w'] and row['pnl_4w'] < 0 else Fore.WHITE

        conv = (row['conviction'] or 'N/A')[:9]
        pat = (row['pattern'] or 'N/A')[:15]

        print(f"{row['signal_date']:<12}"
              f"{Fore.CYAN}{row['ticker']:<8}{Style.RESET_ALL}"
              f"{conv:<10}"
              f"{pat:<16}"
              f"{price:>8}"
              f"  {pnl1_clr}{pnl_1w:>6}{Style.RESET_ALL}"
              f"  {pnl2_clr}{pnl_2w:>6}{Style.RESET_ALL}"
              f"  {pnl4_clr}{pnl_4w:>6}{Style.RESET_ALL}"
              f"  {icon} {res_clr}{result}{Style.RESET_ALL}")

    print(f"{'─'*85}")

    # Quick summary
    resolved = [r for r in rows if r['result'] in ('WIN', 'LOSS', 'FLAT')]
    wins = len([r for r in resolved if r['result'] == 'WIN'])
    losses = len([r for r in resolved if r['result'] == 'LOSS'])
    pending = len([r for r in rows if r['result'] is None or r['result'] == ''])

    if resolved:
        wr = wins / len(resolved) * 100
        wr_clr = Fore.GREEN if wr >= 50 else Fore.RED
        print(f"\n  Overall: {wr_clr}{wr:.1f}% win rate{Style.RESET_ALL} ({wins}W / {losses}L)  |  Pending: {pending}")
    else:
        print(f"\n  {Fore.YELLOW}No resolved signals yet.{Style.RESET_ALL} Pending: {pending}")

    print()
    conn.close()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}📈 SIGNAL TRACKER{Style.RESET_ALL}")
        print(f"\nUsage: python3 signal_tracker.py <command>\n")
        print(f"Commands:")
        print(f"  {Fore.GREEN}record{Style.RESET_ALL}  — Record current signals from signals_latest.json")
        print(f"  {Fore.GREEN}update{Style.RESET_ALL}  — Update past signals with current prices & P&L")
        print(f"  {Fore.GREEN}stats{Style.RESET_ALL}   — Show win rates by conviction, pattern, flow bias")
        print(f"  {Fore.GREEN}report{Style.RESET_ALL}  — Detailed report of all tracked signals")
        print()
        return

    cmd = sys.argv[1].lower()

    if cmd == 'record':
        cmd_record()
    elif cmd == 'update':
        cmd_update()
    elif cmd == 'stats':
        cmd_stats()
    elif cmd == 'report':
        cmd_report()
    else:
        print(f"\n  {Fore.RED}Unknown command: {cmd}{Style.RESET_ALL}")
        print(f"  Available: record, update, stats, report\n")


if __name__ == '__main__':
    main()
