"""
Strat Pattern Backtester
Compares performance of different Strat patterns

Patterns tested:
1. 2-1-2 Continuation (2U→1→2U / 2D→1→2D)
2. 3-1-2 Reversal (3→1→2 opposite)
3. 2-2 Continuation (2U→2U / 2D→2D)
4. 1-2 Breakout (1→2U / 1→2D)
5. Hammer (bullish reversal)
6. Shooter (bearish reversal)

Trade Rules:
- Entry: Pattern completes → buy/short next day open
- Stop Loss: Below pattern low (bullish) / above pattern high (bearish), max 8%
- Target: 2:1 risk/reward
- Time stop: Exit after 20 days if neither hit
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# === Strat Scenario Detection ===

class Scenario(Enum):
    INSIDE = 1
    UP = 2
    DOWN = -2
    OUTSIDE_UP = 3
    OUTSIDE_DOWN = -3

def get_scenario(curr_high, curr_low, curr_close, curr_open, 
                 prev_high, prev_low) -> Scenario:
    """Determine scenario of current bar vs previous"""
    broke_high = curr_high > prev_high
    broke_low = curr_low < prev_low
    
    if broke_high and broke_low:
        if curr_close > curr_open:
            return Scenario.OUTSIDE_UP
        else:
            return Scenario.OUTSIDE_DOWN
    elif broke_high:
        return Scenario.UP
    elif broke_low:
        return Scenario.DOWN
    else:
        return Scenario.INSIDE

def add_scenarios(df: pd.DataFrame) -> pd.DataFrame:
    """Add scenario column to dataframe"""
    scenarios = []
    for i in range(len(df)):
        if i == 0:
            scenarios.append(None)
        else:
            s = get_scenario(
                df['High'].iloc[i], df['Low'].iloc[i],
                df['Close'].iloc[i], df['Open'].iloc[i],
                df['High'].iloc[i-1], df['Low'].iloc[i-1]
            )
            scenarios.append(s)
    df['Scenario'] = scenarios
    return df

def detect_hammer(row) -> bool:
    """Hammer: small body at top, long lower wick"""
    range_size = row['High'] - row['Low']
    if range_size == 0:
        return False
    body_top = max(row['Open'], row['Close'])
    body_bottom = min(row['Open'], row['Close'])
    body_size = body_top - body_bottom
    lower_wick = body_bottom - row['Low']
    body_position = (body_bottom - row['Low']) / range_size
    
    return body_position >= 0.6 and lower_wick >= 2 * max(body_size, 0.001)

def detect_shooter(row) -> bool:
    """Shooter: small body at bottom, long upper wick"""
    range_size = row['High'] - row['Low']
    if range_size == 0:
        return False
    body_top = max(row['Open'], row['Close'])
    body_bottom = min(row['Open'], row['Close'])
    body_size = body_top - body_bottom
    upper_wick = row['High'] - body_top
    body_position = (body_top - row['Low']) / range_size
    
    return body_position <= 0.4 and upper_wick >= 2 * max(body_size, 0.001)

# === Trade Simulation ===

@dataclass
class Trade:
    """Single trade record"""
    ticker: str
    pattern: str
    direction: str  # 'long' or 'short'
    entry_date: str = None
    entry_price: float = None
    exit_date: str = None
    exit_price: float = None
    exit_reason: str = None  # 'target', 'stop', 'time'
    pnl_pct: float = None
    risk_pct: float = None
    days_held: int = None

def simulate_trade(df: pd.DataFrame, entry_idx: int, 
                   direction: str, stop_price: float, 
                   target_price: float, max_days: int = 20,
                   max_stop_pct: float = 0.08) -> Optional[Dict]:
    """
    Simulate a trade from entry_idx+1 (next day open)
    Returns trade result dict or None if can't enter
    """
    if entry_idx + 1 >= len(df):
        return None
    
    entry_bar = df.iloc[entry_idx + 1]
    entry_price = entry_bar['Open']
    entry_date = df.index[entry_idx + 1]
    
    if pd.isna(entry_price) or entry_price <= 0:
        return None
    
    # Calculate risk and adjust stop if needed
    if direction == 'long':
        risk_pct = (entry_price - stop_price) / entry_price
        if risk_pct <= 0:  # Invalid stop (above entry)
            return None
        if risk_pct > max_stop_pct:
            stop_price = entry_price * (1 - max_stop_pct)
            risk_pct = max_stop_pct
        # Recalc target at 2:1
        target_price = entry_price * (1 + 2 * risk_pct)
    else:  # short
        risk_pct = (stop_price - entry_price) / entry_price
        if risk_pct <= 0:  # Invalid stop (below entry)
            return None
        if risk_pct > max_stop_pct:
            stop_price = entry_price * (1 + max_stop_pct)
            risk_pct = max_stop_pct
        target_price = entry_price * (1 - 2 * risk_pct)
    
    # Simulate forward
    for days_held in range(1, max_days + 1):
        bar_idx = entry_idx + 1 + days_held
        if bar_idx >= len(df):
            break
        
        bar = df.iloc[bar_idx]
        bar_date = df.index[bar_idx]
        
        if direction == 'long':
            # Check stop first (conservative)
            if bar['Low'] <= stop_price:
                return {
                    'entry_date': str(entry_date),
                    'entry_price': entry_price,
                    'exit_date': str(bar_date),
                    'exit_price': stop_price,
                    'exit_reason': 'stop',
                    'pnl_pct': -risk_pct,
                    'risk_pct': risk_pct,
                    'days_held': days_held
                }
            # Check target
            if bar['High'] >= target_price:
                pnl = (target_price - entry_price) / entry_price
                return {
                    'entry_date': str(entry_date),
                    'entry_price': entry_price,
                    'exit_date': str(bar_date),
                    'exit_price': target_price,
                    'exit_reason': 'target',
                    'pnl_pct': pnl,
                    'risk_pct': risk_pct,
                    'days_held': days_held
                }
        else:  # short
            if bar['High'] >= stop_price:
                return {
                    'entry_date': str(entry_date),
                    'entry_price': entry_price,
                    'exit_date': str(bar_date),
                    'exit_price': stop_price,
                    'exit_reason': 'stop',
                    'pnl_pct': -risk_pct,
                    'risk_pct': risk_pct,
                    'days_held': days_held
                }
            if bar['Low'] <= target_price:
                pnl = (entry_price - target_price) / entry_price
                return {
                    'entry_date': str(entry_date),
                    'entry_price': entry_price,
                    'exit_date': str(bar_date),
                    'exit_price': target_price,
                    'exit_reason': 'target',
                    'pnl_pct': pnl,
                    'risk_pct': risk_pct,
                    'days_held': days_held
                }
    
    # Time stop - exit at close
    if bar_idx < len(df):
        bar = df.iloc[bar_idx]
        exit_price = bar['Close']
        if direction == 'long':
            pnl = (exit_price - entry_price) / entry_price
        else:
            pnl = (entry_price - exit_price) / entry_price
        return {
            'entry_date': str(entry_date),
            'entry_price': entry_price,
            'exit_date': str(df.index[bar_idx]),
            'exit_price': exit_price,
            'exit_reason': 'time',
            'pnl_pct': pnl,
            'risk_pct': risk_pct,
            'days_held': max_days
        }
    
    return None

# === Pattern Detection & Trade Generation ===

def find_pattern_trades(df: pd.DataFrame, ticker: str) -> List[Trade]:
    """Find all pattern trades in a dataframe"""
    trades = []
    df = add_scenarios(df.copy())
    
    for i in range(4, len(df) - 1):  # Need lookback and forward space
        row = df.iloc[i]
        prev1 = df.iloc[i-1]
        prev2 = df.iloc[i-2]
        prev3 = df.iloc[i-3]
        
        s0 = df['Scenario'].iloc[i]
        s1 = df['Scenario'].iloc[i-1]
        s2 = df['Scenario'].iloc[i-2]
        
        if s0 is None or s1 is None:
            continue
        
        # 1. 2-1-2 Continuation
        # Bullish: 2U → 1 → 2U
        if s2 == Scenario.UP and s1 == Scenario.INSIDE and s0 == Scenario.UP:
            stop = prev1['Low']  # Inside bar low
            target = row['High'] * 1.16  # Will be recalculated
            result = simulate_trade(df, i, 'long', stop, target)
            if result:
                trades.append(Trade(
                    ticker=ticker, pattern='2-1-2 Cont', direction='long',
                    **result
                ))
        
        # Bearish: 2D → 1 → 2D
        if s2 == Scenario.DOWN and s1 == Scenario.INSIDE and s0 == Scenario.DOWN:
            stop = prev1['High']
            target = row['Low'] * 0.84
            result = simulate_trade(df, i, 'short', stop, target)
            if result:
                trades.append(Trade(
                    ticker=ticker, pattern='2-1-2 Cont', direction='short',
                    **result
                ))
        
        # 2. 3-1-2 Reversal
        # Bullish: 3D → 1 → 2U
        if s2 == Scenario.OUTSIDE_DOWN and s1 == Scenario.INSIDE and s0 == Scenario.UP:
            stop = row['Low']
            target = prev2['High']
            result = simulate_trade(df, i, 'long', stop, target)
            if result:
                trades.append(Trade(
                    ticker=ticker, pattern='3-1-2 Rev', direction='long',
                    **result
                ))
        
        # Bearish: 3U → 1 → 2D
        if s2 == Scenario.OUTSIDE_UP and s1 == Scenario.INSIDE and s0 == Scenario.DOWN:
            stop = row['High']
            target = prev2['Low']
            result = simulate_trade(df, i, 'short', stop, target)
            if result:
                trades.append(Trade(
                    ticker=ticker, pattern='3-1-2 Rev', direction='short',
                    **result
                ))
        
        # 3. 2-2 Continuation
        # Bullish: 2U → 2U
        if s1 == Scenario.UP and s0 == Scenario.UP:
            stop = prev1['Low']
            target = row['High'] * 1.16
            result = simulate_trade(df, i, 'long', stop, target)
            if result:
                trades.append(Trade(
                    ticker=ticker, pattern='2-2 Cont', direction='long',
                    **result
                ))
        
        # Bearish: 2D → 2D
        if s1 == Scenario.DOWN and s0 == Scenario.DOWN:
            stop = prev1['High']
            target = row['Low'] * 0.84
            result = simulate_trade(df, i, 'short', stop, target)
            if result:
                trades.append(Trade(
                    ticker=ticker, pattern='2-2 Cont', direction='short',
                    **result
                ))
        
        # 4. 1-2 Breakout
        # Bullish: 1 → 2U
        if s1 == Scenario.INSIDE and s0 == Scenario.UP:
            stop = prev1['Low']  # Inside bar low
            target = row['High'] * 1.16
            result = simulate_trade(df, i, 'long', stop, target)
            if result:
                trades.append(Trade(
                    ticker=ticker, pattern='1-2 Break', direction='long',
                    **result
                ))
        
        # Bearish: 1 → 2D
        if s1 == Scenario.INSIDE and s0 == Scenario.DOWN:
            stop = prev1['High']
            target = row['Low'] * 0.84
            result = simulate_trade(df, i, 'short', stop, target)
            if result:
                trades.append(Trade(
                    ticker=ticker, pattern='1-2 Break', direction='short',
                    **result
                ))
        
        # 5. Hammer (bullish reversal)
        if detect_hammer(row):
            # Must be after downtrend (at least 2 down bars in last 5)
            recent_down = sum(1 for j in range(max(0, i-5), i) 
                             if df['Close'].iloc[j] < df['Open'].iloc[j])
            if recent_down >= 2:
                stop = row['Low']
                target = row['High'] * 1.16
                result = simulate_trade(df, i, 'long', stop, target)
                if result:
                    trades.append(Trade(
                        ticker=ticker, pattern='Hammer', direction='long',
                        **result
                    ))
        
        # 6. Shooter (bearish reversal)
        if detect_shooter(row):
            recent_up = sum(1 for j in range(max(0, i-5), i)
                          if df['Close'].iloc[j] > df['Open'].iloc[j])
            if recent_up >= 2:
                stop = row['High']
                target = row['Low'] * 0.84
                result = simulate_trade(df, i, 'short', stop, target)
                if result:
                    trades.append(Trade(
                        ticker=ticker, pattern='Shooter', direction='short',
                        **result
                    ))
    
    return trades

# === Statistics ===

def calculate_stats(trades: List[Trade]) -> Dict:
    """Calculate performance statistics for a list of trades"""
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_gain': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'sharpe': 0,
            'expectancy': 0
        }
    
    pnls = [t.pnl_pct for t in trades if t.pnl_pct is not None]
    if not pnls:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_gain': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'sharpe': 0,
            'expectancy': 0
        }
    
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    avg_gain = np.mean(wins) * 100 if wins else 0
    avg_loss = abs(np.mean(losses)) * 100 if losses else 0
    
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    
    # Sharpe (annualized, assuming avg 5 day hold)
    if len(pnls) > 1:
        mean_ret = np.mean(pnls)
        std_ret = np.std(pnls)
        sharpe = (mean_ret / std_ret) * np.sqrt(252 / 5) if std_ret > 0 else 0
    else:
        sharpe = 0
    
    expectancy = np.mean(pnls) * 100
    
    return {
        'total_trades': len(pnls),
        'win_rate': round(win_rate, 1),
        'avg_gain': round(avg_gain, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 2),
        'sharpe': round(sharpe, 2),
        'expectancy': round(expectancy, 2)
    }

# === Main ===

def run_backtest():
    """Run full backtest on all cached price data"""
    cache_dir = Path.home() / 'clawd' / 'trading' / 'backtest_results' / 'price_cache'
    
    all_trades = []
    processed = 0
    errors = 0
    
    pkl_files = list(cache_dir.glob('*_1d.pkl'))
    print(f"Found {len(pkl_files)} daily price files")
    
    for pkl_file in pkl_files:
        ticker = pkl_file.stem.replace('_1d', '')
        try:
            with open(pkl_file, 'rb') as f:
                df = pickle.load(f)
            
            if len(df) < 50:  # Need enough history
                continue
            
            trades = find_pattern_trades(df, ticker)
            all_trades.extend(trades)
            processed += 1
            
            if processed % 50 == 0:
                print(f"Processed {processed}/{len(pkl_files)} tickers, {len(all_trades)} trades found")
                
        except Exception as e:
            errors += 1
            continue
    
    print(f"\nProcessed {processed} tickers, {errors} errors")
    print(f"Total trades found: {len(all_trades)}")
    
    # Group by pattern
    patterns = {}
    for trade in all_trades:
        if trade.pattern not in patterns:
            patterns[trade.pattern] = []
        patterns[trade.pattern].append(trade)
    
    # Also split by direction
    pattern_direction = {}
    for trade in all_trades:
        key = f"{trade.pattern} ({trade.direction})"
        if key not in pattern_direction:
            pattern_direction[key] = []
        pattern_direction[key].append(trade)
    
    # Calculate stats
    print("\n" + "="*80)
    print("PATTERN PERFORMANCE SUMMARY")
    print("="*80)
    
    results = []
    for pattern, trades in patterns.items():
        stats = calculate_stats(trades)
        stats['pattern'] = pattern
        results.append(stats)
        print(f"\n{pattern}:")
        print(f"  Trades: {stats['total_trades']}")
        print(f"  Win Rate: {stats['win_rate']}%")
        print(f"  Avg Gain: {stats['avg_gain']}% | Avg Loss: {stats['avg_loss']}%")
        print(f"  Profit Factor: {stats['profit_factor']}")
        print(f"  Sharpe: {stats['sharpe']}")
        print(f"  Expectancy: {stats['expectancy']}%")
    
    # Detailed by direction
    print("\n" + "="*80)
    print("BY DIRECTION (Long vs Short)")
    print("="*80)
    
    detailed_results = []
    for key, trades in pattern_direction.items():
        stats = calculate_stats(trades)
        stats['pattern'] = key
        detailed_results.append(stats)
    
    # Sort by profit factor
    detailed_results.sort(key=lambda x: x['profit_factor'], reverse=True)
    
    for r in detailed_results:
        print(f"{r['pattern']:25} | Trades: {r['total_trades']:4} | WR: {r['win_rate']:5.1f}% | PF: {r['profit_factor']:5.2f} | Sharpe: {r['sharpe']:5.2f} | Exp: {r['expectancy']:+5.2f}%")
    
    # Generate markdown report
    generate_report(results, detailed_results)
    
    return results, detailed_results

def generate_report(results: List[Dict], detailed_results: List[Dict]):
    """Generate markdown comparison report"""
    output_path = Path.home() / 'clawd' / 'trading' / 'backtest_results' / 'strat_patterns_comparison.md'
    
    # Sort by profit factor
    results.sort(key=lambda x: x['profit_factor'], reverse=True)
    
    md = """# Strat Pattern Performance Comparison

