#!/usr/bin/env python3
"""
Backtest: BEARISH Squeeze Releases (Shorting)

Tests squeeze releases with NEGATIVE momentum (shorts).

Scenarios:
1. Weekly Squeeze - Bearish Release
2. Daily Squeeze - Bearish Release
Broken down by level: HIGH, MED, LOW

Trade Rules:
- Entry: Squeeze releases (was ON, now OFF) with negative momentum → short next bar open
- Stop Loss: 8% ABOVE entry (short, so stop is higher)
- Target: 20% gain (price drops 20%)
- Time stop: Exit after 30 bars if neither hit
"""
import os
import pickle
import pandas as pd
import numpy as np
from datetime import datetime

CACHE_DIR = os.path.expanduser("~/clawd/trading/backtest_results/price_cache")
OUTPUT_DIR = os.path.expanduser("~/clawd/trading/backtest_results")


def wilder_rma(series, length):
    """Wilder's RMA (SMMA) - matches TradingView's ta.rma()"""
    alpha = 1.0 / length
    return series.ewm(alpha=alpha, adjust=False).mean()


def calculate_squeeze_series(df, bb_len=20, bb_mult=2.0, kc_len=20, kc_mult=2.0, atr_len=10):
    """
    Calculate Squeeze indicator for entire series.
    Returns DataFrame with squeeze_on, squeeze_count, depth, state, momentum columns.
    """
    if len(df) < max(bb_len, kc_len, atr_len) + 5:
        return None
    
    close = df['Close']
    high = df['High'] if 'High' in df.columns else close
    low = df['Low'] if 'Low' in df.columns else close
    
    # === Bollinger Bands (SMA basis) ===
    bb_basis = close.rolling(bb_len).mean()
    bb_dev = bb_mult * close.rolling(bb_len).std()
    bb_upper = bb_basis + bb_dev
    bb_lower = bb_basis - bb_dev
    bb_width = bb_upper - bb_lower
    
    # === Keltner Channels (EMA basis, Wilder's ATR) ===
    kc_basis = close.ewm(span=kc_len, adjust=False).mean()
    
    # True Range
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    tr.iloc[0] = high.iloc[0] - low.iloc[0]
    
    # ATR using Wilder's RMA
    atr = wilder_rma(tr, atr_len)
    
    kc_upper = kc_basis + (kc_mult * atr)
    kc_lower = kc_basis - (kc_mult * atr)
    kc_width = kc_upper - kc_lower
    
    # === Squeeze detection ===
    squeeze_on = (bb_upper < kc_upper) & (bb_lower > kc_lower)
    
    # Count consecutive squeeze bars (vectorized)
    squeeze_on_int = squeeze_on.astype(int)
    # Create groups that reset when squeeze turns off
    groups = (~squeeze_on).cumsum()
    # Within each group, cumsum gives consecutive count
    squeeze_count = squeeze_on_int.groupby(groups).cumsum()
    
    # Depth calculation
    depth = (kc_width - bb_width) / kc_width
    depth = depth.fillna(0)
    
    # Momentum (using 12-period rate of change as momentum proxy)
    momentum = close.pct_change(12)
    
    # Create result DataFrame
    result = pd.DataFrame({
        'squeeze_on': squeeze_on,
        'squeeze_count': squeeze_count,
        'depth': depth,
        'momentum': momentum,
        'close': close,
        'open': df['Open'] if 'Open' in df.columns else close,
        'high': high,
        'low': low
    }, index=df.index)
    
    # Classify squeeze level
    def classify_squeeze(row):
        if not row['squeeze_on']:
            return 'NONE'
        if row['squeeze_count'] >= 10 and row['depth'] >= 0.25:
            return 'HIGH'
        if row['squeeze_count'] >= 5 and row['depth'] >= 0.10:
            return 'MED'
        return 'LOW'
    
    result['state'] = result.apply(classify_squeeze, axis=1)
    
    # Previous values for release detection
    result['prev_squeeze_on'] = squeeze_on.shift(1)
    result['prev_state'] = result['state'].shift(1)
    
    return result


