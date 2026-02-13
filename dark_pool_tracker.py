#!/usr/bin/env python3
"""
Dark Pool Tracker - Track institutional/dark pool indicators using free data.
Identifies accumulation vs distribution patterns from institutional holdings.
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

OUTPUT_FILE = 'dark_pool_latest.json'

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
    if args:
        return [t.upper() for t in args]

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
    """Load signal data for cross-reference."""
    signals = {}
    for path in ['signals_latest.json', '../completeinceptionmigrationeverything2026013101/signals_latest.json']:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                for sig in data.get('signals', data.get('results', [])):
                    if isinstance(sig, dict) and 'ticker' in sig:
                        signals[sig['ticker']] = sig
            except:
                pass
    return signals


def calc_accumulation_distribution(df):
    """Calculate Accumulation/Distribution line from OHLCV data."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    volume = df['Volume']

    # Money Flow Multiplier
    mfm = ((close - low) - (high - close)) / (high - low + 1e-10)
    # Money Flow Volume
    mfv = mfm * volume
    # AD line
    ad = mfv.cumsum()
    return ad


def analyze_ticker(ticker):
    """Analyze institutional/dark pool indicators for a single ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # Current price
        hist = stock.history(period='3mo')
        if hist.empty or len(hist) < 20:
            return None
        price = float(hist['Close'].iloc[-1])

        # --- Institutional Ownership ---
        inst_pct = info.get('heldPercentInstitutions')
        inst_pct = round(inst_pct * 100, 1) if inst_pct is not None else None

        insider_pct = info.get('heldPercentInsiders')
        insider_pct = round(insider_pct * 100, 1) if insider_pct is not None else None

        # --- Short Interest ---
        short_ratio = info.get('shortRatio')  # days to cover
        short_pct = info.get('shortPercentOfFloat')
        short_pct = round(short_pct * 100, 2) if short_pct is not None else None
        shares_short = info.get('sharesShort')
        shares_short_prior = info.get('sharesShortPriorMonth')

        # Short interest change
        short_change = None
        short_trend = 'UNKNOWN'
        if shares_short is not None and shares_short_prior is not None and shares_short_prior > 0:
            short_change = round(((shares_short - shares_short_prior) / shares_short_prior) * 100, 1)
            short_trend = 'DECREASING' if short_change < -5 else 'INCREASING' if short_change > 5 else 'STABLE'

        # --- Volume Analysis (off-exchange estimate) ---
        # Compare recent avg volume to historical — large off-exchange = dark pool
        vol = hist['Volume']
        vol_5d = float(vol.iloc[-5:].mean())
        vol_20d = float(vol.iloc[-20:].mean())
        vol_50d = float(vol.iloc[-50:].mean()) if len(vol) >= 50 else vol_20d

        # Price-volume divergence: price up but volume down = possible dark pool accumulation
        price_chg_20d = float(hist['Close'].iloc[-1] / hist['Close'].iloc[-20] - 1) * 100
        vol_chg_20d = (vol_5d / vol_20d - 1) * 100 if vol_20d > 0 else 0

        # --- Accumulation/Distribution Line ---
        ad_line = calc_accumulation_distribution(hist)
        ad_recent = float(ad_line.iloc[-1])
        ad_20d_ago = float(ad_line.iloc[-20]) if len(ad_line) >= 20 else ad_recent
        ad_trend = 'ACCUMULATION' if ad_recent > ad_20d_ago else 'DISTRIBUTION'

        # --- On-Balance Volume trend ---
        obv = (np.sign(hist['Close'].diff()) * hist['Volume']).cumsum()
        obv_recent = float(obv.iloc[-1])
        obv_20d = float(obv.iloc[-20]) if len(obv) >= 20 else obv_recent
        obv_trend = 'RISING' if obv_recent > obv_20d else 'FALLING'

        # --- Overall Assessment ---
        # Accumulating: increasing inst ownership + decreasing shorts + positive AD + rising OBV
        # Distributing: the opposite
        acc_score = 0  # positive = accumulating, negative = distributing

        if inst_pct is not None and inst_pct > 60:
            acc_score += 1
        if short_trend == 'DECREASING':
            acc_score += 2
        elif short_trend == 'INCREASING':
            acc_score -= 2
        if ad_trend == 'ACCUMULATION':
            acc_score += 2
        else:
            acc_score -= 2
        if obv_trend == 'RISING':
            acc_score += 1
        else:
            acc_score -= 1
        if price_chg_20d > 0 and vol_chg_20d < -10:
            # Price up, volume down = quiet accumulation (dark pool)
            acc_score += 1

        if short_pct is not None and short_pct > 20:
            acc_score -= 1  # High short interest = bearish pressure

        if acc_score >= 2:
            assessment = 'ACCUMULATING'
        elif acc_score <= -2:
            assessment = 'DISTRIBUTING'
        else:
            assessment = 'NEUTRAL'

        return {
            'ticker': ticker,
            'price': round(price, 2),
            'inst_ownership_pct': inst_pct,
            'insider_pct': insider_pct,
            'short_ratio': round(short_ratio, 2) if short_ratio else None,
            'short_float_pct': short_pct,
            'short_change_pct': short_change,
            'short_trend': short_trend,
            'vol_5d_avg': int(vol_5d),
            'vol_20d_avg': int(vol_20d),
            'price_chg_20d': round(price_chg_20d, 2),
            'vol_chg_20d': round(vol_chg_20d, 2),
            'ad_trend': ad_trend,
            'obv_trend': obv_trend,
            'acc_score': acc_score,
            'assessment': assessment,
        }
    except Exception as e:
        return None


def run_scan(args=None):
    """Run dark pool tracker scan."""
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}{Style.BRIGHT}🕵️  DARK POOL TRACKER - Institutional Flow Analysis")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")

    tickers = load_tickers(args or [])
    signal_data = load_signal_tickers()
    if signal_data:
        print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Loaded {len(signal_data)} signals for cross-reference")

    print(f"\n{Fore.YELLOW}Analyzing {len(tickers)} stocks for institutional activity...{Style.RESET_ALL}\n")

    results = []
    for i, ticker in enumerate(tickers):
        sys.stdout.write(f"\r  {ticker}... ({i+1}/{len(tickers)})")
        sys.stdout.flush()
        r = analyze_ticker(ticker)
        if r:
            results.append(r)

    sys.stdout.write(f"\r{' '*50}\r")
    sys.stdout.flush()

    # Sort: accumulating first, then by score
    results.sort(key=lambda x: x['acc_score'], reverse=True)

    # Separate groups
    accumulating = [r for r in results if r['assessment'] == 'ACCUMULATING']
    distributing = [r for r in results if r['assessment'] == 'DISTRIBUTING']
    neutral = [r for r in results if r['assessment'] == 'NEUTRAL']

    # --- ACCUMULATING ---
    print(f"{Fore.WHITE}{Style.BRIGHT}🟢 ACCUMULATING — Institutions Buying{Style.RESET_ALL}")
    print(f"{'─'*80}")
    print(f"{'Ticker':<8}{'Price':>8}{'Inst%':>7}{'Short%':>8}{'SI Chg':>8}{'A/D':>14}{'OBV':>9}{'Score':>7}{'Signal':>8}")
    print(f"{'─'*80}")

    for r in accumulating:
        is_signal = r['ticker'] in signal_data
        inst = f"{r['inst_ownership_pct']:.0f}%" if r['inst_ownership_pct'] is not None else '  N/A'
        short = f"{r['short_float_pct']:.1f}%" if r['short_float_pct'] is not None else '  N/A'
        si_chg = f"{r['short_change_pct']:>+.1f}%" if r['short_change_pct'] is not None else '  N/A'
        sig = f'{Fore.CYAN}⚡ YES{Style.RESET_ALL}' if is_signal else ''

        ad_clr = Fore.GREEN if r['ad_trend'] == 'ACCUMULATION' else Fore.RED
        obv_clr = Fore.GREEN if r['obv_trend'] == 'RISING' else Fore.RED

        print(f"{Fore.GREEN}{r['ticker']:<8}{Style.RESET_ALL}"
              f"${r['price']:>7.2f}"
              f"  {inst:>5}"
              f"  {short:>6}"
              f"  {si_chg:>6}"
              f"  {ad_clr}{r['ad_trend']:>12}{Style.RESET_ALL}"
              f"  {obv_clr}{r['obv_trend']:>7}{Style.RESET_ALL}"
              f"  {Fore.GREEN}{r['acc_score']:>+4}{Style.RESET_ALL}"
              f"  {sig}")

    if not accumulating:
        print(f"  {Fore.YELLOW}No accumulation signals detected{Style.RESET_ALL}")

    # --- DISTRIBUTING ---
    print(f"\n{Fore.WHITE}{Style.BRIGHT}🔴 DISTRIBUTING — Institutions Selling{Style.RESET_ALL}")
    print(f"{'─'*80}")
    print(f"{'Ticker':<8}{'Price':>8}{'Inst%':>7}{'Short%':>8}{'SI Chg':>8}{'A/D':>14}{'OBV':>9}{'Score':>7}{'Signal':>8}")
    print(f"{'─'*80}")

    for r in distributing:
        is_signal = r['ticker'] in signal_data
        inst = f"{r['inst_ownership_pct']:.0f}%" if r['inst_ownership_pct'] is not None else '  N/A'
        short = f"{r['short_float_pct']:.1f}%" if r['short_float_pct'] is not None else '  N/A'
        si_chg = f"{r['short_change_pct']:>+.1f}%" if r['short_change_pct'] is not None else '  N/A'
        sig = f'{Fore.RED}⚡ YES{Style.RESET_ALL}' if is_signal else ''

        ad_clr = Fore.GREEN if r['ad_trend'] == 'ACCUMULATION' else Fore.RED
        obv_clr = Fore.GREEN if r['obv_trend'] == 'RISING' else Fore.RED

        print(f"{Fore.RED}{r['ticker']:<8}{Style.RESET_ALL}"
              f"${r['price']:>7.2f}"
              f"  {inst:>5}"
              f"  {short:>6}"
              f"  {si_chg:>6}"
              f"  {ad_clr}{r['ad_trend']:>12}{Style.RESET_ALL}"
              f"  {obv_clr}{r['obv_trend']:>7}{Style.RESET_ALL}"
              f"  {Fore.RED}{r['acc_score']:>+4}{Style.RESET_ALL}"
              f"  {sig}")

    if not distributing:
        print(f"  {Fore.YELLOW}No distribution signals detected{Style.RESET_ALL}")

    # --- NEUTRAL ---
    if neutral:
        print(f"\n{Fore.WHITE}{Style.BRIGHT}⚪ NEUTRAL — No Clear Institutional Bias{Style.RESET_ALL}")
        print(f"{'─'*80}")
        for r in neutral:
            inst = f"{r['inst_ownership_pct']:.0f}%" if r['inst_ownership_pct'] is not None else 'N/A'
            print(f"  {r['ticker']:<8} ${r['price']:>7.2f}  Inst: {inst}  A/D: {r['ad_trend']}  OBV: {r['obv_trend']}")

    # --- CONVICTION BOOST (cross-ref with signals) ---
    signal_acc = [r for r in accumulating if r['ticker'] in signal_data]
    signal_dist = [r for r in distributing if r['ticker'] in signal_data]

    if signal_acc or signal_dist:
        print(f"\n{Fore.WHITE}{Style.BRIGHT}⚡ SIGNAL CROSS-REFERENCE{Style.RESET_ALL}")
        print(f"{'─'*80}")
        for r in signal_acc:
            sig = signal_data[r['ticker']]
            conv = sig.get('conviction', sig.get('score', 'N/A'))
            print(f"  {Fore.GREEN}✅ {r['ticker']}{Style.RESET_ALL} — Accumulating + Active Signal (Conviction: {conv}) → {Fore.GREEN}CONVICTION BOOST{Style.RESET_ALL}")
        for r in signal_dist:
            sig = signal_data[r['ticker']]
            conv = sig.get('conviction', sig.get('score', 'N/A'))
            print(f"  {Fore.RED}⚠️  {r['ticker']}{Style.RESET_ALL} — Distributing + Active Signal (Conviction: {conv}) → {Fore.RED}CAUTION{Style.RESET_ALL}")

    # --- HIGH SHORT INTEREST ---
    high_short = [r for r in results if r['short_float_pct'] is not None and r['short_float_pct'] > 10]
    if high_short:
        high_short.sort(key=lambda x: x['short_float_pct'], reverse=True)
        print(f"\n{Fore.WHITE}{Style.BRIGHT}🩳 HIGH SHORT INTEREST (>10% float){Style.RESET_ALL}")
        print(f"{'─'*80}")
        for r in high_short:
            si_trend = Fore.GREEN + '↓' if r['short_trend'] == 'DECREASING' else Fore.RED + '↑' if r['short_trend'] == 'INCREASING' else Fore.WHITE + '→'
            print(f"  {r['ticker']:<8} Short: {Fore.RED}{r['short_float_pct']:.1f}%{Style.RESET_ALL}  "
                  f"Days to Cover: {r['short_ratio']:.1f}  "
                  f"Trend: {si_trend} {r['short_trend']}{Style.RESET_ALL}")

    print(f"\n{'─'*80}")
    print(f"  {Fore.GREEN}ACCUMULATING{Style.RESET_ALL} = Inst buying / shorts decreasing / positive A/D")
    print(f"  {Fore.RED}DISTRIBUTING{Style.RESET_ALL} = Inst selling / shorts increasing / negative A/D")
    print(f"  A/D = Accumulation/Distribution line   OBV = On-Balance Volume")
    print()

    # Save
    output = {
        'timestamp': datetime.now().isoformat(),
        'results': results,
        'summary': {
            'accumulating': [r['ticker'] for r in accumulating],
            'distributing': [r['ticker'] for r in distributing],
            'neutral': [r['ticker'] for r in neutral],
            'high_short_interest': [r['ticker'] for r in high_short] if high_short else [],
            'signal_boosted': [r['ticker'] for r in signal_acc],
            'signal_caution': [r['ticker'] for r in signal_dist],
        }
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Saved to {OUTPUT_FILE}\n")

    return results


if __name__ == '__main__':
    args = sys.argv[1:]
    run_scan(args)
