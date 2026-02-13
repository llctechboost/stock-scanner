# Trading System v1.1 — Complete Overview
## How It Works, Why It Works, and How We Use It

---

## WHAT IT IS

A pattern-based stock scanning system that identifies high-probability trade setups using validated technical patterns from William O'Neil's CANSLIM methodology. Every rule in the system was backtested across **64 stocks over 5 years (2021–2026)** before being implemented.

The system does three things:
1. **Detects patterns** — Scans 65 stocks daily for 5 specific chart patterns
2. **Scores signals** — Ranks detected patterns by quality and conviction (0–100)
3. **Manages positions** — Tracks entries, stops, targets, and time exits

---

## THE 5 PATTERNS WE DETECT

Each pattern is a specific price/volume structure that historically precedes upward moves:

### 1. Cup with Handle (Tier 1 — Highest Quality)
**What it is:** A U-shaped recovery in price followed by a small pullback ("handle") before breaking higher.

**Detection rules:**
- Left high established 50–80 days ago
- Price dipped 12–35% from that high (the "cup")
- Right side recovered to within 10% of the left high
- Small handle pullback of 3–15% in the last 10–15 days
- Volume dries up during the handle (institutions resting, not selling)

**Why it works:** The cup shows sellers have exhausted themselves. The handle shakes out weak hands. When price breaks the handle high on volume, institutional buying resumes. Backtested at **2.18x profit factor** standalone.

### 2. Breakout (Tier 1)
**What it is:** Price breaks above its 20-day high on 1.5x+ average volume while above the 50-day moving average.

**Detection rules:**
- Today's close > highest close of last 20 days
- Today's volume ≥ 1.5x the 50-day average volume
- Price is above the 50-day moving average

**Why it works:** New highs on heavy volume = institutional demand. The 50MA filter ensures the stock is in an uptrend. Backtested at **1.78x profit factor**.

### 3. VCP — Volatility Contraction Pattern (Tier 2)
**What it is:** Price swings get progressively tighter over 3 periods, like a coiled spring.

**Detection rules:**
- Period 1 (days -60 to -30): Measured as % price range
- Period 2 (days -30 to -10): Must be < 80% of Period 1
- Period 3 (days -10 to now): Must be < 80% of Period 2
- Volume must be declining in the most recent period

**Why it works:** Each contraction represents fewer sellers willing to dump shares. When supply dries up, any buying pressure causes a sharp move up. Backtested at **1.62x profit factor**.

### 4. Flat Base (Tier 2)
**What it is:** Price trades in a tight range (7–18%) near 52-week highs for several weeks.

**Detection rules:**
- 40-day price range between 7% and 18%
- Current price is in the top 10% of that range (>90th percentile)
- The base high is within 8% of the 52-week high

**Why it works:** Tight consolidation near highs = strong holders. Nobody is willing to sell, and the stock is building a launching pad. Backtested at **1.66x profit factor, 50% win rate** (highest of all patterns).

### 5. Pocket Pivot (Tier 3)
**What it is:** An up-day where volume exceeds the highest down-day volume of the past 10 days.

**Detection rules:**
- Today's close > today's open (up day)
- Today's volume > max volume of any down-day in last 10 sessions
- Price is above the 10-day moving average

**Why it works:** This signals institutional accumulation — big money buying on a day that overwhelms recent selling pressure. Backtested at **1.60x profit factor**.

---

## HOW SCORING WORKS (0–100)

When patterns are detected, the system scores the signal based on three factors:

### Factor 1: Pattern Tier (up to 30 points)
| Tier | Patterns | Points |
|------|----------|--------|
| Tier 1 (best) | Cup w/ Handle, Breakout | 30 pts |
| Tier 2 | VCP, Flat Base | 20 pts |
| Tier 3 | Pocket Pivot | 10 pts |

*Uses the best (lowest-numbered) tier detected.*

### Factor 2: Multiple Patterns (up to 25 points)
| Condition | Points | Backtest Edge |
|-----------|--------|--------------|
| 3+ patterns at once | 25 pts | 1.89x PF, 48.2% win |
| 2 patterns at once | 15 pts | 1.80x PF, 46.5% win |
| 1 pattern | 0 pts | 1.54x PF, 43.1% win |

