"""
Centralized ticker configuration for MLF Trading System.
Single source of truth for available trading symbols.
"""

# Primary tickers tracked in our system - comprehensive list covering major sectors
TRACKED_TICKERS = [
    # Mega-cap Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    # Other Major Tech
    "AVGO", "ORCL", "ADBE", "CRM", "AMD", "INTC", "QCOM", "TXN",
    # Finance
    "BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS",
    # Consumer/Retail
    "WMT", "HD", "PG", "KO", "PEP", "MCD", "NKE", "DIS",
    # Healthcare/Pharma
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK",
    # Hot/Trending Stocks
    "PLTR", "SOFI", "RIVN", "LCID"
]

# Default ticker for new configurations
DEFAULT_TICKER = 'NVDA'

# Intervals we track (in minutes)
TRACKED_INTERVALS = [1, 5]


def get_tracked_tickers():
    """Return list of tracked tickers."""
    return TRACKED_TICKERS.copy()


def get_default_ticker():
    """Return the default ticker symbol."""
    return DEFAULT_TICKER


def is_valid_ticker(ticker: str) -> bool:
    """Check if a ticker is in our tracked list."""
    return ticker.upper() in TRACKED_TICKERS
