#!/usr/bin/env python3
"""
Backtest Engine - Main backtesting orchestrator
"""
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
from .data_loader import DataLoader
from .pattern_detector import PatternDetector
from .trade_simulator import TradeSimulator

class BacktestEngine:
    """Main backtesting engine."""
    
    def __init__(self, initial_capital=100000, max_position_pct=0.10, 
                 max_positions=10, stop_loss_pct=0.08):
        self.data_loader = DataLoader()
        self.initial_capital = initial_capital
        self.max_position_pct = max_position_pct
        self.max_positions = max_positions
        self.stop_loss_pct = stop_loss_pct
        
    def run(self, tickers, start_date, end_date, patterns=['all']):
        """
        Run backtest.
        
        Args:
            tickers: List of stock symbols
            start_date: Start date (str or datetime)
            end_date: End date (str or datetime)
            patterns: List of pattern names or ['all']
            
        Returns:
            dict with results
        """
        print(f"\n{'='*60}")
        print(f"BACKTEST ENGINE")
        print(f"Period: {start_date} to {end_date}")
        print(f"Universe: {len(tickers)} stocks")
        print(f"Patterns: {', '.join(patterns)}")
        print(f"{'='*60}\n")
        
        # Initialize simulator
        simulator = TradeSimulator(
            initial_capital=self.initial_capital,
            max_position_pct=self.max_position_pct,
            max_positions=self.max_positions
        )
        
        # Load all data
        print("Loading historical data...")
        all_data = self.data_loader.get_multiple(tickers, start_date, end_date)
        print(f"Loaded {len(all_data)} stocks\n")
        
        # Get all trading days
        all_dates = set()
        for df in all_data.values():
            all_dates.update(df.index)
        trading_days = sorted(all_dates)
        
        # Simulate day by day
        print("Running simulation...")
        pattern_signals = {}
        
        for i, date in enumerate(trading_days):
            if i % 50 == 0:
                progress = (i / len(trading_days)) * 100
                print(f"  {date.strftime('%Y-%m-%d')} ({progress:.1f}%)")
            
            # Get price data for this date
            current_prices = {}
            for ticker, df in all_data.items():
                if date in df.index:
                    row = df.loc[date]
                    current_prices[ticker] = (
                        row['Open'], row['High'], row['Low'], 
                        row['Close'], row['Volume']
                    )
            
            # Update open positions (check stops, exits)
            simulator.update_positions(date, current_prices)
            
            # Look for new entry signals
            for ticker, df in all_data.items():
                # Only check stocks up to current date
                df_current = df[df.index <= date]
                
                if len(df_current) < 60:  # Need enough history
                    continue
                
                # Detect patterns
                detected = PatternDetector.detect_all(df_current)
                
                for pattern_info in detected:
                    pattern_name = pattern_info['pattern']
                    
                    # Filter by requested patterns
                    if patterns != ['all'] and pattern_name not in patterns:
                        continue
                    
                    # Check if already in this stock
                    if any(t.ticker == ticker for t in simulator.open_trades):
                        continue
                    
                    # Entry signal on next day's open
                    next_idx = df.index.get_loc(date) + 1
                    if next_idx >= len(df):
                        continue
                    
                    next_date = df.index[next_idx]
                    entry_price = df.iloc[next_idx]['Open']
                    
                    # Enter trade
                    trade = simulator.enter_trade(
                        ticker, pattern_name, next_date, 
                        entry_price, self.stop_loss_pct
                    )
                    
                    if trade:
                        # Track signal
                        if ticker not in pattern_signals:
                            pattern_signals[ticker] = []
                        pattern_signals[ticker].append({
                            'date': date.strftime('%Y-%m-%d'),
                            'pattern': pattern_name,
                            'buy_point': pattern_info['buy_point']
                        })
            
            # Record equity
            simulator.record_equity(date, current_prices)
        
        # Close remaining positions at end
        final_date = trading_days[-1]
        for trade in list(simulator.open_trades):
            if trade.ticker in all_data:
                final_price = all_data[trade.ticker].loc[final_date, 'Close']
                simulator.exit_trade(trade, final_date, final_price, 'end_of_test')
        
        # Calculate metrics
        print("\nCalculating metrics...")
        metrics = simulator.get_metrics()
        
        # Results
        results = {
            'config': {
                'start_date': str(start_date),
                'end_date': str(end_date),
                'initial_capital': self.initial_capital,
                'tickers': tickers,
                'patterns': patterns,
                'max_position_pct': self.max_position_pct,
                'max_positions': self.max_positions,
                'stop_loss_pct': self.stop_loss_pct
            },
            'metrics': metrics,
            'trades': [t.to_dict() for t in simulator.closed_trades],
            'equity_curve': simulator.equity_curve,
            'pattern_signals': pattern_signals
        }
        
        self._print_results(results)
        
        return results
    
    def _print_results(self, results):
        """Print results summary."""
        metrics = results['metrics']
        
        print(f"\n{'='*60}")
        print("BACKTEST RESULTS")
        print(f"{'='*60}")
        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Win Rate: {metrics['win_rate']*100:.1f}%")
        print(f"Avg Win: {metrics['avg_win_pct']:.1f}%")
        print(f"Avg Loss: {metrics['avg_loss_pct']:.1f}%")
        print(f"Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"Total Return: ${metrics['total_return_dollars']:,.2f} ({metrics['total_return_pct']*100:.1f}%)")
        print(f"Max Drawdown: {metrics['max_drawdown']*100:.1f}%")
        print(f"Avg Hold Days: {metrics['avg_hold_days']:.1f}")
        print(f"Final Equity: ${metrics['final_equity']:,.2f}")
        print(f"{'='*60}\n")
    
    def save_results(self, results, filename=None):
        """Save results to JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"backtest_results_{timestamp}.json"
        
        results_dir = Path(__file__).parent.parent / 'results' / 'runs'
        results_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"Results saved to: {filepath}")
        return filepath


if __name__ == '__main__':
    # Test run
    engine = BacktestEngine(initial_capital=100000)
    
    # Small universe for testing
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']
    
    results = engine.run(
        tickers=tickers,
        start_date='2023-01-01',
        end_date='2024-01-01',
        patterns=['all']
    )
    
    engine.save_results(results)
