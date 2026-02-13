"""
Pattern-Based Trading Strategy Backtest using backtesting.py
RBI System - Research, Backtest, Implement

Strategies:
1. Breakout
2. Cup with Handle
3. VCP (Volatility Contraction Pattern)
4. Flat Base
5. Pocket Pivot
"""

import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import yfinance as yf
from datetime import datetime, timedelta

# EMA function (replacing talib)
def EMA(data, period):
    return pd.Series(data).ewm(span=period, adjust=False).mean().values

# =============================================================================
# PATTERN DETECTION FUNCTIONS
# =============================================================================

def detect_breakout(data, lookback=20):
    """
    Breakout: Price breaks above recent high with volume surge
    """
    high_max = data['High'].rolling(window=lookback).max()
    vol_avg = data['Volume'].rolling(window=20).mean()
    
    breakout = (data['Close'] > high_max.shift(1)) & (data['Volume'] > vol_avg * 1.5)
    return breakout


def detect_cup_with_handle(data, cup_length=30, handle_length=10):
    """
    Cup with Handle: U-shaped base followed by small pullback
    """
    signals = pd.Series(False, index=data.index)
    
    for i in range(cup_length + handle_length, len(data)):
        # Cup period
        cup_start = i - cup_length - handle_length
        cup_end = i - handle_length
        
        cup_data = data['Close'].iloc[cup_start:cup_end]
        
        if len(cup_data) < cup_length:
            continue
            
        # Cup characteristics: price drops then recovers
        cup_low_idx = cup_data.idxmin()
        cup_low = cup_data.min()
        cup_start_price = cup_data.iloc[0]
        cup_end_price = cup_data.iloc[-1]
        
        # Cup should drop 15-35% and recover
        cup_depth = (cup_start_price - cup_low) / cup_start_price
        cup_recovery = (cup_end_price - cup_low) / (cup_start_price - cup_low) if cup_start_price != cup_low else 0
        
        # Handle period
        handle_data = data['Close'].iloc[cup_end:i]
        handle_pullback = (cup_end_price - handle_data.min()) / cup_end_price if len(handle_data) > 0 else 0
        
        # Valid cup with handle
        if 0.15 <= cup_depth <= 0.35 and cup_recovery >= 0.8 and handle_pullback <= 0.12:
            # Breakout above handle high
            handle_high = handle_data.max()
            if data['Close'].iloc[i] > handle_high:
                signals.iloc[i] = True
    
    return signals


def detect_vcp(data, contractions=3, lookback=50):
    """
    VCP: Series of tightening price contractions
    """
    signals = pd.Series(False, index=data.index)
    
    for i in range(lookback, len(data)):
        window = data.iloc[i-lookback:i]
        
        # Calculate volatility in segments
        segment_len = lookback // contractions
        volatilities = []
        
        for j in range(contractions):
            start = j * segment_len
            end = (j + 1) * segment_len
            segment = window['Close'].iloc[start:end]
            if len(segment) > 1:
                vol = (segment.max() - segment.min()) / segment.mean()
                volatilities.append(vol)
        
        # Check for contracting volatility
        if len(volatilities) >= contractions:
            is_contracting = all(volatilities[k] > volatilities[k+1] for k in range(len(volatilities)-1))
            
            # Final contraction should be tight (< 10%)
            if is_contracting and volatilities[-1] < 0.10:
                # Breakout on volume
                vol_avg = data['Volume'].iloc[i-20:i].mean()
                if data['Volume'].iloc[i] > vol_avg * 1.3:
                    signals.iloc[i] = True
    
    return signals


def detect_flat_base(data, lookback=30, max_range=0.15):
    """
    Flat Base: Tight consolidation (< 15% range) for extended period
    """
    signals = pd.Series(False, index=data.index)
    
    for i in range(lookback, len(data)):
        window = data['Close'].iloc[i-lookback:i]
        
        # Calculate range
        price_range = (window.max() - window.min()) / window.mean()
        
        # Flat base characteristics
        if price_range <= max_range:
            # Price near top of range
            position_in_range = (data['Close'].iloc[i] - window.min()) / (window.max() - window.min())
            
            # Breakout above range high
            if position_in_range >= 0.9 and data['Close'].iloc[i] > window.max():
                signals.iloc[i] = True
    
    return signals


