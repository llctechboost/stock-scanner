# 📚 CANSLIM Pattern Guide — Complete Reference

## The Patterns

### 1. Flat Base ⭐ (Best Win Rate: 46.7%)
**What:** Stock trades sideways in a tight range (<15%) for 5+ weeks after a prior uptrend.

**Why it works:** Big institutions are quietly accumulating shares without pushing the price up. The tighter the range, the more controlled the buying.

**Rules:**
- Range: <15% from high to low
- Duration: 5+ weeks minimum (6-7 preferred)
- Must form after prior uptrend (at least 20% advance)
- Volume should decline during the base (sellers drying up)

**Buy signal:** Price breaks above the TOP of the range on volume 50%+ above average.

**Stop:** 7% below buy point. No exceptions.

**Example:** Stock runs from $50 to $100, then trades between $95-$105 for 6 weeks. Buy at $105.01 breakout.

---

### 2. Cup with Handle
**What:** U-shaped base (7-65 weeks). Price drops, rounds out a bottom, recovers, then pulls back slightly (the "handle") before breaking out.

**Why it works:** The cup shakes out weak holders. The handle is the final shakeout. Only strong hands remain.

**Rules:**
- Cup depth: 12-33% (deeper = riskier)
- Cup shape: U-shaped (NOT V-shaped — V means panic selling, not orderly)
- Handle: 1-4 weeks, max 12% pullback
- Handle should drift DOWN slightly (not up — upward handle = weak)
- Handle should form in upper half of the cup

**Buy signal:** Break above the handle's high on volume 50%+ above average.

**Stop:** Below the handle low or 7% below buy point (whichever is tighter).

---

### 3. High Tight Flag (HTF) — Rare
**What:** Stock explodes 100%+ in 4-8 weeks, then consolidates in a tight flag (<20% pullback).

**Why it works:** Only the strongest momentum stocks do this. The tight flag means nobody wants to sell even after a massive run. It's the most explosive pattern when it works.

**Rules:**
- Prior advance: 100%+ in 4-8 weeks (our scanner uses 40%+ as relaxed threshold)
- Flag: <20% pullback from the high
- Flag duration: 3-5 weeks
- Volume should contract during the flag

**Reality check:** True HTFs happen maybe 2-3 times per YEAR in the entire market. Most "HTFs" are fake. Our old scanner was detecting tons of false positives — we fixed this by raising the threshold.

**Buy signal:** Break above the flag's high.

**Stop:** Below the flag low.

---

### 4. Ascending Base
**What:** 3+ pullbacks where each LOW is higher than the previous low. Like stair steps going up.

**Why it works:** Each dip gets bought at a higher price = increasing demand. Institutions are building positions over multiple weeks.

**Rules:**
- 3+ distinct pullbacks with higher lows
- Each pullback: 10-20% depth
- Duration: 3-9 weeks total
- Volume should decline on pullbacks (less selling pressure each time)

**Buy signal:** Break above the most recent swing high on volume.

**Stop:** Below the most recent higher low.

**Currently seen in:** NU and AMD.

---

### 5. Pocket Pivot
**What:** Early entry signal BEFORE a breakout. Price moves up through the 10-day MA on volume greater than any DOWN day volume in the prior 10 days.

**Why it works:** It's institutions stepping in with conviction before the crowd notices. Gets you in earlier than waiting for a base breakout.

**Rules:**
- Price must close above the 10-day MA
- Volume must exceed the highest DOWN day volume in prior 10 sessions
- Should occur within a base or after a pullback to the 10-day line
- Stock must be in an overall uptrend

**Risk:** Higher failure rate than base breakouts — you're entering earlier, before confirmation.

**Best for:** Adding to existing winners or entering new positions in confirmed uptrends.

---

### 6. VCP (Volatility Contraction Pattern) ⭐ AI-Detected
**What:** Price swings get progressively TIGHTER over time. Like a coil being compressed.

**Created by:** Mark Minervini (US Investing Champion, multiple years).

