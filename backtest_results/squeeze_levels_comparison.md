# Weekly Squeeze Backtest: Levels Comparison

**Generated:** 2026-02-22 20:38

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
| **Total Trades** | 67 | 874 | 992 |
| **Win Rate** | 26.9% | 36.5% | 38.4% |
| **Avg Gain** | +17.8% | +17.2% | +17.0% |
| **Avg Loss** | -8.0% | -7.9% | -7.9% |
| **Sharpe Ratio** | -0.67 | 0.72 | 0.94 |
| **Profit Factor** | 0.82 | 1.25 | 1.34 |
| **Total Return** | -71.9% | 1098.1% | 1633.6% |

### Exit Breakdown

| Exit Type | HIGH | MED | LOW |
|-----------|-----:|----:|----:|
| Target (20%+) | 12 | 236 | 278 |
| Stop (-8%) | 49 | 546 | 599 |
| Time (30 bars) | 6 | 92 | 115 |

## Analysis

### Key Findings

1. **Best Win Rate:** LOW squeezes at 38.4%
2. **Best Sharpe Ratio:** LOW squeezes at 0.94
3. **Best Profit Factor:** LOW squeezes at 1.34
4. **Most Trade Opportunities:** LOW with 992 trades

### Conclusion

**NO - HIGH squeezes are NOT demonstrably better. In fact, they underperform!**

This counterintuitive result deserves analysis:

### Why HIGH Squeezes Underperform

1. **Sample Size Problem:** Only 67 HIGH trades vs 992 LOW trades. Statistical reliability is much weaker for HIGH.

2. **Timing Issue:** By the time a squeeze reaches "HIGH" (10+ bars, 25%+ depth), the best breakout opportunity may have already passed. The stock has been coiling so long that:
   - Traders are fatigued/gave up
   - The move happened gradually during compression
   - Momentum may be exhausted

3. **Stop Distance Problem:** Using a fixed 8% stop on both HIGH and LOW squeezes may not be optimal. HIGH squeezes (with deeper compression) might need wider stops.

4. **Selection Bias:** HIGH squeezes happen in stocks with extended sideways action - often in mature names with less explosive potential.

### Recommendations

1. **Don't wait for HIGH:** Trade MED squeezes (5+ bars, 10%+ depth) - they have positive expectancy (1.25 profit factor)

2. **LOW is surprisingly viable:** 38.4% win rate with 1.34 profit factor suggests even basic squeeze releases work

3. **Trade more frequently:** LOW offers 992 opportunities vs 67 for HIGH - with BETTER results

4. **Consider hybrid approach:** Use squeeze as entry qualifier, but add other filters (RS, sector momentum)

---

## Data Notes
- **Universe:** ~480 S&P 500 stocks (cached data)
- **Timeframe:** Weekly bars
- **Period:** Available cache history (varies by stock)
- **Total Signals Analyzed:** 1933
