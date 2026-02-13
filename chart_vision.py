#!/usr/bin/env python3
"""
Chart Vision — AI-powered pattern recognition using computer vision.
Analyzes TradingView chart screenshots with a vision model to:
1. Identify chart patterns (CANSLIM + additional)
2. Grade pattern quality (A/B/C/F)
3. Spot things the math scanner misses
4. Provide actionable trade assessment

Usage:
    python3 chart_vision.py GOOGL AMD NU     # Analyze specific tickers
    python3 chart_vision.py --all             # Analyze all 7+ score stocks
"""

import os
import sys
import json
import glob
import base64
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(SCRIPT_DIR, 'charts')
VISION_DIR = os.path.join(SCRIPT_DIR, 'vision_reports')
os.makedirs(VISION_DIR, exist_ok=True)

VISION_PROMPT = """You are an expert stock chart analyst trained in William O'Neil's CANSLIM methodology and Chris Kacher's pattern recognition. Analyze this daily stock chart and provide a detailed assessment.

IDENTIFY AND GRADE THESE PATTERNS (if present):

1. **Cup with Handle** — U-shaped base (7-65 weeks), handle pullback <12%, buy on breakout above handle high
2. **Flat Base** — Tight sideways consolidation (<15% range), 5+ weeks, buy on breakout above range high
3. **High Tight Flag** — 100%+ advance followed by <20% pullback, 3-5 week flag, extremely rare
4. **Ascending Base** — 3+ pullbacks with each low higher than previous, 10-20% depth each
5. **Pocket Pivot** — Price moves up through 10-day MA on volume > any down day volume in prior 10 days
6. **Double Bottom** — W-shaped pattern, second low at or above first
7. **Volatility Contraction Pattern (VCP)** — Progressively tighter price ranges with decreasing volume
8. **Base on Base** — New base forms on top of previous base

For each pattern found, provide:
- **Pattern Name**
- **Grade: A/B/C/F** (A = textbook perfect, B = good, C = marginal, F = failed/broken)
- **Why this grade** (specific visual evidence)

ALSO ASSESS:
- **Volume Analysis**: Is volume drying up during consolidation? (bullish). Volume expanding on breakout attempts? 
- **Moving Average Behavior**: Price relationship to 21-day and 50-day MA. Are they supportive?
- **Overall Chart Health**: Is this a leader or laggard? Strong trend or choppy?
- **Key Support/Resistance Levels**: What prices matter?
- **Risk Assessment**: Where would you set a stop? Where's the buy point visually?

PROVIDE YOUR VERDICT:
- **BUY / WATCH / AVOID** with confidence level (High/Medium/Low)
- **One sentence** summary a trader can act on

Be specific. Reference what you actually see in the chart. Don't be generic."""


def get_latest_chart(ticker):
    """Find the most recent chart screenshot for a ticker."""
    pattern = os.path.join(CHARTS_DIR, f"{ticker}_*.png")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


def analyze_chart_with_vision(image_path, ticker, scanner_data=None):
    """
    Send chart to vision model for analysis.
    Uses base64 encoding for the image.
    """
    import subprocess
    
    # Read image and encode
    with open(image_path, 'rb') as f:
        img_data = base64.b64encode(f.read()).decode('utf-8')
    
    # Build context from scanner data
    context = ""
    if scanner_data:
        context = f"\n\nMATH SCANNER SAYS:\n"
        context += f"- Score: {scanner_data.get('score', '?')}/12\n"
        context += f"- Patterns detected: {', '.join(scanner_data.get('patterns', ['none']))}\n"
        context += f"- RS Rating: {scanner_data.get('rs_rating', '?')}\n"
        context += f"- Price: ${scanner_data.get('price', '?')}\n"
        if scanner_data.get('buy_point'):
            context += f"- Buy Point: ${scanner_data['buy_point']}\n"
        if scanner_data.get('earnings_warning'):
            context += f"- ⚠️ EARNINGS in {scanner_data.get('earnings_days', '?')} days\n"
        context += f"\nDo you AGREE or DISAGREE with the math scanner? What does it miss?\n"
    
    full_prompt = f"Analyzing {ticker} daily chart.\n{VISION_PROMPT}{context}"
    
    return full_prompt, f"data:image/png;base64,{img_data}"


