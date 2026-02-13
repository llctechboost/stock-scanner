#!/usr/bin/env python3
"""
Top 200 S&P 500 Stocks by Market Cap Weight (as of 2025)
Source: Various index providers, approximately ordered by weight
"""

# Top 200 S&P 500 components by market cap weight
SP500_TOP200 = [
    # Top 10 (~35% of index)
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'GOOG', 'BRK-B', 'TSLA', 'UNH',
    
    # 11-25
    'XOM', 'JNJ', 'JPM', 'V', 'PG', 'MA', 'AVGO', 'HD', 'CVX', 'MRK',
    'LLY', 'ABBV', 'PEP', 'KO', 'COST',
    
    # 26-50
    'WMT', 'BAC', 'PFE', 'TMO', 'CSCO', 'MCD', 'CRM', 'ACN', 'ABT', 'DHR',
    'NKE', 'ORCL', 'CMCSA', 'DIS', 'ADBE', 'VZ', 'TXN', 'NEE', 'PM', 'INTC',
    'WFC', 'UPS', 'RTX', 'HON', 'COP',
    
    # 51-75
    'QCOM', 'LOW', 'INTU', 'UNP', 'SPGI', 'AMD', 'CAT', 'BA', 'GE', 'IBM',
    'BMY', 'ELV', 'AMGN', 'DE', 'SBUX', 'ISRG', 'AMAT', 'NOW', 'GS', 'LMT',
    'MS', 'BKNG', 'AXP', 'MDLZ', 'BLK',
    
    # 76-100
    'GILD', 'ADI', 'VRTX', 'SYK', 'TJX', 'PLD', 'CVS', 'ADP', 'MMC', 'REGN',
    'LRCX', 'C', 'SCHW', 'TMUS', 'MO', 'CB', 'ZTS', 'SO', 'DUK', 'CI',
    'EOG', 'BDX', 'PGR', 'CME', 'ITW',
    
    # 101-125
    'BSX', 'PYPL', 'NOC', 'SLB', 'EQIX', 'SNPS', 'AON', 'ICE', 'APD', 'CDNS',
    'FDX', 'MU', 'CL', 'HUM', 'SHW', 'FCX', 'ETN', 'KLAC', 'CSX', 'EMR',
    'ORLY', 'MCK', 'GM', 'PNC', 'ATVI',
    
    # 126-150
    'WM', 'NSC', 'MAR', 'PSX', 'GD', 'TGT', 'AZO', 'APH', 'ROP', 'MCO',
    'AIG', 'F', 'NXPI', 'ECL', 'ADM', 'OXY', 'CTAS', 'HCA', 'PCAR', 'MRNA',
    'MNST', 'NEM', 'KMB', 'SRE', 'AEP',
    
    # 151-175
    'PAYX', 'TRV', 'MCHP', 'MSCI', 'AFL', 'D', 'JCI', 'STZ', 'O', 'PH',
    'IDXX', 'MET', 'AJG', 'FTNT', 'KDP', 'PSA', 'A', 'BIIB', 'TEL', 'CMG',
    'CCI', 'DVN', 'DXCM', 'PRU', 'KHC',
    
    # 176-200
    'HES', 'CARR', 'HSY', 'WELL', 'ALL', 'MSI', 'CTSH', 'EW', 'ROST', 'YUM',
    'GEHC', 'IQV', 'GIS', 'DLR', 'VRSK', 'ODFL', 'BK', 'AME', 'HAL', 'KR',
    'SPG', 'PPG', 'FAST', 'EXC', 'XEL',
]

# Just the top 100 for faster testing
SP500_TOP100 = SP500_TOP200[:100]

# Top 50 mega caps
SP500_TOP50 = SP500_TOP200[:50]

if __name__ == '__main__':
    print(f"Top 200 S&P 500 stocks loaded")
    print(f"  Top 50: {len(SP500_TOP50)}")
    print(f"  Top 100: {len(SP500_TOP100)}")
    print(f"  Top 200: {len(SP500_TOP200)}")
