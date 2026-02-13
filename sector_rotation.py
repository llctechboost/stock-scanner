#!/usr/bin/env python3
"""
Sector Rotation Tracker - Track money flow between sectors using sector ETFs.
Identifies where institutional money is rotating TO and FROM.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys
from colorama import Fore, Style, init

init(autoreset=True)

SECTORS = {
    'XLK':  'Technology',
    'XLF':  'Financials',
    'XLE':  'Energy',
    'XLV':  'Healthcare',
    'XLY':  'Consumer Disc',
    'XLI':  'Industrials',
    'XLP':  'Consumer Staples',
    'XLU':  'Utilities',
    'XLRE': 'Real Estate',
    'XLC':  'Communication',
    'XLB':  'Materials',
}

OUTPUT_FILE = 'sector_rotation_latest.json'


def calc_rsi(series, period=14):
    """Calculate RSI for a price series."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def analyze_sector(etf, spy_data):
    """Analyze a single sector ETF relative to SPY."""
    try:
        df = yf.download(etf, period='6mo', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 63:
            return None

        close = df['Close']
        volume = df['Volume']
        price = float(close.iloc[-1])

        # --- Relative performance vs SPY ---
        spy_close = spy_data['Close']
        # Align dates
        common = close.index.intersection(spy_close.index)
        if len(common) < 63:
            return None
        sec = close.reindex(common)
        spy = spy_close.reindex(common)

        def rel_perf(n):
            if len(sec) < n:
                return 0.0
            sec_ret = float(sec.iloc[-1] / sec.iloc[-n] - 1) * 100
            spy_ret = float(spy.iloc[-1] / spy.iloc[-n] - 1) * 100
            return sec_ret - spy_ret

        perf_1w = rel_perf(5)
        perf_1m = rel_perf(21)
        perf_3m = rel_perf(63)

        # --- Volume trend ---
        vol_20 = float(volume.iloc[-20:].mean())
        vol_50 = float(volume.iloc[-50:].mean()) if len(volume) >= 50 else vol_20
        vol_trend = 'RISING' if vol_20 > vol_50 * 1.1 else 'FALLING' if vol_20 < vol_50 * 0.9 else 'FLAT'
        vol_ratio = vol_20 / vol_50 if vol_50 > 0 else 1.0

        # --- RSI ---
        rsi_series = calc_rsi(close)
        rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0
        rsi_label = 'OVERBOUGHT' if rsi > 70 else 'OVERSOLD' if rsi < 30 else 'NEUTRAL'

        # --- Money flow direction ---
        # Positive price change + rising volume = inflow
        # Negative price change + rising volume = outflow
        price_chg_1m = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) >= 21 else 0
        price_chg_1w = float(close.iloc[-1] / close.iloc[-5] - 1) if len(close) >= 5 else 0

        # Money flow score: combine price momentum and volume
        mf_score = 0
        mf_score += perf_1w * 2   # weight recent more
        mf_score += perf_1m * 1.5
        mf_score += perf_3m * 0.5
        if vol_trend == 'RISING':
            mf_score *= 1.3 if mf_score > 0 else 0.7
        elif vol_trend == 'FALLING':
            mf_score *= 0.7 if mf_score > 0 else 1.3

        flow_dir = 'IN' if mf_score > 0 else 'OUT'

        # Absolute performance
        abs_perf_1w = float(sec.iloc[-1] / sec.iloc[-5] - 1) * 100 if len(sec) >= 5 else 0
        abs_perf_1m = float(sec.iloc[-1] / sec.iloc[-21] - 1) * 100 if len(sec) >= 21 else 0

        return {
            'etf': etf,
            'sector': SECTORS[etf],
            'price': round(price, 2),
            'rel_perf_1w': round(perf_1w, 2),
            'rel_perf_1m': round(perf_1m, 2),
            'rel_perf_3m': round(perf_3m, 2),
            'abs_perf_1w': round(abs_perf_1w, 2),
            'abs_perf_1m': round(abs_perf_1m, 2),
            'vol_trend': vol_trend,
            'vol_ratio': round(vol_ratio, 2),
            'rsi': round(rsi, 1),
            'rsi_label': rsi_label,
            'flow_direction': flow_dir,
            'mf_score': round(mf_score, 2),
        }
    except Exception as e:
        return None


