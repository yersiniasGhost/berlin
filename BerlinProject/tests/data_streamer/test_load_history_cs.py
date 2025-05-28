import sys
import os
import logging
import requests
import json
import traceback
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('RawSchwabData')

# Add project path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..', 'src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import auth manager
try:
    from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
except ImportError:
    logger.error("Error importing SchwabAuthManager, trying alternative path")
    try:
        from services.schwab_auth import SchwabAuthManager
    except ImportError:
        logger.error("Failed to import SchwabAuthManager")
        sys.exit(1)


def get_raw_schwab_data(symbol, timeframe="1m", hours=5):
    """
    Get truly raw data directly from Schwab API with no processing.

    Args:
        symbol: Stock symbol
        timeframe: Timeframe string (1m, 5m, etc.)
        hours: Hours of history to fetch

    Returns:
        Raw JSON response from Schwab
    """
    # Get authentication
    auth_manager = SchwabAuthManager()
    if not auth_manager.is_authenticated():
        logger.error("Not authenticated!")
        return None

    access_token = auth_manager.access_token

    # Calculate time range
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    start_timestamp = int(start_time.timestamp() * 1000)
    end_timestamp = int(end_time.timestamp() * 1000)

    # Map timeframe to API parameters
    frequency_type = "minute"
    frequency = 1

    if timeframe == "5m":
        frequency = 5
    elif timeframe == "15m":
        frequency = 15
    elif timeframe == "30m":
        frequency = 30
    elif timeframe == "1h":
        frequency_type = "hour"
        frequency = 1

    # API parameters
    url = "https://api.schwabapi.com/marketdata/v1/pricehistory"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        'symbol': symbol,
        'periodType': 'day',
        'period': 1,
        'frequencyType': frequency_type,
        'frequency': frequency,
        'startDate': start_timestamp,
        'endDate': end_timestamp,
        'needExtendedHoursData': True
    }

    logger.info(f"Getting raw data for {symbol} {timeframe}")

    try:
        # Make API request
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return None

        # Just return the raw data
        return response.json()

    except Exception as e:
        logger.error(f"Error getting raw data: {e}")
        traceback.print_exc()
        return None


def test_raw_data():
    """Get completely raw data from Schwab API"""

    # Define symbols and timeframes to test
    symbols = ["NVDA"]
    timeframes = ["1m", "5m"]

    # Create result folder
    result_folder = "completely_raw_data"
    os.makedirs(result_folder, exist_ok=True)

    # Test each combination
    for symbol in symbols:
        for timeframe in timeframes:
            logger.info(f"Testing {symbol} {timeframe}...")

            try:
                # Get raw data
                raw_data = get_raw_schwab_data(symbol, timeframe)

                if raw_data:
                    # Save truly raw JSON as-is
                    filepath = os.path.join(result_folder, f"{symbol}_{timeframe}_raw.json")
                    with open(filepath, 'w') as f:
                        json.dump(raw_data, f, indent=2)

                    logger.info(f"Saved raw data to {filepath}")

                    # Extract just the candles part to a separate file
                    if 'candles' in raw_data:
                        candles = raw_data['candles']
                        candles_filepath = os.path.join(result_folder, f"{symbol}_{timeframe}_candles.json")
                        with open(candles_filepath, 'w') as f:
                            json.dump(candles, f, indent=2)

                        logger.info(f"Extracted {len(candles)} candles to {candles_filepath}")

                        # Show sample
                        if candles:
                            logger.info(f"First candle: {candles[0]}")
                            logger.info(f"Last candle: {candles[-1]}")
                    else:
                        logger.warning("No 'candles' key in response!")
                else:
                    logger.warning(f"No data returned for {symbol} {timeframe}")

            except Exception as e:
                logger.error(f"Error processing {symbol} {timeframe}: {e}")
                traceback.print_exc()


if __name__ == "__main__":
    test_raw_data()