**Why it works:** The contracting range shows supply (sellers) drying up. When there are no more sellers, even small buying demand causes an explosive breakout.

**How to spot it visually:**
1. Draw the high-low range of each swing within a base
2. Each swing should be SMALLER than the last
3. Volume should DECREASE during contractions
4. The final contraction is very tight (2-3%)
5. Buy on breakout from the final tight range

**Example:**
- First swing: 15% range
- Second swing: 10% range
- Third swing: 7% range
- Fourth swing: 3% range ← BUY here on breakout

**Our system:** Math scanner doesn't detect VCPs yet. AI Vision catches them by looking at the actual chart. This is why vision analysis adds value.

**NU currently has a VCP inside its ascending base — the best kind of setup.**

---

### 7. Double Bottom
**What:** W-shaped pattern. Price drops, bounces, drops again to near the same level, then bounces again.

**Why it works:** The second test of the low proves that level is real support. Institutions are defending that price.

**Rules:**
- Second low should be AT or SLIGHTLY ABOVE first low
- If second low is below first low = failed pattern, avoid
- Duration: 7+ weeks
- Middle peak of the W is the buy point

**Buy signal:** Break above the middle peak of the W on volume.

**Stop:** Below the second low or 7% below buy.

---

## Key Concepts

### RS Rating (Relative Strength) — 0 to 100
Ranks a stock's price performance vs ALL other stocks over the past 12 months.
- **80+ = Top 20%** — These are the leaders. Focus here.
- **70-79 = Good** — Worth watching.
- **Below 70** — Laggards. Avoid for CANSLIM.

### Distribution Days
A day when the index drops on HIGHER volume than the previous day. This means institutions are selling.
- **0-3 distribution days** in 25 days = Green Light ✅
- **4-5 distribution days** = Caution ⚠️
- **6+ distribution days** = Danger 🔴 — Market may be topping

**Current: 8 distribution days = ⚠️ CAUTION**

### Volume Rules
- **Breakout + HIGH volume** (50%+ above avg) = REAL breakout. Institutions buying.
- **Breakout + LOW volume** = Weak. Likely to fail. Skip.
- **Base + DECLINING volume** = Sellers drying up. BULLISH.
- **Base + HIGH volume** = Institutions dumping. BEARISH.

### O'Neil Sell Rules
1. **-7% stop** from buy point — NO EXCEPTIONS. This is the #1 rule.
2. **Take profits at +20-25%** (sell into strength, not weakness)
3. **If stock gains 20% in 3 weeks or less** → HOLD for 8 weeks minimum (it's a monster)
4. **Sell on climax top** (huge volume spike after long run = blow-off top)

### Position Sizing
| Conviction | Position Size | Notes |
|---|---|---|
| 🔥 95+ | 15% of portfolio | Stock + options allowed |
| 🟢 85-94 | 10% of portfolio | Stock only |
| 🟡 70-84 | 5% of portfolio | Or paper trade first |
| ⚪ Below 70 | 0% | Don't trade it |

- **Max risk per trade:** 1-2% of total portfolio
- **Max positions:** 5 at once
- **Max sector exposure:** 40% (don't put everything in tech)

---

## How Our System Stacks All This Together

```
Math Scanner     → Finds WHAT has a pattern (score 0-12)
Money Scanner    → Ranks WHICH are strongest (score 0-100)
Options Flow     → Confirms WHO is buying (smart money)
AI Vision        → Grades HOW GOOD the pattern is (A/B/C/F)
Earnings Filter  → Prevents WHEN disasters
Sector Rotation  → Shows WHERE money is flowing
Dark Pool Data   → Reveals institutional accumulation
Signal Tracker   → Learns WHICH signals actually win over time
```

**The edge:** You don't just buy because a chart looks good. You buy when:
1. Chart pattern detected ✓
2. Strong fundamentals ✓
3. Institutions buying options ✓
4. AI confirms pattern quality ✓
5. No earnings risk ✓
6. Money flowing into the sector ✓
7. Historical win rate supports it ✓

All 7 agree = maximum conviction. That's how you get rich. 💰
