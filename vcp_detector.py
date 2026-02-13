#!/usr/bin/env python3
"""
VCP (Volatility Contraction Pattern) Detector
Identifies Mark Minervini-style VCP patterns in stock price data.

A VCP has:
- Successive tighter contractions (T1 > T2 > T3...)
- Volume dry-up in later contractions
- Price near 52-week high (within 10-15%)
- Base depth typically 10-35%
- Duration 3-12 weeks
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Contraction:
    """A single contraction wave within a VCP."""
    start_idx: int
    end_idx: int
    peak_price: float
    trough_price: float
    depth_pct: float          # % decline from peak to trough
    avg_volume: float         # average volume during this contraction
    duration_days: int
    start_date: str = ""
    end_date: str = ""


@dataclass
class VCPResult:
    """Result of VCP analysis for a single stock."""
    ticker: str
    score: float              # 0-10 quality score
    num_contractions: int
    contractions: List[Contraction] = field(default_factory=list)
    tightness_ratios: List[float] = field(default_factory=list)  # each contraction vs prior
    volume_ratios: List[float] = field(default_factory=list)     # volume vs 50d avg
    pivot_price: float = 0.0  # buy point (top of last contraction)
    current_price: float = 0.0
    pct_from_high: float = 0.0
    base_depth: float = 0.0   # total correction from high
    base_duration_weeks: float = 0.0
    is_textbook: bool = False  # flags truly classic patterns
    error: str = ""

    @property
    def near_pivot(self) -> bool:
        """Is price within 3% of pivot?"""
        if self.pivot_price == 0:
            return False
        return abs(self.current_price - self.pivot_price) / self.pivot_price < 0.03

    @property
    def grade(self) -> str:
        if self.score >= 8:
            return "A"
        elif self.score >= 6:
            return "B"
        elif self.score >= 4:
            return "C"
        else:
            return "D"


def _find_swing_points(prices: pd.Series, order: int = 5) -> tuple:
    """
    Find local peaks and troughs in price data.
    `order` controls how many bars on each side to consider for a swing point.
    Returns (peaks_indices, troughs_indices).
    """
    from scipy.signal import argrelextrema

    arr = prices.values.astype(float)

    # Find local maxima and minima
    peak_idxs = argrelextrema(arr, np.greater_equal, order=order)[0]
    trough_idxs = argrelextrema(arr, np.less_equal, order=order)[0]

    return peak_idxs, trough_idxs


def _find_swing_points_simple(prices: pd.Series, window: int = 5) -> tuple:
    """
    Fallback swing detection without scipy.
    Uses rolling window to find local highs/lows.
    """
    arr = prices.values.astype(float)
    n = len(arr)
    peaks = []
    troughs = []

    for i in range(window, n - window):
        segment = arr[i - window: i + window + 1]
        if arr[i] == segment.max():
            peaks.append(i)
        if arr[i] == segment.min():
            troughs.append(i)

    # De-duplicate consecutive same-type points (keep most extreme)
    def dedup(indices, arr, pick_max=True):
        if not indices:
            return indices
        result = [indices[0]]
        for idx in indices[1:]:
            if idx - result[-1] <= window:
                # Keep the more extreme one
                if pick_max and arr[idx] > arr[result[-1]]:
                    result[-1] = idx
                elif not pick_max and arr[idx] < arr[result[-1]]:
                    result[-1] = idx
            else:
                result.append(idx)
        return result

    peaks = dedup(peaks, arr, pick_max=True)
    troughs = dedup(troughs, arr, pick_max=False)

    return np.array(peaks), np.array(troughs)


def _extract_contractions(df: pd.DataFrame, peak_idxs, trough_idxs) -> List[Contraction]:
    """
    Extract contraction waves from alternating peaks and troughs.
    A contraction = peak followed by a trough (a decline).
    """
    close = df['Close'].values.astype(float)
    volume = df['Volume'].values.astype(float)
    dates = df.index

    # Build alternating sequence of peaks and troughs
    events = []
    for idx in peak_idxs:
        events.append(('peak', int(idx)))
    for idx in trough_idxs:
        events.append(('trough', int(idx)))
    events.sort(key=lambda x: x[1])

    # Extract peak -> trough pairs (contractions)
    contractions = []
    i = 0
    while i < len(events) - 1:
        if events[i][0] == 'peak':
            # Look for next trough
            j = i + 1
            while j < len(events) and events[j][0] != 'trough':
                j += 1
            if j < len(events):
                peak_i = events[i][1]
                trough_i = events[j][1]
                peak_price = close[peak_i]
                trough_price = close[trough_i]

                if peak_price > trough_price and peak_price > 0:
                    depth = (peak_price - trough_price) / peak_price * 100
                    duration = trough_i - peak_i
                    avg_vol = volume[peak_i:trough_i + 1].mean() if trough_i > peak_i else volume[peak_i]

                    contractions.append(Contraction(
                        start_idx=peak_i,
                        end_idx=trough_i,
                        peak_price=float(peak_price),
                        trough_price=float(trough_price),
                        depth_pct=float(depth),
                        avg_volume=float(avg_vol),
                        duration_days=int(duration),
                        start_date=str(dates[peak_i].date()) if peak_i < len(dates) else "",
                        end_date=str(dates[trough_i].date()) if trough_i < len(dates) else "",
                    ))
                i = j + 1
            else:
                break
        else:
            i += 1

    return contractions


def _find_vcp_sequence(contractions: List[Contraction], avg_volume_50d: float) -> tuple:
    """
    Find the best VCP sequence within the contractions.
    Returns (best_sequence, tightness_ratios, volume_ratios).

    A VCP sequence is a set of successive contractions where each is tighter than the last.
    """
    if len(contractions) < 2:
        return contractions, [], []

    # Try to find the longest tightening sequence ending near the most recent data
    best_seq = []
    best_ratios = []
    best_vol_ratios = []

    # Work backwards from the most recent contractions
    for start in range(len(contractions)):
        seq = [contractions[start]]
        ratios = []
        vol_ratios = [contractions[start].avg_volume / avg_volume_50d if avg_volume_50d > 0 else 1.0]

        for k in range(start + 1, len(contractions)):
            curr = contractions[k]
            prev = seq[-1]

            ratio = curr.depth_pct / prev.depth_pct if prev.depth_pct > 0 else 1.0

            # Allow some tolerance - contraction should be at most ~120% of prior
            # (ideally < 100%, meaning tighter)
            if ratio <= 1.2:
                seq.append(curr)
                ratios.append(ratio)
                vol_ratios.append(curr.avg_volume / avg_volume_50d if avg_volume_50d > 0 else 1.0)
            else:
                # If it widens significantly, this breaks the pattern
                # But keep going to see if there's a tighter one after
                continue

        if len(seq) >= len(best_seq):
            best_seq = seq
            best_ratios = ratios
            best_vol_ratios = vol_ratios

    return best_seq, best_ratios, best_vol_ratios


def analyze_vcp(ticker: str, period: str = '6mo') -> VCPResult:
    """
    Analyze a stock for VCP pattern.

    Returns VCPResult with score 0-10 and detailed metrics.
    """
    result = VCPResult(ticker=ticker, score=0, num_contractions=0)

    try:
        df = yf.download(ticker, period='1y', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if len(df) < 60:
            result.error = "Insufficient data"
            return result

        close = df['Close'].astype(float)
        volume = df['Volume'].astype(float)
        current_price = float(close.iloc[-1])
        result.current_price = current_price

        # 52-week high
        high_52w = float(close.max())
        result.pct_from_high = (high_52w - current_price) / high_52w * 100

        # Average volume (50-day)
        avg_vol_50d = float(volume.iloc[-50:].mean()) if len(volume) >= 50 else float(volume.mean())

        # Focus on the last 3-4 months for VCP detection (pattern formation window)
        lookback = min(len(df), 84)  # ~4 months of trading days
        df_recent = df.iloc[-lookback:].copy()
        close_recent = df_recent['Close'].astype(float)

        # Find swing points
        try:
            peak_idxs, trough_idxs = _find_swing_points(close_recent, order=4)
        except ImportError:
            peak_idxs, trough_idxs = _find_swing_points_simple(close_recent, window=4)

        if len(peak_idxs) < 2 or len(trough_idxs) < 1:
            result.error = "Not enough swing points"
            return result

        # Extract contractions
        all_contractions = _extract_contractions(df_recent, peak_idxs, trough_idxs)

        if len(all_contractions) < 2:
            result.error = "Fewer than 2 contractions found"
            return result

        # Filter out tiny noise contractions (< 2% depth)
        meaningful = [c for c in all_contractions if c.depth_pct >= 2.0]
        if len(meaningful) < 2:
            meaningful = all_contractions  # fall back to all

        # Find best VCP tightening sequence
        vcp_seq, tightness_ratios, vol_ratios = _find_vcp_sequence(meaningful, avg_vol_50d)

        result.contractions = vcp_seq
        result.num_contractions = len(vcp_seq)
        result.tightness_ratios = tightness_ratios
        result.volume_ratios = vol_ratios

        # Base metrics
        if vcp_seq:
            base_high = max(c.peak_price for c in vcp_seq)
            base_low = min(c.trough_price for c in vcp_seq)
            result.base_depth = (base_high - base_low) / base_high * 100

            first_date = vcp_seq[0].start_idx
            last_date = vcp_seq[-1].end_idx
            result.base_duration_weeks = (last_date - first_date) / 5.0  # trading days to weeks

            # Pivot = peak of the last contraction (breakout point)
            result.pivot_price = float(vcp_seq[-1].peak_price)

        # ── SCORING (0-10) ──────────────────────────────────────────

        score = 0.0

        # 1. Number of contractions (0-2 pts)
        #    2 contractions = 1pt, 3+ = 2pts
        if result.num_contractions >= 3:
            score += 2.0
        elif result.num_contractions >= 2:
            score += 1.0

        # 2. Tightness quality (0-3 pts)
        #    How well do contractions successively tighten?
        if tightness_ratios:
            avg_tightness = np.mean(tightness_ratios)
            tightening_count = sum(1 for r in tightness_ratios if r < 1.0)

            if avg_tightness < 0.5:
                score += 3.0  # Excellent tightening (each wave < 50% of prior)
            elif avg_tightness < 0.7:
                score += 2.0
            elif avg_tightness < 0.9:
                score += 1.5
            elif avg_tightness < 1.0:
                score += 1.0

            # Bonus: all contractions tightened
            if tightening_count == len(tightness_ratios):
                score += 0.5

        # 3. Volume dry-up (0-2 pts)
        #    Volume in later contractions should be well below average
        if vol_ratios and len(vol_ratios) >= 2:
            last_vol_ratio = vol_ratios[-1]
            vol_declining = all(vol_ratios[i] >= vol_ratios[i + 1] for i in range(len(vol_ratios) - 1))

            if last_vol_ratio < 0.5:
                score += 2.0  # Volume dried up significantly
            elif last_vol_ratio < 0.7:
                score += 1.5
            elif last_vol_ratio < 0.9:
                score += 1.0
            elif last_vol_ratio < 1.0:
                score += 0.5

            # Bonus for consistently declining volume
            if vol_declining:
                score += 0.3

        # 4. Price near 52-week high (0-1.5 pts)
        if result.pct_from_high <= 5:
            score += 1.5
        elif result.pct_from_high <= 10:
            score += 1.0
        elif result.pct_from_high <= 15:
            score += 0.5

        # 5. Base depth in ideal range 10-35% (0-1 pt)
        if 10 <= result.base_depth <= 35:
            score += 1.0
        elif 5 <= result.base_depth <= 40:
            score += 0.5

        # 6. Base duration in ideal range 3-12 weeks (0-0.5 pts)
        if 3 <= result.base_duration_weeks <= 12:
            score += 0.5
        elif 2 <= result.base_duration_weeks <= 16:
            score += 0.25

        # Cap at 10
        result.score = round(min(10.0, score), 1)

        # Textbook check: score >= 7 AND at least 3 contractions AND all tightening
        result.is_textbook = (
            result.score >= 7.0
            and result.num_contractions >= 3
            and all(r < 1.0 for r in tightness_ratios)
            and result.pct_from_high <= 15
        )

    except Exception as e:
        result.error = str(e)

    return result


def scan_universe_vcp(tickers: list, min_score: float = 3.0) -> List[VCPResult]:
    """Scan a list of tickers for VCP patterns."""
    results = []
    for ticker in tickers:
        r = analyze_vcp(ticker)
        if r.score >= min_score and not r.error:
            results.append(r)
    results.sort(key=lambda x: x.score, reverse=True)
    return results


# ── Standalone runner ───────────────────────────────────────────────────────

if __name__ == '__main__':
    from colorama import Fore, Style, init as colorama_init
    import sys

    colorama_init(autoreset=True)

    # Default universe (same as money_scanner)
    UNIVERSE = [
        'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO', 'CRM',
        'PLTR', 'NET', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'MDB', 'PANW', 'NOW', 'SHOP',
        'SMCI', 'ARM', 'IONQ', 'RGTI', 'APP', 'HIMS', 'DUOL', 'CELH', 'TOST', 'CAVA',
        'GS', 'JPM', 'V', 'MA', 'AXP', 'COIN', 'HOOD', 'SOFI', 'NU',
        'LLY', 'NVO', 'UNH', 'ISRG', 'DXCM', 'PODD', 'VRTX',
        'UBER', 'ABNB', 'DASH', 'RKLB', 'AXON', 'DECK', 'GWW', 'URI',
        'ASML', 'LRCX', 'KLAC', 'AMAT', 'MRVL', 'QCOM',
        'COST', 'TJX', 'LULU', 'NKE', 'HD', 'LOW'
    ]

    # Allow single ticker from command line
    if len(sys.argv) > 1:
        tickers = sys.argv[1:]
    else:
        tickers = UNIVERSE

    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📐 VCP DETECTOR - Volatility Contraction Patterns")
    print(f"{Fore.CYAN}   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}Scanning {len(tickers)} stocks for VCP patterns...{Style.RESET_ALL}\n")

    all_results = []
    for i, t in enumerate(tickers):
        sys.stdout.write(f"\r  Analyzing {t}... ({i + 1}/{len(tickers)})")
        sys.stdout.flush()
        r = analyze_vcp(t)
        if not r.error:
            all_results.append(r)

    all_results.sort(key=lambda x: x.score, reverse=True)

    print(f"\r{' ' * 60}\r")
    print(f"{Fore.WHITE}{Style.BRIGHT}VCP SCAN RESULTS{Style.RESET_ALL}")
    print(f"{'─' * 70}")
    print(f"{'Ticker':<7}{'Score':>6}{'Grade':>6}{'#C':>4}{'Tightness':>11}{'VolDry':>8}{'Pivot':>9}{'%High':>7}{'Depth':>7}  {'Flag'}")
    print(f"{'─' * 70}")

    shown = 0
    for r in all_results:
        if r.score < 2.0:
            continue
        shown += 1

        # Score color
        if r.score >= 7:
            sc = Fore.GREEN
        elif r.score >= 5:
            sc = Fore.YELLOW
        else:
            sc = Fore.WHITE

        # Tightness display
        if r.tightness_ratios:
            tight_str = '/'.join(f"{t:.0%}" for t in r.tightness_ratios[:3])
        else:
            tight_str = "—"

        # Volume dry-up (last contraction volume vs avg)
        if r.volume_ratios:
            vdry = f"{r.volume_ratios[-1]:.1f}x"
        else:
            vdry = "—"

        # Flag
        if r.is_textbook:
            flag = f"{Fore.GREEN}{Style.BRIGHT}⭐ TEXTBOOK{Style.RESET_ALL}"
        elif r.near_pivot:
            flag = f"{Fore.YELLOW}🎯 AT PIVOT{Style.RESET_ALL}"
        elif r.score >= 5:
            flag = f"{Fore.CYAN}📐 FORMING{Style.RESET_ALL}"
        else:
            flag = ""

        print(
            f"{Fore.CYAN}{r.ticker:<7}{Style.RESET_ALL}"
            f"{sc}{r.score:>5.1f}{Style.RESET_ALL}"
            f"{'':>2}{r.grade:>3}"
            f"{r.num_contractions:>4}"
            f"{tight_str:>11}"
            f"{vdry:>8}"
            f"  ${r.pivot_price:>7.2f}"
            f"{r.pct_from_high:>6.1f}%"
            f"{r.base_depth:>6.1f}%"
            f"  {flag}"
        )

    print(f"{'─' * 70}")
    textbook_count = sum(1 for r in all_results if r.is_textbook)
    forming_count = sum(1 for r in all_results if r.score >= 5 and not r.is_textbook)

    if textbook_count:
        print(f"\n  {Fore.GREEN}⭐ {textbook_count} TEXTBOOK VCP{'s' if textbook_count > 1 else ''}{Style.RESET_ALL} — Classic Minervini pattern")
    if forming_count:
        print(f"  {Fore.CYAN}📐 {forming_count} FORMING{Style.RESET_ALL} — Pattern developing, watch for tightening")
    if not textbook_count and not forming_count:
        print(f"\n  {Fore.YELLOW}No strong VCP patterns detected right now.{Style.RESET_ALL}")

    print(f"\n{Fore.YELLOW}Legend:{Style.RESET_ALL}")
    print(f"  Score = VCP quality 0-10  |  #C = contractions  |  Tightness = each wave vs prior")
    print(f"  VolDry = last contraction vol vs 50d avg  |  Pivot = breakout buy point")
    print(f"  ⭐ TEXTBOOK = Score 7+, 3+ contractions, all tightening, near highs")
    print()
