#!/usr/bin/env python3
"""
Earnings Calendar - Proximity checker for watchlist stocks.
Flags danger zones for stocks with upcoming earnings.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys
import os
from colorama import Fore, Style, init

init(autoreset=True)

OUTPUT_FILE = 'earnings_calendar_latest.json'

# Default watchlist if no JSON/args
DEFAULT_TICKERS = [
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO', 'CRM',
    'PLTR', 'NET', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'MDB', 'PANW', 'NOW', 'SHOP',
    'SMCI', 'ARM', 'APP', 'HIMS', 'DUOL', 'CELH', 'TOST', 'CAVA',
    'GS', 'JPM', 'V', 'MA', 'COIN', 'HOOD', 'SOFI',
    'LLY', 'NVO', 'UNH', 'ISRG',
    'UBER', 'ABNB', 'DASH', 'RKLB', 'AXON',
]


def load_tickers(args):
    """Load tickers from args, money_scan_latest.json, or defaults."""
    # Command line args first
    if args:
        return [t.upper() for t in args]

    # Try money_scan_latest.json
    for path in ['money_scan_latest.json', '../completeinceptionmigrationeverything2026013101/money_scan_latest.json']:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                tickers = [r['ticker'] for r in data.get('results', [])[:30]]
                if tickers:
                    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Loaded {len(tickers)} tickers from {path}")
                    return tickers
            except:
                pass

    print(f"  {Fore.YELLOW}ℹ{Style.RESET_ALL} Using default watchlist ({len(DEFAULT_TICKERS)} tickers)")
    return DEFAULT_TICKERS


def load_signal_tickers():
    """Load tickers from signals_latest.json for cross-reference."""
    signal_tickers = set()
    for path in ['signals_latest.json', '../completeinceptionmigrationeverything2026013101/signals_latest.json']:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                for sig in data.get('signals', data.get('results', [])):
                    if isinstance(sig, dict) and 'ticker' in sig:
                        signal_tickers.add(sig['ticker'])
            except:
                pass
    return signal_tickers


def analyze_earnings(ticker):
    """Get earnings info for a single ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # Current price
        hist = stock.history(period='5d')
        price = float(hist['Close'].iloc[-1]) if not hist.empty else info.get('currentPrice', 0)

        # Next earnings date
        cal = stock.calendar
        earnings_date = None
        if isinstance(cal, dict):
            # yfinance may return dict with 'Earnings Date'
            ed = cal.get('Earnings Date')
            if ed:
                if isinstance(ed, list) and len(ed) > 0:
                    earnings_date = pd.Timestamp(ed[0])
                elif isinstance(ed, (str, datetime, pd.Timestamp)):
                    earnings_date = pd.Timestamp(ed)
        elif isinstance(cal, pd.DataFrame) and not cal.empty:
            try:
                ed = cal.loc['Earnings Date']
                if hasattr(ed, 'iloc'):
                    earnings_date = pd.Timestamp(ed.iloc[0])
                else:
                    earnings_date = pd.Timestamp(ed)
            except:
                pass

        # Fallback: try earnings_dates attribute
        if earnings_date is None:
            try:
                ed_df = stock.earnings_dates
                if ed_df is not None and not ed_df.empty:
                    future = ed_df.index[ed_df.index >= pd.Timestamp.now(tz=ed_df.index.tz)]
                    if len(future) > 0:
                        earnings_date = future[-1]  # earliest future date
                    else:
                        # Use most recent past date
                        earnings_date = ed_df.index[0]
            except:
                pass

        # Calculate days until
        days_until = None
        category = 'UNKNOWN'
        if earnings_date is not None:
            # Normalize timezone
            if hasattr(earnings_date, 'tz') and earnings_date.tz is not None:
                now = pd.Timestamp.now(tz=earnings_date.tz)
            else:
                now = pd.Timestamp.now()
                earnings_date = pd.Timestamp(earnings_date)
            days_until = (earnings_date - now).days

            if days_until < 0:
                category = 'PASSED'
            elif days_until <= 7:
                category = 'DANGER'
            elif days_until <= 14:
                category = 'CAUTION'
            else:
                category = 'CLEAR'

        # EPS data from earnings history
        est_eps = None
        prev_eps = None
        surprise_pct = None
        try:
            ed_df = stock.earnings_dates
            if ed_df is not None and not ed_df.empty:
                # Most recent reported
                reported = ed_df[ed_df['Reported EPS'].notna()]
                if not reported.empty:
                    prev_eps = float(reported.iloc[0]['Reported EPS'])
                    if 'Surprise(%)' in reported.columns:
                        sp = reported.iloc[0]['Surprise(%)']
                        if pd.notna(sp):
                            surprise_pct = float(sp)

                # Estimated EPS (next)
                estimated = ed_df[ed_df['Reported EPS'].isna()]
                if not estimated.empty and 'EPS Estimate' in estimated.columns:
                    ee = estimated.iloc[-1]['EPS Estimate']
                    if pd.notna(ee):
                        est_eps = float(ee)
        except:
            pass

        return {
            'ticker': ticker,
            'price': round(price, 2),
            'earnings_date': str(earnings_date.date()) if earnings_date is not None else None,
            'days_until': days_until,
            'category': category,
            'est_eps': round(est_eps, 2) if est_eps is not None else None,
            'prev_eps': round(prev_eps, 2) if prev_eps is not None else None,
            'surprise_pct': round(surprise_pct, 1) if surprise_pct is not None else None,
        }
    except Exception as e:
        return {
            'ticker': ticker,
            'price': 0,
            'earnings_date': None,
            'days_until': None,
            'category': 'UNKNOWN',
            'est_eps': None,
            'prev_eps': None,
            'surprise_pct': None,
        }


