# Trading Strategy v2.0: Munger + Momentum + Options Flow

## Core Philosophy
Buy **quality stocks** at **key technical levels** with **institutional confirmation**.

> "If all you ever did was buy high-quality stocks on the 200-week moving average, you would beat the S&P 500 by a large margin over time." — Charlie Munger

---

## Related Docs
- `system_overview.md` — Pattern detection system (VCP, Cup, Flat Base, etc.)
- `PATTERN_GUIDE.md` — Pattern rules and definitions
- `CANSLIM_VISUAL_GUIDE.md` — Visual chart examples

This strategy **layers on top** of the existing pattern system, adding:
1. 200-Week MA filter (Munger)
2. Unusual options activity (smart money)
3. Fundamental quality scoring

---

## Screening Criteria (Scoring System)

### Score Breakdown
| Criteria | Points | Required? |
|----------|--------|-----------|
| 200-Week MA (within 5%) | 30 pts | ✅ YES |
| Unusual Options Activity | 30 pts | ✅ YES |
| Strong Fundamentals | 25 pts | ✅ YES |
| Technical Pattern (VCP/Cup/Flat) | 15 pts | ❌ Bonus |
| **Total Possible** | **100 pts** | |

**Trade Grades:**
- **A+ (90-100):** Full position — all criteria + pattern
- **A (85-89):** Full position — all required criteria, no pattern
- **B (70-84):** Half position — strong but missing something
- **Below 70:** No trade — wait for better setup

---

### 1. 📊 200-Week Moving Average (Munger) — 30 pts
> "If all you ever did was buy high-quality stocks on the 200-week moving average, you would beat the S&P 500 by a large margin over time." — Charlie Munger

**Buy Zone:**
- Price within **0-5% ABOVE** the 200-week SMA = 🎯 Ideal entry
- Price **BELOW** the 200-week SMA = ⚠️ Deep value (verify fundamentals still intact)
- Price >10% above = Wait for pullback

**Why it works:**
- Rare signal (happens few times per decade per stock)
- Only quality stocks hold this level long-term
- Institutional accumulation zone

**Scoring:**
- At or below 200W MA: 30 pts
- 1-5% above: 25 pts
- 5-10% above: 15 pts
- >10% above: 0 pts

---

### 2. 📈 Technical Patterns (Bonus +15 pts)

**VCP (Volatility Contraction Pattern)**
- Successive tightening of price range (e.g., 20% → 12% → 6%)
- Declining volume during contractions
- Breakout on volume expansion

**Cup with Handle**
- U-shaped base with 12-35% depth
- Handle pullback 3-15%
- Volume dry-up in handle

**Flat Base**
- Tight consolidation (7-18% range)
- Near 52-week highs
- 5+ weeks of sideways action

**Scoring:**
- Clear VCP/Cup/Flat Base: +15 pts
- Partial pattern forming: +8 pts
- No pattern: +0 pts (still tradeable!)

---

### 3. 🔥 Unusual Options Activity (Smart Money) — 30 pts

**What to look for:**
- Call volume > 2x average daily volume
- Large block trades (100+ contracts)
- OTM calls with near-term expiration (2-6 weeks)
- Call/Put ratio spike
- Unusual sweep orders (aggressive fills across exchanges)

**Sources:**
- Unusual Whales (unusualwhales.com)
- Barchart Unusual Options
- FlowAlgo
- Cheddar Flow
- TradingView Options Flow

**Red flags (deduct points):**
- Hedging activity (puts + calls together): -10 pts
- Earnings plays (ignore pre-earnings spikes): -15 pts
- Low open interest (illiquid): -5 pts

**Scoring:**
- Multiple large call sweeps: 30 pts
- Unusual call volume (>2x avg): 20 pts
- Moderate activity: 10 pts
- No unusual activity: 0 pts

---

### 4. 💰 Fundamentals (Quality Filter) — 25 pts

**Required:**
| Metric | Minimum |
|--------|---------|
| Market Cap | >$10B (institutional quality) |
| Revenue Growth | >10% YoY |
| EPS Growth | >15% YoY |
| ROE | >15% |
| Debt/Equity | <1.0 |
| Current Ratio | >1.5 |

**IBD/MarketSmith Ratings:**
- EPS Rating: >80
- RS Rating: >70
- Composite Rating: >80
- SMR Rating: A or B

**Sector Leadership:**
- Industry rank top 40% 
- Relative strength vs sector positive

**Scoring:**
- All metrics excellent (EPS >90, RS >80): 25 pts
- Strong (EPS >80, RS >70): 20 pts
- Decent (EPS >70, RS >60): 12 pts
- Weak fundamentals: 0 pts

---

## Entry Rules (Based on Score)

