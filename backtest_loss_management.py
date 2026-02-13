#!/usr/bin/env python3
"""
Loss Management Strategy Comparison
Test different stop loss approaches on the same signals
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from sp500_top200 import SP500_TOP200
from data_utils import get_stock_data, load_from_cache, save_to_cache
from backtest_patterns_sp500 import detect_patterns, get_spy_regime, get_spy_return

PROFIT_TARGET = 0.20  # 20% target for all strategies


def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    
    tr = np.zeros(len(df))
    for i in range(1, len(df)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    atr = pd.Series(tr).rolling(period).mean().values
    return atr


def simulate_fixed_stop(df, signals, stop_pct=0.10):
    """Strategy 1: Fixed percentage stop loss"""
    close = df['Close'].values
    trades = []
    
    for sig in signals:
        entry_idx = sig['idx']
        entry_price = sig['price']
        stop_price = entry_price * (1 - stop_pct)
        target_price = entry_price * (1 + PROFIT_TARGET)
        
        exit_idx = None
        exit_reason = None
        
        for j in range(entry_idx + 1, len(close)):
            if close[j] <= stop_price:
                exit_idx = j
                exit_reason = 'stop'
                break
            if close[j] >= target_price:
                exit_idx = j
                exit_reason = 'target'
                break
        
        if exit_idx:
            trades.append({
                'entry_date': sig['date'],
                'entry_price': entry_price,
                'exit_date': df.index[exit_idx],
                'exit_price': close[exit_idx],
                'return_pct': (close[exit_idx] - entry_price) / entry_price * 100,
                'exit_reason': exit_reason,
                'hold_days': (df.index[exit_idx] - sig['date']).days
            })
    
    return trades


def simulate_trailing_stop(df, signals, stop_pct=0.10):
    """Strategy 2: Simple trailing stop"""
    close = df['Close'].values
    trades = []
    
    for sig in signals:
        entry_idx = sig['idx']
        entry_price = sig['price']
        highest = entry_price
        target_price = entry_price * (1 + PROFIT_TARGET)
        
        exit_idx = None
        exit_reason = None
        
        for j in range(entry_idx + 1, len(close)):
            if close[j] > highest:
                highest = close[j]
            
            stop_price = highest * (1 - stop_pct)
            
            if close[j] <= stop_price:
                exit_idx = j
                exit_reason = 'trailing_stop'
                break
            if close[j] >= target_price:
                exit_idx = j
                exit_reason = 'target'
                break
        
        if exit_idx:
            trades.append({
                'entry_date': sig['date'],
                'entry_price': entry_price,
                'exit_date': df.index[exit_idx],
                'exit_price': close[exit_idx],
                'return_pct': (close[exit_idx] - entry_price) / entry_price * 100,
                'exit_reason': exit_reason,
                'hold_days': (df.index[exit_idx] - sig['date']).days
            })
    
    return trades


def simulate_atr_trailing(df, signals, atr_mult=2.5):
    """Strategy 3: ATR-based trailing stop (Chandelier Exit)"""
    close = df['Close'].values
    atr = calculate_atr(df)
    trades = []
    
    for sig in signals:
        entry_idx = sig['idx']
        entry_price = sig['price']
        highest = entry_price
        target_price = entry_price * (1 + PROFIT_TARGET)
        
        exit_idx = None
        exit_reason = None
        
        for j in range(entry_idx + 1, len(close)):
            if close[j] > highest:
                highest = close[j]
            
            # Chandelier: highest high - ATR * multiplier
            stop_price = highest - (atr[j] * atr_mult) if not np.isnan(atr[j]) else highest * 0.90
            
            if close[j] <= stop_price:
                exit_idx = j
                exit_reason = 'atr_stop'
                break
            if close[j] >= target_price:
                exit_idx = j
                exit_reason = 'target'
                break
        
        if exit_idx:
            trades.append({
                'entry_date': sig['date'],
                'entry_price': entry_price,
                'exit_date': df.index[exit_idx],
                'exit_price': close[exit_idx],
                'return_pct': (close[exit_idx] - entry_price) / entry_price * 100,
                'exit_reason': exit_reason,
                'hold_days': (df.index[exit_idx] - sig['date']).days
            })
    
    return trades


def simulate_time_hybrid(df, signals, stop_pct=0.10, stale_days=20):
    """Strategy 4: Time + Price hybrid - exit stale trades"""
    close = df['Close'].values
    trades = []
    
    for sig in signals:
        entry_idx = sig['idx']
        entry_price = sig['price']
        highest = entry_price
        target_price = entry_price * (1 + PROFIT_TARGET)
        days_since_new_high = 0
        
        exit_idx = None
        exit_reason = None
        
        for j in range(entry_idx + 1, len(close)):
            if close[j] > highest:
                highest = close[j]
                days_since_new_high = 0
            else:
                days_since_new_high += 1
            
            stop_price = highest * (1 - stop_pct)
            
            # Fixed stop
            if close[j] <= stop_price:
                exit_idx = j
                exit_reason = 'stop'
                break
            
            # Target
            if close[j] >= target_price:
                exit_idx = j
                exit_reason = 'target'
                break
            
            # Time exit: no new high for N days AND below breakeven
            if days_since_new_high >= stale_days and close[j] < entry_price * 1.02:
                exit_idx = j
                exit_reason = 'time_exit'
                break
        
        if exit_idx:
            trades.append({
                'entry_date': sig['date'],
                'entry_price': entry_price,
                'exit_date': df.index[exit_idx],
                'exit_price': close[exit_idx],
                'return_pct': (close[exit_idx] - entry_price) / entry_price * 100,
                'exit_reason': exit_reason,
                'hold_days': (df.index[exit_idx] - sig['date']).days
            })
    
    return trades


def simulate_breakeven_lock(df, signals, initial_stop=0.10, breakeven_trigger=0.05):
    """Strategy 5: Move to breakeven after 5% gain, then trail"""
    close = df['Close'].values
    trades = []
    
    for sig in signals:
        entry_idx = sig['idx']
        entry_price = sig['price']
        highest = entry_price
        target_price = entry_price * (1 + PROFIT_TARGET)
        stop_price = entry_price * (1 - initial_stop)
        breakeven_locked = False
        
        exit_idx = None
        exit_reason = None
        
        for j in range(entry_idx + 1, len(close)):
            if close[j] > highest:
                highest = close[j]
            
            # Lock in breakeven after 5% gain
            if not breakeven_locked and close[j] >= entry_price * (1 + breakeven_trigger):
                stop_price = entry_price * 1.001  # Tiny profit
                breakeven_locked = True
            
            # After breakeven, trail at 10% from high
            if breakeven_locked:
                trailing_stop = highest * (1 - initial_stop)
                stop_price = max(stop_price, trailing_stop)
            
            if close[j] <= stop_price:
                exit_idx = j
                exit_reason = 'breakeven_stop' if breakeven_locked else 'initial_stop'
                break
            if close[j] >= target_price:
                exit_idx = j
                exit_reason = 'target'
                break
        
        if exit_idx:
            trades.append({
                'entry_date': sig['date'],
                'entry_price': entry_price,
                'exit_date': df.index[exit_idx],
                'exit_price': close[exit_idx],
                'return_pct': (close[exit_idx] - entry_price) / entry_price * 100,
                'exit_reason': exit_reason,
                'hold_days': (df.index[exit_idx] - sig['date']).days
            })
    
    return trades


def simulate_stepped_trail(df, signals, initial_stop=0.10):
    """Strategy 6: Stepped trailing - ratchet up at milestones"""
    close = df['Close'].values
    trades = []
    
    # Milestones: at each gain level, set stop at previous level
    milestones = [(0.05, 0.0), (0.10, 0.05), (0.15, 0.10), (0.20, 0.15)]
    
    for sig in signals:
        entry_idx = sig['idx']
        entry_price = sig['price']
        target_price = entry_price * (1 + PROFIT_TARGET)
        stop_pct = -initial_stop  # Negative = below entry
        
        exit_idx = None
        exit_reason = None
        
        for j in range(entry_idx + 1, len(close)):
            current_gain = (close[j] - entry_price) / entry_price
            
            # Check milestones
            for trigger, new_stop in milestones:
                if current_gain >= trigger:
                    stop_pct = max(stop_pct, new_stop)
            
            stop_price = entry_price * (1 + stop_pct)
            
            if close[j] <= stop_price:
                exit_idx = j
                exit_reason = 'stepped_stop'
                break
            if close[j] >= target_price:
                exit_idx = j
                exit_reason = 'target'
                break
        
        if exit_idx:
            trades.append({
                'entry_date': sig['date'],
                'entry_price': entry_price,
                'exit_date': df.index[exit_idx],
                'exit_price': close[exit_idx],
                'return_pct': (close[exit_idx] - entry_price) / entry_price * 100,
                'exit_reason': exit_reason,
                'hold_days': (df.index[exit_idx] - sig['date']).days
            })
    
    return trades


def simulate_atr_initial_trailing(df, signals, atr_mult_initial=1.5, atr_mult_trail=2.5):
    """Strategy 7: Tighter initial ATR stop, wider trailing after profit"""
    close = df['Close'].values
    atr = calculate_atr(df)
    trades = []
    
    for sig in signals:
        entry_idx = sig['idx']
        entry_price = sig['price']
        entry_atr = atr[entry_idx] if not np.isnan(atr[entry_idx]) else entry_price * 0.02
        highest = entry_price
        target_price = entry_price * (1 + PROFIT_TARGET)
        in_profit = False
        
        exit_idx = None
        exit_reason = None
        
        for j in range(entry_idx + 1, len(close)):
            if close[j] > highest:
                highest = close[j]
            
            # Switch to wider trail after reaching 5% profit
            if close[j] >= entry_price * 1.05:
                in_profit = True
            
            if in_profit:
                # Wider trailing from high
                current_atr = atr[j] if not np.isnan(atr[j]) else entry_atr
                stop_price = highest - (current_atr * atr_mult_trail)
            else:
                # Tighter initial stop from entry
                stop_price = entry_price - (entry_atr * atr_mult_initial)
            
            if close[j] <= stop_price:
                exit_idx = j
                exit_reason = 'atr_trail' if in_profit else 'atr_initial'
                break
            if close[j] >= target_price:
                exit_idx = j
                exit_reason = 'target'
                break
        
        if exit_idx:
            trades.append({
                'entry_date': sig['date'],
                'entry_price': entry_price,
                'exit_date': df.index[exit_idx],
                'exit_price': close[exit_idx],
                'return_pct': (close[exit_idx] - entry_price) / entry_price * 100,
                'exit_reason': exit_reason,
                'hold_days': (df.index[exit_idx] - sig['date']).days
            })
    
    return trades


STRATEGIES = {
    '1_Fixed_10%': lambda df, sigs: simulate_fixed_stop(df, sigs, 0.10),
    '2_Trailing_10%': lambda df, sigs: simulate_trailing_stop(df, sigs, 0.10),
    '3_ATR_Trail_2.5x': lambda df, sigs: simulate_atr_trailing(df, sigs, 2.5),
    '4_ATR_Trail_3x': lambda df, sigs: simulate_atr_trailing(df, sigs, 3.0),
    '5_Time_Hybrid': lambda df, sigs: simulate_time_hybrid(df, sigs, 0.10, 20),
    '6_Breakeven_Lock': lambda df, sigs: simulate_breakeven_lock(df, sigs, 0.10, 0.05),
    '7_Stepped_Trail': lambda df, sigs: simulate_stepped_trail(df, sigs, 0.10),
    '8_ATR_Tight_Wide': lambda df, sigs: simulate_atr_initial_trailing(df, sigs, 1.5, 2.5),
}


def run_comparison():
    """Compare all loss management strategies"""
    print(f"\n{'='*70}")
    print(f"  LOSS MANAGEMENT STRATEGY COMPARISON")
    print(f"  Testing {len(STRATEGIES)} strategies on S&P 500 Top 50")
    print(f"{'='*70}\n")
    
    # Use top 50 for faster testing
    test_stocks = SP500_TOP200[:50]
    
    all_results = {name: [] for name in STRATEGIES.keys()}
    
    for i, ticker in enumerate(test_stocks):
        print(f"  [{i+1}/{len(test_stocks)}] {ticker}...", end=' ', flush=True)
        
        df = get_stock_data(ticker, period='15y', interval='1d', cache_ttl=24)
        if df is None or len(df) < 300:
            print("skip")
            continue
        
        # Get signals
        signals = detect_patterns(df)
        if not signals:
            print("no signals")
            continue
        
        # Filter bull market signals
        bull_signals = [s for s in signals if get_spy_regime(s['date'] - timedelta(days=7), s['date'])]
        if not bull_signals:
            print("no bull signals")
            continue
        
        # Test each strategy
        trade_counts = []
        for name, strategy_func in STRATEGIES.items():
            trades = strategy_func(df, bull_signals)
            for t in trades:
                t['ticker'] = ticker
            all_results[name].extend(trades)
            trade_counts.append(len(trades))
        
        print(f"{min(trade_counts)}-{max(trade_counts)} trades")
    
    # Calculate results
    print(f"\n{'='*70}")
    print(f"  RESULTS COMPARISON")
    print(f"{'='*70}\n")
    
    summary = []
    
    for name, trades in all_results.items():
        if not trades:
            continue
        
        df_trades = pd.DataFrame(trades)
        
        # Get SPY returns for alpha calculation
        spy_returns = []
        for _, row in df_trades.iterrows():
            spy_ret = get_spy_return(row['entry_date'], row['exit_date'])
            spy_returns.append(spy_ret)
        df_trades['spy_return'] = spy_returns
        df_trades['alpha'] = df_trades['return_pct'] - df_trades['spy_return']
        
        win_rate = (df_trades['return_pct'] > 0).mean() * 100
        avg_return = df_trades['return_pct'].mean()
        avg_alpha = df_trades['alpha'].mean()
        avg_hold = df_trades['hold_days'].mean()
        target_rate = (df_trades['exit_reason'] == 'target').mean() * 100
        
        # Profit factor
        wins = df_trades[df_trades['return_pct'] > 0]['return_pct'].sum()
        losses = abs(df_trades[df_trades['return_pct'] < 0]['return_pct'].sum())
        profit_factor = wins / losses if losses > 0 else float('inf')
        
        # Sharpe-like ratio (return / volatility)
        sharpe = avg_return / df_trades['return_pct'].std() if df_trades['return_pct'].std() > 0 else 0
        
        summary.append({
            'Strategy': name,
            'Trades': len(df_trades),
            'Win%': win_rate,
            'Avg_Ret': avg_return,
            'Avg_Alpha': avg_alpha,
            'Profit_Factor': profit_factor,
            'Target%': target_rate,
            'Avg_Hold': avg_hold,
            'Sharpe': sharpe
        })
    
    # Print summary
    summary_df = pd.DataFrame(summary).sort_values('Avg_Alpha', ascending=False)
    
    print(f"{'Strategy':<20} {'Trades':>7} {'Win%':>7} {'Avg Ret':>9} {'Alpha':>8} {'PF':>6} {'Target%':>8} {'Hold':>6}")
    print('-' * 85)
    
    for _, row in summary_df.iterrows():
        print(f"{row['Strategy']:<20} {int(row['Trades']):>7} {row['Win%']:>6.1f}% {row['Avg_Ret']:>8.2f}% {row['Avg_Alpha']:>7.2f}% {row['Profit_Factor']:>5.2f} {row['Target%']:>7.1f}% {row['Avg_Hold']:>5.0f}d")
    
    # Best strategy details
    best = summary_df.iloc[0]
    print(f"\n🏆 Best by Alpha: {best['Strategy']}")
    print(f"   Alpha: {best['Avg_Alpha']:.2f}% | Win Rate: {best['Win%']:.1f}% | Profit Factor: {best['Profit_Factor']:.2f}")
    
    return summary_df, all_results


if __name__ == '__main__':
    run_comparison()