def run_bearish_backtest(level, all_data, timeframe='weekly'):
    """
    Run BEARISH (short) backtest for a specific squeeze level.
    
    Entry on squeeze release with NEGATIVE momentum.
    Short trade rules (inverted from long):
    - Entry: short at next bar open
    - Stop: 8% ABOVE entry (we lose if price goes up)
    - Target: 20% below entry (we win if price goes down)
    """
    trades = []
    
    for ticker, df_data in all_data.items():
        if df_data is None or len(df_data) < 50:
            continue
        
        # Calculate squeeze series
        squeeze_data = calculate_squeeze_series(df_data)
        if squeeze_data is None:
            continue
        
        # Find bearish release signals for this level
        for i in range(2, len(squeeze_data) - 31):  # Need 30 bars forward
            row = squeeze_data.iloc[i]
            prev_row = squeeze_data.iloc[i-1]
            
            # Check for release of specific level
            if prev_row['state'] == level and row['state'] == 'NONE':
                # Check momentum is NEGATIVE (bearish)
                if prev_row['momentum'] < 0:
                    # Entry at next bar's open
                    entry_idx = i + 1
                    if entry_idx >= len(squeeze_data):
                        continue
                    
                    entry_price = float(squeeze_data.iloc[entry_idx]['open'])
                    entry_date = squeeze_data.index[entry_idx]
                    
                    # SHORT trade: stop is ABOVE, target is BELOW
                    stop_price = entry_price * 1.08   # 8% above = stop loss
                    target_price = entry_price * 0.80  # 20% below = target profit
                    
                    exit_price = None
                    exit_date = None
                    exit_reason = None
                    
                    for j in range(entry_idx + 1, min(entry_idx + 31, len(squeeze_data))):
                        bar = squeeze_data.iloc[j]
                        bar_date = squeeze_data.index[j]
                        
                        bar_high = float(bar['high'])
                        bar_low = float(bar['low'])
                        
                        # SHORT: Stop is hit if price goes UP to stop level
                        if bar_high >= stop_price:
                            exit_price = stop_price
                            exit_date = bar_date
                            exit_reason = 'STOP'
                            break
                        
                        # SHORT: Target hit if price goes DOWN to target level
                        if bar_low <= target_price:
                            exit_price = target_price
                            exit_date = bar_date
                            exit_reason = 'TARGET'
                            break
                    
                    # Time stop if neither hit
                    if exit_price is None:
                        final_idx = min(entry_idx + 30, len(squeeze_data) - 1)
                        exit_price = float(squeeze_data.iloc[final_idx]['close'])
                        exit_date = squeeze_data.index[final_idx]
                        exit_reason = 'TIME'
                    
                    # Calculate return for SHORT trade
                    # SHORT: profit = (entry - exit) / entry
                    # If price drops, we profit. If price rises, we lose.
                    pct_return = (entry_price - exit_price) / entry_price * 100
                    
                    trades.append({
                        'ticker': ticker,
                        'level': level,
                        'timeframe': timeframe,
                        'direction': 'SHORT',
                        'entry_date': entry_date,
                        'entry_price': entry_price,
                        'exit_date': exit_date,
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'pct_return': pct_return,
                        'squeeze_count': prev_row['squeeze_count'],
                        'depth': prev_row['depth'],
                        'momentum': prev_row['momentum']
                    })
    
    return trades