def detect_pocket_pivot(data, lookback=10):
    """
    Pocket Pivot: Up day with volume > any down day volume in last 10 days
    """
    signals = pd.Series(False, index=data.index)
    
    for i in range(lookback, len(data)):
        # Current day must be up
        if data['Close'].iloc[i] <= data['Open'].iloc[i]:
            continue
            
        current_volume = data['Volume'].iloc[i]
        
        # Get max down day volume in lookback
        window = data.iloc[i-lookback:i]
        down_days = window[window['Close'] < window['Open']]
        
        if len(down_days) > 0:
            max_down_volume = down_days['Volume'].max()
            
            # Pocket pivot: current volume > max down volume
            if current_volume > max_down_volume:
                # Price should be above 10 EMA
                ema_10 = data['Close'].ewm(span=10).mean()
                if data['Close'].iloc[i] > ema_10.iloc[i]:
                    signals.iloc[i] = True
    
    return signals


# =============================================================================
# BACKTESTING STRATEGIES
# =============================================================================

class BreakoutStrategy(Strategy):
    """Breakout above recent highs with volume"""
    lookback = 20
    take_profit = 0.20  # 20%
    stop_loss = 0.10    # 10%
    
    def init(self):
        self.breakout_signal = self.I(detect_breakout, self.data.df, self.lookback)
        self.ema_200 = self.I(EMA, self.data.Close, period=200)
    
    def next(self):
        # Only trade above 200 EMA (bull market filter)
        if self.data.Close[-1] < self.ema_200[-1]:
            return
            
        if self.breakout_signal[-1] and not self.position:
            self.buy(
                sl=self.data.Close[-1] * (1 - self.stop_loss),
                tp=self.data.Close[-1] * (1 + self.take_profit)
            )


class CupWithHandleStrategy(Strategy):
    """Cup with Handle pattern"""
    cup_length = 30
    handle_length = 10
    take_profit = 0.20
    stop_loss = 0.10
    
    def init(self):
        self.signal = self.I(detect_cup_with_handle, self.data.df, self.cup_length, self.handle_length)
        self.ema_200 = self.I(EMA, self.data.Close, period=200)
    
    def next(self):
        if self.data.Close[-1] < self.ema_200[-1]:
            return
            
        if self.signal[-1] and not self.position:
            self.buy(
                sl=self.data.Close[-1] * (1 - self.stop_loss),
                tp=self.data.Close[-1] * (1 + self.take_profit)
            )


class VCPStrategy(Strategy):
    """Volatility Contraction Pattern"""
    contractions = 3
    lookback = 50
    take_profit = 0.20
    stop_loss = 0.10
    
    def init(self):
        self.signal = self.I(detect_vcp, self.data.df, self.contractions, self.lookback)
        self.ema_200 = self.I(EMA, self.data.Close, period=200)
    
    def next(self):
        if self.data.Close[-1] < self.ema_200[-1]:
            return
            
        if self.signal[-1] and not self.position:
            self.buy(
                sl=self.data.Close[-1] * (1 - self.stop_loss),
                tp=self.data.Close[-1] * (1 + self.take_profit)
            )


class FlatBaseStrategy(Strategy):
    """Flat Base breakout"""
    lookback = 30
    max_range = 0.15
    take_profit = 0.20
    stop_loss = 0.10
    
    def init(self):
        self.signal = self.I(detect_flat_base, self.data.df, self.lookback, self.max_range)
        self.ema_200 = self.I(EMA, self.data.Close, period=200)
    
    def next(self):
        if self.data.Close[-1] < self.ema_200[-1]:
            return
            
        if self.signal[-1] and not self.position:
            self.buy(
                sl=self.data.Close[-1] * (1 - self.stop_loss),
                tp=self.data.Close[-1] * (1 + self.take_profit)
            )


class PocketPivotStrategy(Strategy):
    """Pocket Pivot volume signal"""
    lookback = 10
    take_profit = 0.20
    stop_loss = 0.10
    
    def init(self):
        self.signal = self.I(detect_pocket_pivot, self.data.df, self.lookback)
        self.ema_200 = self.I(EMA, self.data.Close, period=200)
    
    def next(self):
        if self.data.Close[-1] < self.ema_200[-1]:
            return
            
        if self.signal[-1] and not self.position:
            self.buy(
                sl=self.data.Close[-1] * (1 - self.stop_loss),
                tp=self.data.Close[-1] * (1 + self.take_profit)
            )


