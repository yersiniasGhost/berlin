import time
import logging
from src.schwab_api.authentication import SchwabClient
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('StreamingTest')


def handle_quote_data(data: List[Dict[str, Any]]):
    """Handle incoming quote data"""
    for quote in data:
        symbol = quote.get('key', 'UNKNOWN')
        bid = quote.get('1', 0.0)
        ask = quote.get('2', 0.0)
        last = quote.get('3', 0.0)
        volume = quote.get('8', 0)

        logger.info(f"QUOTE: {symbol} - Bid: {bid}, Ask: {ask}, Last: {last}, Volume: {volume}")


def handle_chart_data(data: List[Dict[str, Any]]):
    """Handle incoming chart data"""
    for candle in data:
        symbol = candle.get('key', 'UNKNOWN')
        open_price = candle.get('1', 0.0)
        high = candle.get('2', 0.0)
        low = candle.get('3', 0.0)
        close = candle.get('4', 0.0)
        volume = candle.get('5', 0)

        logger.info(f"CANDLE: {symbol} - OHLC: {open_price}/{high}/{low}/{close}, Volume: {volume}")


def main():
    # Create Schwab client - no config file needed now
    client = SchwabClient()

    # Authenticate
    if not client.authenticate():
        logger.error("Authentication failed")
        return
    logger.info("Authentication successful!")

    # Get user preferences
    user_prefs = client.get_user_preferences()
    if not user_prefs:
        logger.warning("Failed to get user preferences, using defaults")
    else:
        logger.info("Successfully fetched user preferences")

    # Connect to streaming API
    if not client.connect_stream():
        logger.error("Failed to connect to streaming API")
        return
    logger.info("Successfully connected to streaming API")

    # Wait a moment for connection to stabilize
    time.sleep(2)

    # Subscribe to quotes for specific symbols
    symbols = ['NVDA', 'PLTR']  # Replace with your desired symbols
    client.subscribe_quotes(symbols, handle_quote_data)

    # Subscribe to chart data
    client.subscribe_charts(symbols, handle_chart_data)

    # Keep the script running to receive data
    logger.info("\nReceiving data (press Ctrl+C to exit)...\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()