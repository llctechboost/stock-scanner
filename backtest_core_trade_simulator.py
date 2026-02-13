#!/usr/bin/env python3
"""
Trade Simulator - Realistic trade execution and management
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class Trade:
    """Represents a single trade."""
    
    def __init__(self, ticker, pattern, entry_date, entry_price, position_size, stop_loss_pct=0.08):
        self.ticker = ticker
        self.pattern = pattern
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.position_size = position_size
        self.shares = int(position_size / entry_price)
        self.stop_loss_pct = stop_loss_pct
        self.stop_loss_price = entry_price * (1 - stop_loss_pct)
        
        self.exit_date = None
        self.exit_price = None
        self.exit_reason = None
        self.return_pct = None
        self.return_dollars = None
        self.hold_days = None
    
    def close(self, exit_date, exit_price, reason):
        """Close the trade."""
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = reason
        
        self.return_dollars = (exit_price - self.entry_price) * self.shares
        self.return_pct = (exit_price - self.entry_price) / self.entry_price
        self.hold_days = (exit_date - self.entry_date).days
    
    def to_dict(self):
        """Convert to dict for storage."""
        return {
            'ticker': self.ticker,
            'pattern': self.pattern,
            'entry_date': self.entry_date.strftime('%Y-%m-%d'),
            'entry_price': self.entry_price,
            'shares': self.shares,
            'position_size': self.position_size,
            'stop_loss_price': self.stop_loss_price,
            'exit_date': self.exit_date.strftime('%Y-%m-%d') if self.exit_date else None,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason,
            'return_pct': self.return_pct * 100 if self.return_pct else None,
            'return_dollars': self.return_dollars,
            'hold_days': self.hold_days
        }


class TradeSimulator:
    """Simulates trade execution with realistic constraints."""
    
    def __init__(self, initial_capital=100000, max_position_pct=0.10, 
                 max_positions=10, commission=0, slippage_pct=0.001):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.max_position_pct = max_position_pct
        self.max_positions = max_positions
        self.commission = commission
        self.slippage_pct = slippage_pct
        
        self.open_trades = []
        self.closed_trades = []
        self.equity_curve = []
        
    def can_enter_trade(self):
        """Check if we can enter a new trade."""
        if len(self.open_trades) >= self.max_positions:
            return False
        
        position_size = self.cash * self.max_position_pct
        if position_size < 100:  # Minimum $100 position
            return False
        
        return True
    
    def enter_trade(self, ticker, pattern, date, price, stop_loss_pct=0.08):
        """
        Enter a new trade.
        
        Returns:
            Trade object if entered, None if rejected
        """
        if not self.can_enter_trade():
            return None
        
        # Calculate position size (% of available cash)
        position_size = self.cash * self.max_position_pct
        
        # Apply slippage (pay slightly more)
        fill_price = price * (1 + self.slippage_pct)
        
        # Create trade
        trade = Trade(ticker, pattern, date, fill_price, position_size, stop_loss_pct)
        
        # Deduct cash
        total_cost = trade.shares * fill_price + self.commission
        self.cash -= total_cost
        
        self.open_trades.append(trade)
        return trade
    
    def exit_trade(self, trade, date, price, reason):
        """Exit an open trade."""
        # Apply slippage (receive slightly less)
        fill_price = price * (1 - self.slippage_pct)
        
        # Close trade
        trade.close(date, fill_price, reason)
        
        # Add proceeds to cash
        proceeds = trade.shares * fill_price - self.commission
        self.cash += proceeds
        
        # Move to closed trades
        self.open_trades.remove(trade)
        self.closed_trades.append(trade)
    
    def update_positions(self, date, price_data):
        """
        Update all open positions and check exit conditions.
        
        Args:
            date: Current date
            price_data: dict of {ticker: (open, high, low, close, volume)}
        """
        trades_to_exit = []
        
        for trade in self.open_trades:
            if trade.ticker not in price_data:
                continue
            
            open_p, high, low, close, vol = price_data[trade.ticker]
            
            # Check stop loss
            if low <= trade.stop_loss_price:
                trades_to_exit.append((trade, trade.stop_loss_price, 'stop_loss'))
                continue
            
            # Check time-based exit (30 days max hold)
            if (date - trade.entry_date).days >= 30:
                trades_to_exit.append((trade, close, 'time_exit'))
                continue
            
            # Check take profit (25% gain)
            if close >= trade.entry_price * 1.25:
                trades_to_exit.append((trade, close, 'take_profit'))
                continue
        
        # Execute exits
        for trade, price, reason in trades_to_exit:
            self.exit_trade(trade, date, price, reason)
    
    def get_portfolio_value(self, date, price_data):
        """Calculate current portfolio value."""
        value = self.cash
        
        for trade in self.open_trades:
            if trade.ticker in price_data:
                _, _, _, close, _ = price_data[trade.ticker]
                value += trade.shares * close
        
        return value
    
    def record_equity(self, date, price_data):
        """Record current equity for equity curve."""
        equity = self.get_portfolio_value(date, price_data)
        self.equity_curve.append({
            'date': date,
            'equity': equity,
            'cash': self.cash,
            'open_positions': len(self.open_trades)
        })
    
    def get_metrics(self):
        """Calculate performance metrics."""
        if len(self.closed_trades) == 0:
            return None
        
        trades_df = pd.DataFrame([t.to_dict() for t in self.closed_trades])
        
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['return_pct'] > 0])
        losing_trades = len(trades_df[trades_df['return_pct'] < 0])
        
        win_rate = winning_trades / total_trades
        avg_win = trades_df[trades_df['return_pct'] > 0]['return_pct'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['return_pct'] < 0]['return_pct'].mean() if losing_trades > 0 else 0
        
        total_return = trades_df['return_dollars'].sum()
        total_return_pct = total_return / self.initial_capital
        
        # Drawdown
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak']
        max_drawdown = equity_df['drawdown'].min()
        
        # Profit factor
        gross_profit = trades_df[trades_df['return_dollars'] > 0]['return_dollars'].sum() if winning_trades > 0 else 0
        gross_loss = abs(trades_df[trades_df['return_dollars'] < 0]['return_dollars'].sum()) if losing_trades > 0 else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'total_return_dollars': total_return,
            'total_return_pct': total_return_pct,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'avg_hold_days': trades_df['hold_days'].mean(),
            'final_equity': equity_df['equity'].iloc[-1] if len(equity_df) > 0 else self.cash
        }


if __name__ == '__main__':
    # Test
    sim = TradeSimulator(initial_capital=100000)
    
    # Enter trade
    trade = sim.enter_trade('AAPL', 'Cup with Handle', datetime.now(), 150.0)
    print(f"Entered trade: {trade.shares} shares @ ${trade.entry_price:.2f}")
    
    # Exit trade (simulate profit)
    sim.exit_trade(trade, datetime.now() + timedelta(days=10), 160.0, 'take_profit')
    print(f"Exited trade: ${trade.return_dollars:.2f} ({trade.return_pct*100:.1f}%)")
    
    # Metrics
    metrics = sim.get_metrics()
    print(f"\nMetrics: {metrics}")