### A+ Trade (90-100 pts)
- At 200-week MA (30) + Options flow (30) + Fundamentals (25) + Pattern (15)
- **Full position size**
- Highest conviction

### A Trade (85-89 pts)
- At 200-week MA + Options flow + Fundamentals
- No pattern required
- **Full position size**

### B Trade (70-84 pts)
- Most criteria met, one weak area
- **Half position size**
- Tighter stop loss

### No Trade (<70 pts)
- Missing required criteria
- Wait for better setup

### Avoid Completely
- Below 200-week MA with deteriorating fundamentals
- Options activity is hedging (puts + calls)
- Extended >15% above 200-week MA
- Within 2 weeks of earnings

---

## Position Sizing & Risk Management

### Entry
- **Full position:** A+ setup at 200-week MA
- **Half position:** B setup or >5% above MA
- **Scale in:** Add on breakout confirmation

### Stop Loss
- **Fixed 10% stop** from entry (backtested optimal)
- Below 200-week MA = stop at -12% (wider for value plays)
- Never risk >2% of portfolio per trade

### Profit Target
- **20% target** (2:1 reward/risk with 10% stop)
- Trail stop after +10% gain
- Let winners run if RS improving

---

## Watchlist Workflow

### Daily Scan
```
1. Run 200-week MA proximity scan (S&P 500)
2. Filter for VCP/Cup patterns forming
3. Check unusual options activity
4. Verify fundamentals
5. Add to watchlist if 3+ criteria met
```

### Weekly Review
- Update 200-week MA levels
- Check for pattern breakouts
- Review options flow for watchlist stocks
- Earnings calendar check (avoid 2 weeks before)

---

## Current Watchlist (as of 2026-02-03)

### 🎯 At 200-Week MA (Buy Zone)
| Ticker | Distance | Pattern | Options | Fundamentals |
|--------|----------|---------|---------|--------------|
| REGN | -0.7% | VCP | Check | Strong |
| AMD | -8% | Near MA | Check | Strong |
| ABT | -0.6% | Base | Check | Strong |
| PPG | +0.1% | Base | Check | Solid |
| QCOM | +4.4% | Base | Check | Strong |
| DIS | +3.9% | Recovery | Check | Mixed |

### ⚠️ Below MA (Deep Value - Verify)
| Ticker | Distance | Notes |
|--------|----------|-------|
| NKE | -36% | Consumer weakness |
| INTC | -32% | Turnaround play |
| PFE | -18% | Post-COVID reset |
| BA | -13% | Operational issues |

---

## Tools & Resources

### Screening
- **MarketSmith/IBD** — Fundamentals + RS ratings
- **TradingView** — Charts + Pine scripts
- **Finviz** — Quick fundamental screens

### Options Flow
- **Unusual Whales** — Real-time flow
- **Barchart** — Unusual activity scanner
- **TradingView** — Options overlay

### News/Catalysts
- **Earnings Whispers** — Earnings calendar
- **SEC Filings** — Insider activity
- **Seeking Alpha** — Analysis

---

## Pine Script (TradingView)

```pinescript
//@version=5
indicator("200-Week MA + Buy Zone", overlay=true)

// 200-week SMA (adjust for timeframe)
weeksInBars = timeframe.isweekly ? 1 : timeframe.isdaily ? 5 : 1
length = 200 * weeksInBars
sma200w = ta.sma(close, length)

// Plot
plot(sma200w, "200W SMA", color=color.black, linewidth=2)

// Buy zone highlight (0-5% above MA)
inBuyZone = close >= sma200w and close <= sma200w * 1.05
belowMA = close < sma200w
bgcolor(belowMA ? color.new(color.red, 90) : inBuyZone ? color.new(color.green, 90) : na)

// Distance label
distance = ((close - sma200w) / sma200w) * 100
var label distLabel = na
label.delete(distLabel)
distLabel := label.new(bar_index, high, str.tostring(distance, "#.#") + "% from 200W", 
    color=distance <= 5 ? color.green : color.gray, textcolor=color.white, size=size.small)
```

---

## Backtest Results (S&P 500, 2012-2026)

**Strategy: Fixed 10% Stop / 20% Target / No Time Limit**

| Metric | Result |
|--------|--------|
| Total Trades | 189,619 |
| Win Rate | 56.8% |
| Avg Return | +7.05% |
| Avg Alpha | +0.28% |
| Profit Factor | 2.42 |
| Est. Annual Return | ~14% |

**Best Patterns by Alpha:**
1. VCP: +0.63%
2. Cup w/ Handle: +0.40%
3. Pocket Pivot: +0.25%

---

## Notes

- The 200-week MA is a **rare** signal — patience required
- Options flow confirms **institutional interest**
- Fundamentals filter out **value traps**
- Patterns provide **entry timing**

*Last updated: 2026-02-03*
