"""Trading Bot Configuration"""
import os
from pathlib import Path

# Load from .env.alpaca
env_file = Path(__file__).parent.parent / ".env.alpaca"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip()

# Alpaca API
ALPACA_BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
ALPACA_KEY = os.getenv("APCA_API_KEY_ID")
ALPACA_SECRET = os.getenv("APCA_API_SECRET_KEY")

# Strategies
STRATEGIES = {
    "VCP": "Volatility Contraction Pattern",
    "CUP": "Cup and Handle",
    "M200": "Munger 200-day"
}

# Risk Management
DEFAULT_POSITION_SIZE = 5000  # $5K per trade
MAX_POSITION_PCT = 0.10       # 10% of portfolio max per position
DEFAULT_STOP_LOSS_PCT = 0.07  # 7% stop loss
DEFAULT_TARGET_PCT = 0.20     # 20% profit target

# Paths
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
TRADES_FILE = DATA_DIR / "trades.json"
