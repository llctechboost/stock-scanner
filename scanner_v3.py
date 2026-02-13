#!/usr/bin/env python3
"""
William O'Neil / Chris Kacher Stock Scanner v2
Implements exact CANSLIM methodology with precise pattern detection
"""

import yfinance as yf
import pandas as pd
import numpy as np
from ta.volatility import BollingerBands, KeltnerChannel, AverageTrueRange
from ta.trend import EMAIndicator
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


def clean_dataframe(df):
    """
    Utility function to handle common DataFrame issues.
    Flattens multi-index columns, ensures proper data types.
    """
    # Flatten multi-index columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # Remove any duplicate index entries
    df = df[~df.index.duplicated(keep='first')]
    
    # Sort by date
    df = df.sort_index()
    
    return df


class CANSLIMScanner:
    def __init__(self, universe):
        self.universe = universe
        self.results = []
        self.all_stocks_data = {}  # Cache for RS calculation
    
    def calculate_rs_rating(self, ticker, df):
        """
        O'Neil RS Rating - Exact IBD methodology
        Weighted 4-quarter performance vs all stocks in universe
        """
        if len(df) < 252:  # Need 1 year of data
            return 0
        
        # Define quarters (60 trading days each)
        q1_start, q1_end = -63, -1      # 0-3 months (most recent)
        q2_start, q2_end = -126, -64    # 3-6 months
        q3_start, q3_end = -189, -127   # 6-9 months
        q4_start, q4_end = -252, -190   # 9-12 months
        
        # Calculate ROC for each quarter
        def calc_roc(start, end):
            try:
                return (df['Close'].iloc[end] / df['Close'].iloc[start]) - 1
            except:
                return 0
        
        q1_roc = calc_roc(q1_start, q1_end)
        q2_roc = calc_roc(q2_start, q2_end)
        q3_roc = calc_roc(q3_start, q3_end)
        q4_roc = calc_roc(q4_start, q4_end)
        
        # Weighted performance (Q1 gets double weight: 40%)
        weighted_perf = (q1_roc * 0.40) + (q2_roc * 0.20) + (q3_roc * 0.20) + (q4_roc * 0.20)
        
        # Store for universe comparison
        self.all_stocks_data[ticker] = weighted_perf
        
        return weighted_perf
    
    def rank_rs_ratings(self):
        """Convert weighted performance to percentile rankings (0-100)"""
        if not self.all_stocks_data:
            return
        
        performances = list(self.all_stocks_data.values())
        
        # Need at least 20 stocks for meaningful RS rankings
        min_universe = 20
        if len(performances) < min_universe:
            # With small samples, use absolute performance thresholds instead
            for result in self.results:
                ticker = result['ticker']
                perf = self.all_stocks_data.get(ticker, 0)
                # Rough absolute RS: >30% = 90, >20% = 80, >10% = 70, etc.
                if perf > 0.30:
                    result['rs_rating'] = 90
                elif perf > 0.20:
                    result['rs_rating'] = 80
                elif perf > 0.10:
                    result['rs_rating'] = 70
                elif perf > 0.05:
                    result['rs_rating'] = 60
                elif perf > 0:
                    result['rs_rating'] = 50
                else:
                    result['rs_rating'] = 30
            return
        
        for result in self.results:
            ticker = result['ticker']
            perf = self.all_stocks_data.get(ticker, 0)
            
            # Calculate percentile rank
            rank = sum(1 for p in performances if p < perf) / len(performances) * 100
            result['rs_rating'] = int(rank)
    
    def detect_cup_with_handle(self, df, min_weeks=7, max_weeks=65):
        """
        Exact O'Neil Cup with Handle detection
        
        Rules:
        - Cup: 7-65 weeks, 12-33% depth, U-shaped
        - Handle: 1-4 weeks, max 12% pullback, ≤1/3 cup depth
        - Handle must be in upper 50% of cup
        - Volume dries up in handle
        """
        min_days = min_weeks * 5
        max_days = max_weeks * 5
        
        if len(df) < min_days:
            return None
        
        # Look for cup patterns in recent history
        lookback = min(max_days, len(df))
        recent = df.tail(lookback)
        
        # Find potential left side high (cup start)
        left_high_idx = recent['High'].idxmax()
        left_high = recent.loc[left_high_idx, 'High']
        
        # Find cup bottom
        cup_data = recent.loc[left_high_idx:]
        if len(cup_data) < min_days:
            return None
        
        cup_low = cup_data['Low'].min()
        cup_low_idx = cup_data['Low'].idxmin()
        
        # Check cup depth (12-33%)
        cup_depth = ((left_high - cup_low) / left_high) * 100
        if cup_depth < 12 or cup_depth > 33:
            return None
        
        # Check for U-shape (not V-shape)
        # Bottom period should be wide (at least 3 weeks)
        bottom_area = cup_data.loc[:cup_low_idx]
        if len(bottom_area) < 15:  # Less than 3 weeks = V-shape
            return None
        
        # Find right side recovery
        right_side = cup_data.loc[cup_low_idx:]
        if len(right_side) < 15:  # Need recovery period
            return None
        
        # Right side should approach left high (within 5%)
        recent_high = right_side['High'].max()
        if recent_high < (left_high * 0.95):
            return None
        
        # Detect handle in most recent 1-4 weeks
        handle_lookback = min(20, len(right_side))  # Up to 4 weeks
        handle_data = right_side.tail(handle_lookback)
        
        if len(handle_data) < 5:  # At least 1 week
            return None
        
        handle_high = handle_data['High'].max()
        handle_low = handle_data['Low'].min()
        current_price = df['Close'].iloc[-1]
        
        # Handle depth (max 12% pullback)
        handle_depth = ((handle_high - handle_low) / handle_high) * 100
        if handle_depth > 12:
            return None
        
        # Handle must be ≤ 1/3 of cup depth
        if handle_depth > (cup_depth / 3):
            return None
        
        # Handle must be in upper 50% of cup (preferably upper 33%)
        handle_position = (handle_low - cup_low) / (left_high - cup_low)
        if handle_position < 0.5:
            return None
        
        # Check volume contraction in handle
        handle_avg_vol = handle_data['Volume'].mean()
        cup_avg_vol = cup_data['Volume'].mean()
        volume_contraction = handle_avg_vol < (cup_avg_vol * 0.8)
        
        # Buy point: 0.10 or 0.2% above handle high
        buy_point = handle_high * 1.002
        
        return {
            'pattern': 'Cup with Handle',
            'cup_depth': cup_depth,
            'handle_depth': handle_depth,
            'buy_point': buy_point,
            'volume_contraction': volume_contraction,
            'handle_position': handle_position * 100,
            'valid': True
        }
    
    def detect_flat_base(self, df, min_weeks=5):
        """
        Exact O'Neil Flat Base detection
        
        Rules:
        - 5-6 weeks minimum (can extend to 65)
        - 10-15% maximum correction
        - Second-stage base (after 20%+ advance)
        - Tight sideways movement near highs
        """
        min_days = min_weeks * 5
        
        if len(df) < min_days + 60:  # Need prior advance data
            return None
        
        # Check for prior advance (20%+)
        lookback_start = -(min_days + 60)
        prior_low = df['Low'].iloc[lookback_start:-min_days].min()
        base_start_price = df['Close'].iloc[-min_days]
        
        prior_advance = ((base_start_price - prior_low) / prior_low) * 100
        if prior_advance < 20:
            return None  # Not a second-stage base
        
        # Analyze potential flat base (last 5-6 weeks)
        base_data = df.tail(min_days)
        base_high = base_data['High'].max()
        base_low = base_data['Low'].min()
        current_price = df['Close'].iloc[-1]
        
        # Check correction depth (max 15%)
        correction = ((base_high - base_low) / base_high) * 100
        if correction > 15:
            return None
        
        # Check if price is near high (upper 80% of range)
        price_position = (current_price - base_low) / (base_high - base_low)
        if price_position < 0.8:
            return None
        
        # Check for tight, orderly movement (low volatility)
        daily_changes = base_data['Close'].pct_change().abs()
        avg_daily_change = daily_changes.mean() * 100
        
        if avg_daily_change > 2.5:  # Too volatile for flat base
            return None
        
        # Buy point: 0.10 or 0.2% above base high
        buy_point = base_high * 1.002
        
        return {
            'pattern': 'Flat Base',
            'correction': correction,
            'prior_advance': prior_advance,
            'buy_point': buy_point,
            'weeks': len(base_data) / 5,
            'tightness': avg_daily_change,
            'valid': True
        }
    
    def detect_high_tight_flag(self, df):
        """
        High Tight Flag - Rare but explosive pattern
        
        O'Neil Rules (strict):
        - 100-120%+ advance in 4-8 weeks (the "high tight" move)
        - Tight consolidation with <20% depth (the "flag")
        - Flag duration: 3-5 weeks
        
        Relaxed Mode (still useful):
        - 40%+ advance in 4-8 weeks
        - <15% pullback consolidation
        - This catches strong momentum setups
        """
        if len(df) < 60:
            return None
        
        # Look for sharp advance (4-8 weeks)
        for weeks in range(4, 9):
            days = weeks * 5
            if len(df) < days + 25:
                continue
            
            # Calculate advance from start to peak
            start_price = df['Close'].iloc[-(days + 25)]
            peak_price = df['High'].iloc[-(days + 25):-15].max()
            advance = ((peak_price / start_price) - 1) * 100
            
            # Check for valid advance — 40%+ minimum (real HTFs are rare)
            if pd.isna(advance) or advance < 40:
                continue
            
            # Check consolidation (tight, shallow pullback) — last 3-5 weeks
            recent = df.tail(25)
            high = recent['High'].max()
            low = recent['Low'].min()
            correction = ((high - low) / high) * 100
            
            if correction > 15:  # Too deep — not a tight flag
                continue
            
            # Buy point: breakout above consolidation high
            buy_point = high * 1.002
            
            return {
                'pattern': 'High Tight Flag',
                'prior_advance': round(advance, 1),
                'consolidation_depth': round(correction, 1),
                'weeks': weeks,
                'buy_point': buy_point,
                'valid': True
            }
        
        return None
    
    def detect_ascending_base(self, df):
        """
        Ascending Base - Series of higher lows
        
        Rules:
        - 3+ pullbacks with each low higher than previous
        - Each pullback 10-20% depth
        - Base forms over 3-9 weeks
        """
        if len(df) < 60:
            return None
        
        recent = df.tail(60)
        
        # Find local lows (pullback bottoms)
        lows = []
        for i in range(10, len(recent) - 5):
            window = recent['Low'].iloc[i-10:i+5]
            if recent['Low'].iloc[i] == window.min():
                lows.append((i, recent['Low'].iloc[i]))
        
        # Need at least 3 lows
        if len(lows) < 3:
            return None
        
        # Check if ascending (each low higher than previous)
        ascending = all(lows[i][1] > lows[i-1][1] for i in range(1, len(lows)))
        
        if not ascending:
            return None
        
        # Check pullback depths
        highs_between = []
        for i in range(len(lows) - 1):
            start_idx, end_idx = lows[i][0], lows[i+1][0]
            high_between = recent['High'].iloc[start_idx:end_idx].max()
            low = lows[i+1][1]
            depth = ((high_between - low) / high_between) * 100
            
            if depth < 10 or depth > 25:  # Not proper pullback
                return None
        
        current_price = df['Close'].iloc[-1]
        highest_high = recent['High'].max()
        buy_point = highest_high * 1.002
        
        return {
            'pattern': 'Ascending Base',
            'num_lows': len(lows),
            'buy_point': buy_point,
            'weeks': len(recent) / 5,
            'valid': True
        }

    def detect_pocket_pivot(self, df):
        """
        Kacher/Morales Pocket Pivot
        
        Rules:
        - Up day (close > prior close)
        - Volume > MAX(last 10 down days' volume)
        - Price near 10-day MA (continuation) or 50-day MA (initial)
        """
        if len(df) < 50:
            return None
        
        # Calculate moving averages
        ma10 = df['Close'].rolling(10).mean()
        ma50 = df['Close'].rolling(50).mean()
        
        current = df.iloc[-1]
        current_ma10 = ma10.iloc[-1]
        current_ma50 = ma50.iloc[-1]
        
        # Check if up day
        if current['Close'] <= df['Close'].iloc[-2]:
            return None
        
        # Find last 10 down days
        recent = df.tail(20)  # Look back 20 days to find 10 down days
        down_days = recent[recent['Close'] < recent['Close'].shift(1)]
        
        if len(down_days) < 5:  # Need at least some down days
            return None
        
        # Get max volume from down days
        max_down_volume = down_days['Volume'].nlargest(10).max()
        
        # Check if current volume exceeds max down volume
        if current['Volume'] <= max_down_volume:
            return None
        
        # Check proximity to moving averages (within 2%)
        near_ma10 = abs(current['Close'] - current_ma10) / current_ma10 < 0.02
        near_ma50 = abs(current['Close'] - current_ma50) / current_ma50 < 0.02
        
        if not (near_ma10 or near_ma50):
            return None
        
        pivot_type = 'continuation' if near_ma10 else 'initial'
        volume_ratio = current['Volume'] / max_down_volume
        
        return {
            'pattern': 'Pocket Pivot',
            'type': pivot_type,
            'volume_ratio': volume_ratio,
            'ma_level': current_ma10 if near_ma10 else current_ma50,
            'valid': True
        }
    
    def check_volume_breakout(self, df):
        """Check for volume surge on breakout (50%+ above average)"""
        if len(df) < 50:
            return False, 0
        
        avg_volume = df['Volume'].tail(50).mean()
        current_volume = df['Volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume
        
        return volume_ratio >= 1.5, volume_ratio
    
    def check_fundamentals(self, ticker):
        """Check CANSLIM fundamentals + earnings proximity"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            scores = {}
            
            # Current quarterly earnings growth (>25%)
            earnings_growth = info.get('earningsQuarterlyGrowth', 0) or 0
            scores['eps_growth'] = earnings_growth * 100 if earnings_growth else 0
            
            # Annual earnings growth
            revenue_growth = info.get('revenueGrowth', 0) or 0
            scores['revenue_growth'] = revenue_growth * 100 if revenue_growth else 0
            
            # ROE (>17%)
            roe = info.get('returnOnEquity', 0) or 0
            scores['roe'] = roe * 100 if roe else 0
            
            # Profit margins
            profit_margin = info.get('profitMargins', 0) or 0
            scores['profit_margin'] = profit_margin * 100 if profit_margin else 0
            
            # Earnings proximity check
            scores['earnings_warning'] = False
            scores['earnings_date'] = None
            try:
                cal = stock.calendar
                if cal is not None:
                    # Handle both dict and DataFrame formats
                    if isinstance(cal, dict):
                        earn_date = cal.get('Earnings Date', [None])[0] if 'Earnings Date' in cal else None
                    else:
                        earn_date = cal.iloc[0].get('Earnings Date', None) if len(cal) > 0 else None
                    
                    if earn_date is not None:
                        from datetime import datetime, timedelta
                        if hasattr(earn_date, 'date'):
                            earn_date = earn_date.date()
                        days_to_earnings = (earn_date - datetime.now().date()).days
                        scores['earnings_date'] = str(earn_date)
                        scores['days_to_earnings'] = days_to_earnings
                        if 0 < days_to_earnings <= 14:
                            scores['earnings_warning'] = True
            except:
                pass
            
            return scores
            
        except Exception as e:
            return {'error': str(e)}
    
    def check_market_timing(self):
        """
        Market Timing - Check S&P 500 trend, distribution days, VIX
        Returns: market status and recommendation
        """
        try:
            # Download S&P 500 and VIX
            spy = yf.download('^GSPC', period='3mo', progress=False)
            vix = yf.download('^VIX', period='3mo', progress=False)
            
            spy = clean_dataframe(spy)
            vix = clean_dataframe(vix)
            
            if len(spy) < 50:
                return {'status': 'unknown', 'recommendation': 'Proceed with caution'}
            
            # Calculate MAs
            ma21 = spy['Close'].rolling(21).mean().iloc[-1]
            ma50 = spy['Close'].rolling(50).mean().iloc[-1]
            current = spy['Close'].iloc[-1]
            
            # Check trend
            uptrend = current > ma21 and ma21 > ma50
            
            # Count distribution days (last 25 days)
            recent = spy.tail(25)
            dist_days = 0
            for i in range(1, len(recent)):
                if recent['Close'].iloc[i] < recent['Close'].iloc[i-1]:
                    if recent['Volume'].iloc[i] > recent['Volume'].iloc[i-1]:
                        dist_days += 1
            
            # VIX analysis
            vix_current = vix['Close'].iloc[-1] if len(vix) > 0 else 0
            vix_signal = 'Low' if vix_current < 15 else 'Moderate' if vix_current < 20 else 'Elevated' if vix_current < 30 else 'High'
            
            # Determine market status
            if uptrend and dist_days < 5 and vix_current < 20:
                status = 'confirmed_uptrend'
                recommendation = '✅ Green light - Buy setups'
            elif uptrend and dist_days >= 5:
                status = 'uptrend_under_pressure'
                recommendation = '⚠️ Caution - Reduce position sizes'
            elif not uptrend or vix_current > 30:
                status = 'correction'
                recommendation = '🛑 Red light - Preserve capital, wait'
            else:
                status = 'uncertain'
                recommendation = '⚠️ Mixed signals - Be selective'
            
            return {
                'status': status,
                'sp500_price': current,
                'above_21ma': current > ma21,
                'above_50ma': current > ma50,
                'distribution_days': dist_days,
                'vix': vix_current,
                'vix_signal': vix_signal,
                'recommendation': recommendation
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e), 'recommendation': 'Check manually'}
    
    def analyze_industry_groups(self, results):
        """
        Analyze which industry sectors are showing strength
        Returns top performing sectors based on scan results
        """
        if not results:
            return {}
        
        sector_scores = {}
        sector_counts = {}
        
        for result in results:
            ticker = result['ticker']
            score = result['score']
            
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                sector = info.get('sector', 'Unknown')
                
                if sector not in sector_scores:
                    sector_scores[sector] = []
                    sector_counts[sector] = 0
                
                sector_scores[sector].append(score)
                sector_counts[sector] += 1
            except:
                continue
        
        # Calculate average scores by sector
        sector_analysis = []
        for sector, scores in sector_scores.items():
            avg_score = sum(scores) / len(scores)
            sector_analysis.append({
                'sector': sector,
                'avg_score': round(avg_score, 1),
                'count': sector_counts[sector],
                'strength': 'Strong' if avg_score >= 6 else 'Moderate' if avg_score >= 4 else 'Weak'
            })
        
        # Sort by average score
        sector_analysis.sort(key=lambda x: x['avg_score'], reverse=True)
        
        return sector_analysis

    def scan_stock(self, ticker):
        """Run full CANSLIM scan on a single stock"""
        try:
            # Download 2 years of data for proper RS calculation
            df = yf.download(ticker, period='2y', progress=False)
            
            # Clean DataFrame using utility function
            df = clean_dataframe(df)
            
            if len(df) < 100:
                return None
            
            # Calculate RS rating (will be ranked later)
            rs_perf = self.calculate_rs_rating(ticker, df)
            
            # Pattern detection
            cup_handle = self.detect_cup_with_handle(df)
            flat_base = self.detect_flat_base(df)
            pocket_pivot = self.detect_pocket_pivot(df)
            high_tight_flag = self.detect_high_tight_flag(df)
            ascending_base = self.detect_ascending_base(df)
            
            # Volume analysis
            volume_breakout, volume_ratio = self.check_volume_breakout(df)
            
            # Fundamentals
            fundamentals = self.check_fundamentals(ticker)
            
            # Score the setup
            score = 0
            signals = []
            patterns = []
            
            # Pattern signals
            if cup_handle:
                score += 4
                signals.append(f"Cup with Handle ({cup_handle['cup_depth']:.1f}% cup, {cup_handle['handle_depth']:.1f}% handle)")
                patterns.append(cup_handle)
            
            if flat_base:
                score += 3
                signals.append(f"Flat Base ({flat_base['correction']:.1f}% range, {flat_base['weeks']:.0f} weeks)")
                patterns.append(flat_base)
            
            if pocket_pivot:
                score += 3
                signals.append(f"Pocket Pivot ({pocket_pivot['type']}, {pocket_pivot['volume_ratio']:.1f}x volume)")
                patterns.append(pocket_pivot)
            
            if high_tight_flag:
                score += 4  # Rare and powerful
                signals.append(f"High Tight Flag ({high_tight_flag['prior_advance']:.1f}% advance, {high_tight_flag['consolidation_depth']:.1f}% pullback)")
                patterns.append(high_tight_flag)
            
            if ascending_base:
                score += 3
                signals.append(f"Ascending Base ({ascending_base['num_lows']} higher lows)")
                patterns.append(ascending_base)
            
            if volume_breakout:
                score += 1
                signals.append(f"Volume Breakout ({volume_ratio:.1f}x avg)")
            
            # Fundamental signals
            if fundamentals.get('eps_growth', 0) > 25:
                score += 2
                signals.append(f"EPS Growth {fundamentals['eps_growth']:.0f}%")
            
            if fundamentals.get('roe', 0) > 17:
                score += 1
                signals.append(f"ROE {fundamentals['roe']:.1f}%")
            
            # Earnings proximity warning
            if fundamentals.get('earnings_warning'):
                signals.append(f"⚠️ EARNINGS IN {fundamentals.get('days_to_earnings', '?')} DAYS ({fundamentals.get('earnings_date', '?')})")
            
            # RS will be scored after universe ranking
            
            # Cap score at 12
            score = min(score, 12)
            
            # Only return stocks with meaningful signals
            if score >= 3:
                return {
                    'ticker': ticker,
                    'score': score,
                    'signals': signals,
                    'patterns': patterns,
                    'price': df['Close'].iloc[-1],
                    'volume_ratio': volume_ratio,
                    'fundamentals': fundamentals,
                    'rs_performance': rs_perf
                }
            
            return None
            
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            return None
    
    def scan(self):
        """Scan entire universe"""
        print(f"Scanning {len(self.universe)} stocks...")
        print("This may take a few minutes...\n")
        
        # First pass: collect all data and RS performances
        for i, ticker in enumerate(self.universe):
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i+1}/{len(self.universe)}")
            
            result = self.scan_stock(ticker)
            if result:
                self.results.append(result)
        
        # Second pass: rank RS ratings
        print("\nRanking relative strength...")
        self.rank_rs_ratings()
        
        # Add RS score
        for result in self.results:
            rs_rating = result.get('rs_rating', 0)
            if rs_rating >= 80:
                result['score'] += 3
                result['signals'].insert(0, f"RS Rating {rs_rating} (Top 20%)")
            elif rs_rating >= 70:
                result['score'] += 1
                result['signals'].insert(0, f"RS Rating {rs_rating}")
        
        # Sort by score
        self.results.sort(key=lambda x: x['score'], reverse=True)
        
        return self.results
    
    def print_results(self, max_results=25):
        """Print scan results with market context and segmentation"""
        print("\n" + "="*80)
        print("                    CANSLIM STOCK SCANNER v3")
        print("              O'Neil / Kacher Methodology - Enhanced")
        print("                    " + datetime.now().strftime("%Y-%m-%d %H:%M"))
        print("="*80)
        
        # Market timing
        print("\n📊 MARKET TIMING")
        print("-" * 80)
        market = self.check_market_timing()
        print(f"S&P 500: ${market.get('sp500_price', 0):.2f}")
        print(f"Above 21-day MA: {'✓' if market.get('above_21ma') else '✗'}")
        print(f"Above 50-day MA: {'✓' if market.get('above_50ma') else '✗'}")
        print(f"Distribution Days: {market.get('distribution_days', 0)}")
        print(f"VIX: {market.get('vix', 0):.2f} ({market.get('vix_signal', 'Unknown')})")
        print(f"\n{market.get('recommendation', 'Unknown')}")
        
        # Industry group analysis
        print("\n🏭 INDUSTRY GROUP STRENGTH")
        print("-" * 80)
        sectors = self.analyze_industry_groups(self.results)
        for sector in sectors[:5]:  # Top 5 sectors
            print(f"  {sector['sector']}: Avg Score {sector['avg_score']} ({sector['count']} stocks) - {sector['strength']}")
        
        if not self.results:
            print("\nNo stocks met the criteria.")
            return
        
        # Segment results — each stock appears in ONE section only (highest priority)
        breakouts_now = []
        bases_forming = []
        pocket_pivots = []
        seen = set()
        
        for r in self.results:
            ticker = r['ticker']
            if ticker in seen:
                continue
            pattern_names = [p.get('pattern') for p in r.get('patterns', [])]
            if any(p in ['Cup with Handle', 'High Tight Flag'] for p in pattern_names):
                breakouts_now.append(r)
                seen.add(ticker)
            elif any(p in ['Flat Base', 'Ascending Base'] for p in pattern_names):
                bases_forming.append(r)
                seen.add(ticker)
            elif any(p == 'Pocket Pivot' for p in pattern_names):
                pocket_pivots.append(r)
                seen.add(ticker)
        
        # Breakouts Now
        if breakouts_now:
            print("\n🚀 BREAKOUTS NOW (Action Setups)")
            print("-" * 80)
            for r in breakouts_now[:10]:
                self._print_stock_result(r)
        
        # Bases Forming  
        if bases_forming:
            print("\n📈 BASES FORMING (Watch List)")
            print("-" * 80)
            for r in bases_forming[:10]:
                self._print_stock_result(r)
        
        # Pocket Pivots
        if pocket_pivots:
            print("\n⚡ POCKET PIVOTS (Early Entry)")
            print("-" * 80)
            for r in pocket_pivots[:10]:
                self._print_stock_result(r)
        
        print("\n" + "="*80)
        print(f"Total stocks scanned: {len(self.universe)}")
        print(f"Stocks meeting criteria: {len(self.results)}")
        print(f"  Breakouts: {len(breakouts_now)}")
        print(f"  Bases forming: {len(bases_forming)}")
        print(f"  Pocket pivots: {len(pocket_pivots)}")
        print("="*80)
    
    def _print_stock_result(self, r):
        """Helper to print individual stock result"""
        print(f"\n{r['ticker']} - Score: {r['score']}/12 - ${r['price']:.2f}")
        print(f"  RS Rating: {r.get('rs_rating', 0)}")
        
        for signal in r['signals']:
            print(f"  ✓ {signal}")
        
        # Show best buy point (avoid duplicates)
        buy_points = set()
        for pattern in r.get('patterns', []):
            if 'buy_point' in pattern:
                bp = round(pattern['buy_point'], 2)
                buy_points.add(bp)
        for bp in sorted(buy_points):
            print(f"    → Buy point: ${bp:.2f}")


# Expanded watchlist - Growth stocks, recent IPOs, market leaders
DEFAULT_TICKERS = [
    # Mag 7 + Tech Leaders
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA', 'AMD', 'AVGO', 'CRM',
    # Cloud/SaaS
    'PLTR', 'NET', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'MDB', 'PANW', 'NOW', 'SHOP',
    # Recent Momentum
    'SMCI', 'ARM', 'IONQ', 'RGTI', 'APP', 'HIMS', 'DUOL', 'CELH', 'TOST', 'CAVA',
    # Financials
    'GS', 'JPM', 'V', 'MA', 'AXP', 'COIN', 'HOOD', 'SOFI', 'NU',
    # Healthcare
    'LLY', 'NVO', 'UNH', 'ISRG', 'DXCM', 'PODD', 'VRTX',
    # Industrial/Transportation
    'UBER', 'ABNB', 'DASH', 'RKLB', 'AXON', 'DECK', 'GWW', 'URI',
    # Semiconductors
    'ASML', 'LRCX', 'KLAC', 'AMAT', 'MRVL', 'QCOM',
    # Consumer
    'COST', 'TJX', 'LULU', 'NKE', 'HD', 'LOW',
    # Energy/Materials
    'XOM', 'CVX', 'EOG', 'FCX', 'NUE'
]


if __name__ == "__main__":
    import sys
    import os
    
    # Check for large watchlist file
    watchlist_file = 'large_watchlist.txt'
    if os.path.exists(watchlist_file):
        print(f"Loading tickers from {watchlist_file}...")
        with open(watchlist_file, 'r') as f:
            content = f.read()
            tickers = [t.strip() for t in content.replace('\n', ',').split(',') if t.strip()]
        print(f"Loaded {len(tickers)} tickers from watchlist")
    else:
        print(f"Using default watchlist ({len(DEFAULT_TICKERS)} tickers)")
        tickers = DEFAULT_TICKERS
    
    # Allow command line ticker list override
    if len(sys.argv) > 1:
        tickers = sys.argv[1:]
        print(f"Using command-line tickers: {','.join(tickers)}")
    
    scanner = CANSLIMScanner(tickers)
    results = scanner.scan()
    scanner.print_results()
    
    # Save to file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_file = f"scan_results_{timestamp}.txt"
    
    # Redirect print to file
    import sys
    original_stdout = sys.stdout
    with open(output_file, 'w') as f:
        sys.stdout = f
        scanner.print_results()
    sys.stdout = original_stdout
    
    print(f"\n✓ Results saved to {output_file}")