**Why:** Multiple patterns firing simultaneously means multiple independent technical signals agree — stronger confirmation.

### Factor 3: Specific Combo Bonuses (up to 20 points)
| Combo | Points | Backtest Edge |
|-------|--------|--------------|
| Breakout + Cup w/ Handle | 20 pts | **2.56x PF**, 51.6% win, 6.25% avg return |
| VCP + Flat Base | 15 pts | **1.91x PF**, 53.0% win |

**Why:** These specific combinations were the strongest performers in our 5-year backtest.

### Factor 4: Volume Strength (up to 10 points)
| Volume Ratio | Points |
|-------------|--------|
| ≥ 3.0x average | 10 pts |
| ≥ 2.0x average | 7 pts |
| ≥ 1.5x average | 5 pts |
| < 1.5x average | 0 pts |

*Volume = today's volume ÷ 50-day average volume.*

### Score Ranges
| Score | Meaning | Action |
|-------|---------|--------|
| 70–100 | Elite setup (multi-pattern + volume + combo) | Strong buy signal |
| 45–69 | Solid setup (good pattern combo) | Buy if slots available |
| 20–44 | Single pattern detected | Consider, lower priority |
| 0–19 | Weak/marginal | Skip or watchlist only |

---

## ABNB SCORING WALKTHROUGH (Score: 45)

Here's exactly how ABNB's score of 45 was calculated on Feb 2, 2026:

### Step 1: Pattern Detection

**VCP — DETECTED ✅**
```
Contraction 1 (days -60 to -30): 17.0%
Contraction 2 (days -30 to -10):  5.6%  (< 13.6% threshold = 17.0 × 0.8) ✅
Contraction 3 (days -10 to now):  3.4%  (< 4.5% threshold = 5.6 × 0.8)  ✅
Volume declining: 3.57M < 4.17M ✅
```
Price swings tightened from 17% → 5.6% → 3.4%. Each contraction is less than 80% of the prior one. Volume is drying up. Classic VCP.

**Cup with Handle — DETECTED ✅**
```
Left high (80–50 days ago):  $129.07
Cup low (50–15 days ago):    $111.54  → Depth: 13.6% (12–35% range) ✅
Right side (15–5 days ago):  $140.07  → Recovery: 109% of left high  ✅
Handle high:                 $140.07
Handle low:                  $129.37  → Handle depth: 7.6% (3–15%)   ✅
Handle volume < Base volume: 3.57M < 4.63M                           ✅
```
Price formed a U-shape (13.6% deep), recovered above the left side, then pulled back 7.6% on lighter volume. Textbook cup with handle.

### Step 2: Score Calculation

```
Pattern tier:    Cup w/ Handle = Tier 1           → +30 points
Multi-pattern:   2 patterns (VCP + Cup)            → +15 points
Combo bonus:     VCP + Cup (not a tracked combo)   → +0 points
Volume:          0.2x (light day, < 1.5x)          → +0 points
                                                    ─────────
TOTAL:                                               45 / 100
```

**Why 45 and not higher:** ABNB has two strong patterns but the entry-day volume was weak (0.2x average — a quiet trading day). If ABNB breaks out on 2x+ volume, the score would jump to 52+. The VCP+Cup combo isn't one of our tracked "bonus" combos (Breakout+Cup and VCP+Flat are), so no combo bonus.

---

## TRADE MANAGEMENT RULES

Every trade follows the same rules (validated by backtest):

| Rule | Setting | Why |
|------|---------|-----|
| **Stop Loss** | -10% from entry | Limits max loss per trade. Backtest showed 10% stop outperforms 8% and 15% on profit factor (2.00x PF) |
| **Profit Target** | +20% from entry | Fixed target at 2:1 reward/risk. Produced 52% win rate and 2.06 Sharpe |
| **Max Hold** | 60 days | If neither stop nor target hit in 60 days, exit at market. Prevents capital lockup |
| **Position Size** | 2% account risk | If $25K account, risk $500 per trade. Shares = $500 ÷ (entry × 10%) |
| **Max Positions** | 5 simultaneous | Diversification without over-dilution |

