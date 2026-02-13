#!/usr/bin/env python3
"""
Backtest CLI - Command-line interface for backtesting
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).parent))

from core.engine import BacktestEngine

# Default stock universe (from scanner_v3.py)
DEFAULT_UNIVERSE = [
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO', 'CRM',
    'PLTR', 'NET', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'MDB', 'PANW', 'NOW', 'SHOP',
    'SMCI', 'ARM', 'IONQ', 'RGTI', 'APP', 'HIMS', 'DUOL', 'CELH', 'TOST', 'CAVA',
    'GS', 'JPM', 'V', 'MA', 'AXP', 'COIN', 'HOOD', 'SOFI', 'NU',
    'LLY', 'NVO', 'UNH', 'ISRG', 'DXCM', 'PODD', 'VRTX',
    'UBER', 'ABNB', 'DASH', 'RKLB', 'AXON', 'DECK', 'GWW', 'URI',
    'ASML', 'LRCX', 'KLAC', 'AMAT', 'MRVL', 'QCOM',
    'COST', 'TJX', 'LULU', 'NKE', 'HD', 'LOW',
    'XOM', 'CVX', 'EOG', 'FCX', 'NUE'
]

AVAILABLE_PATTERNS = [
    'Cup with Handle',
    'Flat Base',
    'High Tight Flag',
    'Pocket Pivot'
]

def main():
    parser = argparse.ArgumentParser(description='CANSLIM Pattern Backtester')
    
    parser.add_argument('--years', type=int, default=5,
                       help='Years to backtest (default: 5)')
    
    parser.add_argument('--start', type=str,
                       help='Start date (YYYY-MM-DD)')
    
    parser.add_argument('--end', type=str,
                       help='End date (YYYY-MM-DD, default: today)')
    
    parser.add_argument('--patterns', type=str, default='all',
                       help='Comma-separated pattern names or "all" (default: all)')
    
    parser.add_argument('--tickers', type=str,
                       help='Comma-separated ticker list (default: built-in universe)')
    
    parser.add_argument('--capital', type=float, default=100000,
                       help='Initial capital (default: 100000)')
    
    parser.add_argument('--position-size', type=float, default=0.10,
                       help='Max position size as % of capital (default: 0.10)')
    
    parser.add_argument('--max-positions', type=int, default=10,
                       help='Max concurrent positions (default: 10)')
    
    parser.add_argument('--stop-loss', type=float, default=0.08,
                       help='Stop loss percentage (default: 0.08)')
    
    parser.add_argument('--quick', action='store_true',
                       help='Quick test: 10 stocks, 1 year')
    
    parser.add_argument('--save', type=str,
                       help='Save results to custom filename')
    
    args = parser.parse_args()
    
    # Quick test mode
    if args.quick:
        print("\n🚀 QUICK TEST MODE (10 stocks, 1 year)")
        tickers = DEFAULT_UNIVERSE[:10]
        years = 1
    else:
        tickers = DEFAULT_UNIVERSE
        years = args.years
        if args.tickers:
            tickers = [t.strip().upper() for t in args.tickers.split(',')]
    
    # Date range
    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    if args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
    else:
        start_date = end_date - timedelta(days=365 * years)
    
    # Patterns
    if args.patterns.lower() == 'all':
        patterns = ['all']
    else:
        patterns = [p.strip() for p in args.patterns.split(',')]
        # Validate
        for p in patterns:
            if p not in AVAILABLE_PATTERNS:
                print(f"❌ Unknown pattern: {p}")
                print(f"Available patterns: {', '.join(AVAILABLE_PATTERNS)}")
                sys.exit(1)
    
    # Create engine
    engine = BacktestEngine(
        initial_capital=args.capital,
        max_position_pct=args.position_size,
        max_positions=args.max_positions,
        stop_loss_pct=args.stop_loss
    )
    
    # Run backtest
    try:
        results = engine.run(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            patterns=patterns
        )
        
        # Save results
        engine.save_results(results, args.save)
        
        # Pattern breakdown
        if results['metrics']:
            print("\n📊 PATTERN BREAKDOWN:")
            pattern_stats = {}
            for trade in results['trades']:
                pattern = trade['pattern']
                if pattern not in pattern_stats:
                    pattern_stats[pattern] = {'wins': 0, 'losses': 0, 'total_return': 0}
                
                if trade['return_pct'] and trade['return_pct'] > 0:
                    pattern_stats[pattern]['wins'] += 1
                else:
                    pattern_stats[pattern]['losses'] += 1
                
                if trade['return_pct']:
                    pattern_stats[pattern]['total_return'] += trade['return_pct']
            
            for pattern, stats in pattern_stats.items():
                total = stats['wins'] + stats['losses']
                win_rate = stats['wins'] / total if total > 0 else 0
                avg_return = stats['total_return'] / total if total > 0 else 0
                
                print(f"\n  {pattern}:")
                print(f"    Trades: {total}")
                print(f"    Win Rate: {win_rate*100:.1f}%")
                print(f"    Avg Return: {avg_return:.1f}%")
        
        print("\n✅ Backtest complete!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Backtest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
