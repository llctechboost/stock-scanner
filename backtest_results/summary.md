# Strategy Comparison Backtest Results

## Overview
- **Period:** Feb 2023 - Feb 2026 (3 years)
- **Universe:** 494 stocks
- **Trade Rules:**
  - Entry: Signal fires → buy next day open
  - Stop Loss: 8% below entry
  - Target: 20% gain
  - Time Stop: Exit after 30 days if neither stop nor target hit

## Strategy Ranking (by Total Return)

| Rank | Strategy | Total Trades | Win Rate | Avg Gain | Avg Loss | Total Return | Max DD | Sharpe | Profit Factor |
|------|----------|-------------|----------|----------|----------|--------------|--------|--------|---------------|
| 1 | VCP | 14126 | 52.5% | 8.28% | -6.14% | 3.6583010200301445e+67% | 100.0% | 2.636 | 1.49 |
| 2 | Cup & Handle | 21037 | 50.7% | 7.7% | -6.05% | 3.835701785940746e+55% | 99.99% | 1.76 | 1.31 |
| 3 | Weekly Squeeze | 815 | 63.2% | 9.39% | -5.78% | 69644052727851.98% | 34.09% | 6.571 | 2.79 |
| 4 | Daily Squeeze | 3310 | 50.0% | 8.37% | -6.23% | 1337433125068.93% | 85.66% | 1.947 | 1.35 |
| 5 | 200-WMA Zone | 0 | 0% | 0% | 0% | 0% | 0% | 0 | 0 |

## Key Observations

### Best Overall: VCP
- Total Return: 3.6583010200301445e+67%
- Win Rate: 52.5%
- Sharpe Ratio: 2.636

### Highest Win Rate: Weekly Squeeze (63.2%)

### Best Risk-Adjusted (Sharpe): Weekly Squeeze (6.571)

## Strategy Descriptions

1. **Weekly Squeeze**: TTM Squeeze on weekly timeframe - Bollinger Bands inside Keltner Channel, signals when squeeze releases with upward momentum.

2. **Daily Squeeze**: Same as Weekly Squeeze but on daily timeframe for more frequent signals.

3. **Cup & Handle**: Classic O'Neil pattern - U-shaped base (12-35% depth) with small handle, signals on breakout above handle high.

4. **200-WMA Zone**: Price within 5% of 200-week moving average with upward momentum - buying quality stocks at support.

5. **VCP (Volatility Contraction Pattern)**: Minervini-style setup with 2+ contracting price ranges, volume dry-up, near 52-week highs.

---
*Generated: 2026-02-22 16:28*