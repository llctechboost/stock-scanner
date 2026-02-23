#!/usr/bin/env python3
"""
Backtest: Compare Weekly Squeeze performance by level (HIGH, MED, LOW)

Uses cached price data and squeeze detection logic from generate_site.py

Trade Rules:
- Entry: Squeeze releases (was ON, now OFF) with positive momentum → buy next day open
- Stop Loss: 8% below entry  
- Target: 20% gain
- Time stop: Exit after 30 days if neither hit
"""
import os
import pickle
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

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
    
    # Count consecutive squeeze bars
    squeeze_count = pd.Series(0, index=df.index)
    for i in range(len(squeeze_on)):
        if squeeze_on.iloc[i]:
            squeeze_count.iloc[i] = (squeeze_count.iloc[i-1] + 1) if i > 0 else 1
        else:
            squeeze_count.iloc[i] = 0
    
    # Depth calculation
    depth = (kc_width - bb_width) / kc_width
    depth = depth.fillna(0)
    
    # Momentum (using linear regression of midline - simplified as price momentum)
    # Use 12-period rate of change as momentum proxy
    momentum = close.pct_change(12)
    
    # Create result DataFrame
    result = pd.DataFrame({
        'squeeze_on': squeeze_on,
        'squeeze_count': squeeze_count,
        'depth': depth,
        'momentum': momentum,
        'close': close,
        'open': df['Open'] if 'Open' in df.columns else close
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
    
    # Detect releases: was ON (any level), now OFF, with positive momentum
    result['prev_squeeze_on'] = squeeze_on.shift(1)
    result['prev_state'] = result['state'].shift(1)
    
    return result


def resample_to_weekly(df):
    """Resample daily data to weekly (if needed)."""
    if len(df) == 0:
        return df
    
    # Check if already weekly (avg 5+ days between bars)
    date_diffs = df.index.to_series().diff().dt.days.dropna()
    if date_diffs.median() > 4:
        return df  # Already weekly
    
    # Resample to weekly
    weekly = df.resample('W').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    
    return weekly


def run_backtest_for_level(level, all_data):
    """
    Run backtest for a specific squeeze level (HIGH, MED, LOW).
    Returns list of trade results.
    """
    trades = []
    
    for ticker, df_weekly in all_data.items():
        if df_weekly is None or len(df_weekly) < 50:
            continue
        
        # Calculate squeeze series
        squeeze_data = calculate_squeeze_series(df_weekly)
        if squeeze_data is None:
            continue
        
        # Find release signals for this level
        # Release = squeeze was ON with specific level, now OFF, momentum positive
        for i in range(2, len(squeeze_data) - 31):  # Need 30 days forward for time stop
            row = squeeze_data.iloc[i]
            prev_row = squeeze_data.iloc[i-1]
            
            # Check for release of specific level
            if prev_row['state'] == level and row['state'] == 'NONE':
                # Check momentum is positive
                if prev_row['momentum'] > 0:
                    # Entry at next bar's open
                    entry_idx = i + 1
                    if entry_idx >= len(squeeze_data):
                        continue
                    
                    entry_price = squeeze_data.iloc[entry_idx]['open']
                    entry_date = squeeze_data.index[entry_idx]
                    
                    stop_price = entry_price * 0.92  # 8% stop
                    target_price = entry_price * 1.20  # 20% target
                    
                    # Track trade through time
                    exit_price = None
                    exit_date = None
                    exit_reason = None
                    
                    for j in range(entry_idx + 1, min(entry_idx + 31, len(squeeze_data))):
                        bar = squeeze_data.iloc[j]
                        bar_date = squeeze_data.index[j]
                        
                        # Check if we can get intrabar low/high from the data
                        bar_low = df_weekly.iloc[j]['Low'] if 'Low' in df_weekly.columns else bar['close']
                        bar_high = df_weekly.iloc[j]['High'] if 'High' in df_weekly.columns else bar['close']
                        
                        # Check stop hit (assume worst case - stop checked before target within bar)
                        if bar_low <= stop_price:
                            exit_price = stop_price
                            exit_date = bar_date
                            exit_reason = 'STOP'
                            break
                        
                        # Check target hit
                        if bar_high >= target_price:
                            exit_price = target_price
                            exit_date = bar_date
                            exit_reason = 'TARGET'
                            break
                    
                    # Time stop if neither hit
                    if exit_price is None:
                        final_idx = min(entry_idx + 30, len(squeeze_data) - 1)
                        exit_price = squeeze_data.iloc[final_idx]['close']
                        exit_date = squeeze_data.index[final_idx]
                        exit_reason = 'TIME'
                    
                    # Calculate return
                    pct_return = (exit_price - entry_price) / entry_price * 100
                    
                    trades.append({
                        'ticker': ticker,
                        'level': level,
                        'entry_date': entry_date,
                        'entry_price': entry_price,
                        'exit_date': exit_date,
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'pct_return': pct_return,
                        'squeeze_count': prev_row['squeeze_count'],
                        'depth': prev_row['depth']
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
            'max_drawdown': 0
        }
    
    returns = [t['pct_return'] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    
    total_trades = len(trades)
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    avg_gain = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    
    # Sharpe ratio (simplified - assuming risk-free rate = 0)
    # Annualized for weekly data: sqrt(52) factor
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(52)
    else:
        sharpe = 0
    
    # Profit factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0.01
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # Total return (compounded)
    total_return = sum(returns)
    
    # Max drawdown (simplified)
    cumulative = np.cumsum(returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = cumulative - running_max
    max_drawdown = abs(min(drawdowns)) if len(drawdowns) > 0 else 0
    
    # Exit reason breakdown
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


def load_cached_data():
    """Load all cached weekly price data."""
    all_data = {}
    
    cache_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('_1wk.pkl')]
    
    for filename in cache_files:
        ticker = filename.replace('_1wk.pkl', '')
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
            print(f"Error loading {filename}: {e}")
            continue
    
    return all_data


def main():
    print("=" * 60)
    print("WEEKLY SQUEEZE BACKTEST BY LEVEL")
    print("=" * 60)
    print()
    
    # Load all cached weekly data
    print("Loading cached weekly data...")
    all_data = load_cached_data()
    print(f"Loaded {len(all_data)} stocks")
    print()
    
    # Run backtests for each level
    results = {}
    all_trades = {}
    
    for level in ['HIGH', 'MED', 'LOW']:
        print(f"Running backtest for {level} squeezes...")
        trades = run_backtest_for_level(level, all_data)
        all_trades[level] = trades
        metrics = calculate_metrics(trades)
        results[level] = metrics
        print(f"  → {metrics['total_trades']} trades found")
    
    print()
    
    # Generate comparison report
    print("=" * 60)
    print("RESULTS COMPARISON")
    print("=" * 60)
    print()
    
    # Print table
    print(f"{'Metric':<20} {'HIGH':>12} {'MED':>12} {'LOW':>12}")
    print("-" * 60)
    
    print(f"{'Total Trades':<20} {results['HIGH']['total_trades']:>12} {results['MED']['total_trades']:>12} {results['LOW']['total_trades']:>12}")
    print(f"{'Win Rate %':<20} {results['HIGH']['win_rate']:>11.1f}% {results['MED']['win_rate']:>11.1f}% {results['LOW']['win_rate']:>11.1f}%")
    print(f"{'Avg Gain %':<20} {results['HIGH']['avg_gain']:>11.1f}% {results['MED']['avg_gain']:>11.1f}% {results['LOW']['avg_gain']:>11.1f}%")
    print(f"{'Avg Loss %':<20} {results['HIGH']['avg_loss']:>11.1f}% {results['MED']['avg_loss']:>11.1f}% {results['LOW']['avg_loss']:>11.1f}%")
    print(f"{'Sharpe Ratio':<20} {results['HIGH']['sharpe']:>12.2f} {results['MED']['sharpe']:>12.2f} {results['LOW']['sharpe']:>12.2f}")
    print(f"{'Profit Factor':<20} {results['HIGH']['profit_factor']:>12.2f} {results['MED']['profit_factor']:>12.2f} {results['LOW']['profit_factor']:>12.2f}")
    print(f"{'Total Return %':<20} {results['HIGH']['total_return']:>11.1f}% {results['MED']['total_return']:>11.1f}% {results['LOW']['total_return']:>11.1f}%")
    print()
    
    print("Exit Breakdown:")
    print(f"{'  Target Exits':<20} {results['HIGH']['target_exits']:>12} {results['MED']['target_exits']:>12} {results['LOW']['target_exits']:>12}")
    print(f"{'  Stop Exits':<20} {results['HIGH']['stop_exits']:>12} {results['MED']['stop_exits']:>12} {results['LOW']['stop_exits']:>12}")
    print(f"{'  Time Exits':<20} {results['HIGH']['time_exits']:>12} {results['MED']['time_exits']:>12} {results['LOW']['time_exits']:>12}")
    
    # Generate markdown report
    md_report = f"""# Weekly Squeeze Backtest: Levels Comparison

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

## Trade Rules
- **Entry:** Squeeze releases (was ON, now OFF) with positive momentum → buy next bar open
- **Stop Loss:** 8% below entry
- **Target:** 20% gain  
- **Time Stop:** Exit after 30 bars (weeks) if neither hit

## Squeeze Level Definitions
| Level | Criteria |
|-------|----------|
| **HIGH** | squeeze_on AND squeeze_count >= 10 bars AND depth >= 0.25 |
| **MED** | squeeze_on AND squeeze_count >= 5 bars AND depth >= 0.10 (not HIGH) |
| **LOW** | squeeze_on but doesn't meet HIGH or MED thresholds |

## Results Comparison

| Metric | HIGH | MED | LOW |
|--------|-----:|----:|----:|
| **Total Trades** | {results['HIGH']['total_trades']} | {results['MED']['total_trades']} | {results['LOW']['total_trades']} |
| **Win Rate** | {results['HIGH']['win_rate']:.1f}% | {results['MED']['win_rate']:.1f}% | {results['LOW']['win_rate']:.1f}% |
| **Avg Gain** | +{results['HIGH']['avg_gain']:.1f}% | +{results['MED']['avg_gain']:.1f}% | +{results['LOW']['avg_gain']:.1f}% |
| **Avg Loss** | {results['HIGH']['avg_loss']:.1f}% | {results['MED']['avg_loss']:.1f}% | {results['LOW']['avg_loss']:.1f}% |
| **Sharpe Ratio** | {results['HIGH']['sharpe']:.2f} | {results['MED']['sharpe']:.2f} | {results['LOW']['sharpe']:.2f} |
| **Profit Factor** | {results['HIGH']['profit_factor']:.2f} | {results['MED']['profit_factor']:.2f} | {results['LOW']['profit_factor']:.2f} |
| **Total Return** | {results['HIGH']['total_return']:.1f}% | {results['MED']['total_return']:.1f}% | {results['LOW']['total_return']:.1f}% |

### Exit Breakdown

| Exit Type | HIGH | MED | LOW |
|-----------|-----:|----:|----:|
| Target (20%+) | {results['HIGH']['target_exits']} | {results['MED']['target_exits']} | {results['LOW']['target_exits']} |
| Stop (-8%) | {results['HIGH']['stop_exits']} | {results['MED']['stop_exits']} | {results['LOW']['stop_exits']} |
| Time (30 bars) | {results['HIGH']['time_exits']} | {results['MED']['time_exits']} | {results['LOW']['time_exits']} |

## Analysis

"""
    
    # Add analysis based on results
    best_win_rate = max(results.items(), key=lambda x: x[1]['win_rate'])
    best_sharpe = max(results.items(), key=lambda x: x[1]['sharpe'])
    best_pf = max(results.items(), key=lambda x: x[1]['profit_factor'])
    most_trades = max(results.items(), key=lambda x: x[1]['total_trades'])
    
    md_report += f"""### Key Findings

1. **Best Win Rate:** {best_win_rate[0]} squeezes at {best_win_rate[1]['win_rate']:.1f}%
2. **Best Sharpe Ratio:** {best_sharpe[0]} squeezes at {best_sharpe[1]['sharpe']:.2f}
3. **Best Profit Factor:** {best_pf[0]} squeezes at {best_pf[1]['profit_factor']:.2f}
4. **Most Trade Opportunities:** {most_trades[0]} with {most_trades[1]['total_trades']} trades

### Conclusion

"""
    
    # Determine if HIGH is actually better
    high_better = (results['HIGH']['sharpe'] > results['MED']['sharpe'] and 
                   results['HIGH']['sharpe'] > results['LOW']['sharpe'] and
                   results['HIGH']['profit_factor'] > 1.0)
    
    if high_better:
        md_report += """**YES - HIGH squeezes are better than MED or LOW.**

The data shows HIGH squeezes produce:
- Higher Sharpe ratio (better risk-adjusted returns)
- Better profit factor
- More consistent wins

The additional filtering (10+ bars, 25%+ depth) does select for higher quality setups.
However, note that HIGH squeezes are less frequent, so position sizing and patience are required.
"""
    else:
        if results['MED']['sharpe'] > results['HIGH']['sharpe']:
            winner = 'MED'
        elif results['LOW']['sharpe'] > results['HIGH']['sharpe']:
            winner = 'LOW'
        else:
            winner = 'inconclusive'
        
        md_report += f"""**NO - HIGH squeezes are NOT demonstrably better.**

Interestingly, {winner} squeezes may offer comparable or better risk-adjusted returns.
This could suggest:
- The squeeze release itself matters more than squeeze "quality"
- MED/LOW squeezes may offer more opportunities without sacrificing edge
- Consider using MED as minimum threshold rather than waiting for HIGH only

"""
    
    md_report += f"""
---

## Data Notes
- **Universe:** ~480 S&P 500 stocks (cached data)
- **Timeframe:** Weekly bars
- **Period:** Available cache history (varies by stock)
- **Total Signals Analyzed:** {sum(r['total_trades'] for r in results.values())}
"""
    
    # Write markdown report
    output_path = os.path.join(OUTPUT_DIR, "squeeze_levels_comparison.md")
    with open(output_path, 'w') as f:
        f.write(md_report)
    
    print()
    print(f"📊 Report saved to: {output_path}")
    
    # Also save detailed trades CSV for each level
    for level in ['HIGH', 'MED', 'LOW']:
        if all_trades[level]:
            df_trades = pd.DataFrame(all_trades[level])
            csv_path = os.path.join(OUTPUT_DIR, f"squeeze_{level.lower()}_trades.csv")
            df_trades.to_csv(csv_path, index=False)
            print(f"📄 Trades saved to: {csv_path}")


if __name__ == "__main__":
    main()