## Overview

Backtest of 6 Strat patterns across ~480 stocks using daily data.

**Trade Rules:**
- Entry: Pattern completes → buy/short next day open
- Stop Loss: Below pattern low (bullish) or above pattern high (bearish), max 8%
- Target: 2:1 risk/reward
- Time stop: Exit after 20 days if neither hit

---

## Rankings (Best to Worst)

| Rank | Pattern | Trades | Win Rate | Avg Gain | Avg Loss | Profit Factor | Sharpe | Expectancy |
|------|---------|--------|----------|----------|----------|---------------|--------|------------|
"""
    
    for i, r in enumerate(results, 1):
        md += f"| {i} | {r['pattern']} | {r['total_trades']} | {r['win_rate']}% | {r['avg_gain']}% | {r['avg_loss']}% | {r['profit_factor']} | {r['sharpe']} | {r['expectancy']:+.2f}% |\n"
    
    md += """
---

## Detailed Breakdown by Direction

| Pattern | Trades | Win Rate | Profit Factor | Sharpe | Expectancy |
|---------|--------|----------|---------------|--------|------------|
"""
    
    for r in detailed_results:
        md += f"| {r['pattern']} | {r['total_trades']} | {r['win_rate']}% | {r['profit_factor']} | {r['sharpe']} | {r['expectancy']:+.2f}% |\n"
    
    # Categorize
    continuations = [r for r in results if 'Cont' in r['pattern'] or 'Break' in r['pattern']]
    reversals = [r for r in results if 'Rev' in r['pattern'] or r['pattern'] in ['Hammer', 'Shooter']]
    
    cont_trades = sum(r['total_trades'] for r in continuations)
    cont_avg_pf = np.mean([r['profit_factor'] for r in continuations if r['profit_factor'] < float('inf')])
    
    rev_trades = sum(r['total_trades'] for r in reversals)
    rev_avg_pf = np.mean([r['profit_factor'] for r in reversals if r['profit_factor'] < float('inf')]) if reversals else 0
    
    md += f"""