def load_scanner_data():
    """Load scanner results."""
    import re
    stocks = {}
    txt_files = sorted(glob.glob(os.path.join(SCRIPT_DIR, 'scan_results_*.txt')), reverse=True)
    if not txt_files:
        return stocks
    
    with open(txt_files[0], 'r') as f:
        text = f.read()
    
    current = None
    for line in text.split('\n'):
        ls = line.strip()
        m = re.match(r'^([A-Z]{1,5})\s*-\s*Score:\s*(\d+)/12\s*-\s*\$([\d,.]+)', ls)
        if m:
            t = m.group(1)
            if t not in stocks:
                current = {
                    'ticker': t, 'score': int(m.group(2)),
                    'price': float(m.group(3).replace(',', '')),
                    'patterns': [], 'buy_point': None, 'rs_rating': None,
                    'earnings_warning': False, 'earnings_days': None,
                }
                stocks[t] = current
            continue
        
        if current and '✓' in ls:
            for p in ['Flat Base', 'Cup with Handle', 'High Tight Flag', 'Ascending Base', 'Pocket Pivot']:
                if p in ls:
                    current['patterns'].append(p)
            if 'EARNINGS' in ls.upper():
                current['earnings_warning'] = True
                import re as r2
                dm = r2.search(r'EARNINGS IN (\d+) DAYS', ls)
                if dm: current['earnings_days'] = int(dm.group(1))
        
        if current and '→ Buy point:' in ls:
            import re as r2
            bm = r2.search(r'\$([\d,.]+)', ls)
            if bm: current['buy_point'] = float(bm.group(1).replace(',', ''))
        
        if current and ls.startswith('RS Rating:'):
            import re as r2
            rm = r2.search(r'(\d+)', ls)
            if rm: current['rs_rating'] = int(rm.group(1))
    
    return stocks


def main():
    print(f"\n{'='*60}")
    print(f"  🧠 CHART VISION — AI Pattern Recognition")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")
    
    # Parse args
    tickers = []
    analyze_all = False
    for arg in sys.argv[1:]:
        if arg == '--all':
            analyze_all = True
        elif arg.isupper() and len(arg) <= 5:
            tickers.append(arg)
    
    scanner_data = load_scanner_data()
    
    if analyze_all:
        tickers = [t for t, d in scanner_data.items() if d['score'] >= 7]
        tickers.sort(key=lambda t: scanner_data[t]['score'], reverse=True)
    
    if not tickers:
        print("  Usage: python3 chart_vision.py GOOGL AMD NU")
        print("         python3 chart_vision.py --all\n")
        return
    
    print(f"  Analyzing {len(tickers)} charts: {', '.join(tickers)}\n")
    
    results = []
    
    for ticker in tickers:
        chart_path = get_latest_chart(ticker)
        if not chart_path:
            print(f"  ✗ No chart found for {ticker}. Run chart_intel.py first.\n")
            continue
        
        print(f"  🔍 {ticker}...")
        sdata = scanner_data.get(ticker)
        prompt, image_data = analyze_chart_with_vision(chart_path, ticker, sdata)
        
        # Save prompt + image reference for external analysis
        report = {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat(),
            'chart_path': chart_path,
            'scanner_data': sdata,
            'prompt': prompt,
            'image_b64_length': len(image_data),
            'analysis': None,  # Will be filled by vision model
        }
        
        # Try to use the image analysis tool if available
        # This outputs the prompt and image path for the calling agent to use
        print(f"     Chart: {chart_path}")
        print(f"     Scanner: {', '.join(sdata['patterns']) if sdata else 'no data'}")
        print(f"     Ready for vision analysis\n")
        
        results.append(report)
    
    # Save reports
    report_path = os.path.join(VISION_DIR, f'vision_queue_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"  Reports queued: {report_path}")
    print(f"  Run vision analysis on {len(results)} charts\n")
    
    return results


if __name__ == '__main__':
    main()
