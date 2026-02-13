#!/usr/bin/env python3
"""
Options Flow Scraper
- Scrapes Barchart unusual options activity
- Scores based on: Vol/OI ratio, sentiment, premium size
- Max 30 points
"""

import requests
from bs4 import BeautifulSoup
import re
import time

def get_options_activity(ticker):
    """
    Scrape Barchart for unusual options activity
    Returns score (0-30) and details
    """
    try:
        url = f"https://www.barchart.com/stocks/quotes/{ticker}/options"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code != 200:
            return 0, {"error": f"HTTP {r.status_code}"}
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Look for options data
        # This is a simplified scraper - Barchart requires more sophisticated parsing
        # For now, return placeholder
        
        score = 0
        details = {
            "source": "barchart",
            "status": "scraped",
            "note": "Manual verification recommended"
        }
        
        # Check for unusual activity indicators in the page
        text = soup.get_text().lower()
        
        # Look for bullish signals
        bullish_signals = ['bullish', 'call sweep', 'unusual call', 'high volume call']
        bearish_signals = ['bearish', 'put sweep', 'unusual put', 'high volume put']
        
        bullish_count = sum(1 for signal in bullish_signals if signal in text)
        bearish_count = sum(1 for signal in bearish_signals if signal in text)
        
        if bullish_count > bearish_count:
            score += 10
            details['sentiment'] = 'bullish'
        elif bearish_count > bullish_count:
            details['sentiment'] = 'bearish'
        else:
            details['sentiment'] = 'neutral'
        
        return score, details
        
    except Exception as e:
        return 0, {"error": str(e)}


def search_unusual_options_x(ticker):
    """
    Search X (Twitter) for unusual options activity mentions
    Note: This is a placeholder - would need X API access
    """
    # Placeholder for X search
    # Search terms: "$TICKER unusual options" or "$TICKER sweep"
    return {
        "search_term": f"${ticker} unusual options OR ${ticker} sweep",
        "url": f"https://x.com/search?q=%24{ticker}%20unusual%20options&f=live",
        "note": "Manual search required"
    }


def score_options_activity(vol_oi_ratio=None, sentiment=None, premium_size=None):
    """
    Score options activity based on criteria
    - Sweeps / block trades: 12 pts
    - Unusual volume (Vol/OI > 3x): 10 pts  
    - Bullish sentiment: 8 pts
    Total: 30 pts max
    """
    score = 0
    
    # Volume/OI ratio
    if vol_oi_ratio:
        if vol_oi_ratio >= 3:
            score += 10
        elif vol_oi_ratio >= 2:
            score += 7
        elif vol_oi_ratio >= 1.5:
            score += 4
    
    # Sentiment
    if sentiment == 'bullish':
        score += 8
    elif sentiment == 'neutral':
        score += 4
    
    # Premium size (would need actual data)
    if premium_size:
        if premium_size >= 1000000:  # $1M+
            score += 12
        elif premium_size >= 500000:  # $500K+
            score += 8
        elif premium_size >= 100000:  # $100K+
            score += 4
    
    return min(score, 30)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()
        print(f"Checking options activity for {ticker}...")
        
        score, details = get_options_activity(ticker)
        print(f"Score: {score}/30")
        print(f"Details: {details}")
        
        x_search = search_unusual_options_x(ticker)
        print(f"\nX Search: {x_search['url']}")
    else:
        print("Usage: python options_flow.py TICKER")