class CombinedPatternStrategy(Strategy):
    """Combined: Breakout + Cup w/ Handle (best performers)"""
    take_profit = 0.20
    stop_loss = 0.10
    
    def init(self):
        self.breakout = self.I(detect_breakout, self.data.df, 20)
        self.cup_handle = self.I(detect_cup_with_handle, self.data.df, 30, 10)
        self.ema_200 = self.I(EMA, self.data.Close, period=200)
    
    def next(self):
        if self.data.Close[-1] < self.ema_200[-1]:
            return
            
        if (self.breakout[-1] or self.cup_handle[-1]) and not self.position:
            self.buy(
                sl=self.data.Close[-1] * (1 - self.stop_loss),
                tp=self.data.Close[-1] * (1 + self.take_profit)
            )


# =============================================================================
# RUN BACKTEST
# =============================================================================

def get_data(ticker, period='5y'):
    """Download OHLCV data"""
    stock = yf.Ticker(ticker)
    data = stock.history(period=period)
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    return data


def run_backtest(ticker, strategy_class, cash=25000, commission=0.001):
    """Run single backtest"""
    print(f"\n{'='*60}")
    print(f"Running {strategy_class.__name__} on {ticker}")
    print(f"{'='*60}")
    
    data = get_data(ticker)
    
    bt = Backtest(data, strategy_class, cash=cash, commission=commission)
    stats = bt.run()
    
    print(stats)
    return stats, bt


def run_optimization(ticker, strategy_class, cash=25000):
    """Run optimization on parameters"""
    print(f"\n{'='*60}")
    print(f"Optimizing {strategy_class.__name__} on {ticker}")
    print(f"{'='*60}")
    
    data = get_data(ticker)
    
    bt = Backtest(data, strategy_class, cash=cash, commission=0.001)
    
    stats = bt.optimize(
        take_profit=[i/100 for i in range(10, 30, 5)],  # 10-25%
        stop_loss=[i/100 for i in range(5, 15, 2)],     # 5-13%
        maximize='Equity Final [$]',
        constraint=lambda param: param.take_profit > param.stop_loss
    )
    
    print("\nBest Parameters:")
    print(f"  Take Profit: {stats._strategy.take_profit:.0%}")
    print(f"  Stop Loss: {stats._strategy.stop_loss:.0%}")
    print(f"\nResults:")
    print(stats)
    
    return stats, bt


def run_all_strategies(tickers, cash=25000):
    """Run all strategies across multiple tickers"""
    strategies = [
        BreakoutStrategy,
        CupWithHandleStrategy,
        VCPStrategy,
        FlatBaseStrategy,
        PocketPivotStrategy,
        CombinedPatternStrategy
    ]
    
    results = []
    
    for ticker in tickers:
        print(f"\n{'#'*60}")
        print(f"TESTING: {ticker}")
        print(f"{'#'*60}")
        
        data = get_data(ticker)
        
        for strategy in strategies:
            try:
                bt = Backtest(data, strategy, cash=cash, commission=0.001)
                stats = bt.run()
                
                results.append({
                    'Ticker': ticker,
                    'Strategy': strategy.__name__,
                    'Return': stats['Return [%]'],
                    'Win Rate': stats['Win Rate [%]'],
                    'Profit Factor': stats.get('Profit Factor', 0),
                    'Max Drawdown': stats['Max. Drawdown [%]'],
                    'Trades': stats['# Trades'],
                    'Sharpe': stats.get('Sharpe Ratio', 0)
                })
                
                print(f"\n{strategy.__name__}:")
                print(f"  Return: {stats['Return [%]']:.1f}%")
                print(f"  Win Rate: {stats['Win Rate [%]']:.1f}%")
                print(f"  Trades: {stats['# Trades']}")
                
            except Exception as e:
                print(f"  {strategy.__name__}: Error - {e}")
    
    # Summary DataFrame
    df = pd.DataFrame(results)
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(df.to_string(index=False))
    
    return df


if __name__ == "__main__":
    # Test tickers
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META']
    
    # Run all strategies
    results = run_all_strategies(tickers)
    
    # Save results
    results.to_csv('/Users/rara/clawd/trading/backtest_results.csv', index=False)
    print("\nResults saved to backtest_results.csv")
