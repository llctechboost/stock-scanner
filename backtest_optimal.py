#!/usr/bin/env python3
"""
Optimal Settings Backtest: 10% stop vs 15% stop + Hedge Analysis
Combines best findings from master backtest, tests hedging strategies.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import json, sys

UNIVERSE = [
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO', 'CRM',
    'PLTR', 'NET', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'MDB', 'PANW', 'NOW', 'SHOP',
    'SMCI', 'ARM', 'APP', 'HIMS', 'DUOL', 'CELH', 'TOST', 'CAVA',
    'GS', 'JPM', 'V', 'MA', 'AXP', 'COIN', 'HOOD', 'SOFI', 'NU',
    'LLY', 'NVO', 'UNH', 'ISRG', 'DXCM', 'PODD', 'VRTX',
    'UBER', 'ABNB', 'DASH', 'RKLB', 'AXON', 'DECK', 'GWW', 'URI',
    'ASML', 'LRCX', 'KLAC', 'AMAT', 'MRVL', 'QCOM',
    'COST', 'TJX', 'LULU', 'NKE', 'HD', 'LOW'
]


def detect_patterns(df):
    close = df['Close'].values
    volume = df['Volume'].values
    high = df['High'].values if 'High' in df.columns else close
    low = df['Low'].values if 'Low' in df.columns else close
    opn = df['Open'].values if 'Open' in df.columns else close
    n = len(close)
    ma50_s = pd.Series(close).rolling(50).mean().values
    vol_50 = pd.Series(volume).rolling(50).mean().values
    signals = []

    for i in range(252, n):
        pats = []
        vol_ratio = volume[i] / vol_50[i] if vol_50[i] > 0 else 1.0

        # Pocket Pivot
        if close[i] > opn[i] and i > 11:
            max_dv = 0
            for k in range(i-10, i):
                if close[k] < opn[k]:
                    max_dv = max(max_dv, volume[k])
            if max_dv > 0 and volume[i] > max_dv:
                ma10 = np.mean(close[i-9:i+1])
                if close[i] > ma10:
                    pats.append('Pocket Pivot')

        # Flat Base
        h40 = np.max(close[max(0,i-40):i+1])
        l40 = np.min(close[max(0,i-40):i+1])
        if l40 > 0:
            rng = (h40 - l40) / l40
            if 0.07 <= rng <= 0.18:
                if h40 > 0 and (close[i] - l40) / (h40 - l40) > 0.90:
                    h252 = np.max(close[max(0,i-252):i+1])
                    if h40 >= h252 * 0.92:
                        pats.append('Flat Base')

        # VCP
        if i > 60 and close[i-40] > 0 and close[i-20] > 0:
            r1 = (np.max(close[i-60:i-30]) - np.min(close[i-60:i-30])) / close[i-40]
            r2 = (np.max(close[i-30:i-10]) - np.min(close[i-30:i-10])) / close[i-20]
            r3 = (np.max(close[i-10:i+1]) - np.min(close[i-10:i+1])) / close[i]
            if r1 > 0.05 and r2 < r1 * 0.8 and r3 < r2 * 0.8:
                v1 = np.mean(volume[i-30:i-10])
                v2 = np.mean(volume[i-10:i+1])
                if v2 < v1:
                    pats.append('VCP')

        # Breakout
        if i > 50 and not np.isnan(ma50_s[i]):
            prev_high = np.max(close[i-21:i])
            if close[i] > prev_high and vol_ratio > 1.5 and close[i] > ma50_s[i]:
                pats.append('Breakout')

        # Cup w/ Handle
        if i > 80:
            left_high = np.max(close[i-80:i-50])
            cup_low = np.min(close[i-50:i-15])
            right_side = np.max(close[i-15:i-5])
            if left_high > 0:
                depth = (left_high - cup_low) / left_high
                recovery = right_side / left_high
                if 0.12 <= depth <= 0.35 and recovery >= 0.90:
                    handle_high = np.max(close[i-15:i-3])
                    handle_low = np.min(close[i-10:i+1])
                    if handle_high > 0:
                        hd = (handle_high - handle_low) / handle_high
                        if 0.03 <= hd <= 0.15:
                            hv = np.mean(volume[i-10:i+1])
                            bv = np.mean(volume[i-50:i-10])
                            if hv < bv:
                                pats.append('Cup w/ Handle')

        if pats:
            signals.append({
                'idx': i, 'date': df.index[i], 'patterns': pats,
                'num_patterns': len(pats), 'entry_price': close[i],
                'vol_ratio': vol_ratio
            })
    return signals


def simulate_trade(close, high, low, idx, entry, stop, trail, max_hold):
    """8% or 10% hard stop + trailing stop, no fixed profit target."""
    n = len(close)
    highest = entry
    for j in range(1, min(max_hold + 1, n - idx)):
        highest = max(highest, high[idx + j])
        # Hard stop
        loss = (low[idx + j] - entry) / entry
        if loss <= -stop:
            return -stop, 'stop', j
        # Trailing stop (only activates once profitable)
        if highest > entry:
            trail_loss = (low[idx + j] - highest) / highest
            if trail_loss <= -trail:
                ret = max((low[idx + j] - entry) / entry, -stop)
                return ret, 'trail', j
    end = min(idx + max_hold, n - 1)
    return (close[end] - entry) / entry, 'time', min(max_hold, n - idx - 1)


def simulate_with_hedge(close, high, low, spy_c, spy_h, spy_l, spy_idx_map,
                        idx, entry, stop, trail, max_hold, date,
                        hedge_type, hedge_pct):
    """
    Simulate trade + hedge.
    hedge_type: 'spy_put', 'spy_short', 'portfolio_put'
    hedge_pct: fraction of position allocated to hedge (e.g., 0.03 = 3%)
    """
    n = len(close)
    highest = entry
    trade_ret = None
    hold_days = 0

    for j in range(1, min(max_hold + 1, n - idx)):
        highest = max(highest, high[idx + j])
        loss = (low[idx + j] - entry) / entry
        if loss <= -stop:
            trade_ret = -stop
            hold_days = j
            break
        if highest > entry:
            trail_loss = (low[idx + j] - highest) / highest
            if trail_loss <= -trail:
                trade_ret = max((low[idx + j] - entry) / entry, -stop)
                hold_days = j
                break
        hold_days = j

    if trade_ret is None:
        end = min(idx + max_hold, n - 1)
        trade_ret = (close[end] - entry) / entry
        hold_days = min(max_hold, n - idx - 1)

    # Calculate hedge P&L
    hedge_ret = 0
    if hedge_type == 'spy_put':
        # Simplified: buy ATM put on SPY, costs ~hedge_pct of position
        # If SPY drops X%, put gains ~3x (leverage of ATM 30-day put)
        spy_i = spy_idx_map.get(date)
        if spy_i is not None and spy_i + hold_days < len(spy_c):
            spy_change = (spy_c[spy_i + hold_days] - spy_c[spy_i]) / spy_c[spy_i]
            if spy_change < 0:
                # Put profits: ~3x leverage on SPY decline, minus premium decay
                put_gain = abs(spy_change) * 3 - 0.03 * (hold_days / 30)  # theta decay
                hedge_ret = hedge_pct * max(put_gain, -1)  # can't lose more than premium
            else:
                # Put expires worthless (lose premium, scaled by time)
                time_decay = min(1.0, hold_days / 30)
                hedge_ret = -hedge_pct * time_decay

    elif hedge_type == 'spy_short':
        # Short SPY as hedge (inverse exposure)
        spy_i = spy_idx_map.get(date)
        if spy_i is not None and spy_i + hold_days < len(spy_c):
            spy_change = (spy_c[spy_i + hold_days] - spy_c[spy_i]) / spy_c[spy_i]
            hedge_ret = -spy_change * hedge_pct  # profit when SPY drops

    elif hedge_type == 'portfolio_put':
        # Buy put on the actual stock (protective put)
        stock_change = trade_ret
        if stock_change < -0.05:
            # Put kicks in below 5% loss
            put_gain = abs(stock_change + 0.05) * 2.5 - 0.04 * (hold_days / 30)
            hedge_ret = hedge_pct * max(put_gain, -1)
        else:
            time_decay = min(1.0, hold_days / 30)
            hedge_ret = -hedge_pct * time_decay

    # Net position: (1 - hedge_pct) * trade return + hedge return
    net_ret = (1 - hedge_pct) * trade_ret + hedge_ret

    return trade_ret, hedge_ret, net_ret, hold_days


def calc_stats(returns):
    if not returns:
        return None
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gw = sum(wins) if wins else 0
    gl = abs(sum(losses)) if losses else 0.001
    # Max drawdown (sequential)
    cumulative = np.cumsum(returns)
    peak = np.maximum.accumulate(cumulative)
    dd = cumulative - peak
    max_dd = abs(np.min(dd)) * 100 if len(dd) > 0 else 0
    return {
        'trades': len(returns),
        'win_rate': round(len(wins)/len(returns)*100, 1),
        'avg_return': round(np.mean(returns)*100, 2),
        'total_return': round(np.sum(returns)*100, 1),
        'profit_factor': round(gw/gl, 2),
        'avg_win': round(np.mean(wins)*100, 2) if wins else 0,
        'avg_loss': round(np.mean(losses)*100, 2) if losses else 0,
        'max_drawdown': round(max_dd, 1),
        'sharpe': round(np.mean(returns)/np.std(returns)*np.sqrt(252/5), 2) if np.std(returns) > 0 else 0
    }


def run():
    print(f"\n{'#'*70}")
    print(f"#  OPTIMAL SETTINGS + HEDGE ANALYSIS")
    print(f"#  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'#'*70}\n")

    start_date = '2021-01-01'
    end_date = '2026-01-31'
    scan_start = pd.Timestamp(start_date)

    # Download
    print("📥 Downloading data...")
    all_data = {}
    for i, t in enumerate(UNIVERSE):
        try:
            df = yf.download(t, start='2020-01-01', end=end_date, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 252:
                all_data[t] = df
            sys.stdout.write(f"\r  {i+1}/{len(UNIVERSE)}: {t}     ")
            sys.stdout.flush()
        except:
            pass

    spy = yf.download('SPY', start='2020-01-01', end=end_date, progress=False)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    spy_close = spy['Close'].values
    spy_high = spy['High'].values
    spy_low = spy['Low'].values
    spy_ma200 = pd.Series(spy_close).rolling(200).mean().values
    # Map dates to spy index
    spy_idx_map = {d: i for i, d in enumerate(spy.index)}

    print(f"\n  ✅ {len(all_data)} stocks + SPY\n")

    # Detect patterns
    print("🔍 Detecting patterns...")
    all_signals = {}
    total = 0
    for ticker, df in all_data.items():
        sys.stdout.write(f"\r  {ticker}...          ")
        sys.stdout.flush()
        sigs = [s for s in detect_patterns(df) if s['date'] >= scan_start and s['idx'] + 90 < len(df)]
        all_signals[ticker] = sigs
        total += len(sigs)
    print(f"\n  ✅ {total} signals\n")

    # ════════════════════════════════════════════════
    # PART A: 10% vs 15% stop comparison
    # ════════════════════════════════════════════════
    print("="*70)
    print("📊 PART A: 10% Stop vs 15% Stop (with SPY>200MA filter)")
    print("="*70)

    configs = [
        ('10% stop / 10% trail / 60d', 0.10, 0.10, 60),
        ('10% stop / 12% trail / 60d', 0.10, 0.12, 60),
        ('10% stop / 15% trail / 60d', 0.10, 0.15, 60),
        ('10% stop / 10% trail / 90d', 0.10, 0.10, 90),
        ('10% stop / 12% trail / 90d', 0.10, 0.12, 90),
        ('10% stop / 15% trail / 90d', 0.10, 0.15, 90),
        ('15% stop / 15% trail / 60d', 0.15, 0.15, 60),
        ('15% stop / 15% trail / 90d', 0.15, 0.15, 90),
        ('10% stop / 20% fixed tgt / 60d', 0.10, None, 60),  # fixed target for comparison
    ]

    print(f"\n  {'Config':<32} | {'Trades':>6} | {'Win%':>6} | {'AvgRet':>7} | {'PF':>6} | {'MaxDD':>6} | {'Sharpe':>6}")
    print(f"  {'-'*32}-+-{'-'*6}-+-{'-'*6}-+-{'-'*7}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}")

    best_config = (None, 0)
    for name, stop, trail_or_tgt, max_hold in configs:
        rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                # SPY > 200MA filter
                spy_i = spy_idx_map.get(s['date'])
                if spy_i and spy_i < len(spy_ma200) and not np.isnan(spy_ma200[spy_i]):
                    if spy_close[spy_i] <= spy_ma200[spy_i]:
                        continue
                # Volume filter
                if s['vol_ratio'] < 1.5:
                    continue
                if trail_or_tgt is None:
                    # Fixed 20% target mode
                    r, _, _ = simulate_fixed(c, h, l, s['idx'], s['entry_price'], stop, 0.20, max_hold)
                else:
                    r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], stop, trail_or_tgt, max_hold)
                rets.append(r)

        st = calc_stats(rets)
        if st:
            print(f"  {name:<32} | {st['trades']:>6} | {st['win_rate']:>5.1f}% | {st['avg_return']:>6.2f}% | {st['profit_factor']:>5.2f}x | {st['max_drawdown']:>5.1f}% | {st['sharpe']:>5.2f}")
            if st['profit_factor'] > best_config[1]:
                best_config = (name, st['profit_factor'], st)

    print(f"\n  🏆 Best: {best_config[0]}")

    # ════════════════════════════════════════════════
    # PART B: Hedge Strategies
    # ════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("📊 PART B: Hedge Strategy Comparison")
    print("   Using 10% stop / 12% trail / 90d / SPY>200MA / vol≥1.5x")
    print("="*70)

    stop, trail, max_hold = 0.10, 0.12, 90

    hedge_configs = [
        ('No hedge', None, 0),
        ('SPY put 2%', 'spy_put', 0.02),
        ('SPY put 3%', 'spy_put', 0.03),
        ('SPY put 5%', 'spy_put', 0.05),
        ('SPY short 5%', 'spy_short', 0.05),
        ('SPY short 10%', 'spy_short', 0.10),
        ('SPY short 20%', 'spy_short', 0.20),
        ('Stock put 3%', 'portfolio_put', 0.03),
        ('Stock put 5%', 'portfolio_put', 0.05),
    ]

    print(f"\n  {'Hedge':<18} | {'Trades':>6} | {'Win%':>6} | {'AvgRet':>7} | {'PF':>6} | {'MaxDD':>6} | {'Sharpe':>6} | {'AvgHedge':>8}")
    print(f"  {'-'*18}-+-{'-'*6}-+-{'-'*6}-+-{'-'*7}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*8}")

    for name, h_type, h_pct in hedge_configs:
        net_rets = []
        hedge_rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                spy_i = spy_idx_map.get(s['date'])
                if spy_i and spy_i < len(spy_ma200) and not np.isnan(spy_ma200[spy_i]):
                    if spy_close[spy_i] <= spy_ma200[spy_i]:
                        continue
                if s['vol_ratio'] < 1.5:
                    continue

                if h_type is None:
                    r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], stop, trail, max_hold)
                    net_rets.append(r)
                    hedge_rets.append(0)
                else:
                    tr, hr, nr, _ = simulate_with_hedge(
                        c, h, l, spy_close, spy_high, spy_low, spy_idx_map,
                        s['idx'], s['entry_price'], stop, trail, max_hold,
                        s['date'], h_type, h_pct)
                    net_rets.append(nr)
                    hedge_rets.append(hr)

        st = calc_stats(net_rets)
        avg_hedge = np.mean(hedge_rets) * 100 if hedge_rets else 0
        if st:
            print(f"  {name:<18} | {st['trades']:>6} | {st['win_rate']:>5.1f}% | {st['avg_return']:>6.2f}% | {st['profit_factor']:>5.2f}x | {st['max_drawdown']:>5.1f}% | {st['sharpe']:>5.2f} | {avg_hedge:>7.2f}%")

    # ════════════════════════════════════════════════
    # PART C: Bear market performance (SPY < 200MA periods)
    # ════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("📊 PART C: Bear Market Analysis (SPY < 200MA)")
    print("   How do patterns perform in downtrends? Is hedging worth it?")
    print("="*70)

    bear_configs = [
        ('No hedge (bear)', None, 0),
        ('SPY put 3% (bear)', 'spy_put', 0.03),
        ('SPY put 5% (bear)', 'spy_put', 0.05),
        ('SPY short 10% (bear)', 'spy_short', 0.10),
        ('SPY short 20% (bear)', 'spy_short', 0.20),
        ('Stock put 5% (bear)', 'portfolio_put', 0.05),
    ]

    print(f"\n  {'Hedge':<24} | {'Trades':>6} | {'Win%':>6} | {'AvgRet':>7} | {'PF':>6} | {'MaxDD':>6}")
    print(f"  {'-'*24}-+-{'-'*6}-+-{'-'*6}-+-{'-'*7}-+-{'-'*6}-+-{'-'*6}")

    for name, h_type, h_pct in bear_configs:
        net_rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                # ONLY bear market trades
                spy_i = spy_idx_map.get(s['date'])
                if spy_i is None or spy_i >= len(spy_ma200) or np.isnan(spy_ma200[spy_i]):
                    continue
                if spy_close[spy_i] > spy_ma200[spy_i]:
                    continue  # skip bull trades
                if s['vol_ratio'] < 1.5:
                    continue

                if h_type is None:
                    r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], stop, trail, max_hold)
                    net_rets.append(r)
                else:
                    _, _, nr, _ = simulate_with_hedge(
                        c, h, l, spy_close, spy_high, spy_low, spy_idx_map,
                        s['idx'], s['entry_price'], stop, trail, max_hold,
                        s['date'], h_type, h_pct)
                    net_rets.append(nr)

        st = calc_stats(net_rets)
        if st:
            print(f"  {name:<24} | {st['trades']:>6} | {st['win_rate']:>5.1f}% | {st['avg_return']:>6.2f}% | {st['profit_factor']:>5.2f}x | {st['max_drawdown']:>5.1f}%")

    # ════════════════════════════════════════════════
    # PART D: Pattern combos with best settings
    # ════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("📊 PART D: Best Patterns with Optimal Settings")
    print("   10% stop / 12% trail / 90d / SPY>200MA / vol≥1.5x")
    print("="*70)

    filters = [
        ('All patterns', lambda s: True),
        ('2+ patterns', lambda s: s['num_patterns'] >= 2),
        ('3+ patterns', lambda s: s['num_patterns'] >= 3),
        ('Has Breakout', lambda s: 'Breakout' in s['patterns']),
        ('Has Cup+Handle', lambda s: 'Cup w/ Handle' in s['patterns']),
        ('Breakout+Cup', lambda s: 'Breakout' in s['patterns'] and 'Cup w/ Handle' in s['patterns']),
        ('VCP+Flat', lambda s: 'VCP' in s['patterns'] and 'Flat Base' in s['patterns']),
        ('Flat Base only', lambda s: 'Flat Base' in s['patterns']),
    ]

    print(f"\n  {'Filter':<20} | {'Trades':>6} | {'Win%':>6} | {'AvgRet':>7} | {'PF':>6} | {'MaxDD':>6} | {'Sharpe':>6}")
    print(f"  {'-'*20}-+-{'-'*6}-+-{'-'*6}-+-{'-'*7}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}")

    for name, filt in filters:
        rets = []
        for ticker, sigs in all_signals.items():
            df = all_data[ticker]
            c, h, l = df['Close'].values, df['High'].values, df['Low'].values
            for s in sigs:
                if not filt(s):
                    continue
                spy_i = spy_idx_map.get(s['date'])
                if spy_i and spy_i < len(spy_ma200) and not np.isnan(spy_ma200[spy_i]):
                    if spy_close[spy_i] <= spy_ma200[spy_i]:
                        continue
                if s['vol_ratio'] < 1.5:
                    continue
                r, _, _ = simulate_trade(c, h, l, s['idx'], s['entry_price'], stop, trail, max_hold)
                rets.append(r)
        st = calc_stats(rets)
        if st:
            print(f"  {name:<20} | {st['trades']:>6} | {st['win_rate']:>5.1f}% | {st['avg_return']:>6.2f}% | {st['profit_factor']:>5.2f}x | {st['max_drawdown']:>5.1f}% | {st['sharpe']:>5.2f}")

    print(f"\n{'#'*70}")
    print(f"#  DONE")
    print(f"{'#'*70}\n")


def simulate_fixed(close, high, low, idx, entry, stop, target, max_hold):
    """Fixed stop/target (no trailing)."""
    n = len(close)
    for j in range(1, min(max_hold + 1, n - idx)):
        loss = (low[idx+j] - entry) / entry
        if loss <= -stop:
            return -stop, 'stop', j
        gain = (high[idx+j] - entry) / entry
        if gain >= target:
            return target, 'target', j
    end = min(idx + max_hold, n - 1)
    return (close[end] - entry) / entry, 'time', min(max_hold, n - idx - 1)


if __name__ == '__main__':
    run()
