#!/usr/bin/env python3
"""
CV-Based Chart Pattern Detector v1.0
Uses Computer Vision + Mathematical Analysis to detect chart patterns

Patterns Detected:
- Cup & Handle
- VCP (Volatility Contraction Pattern)
- Head & Shoulders (and Inverse)
- Double Top / Double Bottom
- Ascending / Descending / Symmetric Triangles
- Bull/Bear Flags
- Wyckoff Accumulation / Distribution

Author: Rara (built by Clawdbot)
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import json
import os
import warnings
warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════════════════════
# CORE UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_data(ticker, period="1y"):
    """Fetch OHLCV data for a ticker"""
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval="1d")
    if hasattr(df.columns, 'levels'):
        df.columns = df.columns.get_level_values(0)
    return df

def normalize(arr):
    """Normalize array to 0-1 range"""
    arr = np.array(arr)
    min_val, max_val = arr.min(), arr.max()
    if max_val - min_val == 0:
        return np.zeros_like(arr)
    return (arr - min_val) / (max_val - min_val)

def smooth(arr, window=5):
    """Apply simple moving average smoothing"""
    return np.convolve(arr, np.ones(window)/window, mode='valid')

def find_local_extrema(data, order=5):
    """Find local maxima and minima"""
    maxima = []
    minima = []
    
    for i in range(order, len(data) - order):
        window = data[i-order:i+order+1]
        if data[i] == max(window):
            maxima.append(i)
        if data[i] == min(window):
            minima.append(i)
    
    return maxima, minima

def pearson_correlation(x, y):
    """Calculate Pearson correlation coefficient"""
    x, y = np.array(x), np.array(y)
    if len(x) != len(y):
        return 0
    mean_x, mean_y = np.mean(x), np.mean(y)
    num = np.sum((x - mean_x) * (y - mean_y))
    den = np.sqrt(np.sum((x - mean_x)**2) * np.sum((y - mean_y)**2))
    return num / den if den != 0 else 0

def resample(arr, n):
    """Resample array to n points"""
    x_orig = np.linspace(0, 1, len(arr))
    x_new = np.linspace(0, 1, n)
    return np.interp(x_new, x_orig, arr)


# ═══════════════════════════════════════════════════════════════════════════════
# PATTERN TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

PATTERN_TEMPLATES = {
    # Cup & Handle: U-shape with small handle pullback
    'cup_and_handle': {
        'template': [1.0, 0.7, 0.4, 0.2, 0.1, 0.1, 0.2, 0.4, 0.7, 0.9, 0.85, 0.8, 0.85, 0.95, 1.0, 1.05],
        'min_correlation': 0.70,
        'description': 'U-shaped base with handle pullback before breakout',
        'bias': 'bullish'
    },
    
    # Inverse Cup & Handle (bearish)
    'inverse_cup_handle': {
        'template': [0.0, 0.3, 0.6, 0.8, 0.9, 0.9, 0.8, 0.6, 0.3, 0.1, 0.15, 0.2, 0.15, 0.05, 0.0, -0.05],
        'min_correlation': 0.70,
        'description': 'Inverted U-shape, bearish continuation',
        'bias': 'bearish'
    },
    
    # VCP Tight: Multiple contractions getting tighter
    'vcp_tight': {
        'template': [1.0, 0.5, 0.8, 0.55, 0.75, 0.6, 0.72, 0.65, 0.7, 0.67, 0.69, 0.68, 0.7, 0.75, 0.85, 1.0],
        'min_correlation': 0.60,
        'description': 'Volatility contraction with tightening range',
        'bias': 'bullish'
    },
    
    # VCP Loose: Wider contractions
    'vcp_loose': {
        'template': [1.0, 0.4, 0.9, 0.35, 0.85, 0.45, 0.8, 0.5, 0.75, 0.55, 0.7, 0.6, 0.72, 0.65, 0.8, 1.0],
        'min_correlation': 0.55,
        'description': 'Volatility contraction with looser swings',
        'bias': 'bullish'
    },
    
    # Head & Shoulders (bearish reversal)
    'head_and_shoulders': {
        'template': [0.3, 0.5, 0.7, 0.5, 0.4, 0.6, 1.0, 0.6, 0.4, 0.5, 0.7, 0.5, 0.3, 0.2, 0.1, 0.0],
        'min_correlation': 0.65,
        'description': 'Three peaks with middle highest - bearish reversal',
        'bias': 'bearish'
    },
    
    # Inverse Head & Shoulders (bullish reversal)
    'inverse_head_shoulders': {
        'template': [0.7, 0.5, 0.3, 0.5, 0.6, 0.4, 0.0, 0.4, 0.6, 0.5, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0],
        'min_correlation': 0.65,
        'description': 'Three troughs with middle lowest - bullish reversal',
        'bias': 'bullish'
    },
    
    # Double Top (bearish)
    'double_top': {
        'template': [0.0, 0.3, 0.6, 0.9, 1.0, 0.8, 0.5, 0.4, 0.5, 0.8, 1.0, 0.9, 0.6, 0.3, 0.1, 0.0],
        'min_correlation': 0.70,
        'description': 'Two peaks at similar level - bearish reversal',
        'bias': 'bearish'
    },
    
    # Double Bottom (bullish)
    'double_bottom': {
        'template': [1.0, 0.7, 0.4, 0.1, 0.0, 0.2, 0.5, 0.6, 0.5, 0.2, 0.0, 0.1, 0.4, 0.7, 0.9, 1.0],
        'min_correlation': 0.70,
        'description': 'Two troughs at similar level - bullish reversal',
        'bias': 'bullish'
    },
    
    # Ascending Triangle (bullish)
    'ascending_triangle': {
        'template': [0.0, 0.3, 0.6, 0.5, 0.7, 0.6, 0.75, 0.65, 0.8, 0.7, 0.85, 0.75, 0.9, 0.85, 0.95, 1.0],
        'min_correlation': 0.60,
        'description': 'Flat resistance with higher lows - bullish',
        'bias': 'bullish'
    },
    
    # Descending Triangle (bearish)
    'descending_triangle': {
        'template': [1.0, 0.7, 0.4, 0.5, 0.3, 0.4, 0.25, 0.35, 0.2, 0.3, 0.15, 0.25, 0.1, 0.15, 0.05, 0.0],
        'min_correlation': 0.60,
        'description': 'Flat support with lower highs - bearish',
        'bias': 'bearish'
    },
    
    # Symmetric Triangle (neutral, breakout direction matters)
    'symmetric_triangle': {
        'template': [0.0, 0.8, 0.2, 0.7, 0.25, 0.65, 0.3, 0.6, 0.35, 0.55, 0.4, 0.5, 0.45, 0.48, 0.47, 0.5],
        'min_correlation': 0.55,
        'description': 'Converging trendlines - breakout pending',
        'bias': 'neutral'
    },
    
    # Bull Flag
    'bull_flag': {
        'template': [0.0, 0.3, 0.5, 0.7, 0.9, 1.0, 0.95, 0.9, 0.85, 0.8, 0.82, 0.78, 0.8, 0.85, 0.9, 1.0],
        'min_correlation': 0.65,
        'description': 'Sharp rally followed by downward channel - bullish continuation',
        'bias': 'bullish'
    },
    
    # Bear Flag
    'bear_flag': {
        'template': [1.0, 0.7, 0.5, 0.3, 0.1, 0.0, 0.05, 0.1, 0.15, 0.2, 0.18, 0.22, 0.2, 0.15, 0.1, 0.0],
        'min_correlation': 0.65,
        'description': 'Sharp decline followed by upward channel - bearish continuation',
        'bias': 'bearish'
    },
    
    # Wyckoff Accumulation
    'wyckoff_accumulation': {
        'template': [1.0, 0.5, 0.6, 0.3, 0.4, 0.2, 0.35, 0.5, 0.45, 0.6, 0.55, 0.7, 0.75, 0.85, 0.9, 1.0],
        'min_correlation': 0.60,
        'description': 'Wyckoff accumulation - smart money buying',
        'bias': 'bullish'
    },
    
    # Wyckoff Distribution
    'wyckoff_distribution': {
        'template': [0.0, 0.5, 0.4, 0.7, 0.6, 0.8, 0.65, 0.5, 0.55, 0.4, 0.45, 0.3, 0.25, 0.15, 0.1, 0.0],
        'min_correlation': 0.60,
        'description': 'Wyckoff distribution - smart money selling',
        'bias': 'bearish'
    },
    
    # Flat Base
    'flat_base': {
        'template': [0.5, 0.52, 0.48, 0.51, 0.49, 0.5, 0.52, 0.48, 0.5, 0.51, 0.49, 0.5, 0.52, 0.55, 0.6, 0.7],
        'min_correlation': 0.50,
        'description': 'Tight consolidation near highs - bullish',
        'bias': 'bullish'
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# CV PATTERN DETECTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class CVPatternDetector:
    """Computer Vision Pattern Detector for Stock Charts"""
    
    def __init__(self, ticker, period="1y"):
        self.ticker = ticker
        self.period = period
        self.df = None
        self.closes = None
        self.highs = None
        self.lows = None
        self.volumes = None
        self.results = {}
        
    def load_data(self):
        """Load and prepare price data"""
        self.df = fetch_data(self.ticker, self.period)
        self.closes = self.df['Close'].values
        self.highs = self.df['High'].values
        self.lows = self.df['Low'].values
        self.volumes = self.df['Volume'].values
        self.dates = self.df.index
        return len(self.closes)
    
    def detect_pivots(self, order=10):
        """Detect swing highs and lows"""
        self.pivot_highs, self.pivot_lows = find_local_extrema(self.closes, order)
        return len(self.pivot_highs), len(self.pivot_lows)
    
    def analyze_trendlines(self, window=60):
        """Detect support and resistance trendlines"""
        recent = self.closes[-window:]
        recent_highs_idx, recent_lows_idx = find_local_extrema(recent, order=5)
        
        trendlines = {
            'support': [],
            'resistance': []
        }
        
        # Fit line through recent lows (support)
        if len(recent_lows_idx) >= 2:
            lows_x = np.array(recent_lows_idx)
            lows_y = np.array([recent[i] for i in recent_lows_idx])
            if len(lows_x) >= 2:
                slope = (lows_y[-1] - lows_y[0]) / (lows_x[-1] - lows_x[0] + 1)
                trendlines['support'] = {
                    'slope': slope,
                    'direction': 'up' if slope > 0 else 'down',
                    'points': list(zip(lows_x.tolist(), lows_y.tolist()))
                }
        
        # Fit line through recent highs (resistance)
        if len(recent_highs_idx) >= 2:
            highs_x = np.array(recent_highs_idx)
            highs_y = np.array([recent[i] for i in recent_highs_idx])
            if len(highs_x) >= 2:
                slope = (highs_y[-1] - highs_y[0]) / (highs_x[-1] - highs_x[0] + 1)
                trendlines['resistance'] = {
                    'slope': slope,
                    'direction': 'up' if slope > 0 else 'down',
                    'points': list(zip(highs_x.tolist(), highs_y.tolist()))
                }
        
        self.trendlines = trendlines
        return trendlines
    
    def measure_volatility_contraction(self, window=60):
        """Measure if volatility is contracting (VCP detection)"""
        recent = self.closes[-window:]
        
        # Split into thirds
        third = len(recent) // 3
        
        range1 = (recent[:third].max() - recent[:third].min()) / recent[:third].mean() * 100
        range2 = (recent[third:2*third].max() - recent[third:2*third].min()) / recent[third:2*third].mean() * 100
        range3 = (recent[2*third:].max() - recent[2*third:].min()) / recent[2*third:].mean() * 100
        
        contracting = range1 > range2 > range3
        contraction_ratio = range3 / range1 if range1 > 0 else 1
        
        return {
            'contracting': contracting,
            'ranges': [range1, range2, range3],
            'contraction_ratio': contraction_ratio,
            'vcp_quality': 'tight' if contraction_ratio < 0.4 else 'loose' if contraction_ratio < 0.7 else 'none'
        }
    
    def detect_cup_shape(self, window=120):
        """Detect cup formation using shape analysis"""
        if len(self.closes) < window:
            return {'detected': False}
        
        recent = self.closes[-window:]
        normalized = normalize(recent)
        
        # Find potential cup structure
        min_idx = np.argmin(normalized)
        left_rim_idx = np.argmax(normalized[:max(1, min_idx)])
        right_rim_idx = min_idx + np.argmax(normalized[min_idx:]) if min_idx < len(normalized) else -1
        
        if right_rim_idx <= min_idx:
            return {'detected': False}
        
        # Measure cup characteristics
        depth = normalized[left_rim_idx] - normalized[min_idx]
        left_rim = normalized[left_rim_idx]
        right_rim = normalized[right_rim_idx]
        symmetry = 1 - abs(left_rim - right_rim)
        
        # Check for handle (small pullback after right rim)
        if right_rim_idx < len(normalized) - 5:
            handle_section = normalized[right_rim_idx:]
            handle_depth = (handle_section.max() - handle_section.min())
            has_handle = handle_depth < depth * 0.5 and len(handle_section) >= 5
        else:
            has_handle = False
        
        is_cup = depth > 0.2 and symmetry > 0.7
        
        return {
            'detected': is_cup,
            'depth': depth,
            'symmetry': symmetry,
            'has_handle': has_handle,
            'left_rim_idx': left_rim_idx,
            'bottom_idx': min_idx,
            'right_rim_idx': right_rim_idx
        }
    
    def match_template(self, template, window=None):
        """Match price action against a pattern template"""
        if window is None:
            window = len(template) * 5
        
        recent = self.closes[-window:] if len(self.closes) >= window else self.closes
        normalized = normalize(recent)
        resampled = resample(normalized, len(template))
        
        template_norm = normalize(np.array(template))
        correlation = pearson_correlation(resampled, template_norm)
        
        return correlation
    
    def detect_all_patterns(self, lookback_windows=[60, 90, 120]):
        """Run all pattern detection algorithms"""
        if self.closes is None:
            self.load_data()
        
        self.detect_pivots()
        self.analyze_trendlines()
        
        results = {
            'ticker': self.ticker,
            'current_price': self.closes[-1],
            'date': self.dates[-1].strftime('%Y-%m-%d'),
            'patterns_detected': [],
            'pattern_scores': {},
            'technical_analysis': {}
        }
        
        # Template matching for each pattern
        best_match = None
        best_score = 0
        
        for pattern_name, pattern_data in PATTERN_TEMPLATES.items():
            template = pattern_data['template']
            min_corr = pattern_data['min_correlation']
            
            # Try different windows
            best_corr_for_pattern = 0
            best_window = 60
            
            for window in lookback_windows:
                corr = self.match_template(template, window)
                if corr > best_corr_for_pattern:
                    best_corr_for_pattern = corr
                    best_window = window
            
            results['pattern_scores'][pattern_name] = {
                'correlation': round(best_corr_for_pattern, 3),
                'window': best_window,
                'min_required': min_corr,
                'detected': best_corr_for_pattern >= min_corr,
                'bias': pattern_data['bias'],
                'description': pattern_data['description']
            }
            
            if best_corr_for_pattern >= min_corr:
                results['patterns_detected'].append({
                    'name': pattern_name,
                    'correlation': round(best_corr_for_pattern, 3),
                    'bias': pattern_data['bias']
                })
            
            if best_corr_for_pattern > best_score:
                best_score = best_corr_for_pattern
                best_match = pattern_name
        
        results['best_match'] = {
            'pattern': best_match,
            'correlation': round(best_score, 3),
            'bias': PATTERN_TEMPLATES[best_match]['bias'] if best_match else 'neutral'
        }
        
        # Additional technical analysis
        vol_analysis = self.measure_volatility_contraction()
        cup_analysis = self.detect_cup_shape()
        
        results['technical_analysis'] = {
            'volatility_contraction': vol_analysis,
            'cup_shape': cup_analysis,
            'trendlines': self.trendlines,
            'pivot_highs': len(self.pivot_highs),
            'pivot_lows': len(self.pivot_lows)
        }
        
        # Calculate overall bias
        bullish_patterns = [p for p in results['patterns_detected'] if p['bias'] == 'bullish']
        bearish_patterns = [p for p in results['patterns_detected'] if p['bias'] == 'bearish']
        
        if len(bullish_patterns) > len(bearish_patterns):
            overall_bias = 'BULLISH'
        elif len(bearish_patterns) > len(bullish_patterns):
            overall_bias = 'BEARISH'
        else:
            overall_bias = 'NEUTRAL'
        
        results['overall_bias'] = overall_bias
        results['confidence'] = round(best_score * 100, 1)
        
        self.results = results
        return results
    
    def get_summary(self):
        """Get human-readable summary"""
        if not self.results:
            self.detect_all_patterns()
        
        r = self.results
        
        summary = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CV PATTERN ANALYSIS: {self.ticker:<54}║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Price: ${r['current_price']:.2f}  |  Date: {r['date']}  |  Bias: {r['overall_bias']:<10}  ║
╚══════════════════════════════════════════════════════════════════════════════╝

🏆 BEST MATCH: {r['best_match']['pattern']}
   Correlation: {r['best_match']['correlation']:.3f}
   Bias: {r['best_match']['bias'].upper()}

📊 PATTERNS DETECTED ({len(r['patterns_detected'])}):
"""
        
        for p in sorted(r['patterns_detected'], key=lambda x: x['correlation'], reverse=True)[:5]:
            emoji = "🟢" if p['bias'] == 'bullish' else "🔴" if p['bias'] == 'bearish' else "⚪"
            summary += f"   {emoji} {p['name']}: {p['correlation']:.3f}\n"
        
        # Volatility analysis
        vol = r['technical_analysis']['volatility_contraction']
        summary += f"""
📉 VOLATILITY ANALYSIS:
   Contracting: {'Yes ✅' if vol['contracting'] else 'No'}
   VCP Quality: {vol['vcp_quality'].upper()}
   Ranges: {vol['ranges'][0]:.1f}% → {vol['ranges'][1]:.1f}% → {vol['ranges'][2]:.1f}%
"""
        
        # Cup shape
        cup = r['technical_analysis']['cup_shape']
        if cup['detected']:
            summary += f"""
🏆 CUP SHAPE DETECTED:
   Depth: {cup['depth']:.2f}
   Symmetry: {cup['symmetry']:.2f}
   Has Handle: {'Yes' if cup['has_handle'] else 'No'}
"""
        
        summary += f"""
═══════════════════════════════════════════════════════════════════════════════
CONFIDENCE: {r['confidence']:.1f}%
═══════════════════════════════════════════════════════════════════════════════
"""
        return summary


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