### Market Regime Filter
**SPY must be above its 200-day moving average.** If not, the system goes defensive — no new entries. This single rule is worth more than any hedging strategy we tested:

- Bull mode (SPY > 200MA): 45.8% win rate, 2.93% avg return, 1.71x PF
- Bear mode (SPY < 200MA): 34.1% win rate, 0.68% avg return, 1.14x PF

The best hedge is simply not trading in bear markets.

---

## BACKTEST RESULTS (2021–2026)

Tested across 64 stocks, ~28,000 pattern signals, 5 years of data:

### Optimal Settings (what we use)
| Metric | Value |
|--------|-------|
| Win Rate | 52.0% |
| Average Return | +3.95% per trade |
| Profit Factor | 1.88x |
| Sharpe Ratio | 2.06 |
| Best Pattern Combo | Breakout + Cup w/ Handle (2.56x PF) |

### What We Tested
1. **Stop/Target Grid** — 25 combinations from 5%/15% to 15%/40%. Winner: 10%/20%
2. **Market Regime** — SPY above/below 50MA and 200MA. Winner: SPY > 200MA
3. **Volume Thresholds** — 1.0x to 3.0x entry volume. Winner: 1.5x (for breakouts)
4. **Hold Periods** — 15 to 90 days + trailing stops. Winner: 60 days fixed target
5. **Pattern Combinations** — Single vs multi, specific combos. Winner: Breakout+Cup

### What Didn't Work
- **Score filter on top of patterns** — Adding a separate "money scanner" score on top of pattern detection actually hurt performance (-3.3pp win rate). The pattern IS the signal.
- **Hedging with puts/shorts** — Every hedge strategy tested reduced returns. SPY puts decayed faster than they protected. The regime filter does the job better.
- **Tight stops (5%)** — Got stopped out too often. 10% gives trades room to breathe.

---

## HOW WE'RE USING IT

### Daily Operations
1. **9:30 AM scan** (automated via cron → delivered to Telegram)
   - Checks SPY regime
   - Scans 65 stocks for patterns
   - Scores and ranks signals
   - Shows watchlist (stocks close to triggering)

2. **Mock Portfolios** (tracking in parallel)
   - **Mock 1:** All top signals from each scan
   - **Mock 2:** Top pick only (highest score)
   - **Mock 3:** Watchlist entries (only when a watched stock confirms a pattern)

3. **Position monitoring** (daily check)
   - Alerts when stop/target/time exit hits
   - Tracks P&L per position and portfolio

### Forward Plan
- Run all 3 mock portfolios for **4–6 weeks** to validate live performance
- Compare Mock 1 vs Mock 2 vs Mock 3 to determine which selection method performs best
- Once validated, transition to real capital with the winning approach
- Add stocks to universe as we identify gaps
- Refine pattern parameters if live performance deviates from backtest

### System Commands
```
python3 system.py scan              # Full scan with signals + watchlist
python3 system.py status            # Quick market/account check
python3 system.py check             # Monitor open positions
python3 system.py add ABNB 129.37 38   # Enter a position
python3 system.py close ABNB 155.00    # Exit a position
python3 system.py perf              # Performance stats

python3 mock_tracker.py check       # Check all mock portfolios
python3 mock_tracker.py summary     # Portfolio overview
```

---

## KEY TAKEAWAYS

1. **Patterns are the signal.** Not scores, not moving averages alone — specific price/volume patterns with defined rules that have been backtested over 28,000+ signals.

2. **Multi-pattern = higher conviction.** When VCP + Cup + Breakout all fire at once, the odds are meaningfully better than a single pattern (48% win vs 43%).

3. **Risk management is non-negotiable.** 10% stop, 2% risk per trade, 5 max positions. This means even 5 consecutive losses only costs 10% of the account.

4. **Market regime matters most.** Don't fight the trend. SPY below 200MA = sit on hands.

5. **The system is mechanical.** No gut feelings, no FOMO, no "this feels different." The rules are the rules because the data says they work.

---

*System v1.1 | Built Feb 2026 | Backtested Jan 2021 – Jan 2026*
*64-stock universe | 28,114 pattern signals analyzed | 5 optimization tests*