def run_scan(args=None):
    """Run earnings calendar scan."""
    print(f"\n{Fore.CYAN}{'='*75}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📅 EARNINGS CALENDAR - Proximity Checker")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{Fore.CYAN}{'='*75}{Style.RESET_ALL}\n")

    tickers = load_tickers(args or [])
    signal_tickers = load_signal_tickers()
    if signal_tickers:
        print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Loaded {len(signal_tickers)} signal tickers for cross-reference")

    print(f"\n{Fore.YELLOW}Checking earnings for {len(tickers)} stocks...{Style.RESET_ALL}\n")

    results = []
    for i, ticker in enumerate(tickers):
        sys.stdout.write(f"\r  {ticker}... ({i+1}/{len(tickers)})")
        sys.stdout.flush()
        r = analyze_earnings(ticker)
        if r:
            results.append(r)

    sys.stdout.write(f"\r{' '*50}\r")
    sys.stdout.flush()

    # Sort: DANGER first, then CAUTION, then by days_until
    cat_order = {'DANGER': 0, 'CAUTION': 1, 'CLEAR': 2, 'PASSED': 3, 'UNKNOWN': 4}
    results.sort(key=lambda x: (cat_order.get(x['category'], 5), x['days_until'] if x['days_until'] is not None else 9999))

    # Print table
    print(f"{Fore.WHITE}{Style.BRIGHT}EARNINGS PROXIMITY REPORT{Style.RESET_ALL}")
    print(f"{'─'*75}")
    print(f"{'Ticker':<8}{'Status':<10}{'Days':>6}{'Date':>13}{'Price':>9}{'Est EPS':>9}{'Prev EPS':>9}{'Surprise':>9}{'Signal':>7}")
    print(f"{'─'*75}")

    danger_count = 0
    caution_count = 0

    for r in results:
        cat = r['category']
        is_signal = r['ticker'] in signal_tickers

        if cat == 'DANGER':
            cat_clr = Fore.RED
            icon = '🔴'
            danger_count += 1
        elif cat == 'CAUTION':
            cat_clr = Fore.YELLOW
            icon = '🟡'
            caution_count += 1
        elif cat == 'CLEAR':
            cat_clr = Fore.GREEN
            icon = '🟢'
        elif cat == 'PASSED':
            cat_clr = Fore.WHITE
            icon = '⚪'
        else:
            cat_clr = Fore.WHITE
            icon = '❓'

        days_str = f"{r['days_until']:>4}d" if r['days_until'] is not None else '   N/A'
        date_str = r['earnings_date'] if r['earnings_date'] else 'Unknown'
        eps_est = f"${r['est_eps']:>.2f}" if r['est_eps'] is not None else '    —'
        eps_prev = f"${r['prev_eps']:>.2f}" if r['prev_eps'] is not None else '    —'
        surprise = f"{r['surprise_pct']:>+.1f}%" if r['surprise_pct'] is not None else '    —'
        sig_flag = f'{Fore.CYAN}⚡ YES{Style.RESET_ALL}' if is_signal else '      '

        print(f"{cat_clr}{r['ticker']:<8}{Style.RESET_ALL}"
              f"{icon} {cat_clr}{cat:<8}{Style.RESET_ALL}"
              f"{days_str}"
              f"  {date_str:>11}"
              f"  ${r['price']:>7.2f}"
              f"  {eps_est:>7}"
              f"  {eps_prev:>7}"
              f"  {surprise:>7}"
              f"  {sig_flag}")

    print(f"{'─'*75}")

    # Summary
    print(f"\n{Fore.WHITE}{Style.BRIGHT}SUMMARY{Style.RESET_ALL}")
    if danger_count:
        print(f"  {Fore.RED}🔴 DANGER: {danger_count} stocks with earnings in 0-7 days — consider reducing position{Style.RESET_ALL}")
    if caution_count:
        print(f"  {Fore.YELLOW}🟡 CAUTION: {caution_count} stocks with earnings in 8-14 days — set alerts{Style.RESET_ALL}")

    # Flag signals with upcoming earnings
    signal_danger = [r for r in results if r['ticker'] in signal_tickers and r['category'] in ('DANGER', 'CAUTION')]
    if signal_danger:
        print(f"\n  {Fore.RED}{Style.BRIGHT}⚠️  ACTIVE SIGNALS WITH UPCOMING EARNINGS:{Style.RESET_ALL}")
        for r in signal_danger:
            cat_clr = Fore.RED if r['category'] == 'DANGER' else Fore.YELLOW
            print(f"    {cat_clr}{r['ticker']}{Style.RESET_ALL} — {r['category']} ({r['days_until']}d) — Earnings {r['earnings_date']}")

    print()

    # Save
    output = {
        'timestamp': datetime.now().isoformat(),
        'results': results,
        'summary': {
            'total': len(results),
            'danger': danger_count,
            'caution': caution_count,
            'signal_conflicts': [r['ticker'] for r in signal_danger] if signal_danger else [],
        }
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Saved to {OUTPUT_FILE}\n")

    return results


if __name__ == '__main__':
    args = sys.argv[1:]
    run_scan(args)