def scan_multiple(tickers, min_confidence=50):
    """Scan multiple tickers and return top patterns"""
    results = []
    
    for ticker in tickers:
        try:
            detector = CVPatternDetector(ticker)
            detector.load_data()
            result = detector.detect_all_patterns()
            
            if result['confidence'] >= min_confidence:
                results.append({
                    'ticker': ticker,
                    'best_pattern': result['best_match']['pattern'],
                    'correlation': result['best_match']['correlation'],
                    'bias': result['overall_bias'],
                    'confidence': result['confidence'],
                    'patterns_count': len(result['patterns_detected'])
                })
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
    
    # Sort by confidence
    results = sorted(results, key=lambda x: x['confidence'], reverse=True)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python cv_pattern_detector.py TICKER [TICKER2 ...]")
        print("\nExample:")
        print("  python cv_pattern_detector.py HOOD")
        print("  python cv_pattern_detector.py AAPL GOOGL MSFT")
        sys.exit(1)
    
    tickers = [t.upper() for t in sys.argv[1:]]
    
    if len(tickers) == 1:
        # Single ticker - detailed analysis
        detector = CVPatternDetector(tickers[0])
        detector.load_data()
        detector.detect_all_patterns()
        print(detector.get_summary())
        
        # Save detailed results
        output_file = f"cv_analysis_{tickers[0]}_{datetime.now().strftime('%Y%m%d')}.json"
        with open(output_file, 'w') as f:
            json.dump(detector.results, f, indent=2, default=str)
        print(f"Detailed results saved to: {output_file}")
        
    else:
        # Multiple tickers - summary table
        print(f"\nScanning {len(tickers)} tickers...")
        results = scan_multiple(tickers)
        
        print("\n" + "=" * 80)
        print("CV PATTERN SCAN RESULTS")
        print("=" * 80)
        print(f"\n{'Ticker':<8} {'Best Pattern':<25} {'Corr':<8} {'Bias':<10} {'Conf':<8}")
        print("-" * 70)
        
        for r in results:
            bias_emoji = "🟢" if r['bias'] == 'BULLISH' else "🔴" if r['bias'] == 'BEARISH' else "⚪"
            print(f"{r['ticker']:<8} {r['best_pattern']:<25} {r['correlation']:.3f}   {bias_emoji} {r['bias']:<7} {r['confidence']:.1f}%")