def calculate_metrics(trades):
    """Calculate backtest metrics from list of trades."""
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_gain': 0,
            'avg_loss': 0,
            'sharpe': 0,
            'profit_factor': 0,
            'total_return': 0,
            'max_drawdown': 0,
            'target_exits': 0,
            'stop_exits': 0,
            'time_exits': 0
        }
    
    returns = [t['pct_return'] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    
    total_trades = len(trades)
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    avg_gain = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    
    # Sharpe ratio (annualized)
    if len(returns) > 1 and np.std(returns) > 0:
        # For weekly: sqrt(52), for daily: sqrt(252)
        ann_factor = np.sqrt(52) if trades[0].get('timeframe') == 'weekly' else np.sqrt(252)
        sharpe = (np.mean(returns) / np.std(returns)) * ann_factor
    else:
        sharpe = 0
    
    # Profit factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0.01
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # Total return
    total_return = sum(returns)
    
    # Max drawdown
    cumulative = np.cumsum(returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = cumulative - running_max
    max_drawdown = abs(min(drawdowns)) if len(drawdowns) > 0 else 0
    
    # Exit breakdown
    target_exits = len([t for t in trades if t['exit_reason'] == 'TARGET'])
    stop_exits = len([t for t in trades if t['exit_reason'] == 'STOP'])
    time_exits = len([t for t in trades if t['exit_reason'] == 'TIME'])
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'avg_gain': avg_gain,
        'avg_loss': avg_loss,
        'sharpe': sharpe,
        'profit_factor': profit_factor,
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'target_exits': target_exits,
        'stop_exits': stop_exits,
        'time_exits': time_exits
    }


def load_cached_data(interval='1wk'):
    """Load all cached price data for specified interval."""
    all_data = {}
    suffix = f'_{interval}.pkl'
    
    cache_files = [f for f in os.listdir(CACHE_DIR) if f.endswith(suffix)]
    
    for filename in cache_files:
        ticker = filename.replace(suffix, '')
        filepath = os.path.join(CACHE_DIR, filename)
        
        try:
            with open(filepath, 'rb') as f:
                df = pickle.load(f)
            
            # Ensure proper format
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Make sure index is datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            all_data[ticker] = df
            
        except Exception as e:
            continue
    
    return all_data


def main():
    print("=" * 70)
    print("BEARISH SQUEEZE BACKTEST (SHORTS)")
    print("=" * 70)
    print()
    print("Testing: Squeeze releases with NEGATIVE momentum → SHORT")
    print("Stop: 8% above entry | Target: 20% drop | Time: 30 bars")
    print()
    
    # Load cached data
    print("Loading cached data...")
    weekly_data = load_cached_data('1wk')
    daily_data = load_cached_data('1d')
    print(f"  Weekly: {len(weekly_data)} stocks")
    print(f"  Daily: {len(daily_data)} stocks")
    print()
    
    results = {}
    all_trades = {}
    
    # Run backtests for each timeframe and level
    for timeframe, data, tf_label in [('weekly', weekly_data, 'Weekly'), ('daily', daily_data, 'Daily')]:
        for level in ['HIGH', 'MED', 'LOW']:
            key = f"{tf_label}_{level}"
            print(f"Running {tf_label} {level} bearish backtest...")
            trades = run_bearish_backtest(level, data, timeframe=timeframe)
            all_trades[key] = trades
            metrics = calculate_metrics(trades)
            results[key] = metrics
            print(f"  → {metrics['total_trades']} trades, Win rate: {metrics['win_rate']:.1f}%")
    
    print()
    print("=" * 70)
    print("RESULTS COMPARISON")
    print("=" * 70)
    print()
    
    # Print comparison table
    print("WEEKLY BEARISH SQUEEZE SHORTS:")
    print("-" * 60)
    print(f"{'Metric':<20} {'HIGH':>12} {'MED':>12} {'LOW':>12}")
    print("-" * 60)
    for level in ['HIGH', 'MED', 'LOW']:
        key = f"Weekly_{level}"
        if level == 'HIGH':
            print(f"{'Total Trades':<20}", end="")
        else:
            print(f"{'':<20}", end="")
    print(f"{results['Weekly_HIGH']['total_trades']:>12} {results['Weekly_MED']['total_trades']:>12} {results['Weekly_LOW']['total_trades']:>12}")
    print(f"{'Win Rate %':<20} {results['Weekly_HIGH']['win_rate']:>11.1f}% {results['Weekly_MED']['win_rate']:>11.1f}% {results['Weekly_LOW']['win_rate']:>11.1f}%")
    print(f"{'Avg Gain %':<20} {results['Weekly_HIGH']['avg_gain']:>11.1f}% {results['Weekly_MED']['avg_gain']:>11.1f}% {results['Weekly_LOW']['avg_gain']:>11.1f}%")
    print(f"{'Avg Loss %':<20} {results['Weekly_HIGH']['avg_loss']:>11.1f}% {results['Weekly_MED']['avg_loss']:>11.1f}% {results['Weekly_LOW']['avg_loss']:>11.1f}%")
    print(f"{'Sharpe Ratio':<20} {results['Weekly_HIGH']['sharpe']:>12.2f} {results['Weekly_MED']['sharpe']:>12.2f} {results['Weekly_LOW']['sharpe']:>12.2f}")
    print(f"{'Profit Factor':<20} {results['Weekly_HIGH']['profit_factor']:>12.2f} {results['Weekly_MED']['profit_factor']:>12.2f} {results['Weekly_LOW']['profit_factor']:>12.2f}")
    
    print()
    print("DAILY BEARISH SQUEEZE SHORTS:")
    print("-" * 60)
    print(f"{'Metric':<20} {'HIGH':>12} {'MED':>12} {'LOW':>12}")
    print("-" * 60)
    print(f"{'Total Trades':<20} {results['Daily_HIGH']['total_trades']:>12} {results['Daily_MED']['total_trades']:>12} {results['Daily_LOW']['total_trades']:>12}")
    print(f"{'Win Rate %':<20} {results['Daily_HIGH']['win_rate']:>11.1f}% {results['Daily_MED']['win_rate']:>11.1f}% {results['Daily_LOW']['win_rate']:>11.1f}%")
    print(f"{'Avg Gain %':<20} {results['Daily_HIGH']['avg_gain']:>11.1f}% {results['Daily_MED']['avg_gain']:>11.1f}% {results['Daily_LOW']['avg_gain']:>11.1f}%")
    print(f"{'Avg Loss %':<20} {results['Daily_HIGH']['avg_loss']:>11.1f}% {results['Daily_MED']['avg_loss']:>11.1f}% {results['Daily_LOW']['avg_loss']:>11.1f}%")
    print(f"{'Sharpe Ratio':<20} {results['Daily_HIGH']['sharpe']:>12.2f} {results['Daily_MED']['sharpe']:>12.2f} {results['Daily_LOW']['sharpe']:>12.2f}")
    print(f"{'Profit Factor':<20} {results['Daily_HIGH']['profit_factor']:>12.2f} {results['Daily_MED']['profit_factor']:>12.2f} {results['Daily_LOW']['profit_factor']:>12.2f}")
    
    print()
    print("WEEKLY vs DAILY COMPARISON:")
    print("-" * 60)
    
    # Aggregate weekly vs daily
    weekly_trades = []
    daily_trades = []
    for level in ['HIGH', 'MED', 'LOW']:
        weekly_trades.extend(all_trades.get(f"Weekly_{level}", []))
        daily_trades.extend(all_trades.get(f"Daily_{level}", []))
    
    weekly_agg = calculate_metrics(weekly_trades)
    daily_agg = calculate_metrics(daily_trades)
    
    print(f"{'Metric':<20} {'WEEKLY':>15} {'DAILY':>15}")
    print("-" * 60)
    print(f"{'Total Trades':<20} {weekly_agg['total_trades']:>15} {daily_agg['total_trades']:>15}")
    print(f"{'Win Rate %':<20} {weekly_agg['win_rate']:>14.1f}% {daily_agg['win_rate']:>14.1f}%")
    print(f"{'Avg Gain %':<20} {weekly_agg['avg_gain']:>14.1f}% {daily_agg['avg_gain']:>14.1f}%")
    print(f"{'Avg Loss %':<20} {weekly_agg['avg_loss']:>14.1f}% {daily_agg['avg_loss']:>14.1f}%")
    print(f"{'Sharpe Ratio':<20} {weekly_agg['sharpe']:>15.2f} {daily_agg['sharpe']:>15.2f}")
    print(f"{'Profit Factor':<20} {weekly_agg['profit_factor']:>15.2f} {daily_agg['profit_factor']:>15.2f}")
    
    # Generate markdown report
    md_report = generate_markdown_report(results, all_trades, weekly_agg, daily_agg)
    
    output_path = os.path.join(OUTPUT_DIR, "bearish_squeeze_comparison.md")
    with open(output_path, 'w') as f:
        f.write(md_report)
    
    print()
    print(f"📊 Report saved to: {output_path}")
    
    # Save detailed trades
    for key, trades in all_trades.items():
        if trades:
            df_trades = pd.DataFrame(trades)
            csv_path = os.path.join(OUTPUT_DIR, f"bearish_{key.lower()}_trades.csv")
            df_trades.to_csv(csv_path, index=False)
            print(f"📄 Trades saved to: {csv_path}")


def generate_markdown_report(results, all_trades, weekly_agg, daily_agg):
    """Generate comprehensive markdown report."""
    
    md = f"""# Bearish Squeeze Backtest: Shorts Comparison

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

## Strategy: Short on Bearish Squeeze Release

### Trade Rules
- **Entry:** Squeeze releases (was ON, now OFF) with **negative** momentum → SHORT next bar open
- **Stop Loss:** 8% ABOVE entry (we lose if price rises)
- **Target:** 20% gain (price drops 20% from entry)
- **Time Stop:** Exit after 30 bars if neither hit

### Squeeze Level Definitions
| Level | Criteria |
|-------|----------|
| **HIGH** | squeeze_on AND squeeze_count >= 10 bars AND depth >= 0.25 |
| **MED** | squeeze_on AND squeeze_count >= 5 bars AND depth >= 0.10 (not HIGH) |
| **LOW** | squeeze_on but doesn't meet HIGH or MED thresholds |

---

## Results Summary

### 🗓️ WEEKLY Bearish Squeeze Shorts

| Metric | HIGH | MED | LOW |
|--------|-----:|----:|----:|
| **Total Trades** | {results['Weekly_HIGH']['total_trades']} | {results['Weekly_MED']['total_trades']} | {results['Weekly_LOW']['total_trades']} |
| **Win Rate** | {results['Weekly_HIGH']['win_rate']:.1f}% | {results['Weekly_MED']['win_rate']:.1f}% | {results['Weekly_LOW']['win_rate']:.1f}% |
| **Avg Gain** | +{results['Weekly_HIGH']['avg_gain']:.1f}% | +{results['Weekly_MED']['avg_gain']:.1f}% | +{results['Weekly_LOW']['avg_gain']:.1f}% |
| **Avg Loss** | {results['Weekly_HIGH']['avg_loss']:.1f}% | {results['Weekly_MED']['avg_loss']:.1f}% | {results['Weekly_LOW']['avg_loss']:.1f}% |
| **Sharpe Ratio** | {results['Weekly_HIGH']['sharpe']:.2f} | {results['Weekly_MED']['sharpe']:.2f} | {results['Weekly_LOW']['sharpe']:.2f} |
| **Profit Factor** | {results['Weekly_HIGH']['profit_factor']:.2f} | {results['Weekly_MED']['profit_factor']:.2f} | {results['Weekly_LOW']['profit_factor']:.2f} |
| **Total Return** | {results['Weekly_HIGH']['total_return']:.1f}% | {results['Weekly_MED']['total_return']:.1f}% | {results['Weekly_LOW']['total_return']:.1f}% |

#### Weekly Exit Breakdown
| Exit Type | HIGH | MED | LOW |
|-----------|-----:|----:|----:|
| Target (20% drop) | {results['Weekly_HIGH']['target_exits']} | {results['Weekly_MED']['target_exits']} | {results['Weekly_LOW']['target_exits']} |
| Stop (8% rise) | {results['Weekly_HIGH']['stop_exits']} | {results['Weekly_MED']['stop_exits']} | {results['Weekly_LOW']['stop_exits']} |
| Time (30 bars) | {results['Weekly_HIGH']['time_exits']} | {results['Weekly_MED']['time_exits']} | {results['Weekly_LOW']['time_exits']} |

---

### 📅 DAILY Bearish Squeeze Shorts

| Metric | HIGH | MED | LOW |
|--------|-----:|----:|----:|
| **Total Trades** | {results['Daily_HIGH']['total_trades']} | {results['Daily_MED']['total_trades']} | {results['Daily_LOW']['total_trades']} |
| **Win Rate** | {results['Daily_HIGH']['win_rate']:.1f}% | {results['Daily_MED']['win_rate']:.1f}% | {results['Daily_LOW']['win_rate']:.1f}% |
| **Avg Gain** | +{results['Daily_HIGH']['avg_gain']:.1f}% | +{results['Daily_MED']['avg_gain']:.1f}% | +{results['Daily_LOW']['avg_gain']:.1f}% |
| **Avg Loss** | {results['Daily_HIGH']['avg_loss']:.1f}% | {results['Daily_MED']['avg_loss']:.1f}% | {results['Daily_LOW']['avg_loss']:.1f}% |
| **Sharpe Ratio** | {results['Daily_HIGH']['sharpe']:.2f} | {results['Daily_MED']['sharpe']:.2f} | {results['Daily_LOW']['sharpe']:.2f} |
| **Profit Factor** | {results['Daily_HIGH']['profit_factor']:.2f} | {results['Daily_MED']['profit_factor']:.2f} | {results['Daily_LOW']['profit_factor']:.2f} |
| **Total Return** | {results['Daily_HIGH']['total_return']:.1f}% | {results['Daily_MED']['total_return']:.1f}% | {results['Daily_LOW']['total_return']:.1f}% |

#### Daily Exit Breakdown
| Exit Type | HIGH | MED | LOW |
|-----------|-----:|----:|----:|
| Target (20% drop) | {results['Daily_HIGH']['target_exits']} | {results['Daily_MED']['target_exits']} | {results['Daily_LOW']['target_exits']} |
| Stop (8% rise) | {results['Daily_HIGH']['stop_exits']} | {results['Daily_MED']['stop_exits']} | {results['Daily_LOW']['stop_exits']} |
| Time (30 bars) | {results['Daily_HIGH']['time_exits']} | {results['Daily_MED']['time_exits']} | {results['Daily_LOW']['time_exits']} |

---

## 📊 WEEKLY vs DAILY: Head-to-Head

| Metric | WEEKLY (all) | DAILY (all) | Winner |
|--------|-------------:|------------:|--------|
| **Total Trades** | {weekly_agg['total_trades']} | {daily_agg['total_trades']} | {'Daily' if daily_agg['total_trades'] > weekly_agg['total_trades'] else 'Weekly'} |
| **Win Rate** | {weekly_agg['win_rate']:.1f}% | {daily_agg['win_rate']:.1f}% | {'Daily' if daily_agg['win_rate'] > weekly_agg['win_rate'] else 'Weekly'} |
| **Avg Gain** | +{weekly_agg['avg_gain']:.1f}% | +{daily_agg['avg_gain']:.1f}% | {'Daily' if daily_agg['avg_gain'] > weekly_agg['avg_gain'] else 'Weekly'} |
| **Avg Loss** | {weekly_agg['avg_loss']:.1f}% | {daily_agg['avg_loss']:.1f}% | {'Daily' if daily_agg['avg_loss'] > weekly_agg['avg_loss'] else 'Weekly'} |
| **Sharpe Ratio** | {weekly_agg['sharpe']:.2f} | {daily_agg['sharpe']:.2f} | {'Daily' if daily_agg['sharpe'] > weekly_agg['sharpe'] else 'Weekly'} |
| **Profit Factor** | {weekly_agg['profit_factor']:.2f} | {daily_agg['profit_factor']:.2f} | {'Daily' if daily_agg['profit_factor'] > weekly_agg['profit_factor'] else 'Weekly'} |

---

## 🔑 Key Questions Answered

### 1. Do bearish squeeze breakdowns work for shorting?

"""
    
    # Analyze if shorting works
    all_weekly_pf = weekly_agg['profit_factor']
    all_daily_pf = daily_agg['profit_factor']
    all_weekly_wr = weekly_agg['win_rate']
    all_daily_wr = daily_agg['win_rate']
    
    shorting_works = (all_weekly_pf > 1.0 or all_daily_pf > 1.0)
    
    if shorting_works:
        md += "**YES - Bearish squeeze releases show edge for shorting.**\n\n"
        if all_weekly_pf > 1.0 and all_daily_pf > 1.0:
            md += "Both weekly and daily timeframes show profit factor > 1.0, indicating a positive expectancy.\n"
        elif all_weekly_pf > 1.0:
            md += "Weekly timeframe shows positive expectancy (PF > 1.0). Daily timeframe is weaker.\n"
        else:
            md += "Daily timeframe shows positive expectancy (PF > 1.0). Weekly timeframe is weaker.\n"
    else:
        md += "**NO - Bearish squeeze releases do NOT show consistent edge for shorting.**\n\n"
        md += "Both timeframes show profit factor <= 1.0, indicating negative or break-even expectancy.\n"
        md += "Shorting squeeze releases may not be a viable strategy with these parameters.\n"
    
    md += "\n### 2. Is weekly or daily better for shorts?\n\n"
    
    # Compare weekly vs daily
    if weekly_agg['sharpe'] > daily_agg['sharpe'] and weekly_agg['profit_factor'] > daily_agg['profit_factor']:
        md += "**WEEKLY is better for shorting.**\n\n"
        md += f"Weekly shows better risk-adjusted returns (Sharpe: {weekly_agg['sharpe']:.2f} vs {daily_agg['sharpe']:.2f}) "
        md += f"and better profit factor ({weekly_agg['profit_factor']:.2f} vs {daily_agg['profit_factor']:.2f}).\n"
    elif daily_agg['sharpe'] > weekly_agg['sharpe'] and daily_agg['profit_factor'] > weekly_agg['profit_factor']:
        md += "**DAILY is better for shorting.**\n\n"
        md += f"Daily shows better risk-adjusted returns (Sharpe: {daily_agg['sharpe']:.2f} vs {weekly_agg['sharpe']:.2f}) "
        md += f"and better profit factor ({daily_agg['profit_factor']:.2f} vs {weekly_agg['profit_factor']:.2f}).\n"
    else:
        md += "**Mixed results - no clear winner.**\n\n"
        md += "Weekly and daily have different strengths. Weekly may have better individual trades, "
        md += "while daily offers more opportunities.\n"
    
    md += "\n### 3. Which squeeze level is best for shorts?\n\n"
    
    # Find best level
    best_weekly_level = max(['HIGH', 'MED', 'LOW'], key=lambda l: results[f'Weekly_{l}']['profit_factor'])
    best_daily_level = max(['HIGH', 'MED', 'LOW'], key=lambda l: results[f'Daily_{l}']['profit_factor'])
    
    md += f"- **Best Weekly Level:** {best_weekly_level} (PF: {results[f'Weekly_{best_weekly_level}']['profit_factor']:.2f})\n"
    md += f"- **Best Daily Level:** {best_daily_level} (PF: {results[f'Daily_{best_daily_level}']['profit_factor']:.2f})\n"
    
    md += """

---

## 📝 Conclusions & Recommendations

"""
    
    # Generate recommendations
    if shorting_works:
        md += "### ✅ Shorting bearish squeezes shows potential\n\n"
        if weekly_agg['profit_factor'] > daily_agg['profit_factor']:
            md += f"**Recommendation:** Focus on WEEKLY {best_weekly_level} squeeze releases for shorts.\n"
        else:
            md += f"**Recommendation:** Focus on DAILY {best_daily_level} squeeze releases for shorts.\n"
        md += "\n**Key considerations:**\n"
        md += "- Use proper position sizing (shorting has unlimited loss potential)\n"
        md += "- Consider only shorting during confirmed downtrends\n"
        md += "- Watch for squeeze releases at key resistance levels\n"
    else:
        md += "### ⚠️ Shorting bearish squeezes shows weak/negative edge\n\n"
        md += "**Recommendation:** This strategy may not be worth pursuing as-is.\n\n"
        md += "**Possible improvements to test:**\n"
        md += "- Tighter stops (6% vs 8%)\n"
        md += "- Smaller profit targets (10-15% vs 20%)\n"
        md += "- Add trend filter (only short below 50/200 MA)\n"
        md += "- Add sector/market regime filter\n"
        md += "- Focus on specific sectors that trend down\n"
    
    md += f"""

---

## Data Notes
- **Universe:** ~480 S&P 500 stocks (cached data)
- **Weekly bars:** {len(all_trades.get('Weekly_HIGH', [])) + len(all_trades.get('Weekly_MED', [])) + len(all_trades.get('Weekly_LOW', []))} total signals
- **Daily bars:** {len(all_trades.get('Daily_HIGH', [])) + len(all_trades.get('Daily_MED', [])) + len(all_trades.get('Daily_LOW', []))} total signals
- **Period:** Available cache history

---

*Report generated by bearish_squeeze_backtest.py*
"""
    
    return md


if __name__ == "__main__":
    main()