---

## Key Question: Reversals vs Continuations

### Continuation Patterns
- **Patterns:** 2-1-2 Cont, 2-2 Cont, 1-2 Break
- **Total Trades:** {cont_trades}
- **Avg Profit Factor:** {cont_avg_pf:.2f}

### Reversal Patterns  
- **Patterns:** 3-1-2 Rev, Hammer, Shooter
- **Total Trades:** {rev_trades}
- **Avg Profit Factor:** {rev_avg_pf:.2f}

### Verdict

"""
    
    if cont_avg_pf > rev_avg_pf:
        md += "**Continuation patterns outperform reversals.** Trading with the trend is more reliable than trying to catch reversals.\n"
    elif rev_avg_pf > cont_avg_pf:
        md += "**Reversal patterns outperform continuations.** Counter-trend setups show edge when properly filtered.\n"
    else:
        md += "**Results are mixed.** No clear winner between continuation and reversal strategies.\n"
    
    md += """
---

## Methodology

- **Data:** Daily OHLCV for ~480 liquid US stocks
- **Period:** Full history available in cache (~5 years)
- **Pattern Detection:** Based on Rob Smith's Strat methodology
- **No Optimization:** Rules applied uniformly, no curve fitting

### Metrics Explained

- **Win Rate:** % of trades hitting target before stop
- **Avg Gain/Loss:** Mean P&L of winning/losing trades
- **Profit Factor:** Gross profit / gross loss (>1 = profitable)
- **Sharpe:** Risk-adjusted return (annualized)
- **Expectancy:** Average expected return per trade

---

*Generated by strat_backtest.py*
"""
    
    with open(output_path, 'w') as f:
        f.write(md)
    
    print(f"\n✅ Report saved to: {output_path}")


if __name__ == '__main__':
    run_backtest()