def detect_rotation_signals(results):
    """Find rotation signals — money leaving one sector, entering another."""
    signals = []
    inflows = sorted([r for r in results if r['flow_direction'] == 'IN'], key=lambda x: x['mf_score'], reverse=True)
    outflows = sorted([r for r in results if r['flow_direction'] == 'OUT'], key=lambda x: x['mf_score'])

    # Pair strongest inflow with strongest outflow
    for inf in inflows[:3]:
        for out in outflows[:3]:
            strength = abs(inf['mf_score']) + abs(out['mf_score'])
            signals.append({
                'from_sector': out['sector'],
                'from_etf': out['etf'],
                'to_sector': inf['sector'],
                'to_etf': inf['etf'],
                'strength': round(strength, 2),
                'description': f"Money rotating FROM {out['sector']} → TO {inf['sector']}"
            })

    signals.sort(key=lambda x: x['strength'], reverse=True)
    return signals[:5]


def run_scan():
    """Run sector rotation analysis."""
    print(f"\n{Fore.CYAN}{'='*75}")
    print(f"{Fore.CYAN}{Style.BRIGHT}🔄 SECTOR ROTATION TRACKER")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{Fore.CYAN}{'='*75}{Style.RESET_ALL}\n")

    print(f"{Fore.YELLOW}Downloading SPY benchmark...{Style.RESET_ALL}")
    spy_df = yf.download('SPY', period='6mo', progress=False)
    if isinstance(spy_df.columns, pd.MultiIndex):
        spy_df.columns = spy_df.columns.get_level_values(0)

    print(f"{Fore.YELLOW}Analyzing {len(SECTORS)} sector ETFs...{Style.RESET_ALL}\n")

    results = []
    for etf in SECTORS:
        sys.stdout.write(f"\r  {etf} ({SECTORS[etf]})...           ")
        sys.stdout.flush()
        r = analyze_sector(etf, spy_df)
        if r:
            results.append(r)

    sys.stdout.write(f"\r{' '*50}\r")
    sys.stdout.flush()

    # Sort by money flow score
    results.sort(key=lambda x: x['mf_score'], reverse=True)

    # --- INFLOWS TABLE ---
    inflows = [r for r in results if r['flow_direction'] == 'IN']
    outflows = [r for r in results if r['flow_direction'] == 'OUT']

    print(f"{Fore.WHITE}{Style.BRIGHT}💰 MONEY FLOWING IN (Strongest First){Style.RESET_ALL}")
    print(f"{'─'*75}")
    print(f"{'ETF':<6}{'Sector':<18}{'Price':>8}{'1W vs SPY':>10}{'1M vs SPY':>10}{'3M vs SPY':>10}{'RSI':>6}{'Vol':>8}")
    print(f"{'─'*75}")

    for r in inflows:
        rsi_clr = Fore.RED if r['rsi_label'] == 'OVERBOUGHT' else Fore.GREEN if r['rsi_label'] == 'OVERSOLD' else Fore.WHITE
        vol_clr = Fore.GREEN if r['vol_trend'] == 'RISING' else Fore.RED if r['vol_trend'] == 'FALLING' else Fore.WHITE
        print(f"{Fore.GREEN}{r['etf']:<6}{Style.RESET_ALL}"
              f"{Fore.GREEN}{r['sector']:<18}{Style.RESET_ALL}"
              f"${r['price']:>7.2f}"
              f"{Fore.GREEN}{r['rel_perf_1w']:>+9.2f}%{Style.RESET_ALL}"
              f"{Fore.GREEN}{r['rel_perf_1m']:>+9.2f}%{Style.RESET_ALL}"
              f"{Fore.GREEN}{r['rel_perf_3m']:>+9.2f}%{Style.RESET_ALL}"
              f"{rsi_clr}{r['rsi']:>5.0f}{Style.RESET_ALL}"
              f" {vol_clr}{r['vol_trend']:>7}{Style.RESET_ALL}")

    if not inflows:
        print(f"  {Fore.YELLOW}No strong sector inflows detected{Style.RESET_ALL}")

    print()
    print(f"{Fore.WHITE}{Style.BRIGHT}💸 MONEY FLOWING OUT (Weakest First){Style.RESET_ALL}")
    print(f"{'─'*75}")
    print(f"{'ETF':<6}{'Sector':<18}{'Price':>8}{'1W vs SPY':>10}{'1M vs SPY':>10}{'3M vs SPY':>10}{'RSI':>6}{'Vol':>8}")
    print(f"{'─'*75}")

    for r in outflows:
        rsi_clr = Fore.RED if r['rsi_label'] == 'OVERBOUGHT' else Fore.GREEN if r['rsi_label'] == 'OVERSOLD' else Fore.WHITE
        vol_clr = Fore.GREEN if r['vol_trend'] == 'RISING' else Fore.RED if r['vol_trend'] == 'FALLING' else Fore.WHITE
        print(f"{Fore.RED}{r['etf']:<6}{Style.RESET_ALL}"
              f"{Fore.RED}{r['sector']:<18}{Style.RESET_ALL}"
              f"${r['price']:>7.2f}"
              f"{Fore.RED}{r['rel_perf_1w']:>+9.2f}%{Style.RESET_ALL}"
              f"{Fore.RED}{r['rel_perf_1m']:>+9.2f}%{Style.RESET_ALL}"
              f"{Fore.RED}{r['rel_perf_3m']:>+9.2f}%{Style.RESET_ALL}"
              f"{rsi_clr}{r['rsi']:>5.0f}{Style.RESET_ALL}"
              f" {vol_clr}{r['vol_trend']:>7}{Style.RESET_ALL}")

    if not outflows:
        print(f"  {Fore.YELLOW}No strong sector outflows detected{Style.RESET_ALL}")

    # --- ROTATION SIGNALS ---
    signals = detect_rotation_signals(results)
    if signals:
        print(f"\n{Fore.WHITE}{Style.BRIGHT}🔄 ROTATION SIGNALS{Style.RESET_ALL}")
        print(f"{'─'*75}")
        for i, sig in enumerate(signals):
            strength_bar = '█' * min(10, int(sig['strength'] / 2)) + '░' * max(0, 10 - int(sig['strength'] / 2))
            print(f"  {Fore.RED}{sig['from_sector']:<16}{Style.RESET_ALL}"
                  f" → {Fore.GREEN}{sig['to_sector']:<16}{Style.RESET_ALL}"
                  f" [{strength_bar}] Strength: {sig['strength']:.1f}")

    # --- RSI EXTREMES ---
    overbought = [r for r in results if r['rsi_label'] == 'OVERBOUGHT']
    oversold = [r for r in results if r['rsi_label'] == 'OVERSOLD']
    if overbought or oversold:
        print(f"\n{Fore.WHITE}{Style.BRIGHT}⚠️  RSI EXTREMES{Style.RESET_ALL}")
        print(f"{'─'*75}")
        for r in overbought:
            print(f"  {Fore.RED}⬆ OVERBOUGHT{Style.RESET_ALL}  {r['etf']} ({r['sector']}) RSI: {r['rsi']:.0f}")
        for r in oversold:
            print(f"  {Fore.GREEN}⬇ OVERSOLD{Style.RESET_ALL}    {r['etf']} ({r['sector']}) RSI: {r['rsi']:.0f}")

    print(f"\n{'─'*75}")
    print(f"  {Fore.GREEN}IN{Style.RESET_ALL} = Money flowing in   {Fore.RED}OUT{Style.RESET_ALL} = Money flowing out   vs SPY = Relative to S&P 500")
    print()

    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'sectors': results,
        'rotation_signals': signals,
        'summary': {
            'inflow_sectors': [r['sector'] for r in inflows],
            'outflow_sectors': [r['sector'] for r in outflows],
            'overbought': [r['etf'] for r in overbought],
            'oversold': [r['etf'] for r in oversold],
        }
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Saved to {OUTPUT_FILE}\n")

    return results


if __name__ == '__main__':
    run_scan()
