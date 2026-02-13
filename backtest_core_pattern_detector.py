#!/usr/bin/env python3
"""
Pattern Detector - Integrates with scanner_v3.py patterns
"""
import pandas as pd
import numpy as np

class PatternDetector:
    """Detects O'Neil/CANSLIM patterns in price data."""
    
    @staticmethod
    def detect_cup_with_handle(df, lookback=30):
        """
        Cup with Handle pattern detection.
        
        Requirements:
        - Prior uptrend (30%+ in 4-12 months)
        - Cup depth 12-33%
        - Handle pullback 8-12%
        - Handle on lighter volume
        
        Returns:
            dict with pattern details or None
        """
        if len(df) < lookback:
            return None
        
        close = df['Close']
        volume = df['Volume']
        
        # Find potential cup (U-shape)
        # Look for high point, then low, then recovery
        highs = close.rolling(5).max()
        lows = close.rolling(5).min()
        
        # Cup: 30-120 days
        for cup_len in range(30, min(120, len(df))):
            cup = close.iloc[-cup_len:]
            left_high = cup.iloc[:10].max()
            right_high = cup.iloc[-10:].max()
            cup_low = cup.min()
            
            # Cup depth check (12-33%)
            depth = (left_high - cup_low) / left_high
            if depth < 0.12 or depth > 0.33:
                continue
            
            # Right side recovery (within 5% of left)
            if abs(right_high - left_high) / left_high > 0.05:
                continue
            
            # Look for handle (last 5-20 days)
            for handle_len in range(5, 20):
                if handle_len >= len(cup):
                    continue
                
                handle = cup.iloc[-handle_len:]
                handle_high = handle.iloc[0]
                handle_low = handle.min()
                current_price = close.iloc[-1]
                
                # Handle pullback 8-12%
                handle_depth = (handle_high - handle_low) / handle_high
                if handle_depth < 0.08 or handle_depth > 0.12:
                    continue
                
                # Volume drying up in handle
                handle_vol = volume.iloc[-handle_len:].mean()
                cup_vol = volume.iloc[-cup_len:-handle_len].mean()
                if handle_vol >= cup_vol:
                    continue
                
                # Buy point: handle high + 1-2%
                buy_point = handle_high * 1.01
                
                return {
                    'pattern': 'Cup with Handle',
                    'buy_point': buy_point,
                    'depth': depth * 100,
                    'handle_depth': handle_depth * 100,
                    'cup_weeks': cup_len // 5,
                    'handle_weeks': handle_len // 5,
                    'detected_date': df.index[-1]
                }
        
        return None
    
    @staticmethod
    def detect_flat_base(df, lookback=30):
        """
        Flat Base pattern detection.
        
        Requirements:
        - Tight consolidation (10-15% range)
        - At least 5 weeks
        - Near 52-week highs
        
        Returns:
            dict with pattern details or None
        """
        if len(df) < lookback:
            return None
        
        close = df['Close']
        
        # Check last 5-12 weeks
        for base_len in range(25, min(60, len(df))):
            base = close.iloc[-base_len:]
            high = base.max()
            low = base.min()
            current = close.iloc[-1]
            
            # Range check (10-15%)
            range_pct = (high - low) / low
            if range_pct < 0.10 or range_pct > 0.15:
                continue
            
            # Near highs (within top 5% of range)
            if (current - low) / (high - low) < 0.95:
                continue
            
            # 52-week high check
            year_high = close.iloc[-252:].max() if len(close) >= 252 else close.max()
            if high < year_high * 0.95:
                continue
            
            buy_point = high * 1.01
            
            return {
                'pattern': 'Flat Base',
                'buy_point': buy_point,
                'range': range_pct * 100,
                'weeks': base_len // 5,
                'detected_date': df.index[-1]
            }
        
        return None
    
    @staticmethod
    def detect_high_tight_flag(df, lookback=30):
        """
        High Tight Flag pattern detection.
        
        Requirements:
        - 100%+ gain in 4-8 weeks
        - Tight pullback 10-20%
        - 3-5 weeks consolidation
        
        Returns:
            dict with pattern details or None
        """
        if len(df) < 40:
            return None
        
        close = df['Close']
        
        # Look for strong advance (100%+ in 4-8 weeks)
        for advance_len in range(20, 40):
            if advance_len >= len(close):
                continue
            
            start_price = close.iloc[-advance_len - 20]
            peak_price = close.iloc[-20:].max()
            advance = (peak_price - start_price) / start_price
            
            if advance < 1.00:  # 100%+ gain
                continue
            
            # Look for tight pullback
            pullback = close.iloc[-20:]
            pullback_high = pullback.iloc[0]
            pullback_low = pullback.min()
            current = close.iloc[-1]
            
            pullback_pct = (pullback_high - pullback_low) / pullback_high
            if pullback_pct < 0.10 or pullback_pct > 0.20:
                continue
            
            buy_point = pullback_high * 1.01
            
            return {
                'pattern': 'High Tight Flag',
                'buy_point': buy_point,
                'advance': advance * 100,
                'pullback': pullback_pct * 100,
                'detected_date': df.index[-1]
            }
        
        return None
    
    @staticmethod
    def detect_pocket_pivot(df, lookback=10):
        """
        Pocket Pivot detection.
        
        Requirements:
        - Volume > highest down-day volume in last 10 days
        - Price holding above key MA
        
        Returns:
            dict with pattern details or None
        """
        if len(df) < lookback + 1:
            return None
        
        close = df['Close']
        volume = df['Volume']
        
        # Current day
        current_vol = volume.iloc[-1]
        current_close = close.iloc[-1]
        current_open = df['Open'].iloc[-1]
        
        # Must be up day
        if current_close <= current_open:
            return None
        
        # Find highest down-day volume in last 10 days
        last_10 = df.iloc[-11:-1]  # Exclude today
        down_days = last_10[last_10['Close'] < last_10['Open']]
        
        if len(down_days) == 0:
            return None
        
        max_down_vol = down_days['Volume'].max()
        
        # Volume must exceed max down volume
        if current_vol <= max_down_vol:
            return None
        
        # Check if above 10-day MA
        ma10 = close.iloc[-11:-1].mean()
        if current_close < ma10:
            return None
        
        buy_point = current_close
        
        return {
            'pattern': 'Pocket Pivot',
            'buy_point': buy_point,
            'volume_ratio': current_vol / max_down_vol,
            'detected_date': df.index[-1]
        }
    
    @staticmethod
    def detect_all(df):
        """
        Run all pattern detectors.
        
        Returns:
            list of detected patterns
        """
        patterns = []
        
        detectors = [
            PatternDetector.detect_cup_with_handle,
            PatternDetector.detect_flat_base,
            PatternDetector.detect_high_tight_flag,
            PatternDetector.detect_pocket_pivot
        ]
        
        for detector in detectors:
            result = detector(df)
            if result:
                patterns.append(result)
        
        return patterns


if __name__ == '__main__':
    # Test
    from data_loader import DataLoader
    
    loader = DataLoader()
    df = loader.get_data('AAPL', '2023-01-01', '2024-01-01')
    
    patterns = PatternDetector.detect_all(df)
    print(f"Found {len(patterns)} patterns:")
    for p in patterns:
        print(p)
