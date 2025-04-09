import time
import logging
from datetime import datetime
from data_streamer.schwab_data_link import SchwabDataLink

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TestSchwabData')


def print_quote_data(quote_data):
    """Process and print quote data"""
    symbol = quote_data.get('key', 'Unknown')

    # Extract basic quote information
    bid = quote_data.get('1', 'N/A')
    ask = quote_data.get('2', 'N/A')
    last = quote_data.get('3', 'N/A')
    volume = quote_data.get('8', 'N/A')

    print(f"QUOTE - {symbol}: Last: {last}, Bid: {bid}, Ask: {ask}, Volume: {volume}")

    # Print raw data for debugging
    print(f"Raw quote data: {quote_data}")


def print_chart_data(chart_data):
    """Process and print chart data"""
    symbol = chart_data.get('key', 'Unknown')

    # Extract timestamp
    timestamp_ms = int(chart_data.get('7', 0))
    if timestamp_ms > 0:
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    else:
        timestamp = 'Unknown'

    # Extract OHLCV data
    open_price = chart_data.get('2', 'N/A')
    high_price = chart_data.get('3', 'N/A')
    low_price = chart_data.get('4', 'N/A')
    close_price = chart_data.get('5', 'N/A')
    volume = chart_data.get('6', 'N/A')

    print(f"CANDLE - {symbol} @ {timestamp}: O:{open_price} H:{high_price} L:{low_price} C:{close_price} V:{volume}")

    # Print raw data for debugging
    print(f"Raw chart data: {chart_data}")


def main(symbol='NVDA', timeframe='1m'):
    """
    Main function that can be called with parameters directly

    Args:
        symbol: Stock symbol (e.g., 'NVDA', 'AAPL')
        timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '1d')
    """
    logger.info(f"Using symbol: {symbol} with timeframe: {timeframe}")

    # Create SchwabDataLink instance with hardcoded credentials
    data_link = SchwabDataLink()

    # Authenticate
    if not data_link.authenticate():
        logger.error("Authentication failed, exiting")
        return

    # Load historical data as a test
    logger.info(f"Loading historical data for {symbol} with timeframe {timeframe}")
    historical_data = data_link.load_historical_data(symbol, timeframe)

    if historical_data:
        logger.info(f"Loaded {len(historical_data)} historical candles")
        # Print first and last candle
        if len(historical_data) > 0:
            first_candle = historical_data[0]
            last_candle = historical_data[-1]

            logger.info(
                f"First candle: {first_candle['timestamp']} - O:{first_candle['open']} C:{first_candle['close']}")
            logger.info(f"Last candle: {last_candle['timestamp']} - O:{last_candle['open']} C:{last_candle['close']}")

            # You can set a breakpoint here to inspect historical_data
            print("Set breakpoint here to inspect historical_data")
    else:
        logger.warning("No historical data loaded")

    # Connect to streaming
    logger.info("Connecting to streaming API")
    if not data_link.connect_stream():
        logger.error("Failed to connect to streaming API")
        return

    # Register handlers for streaming data
    # data_link.add_quote_handler(print_quote_data)
    data_link.add_chart_handler(print_chart_data)

    # Subscribe to quotes and charts
    logger.info(f"Subscribing to data for {symbol}")
    data_link.subscribe_quotes([symbol])
    data_link.subscribe_charts([symbol], timeframe)

    # Keep running and receiving data
    try:
        logger.info("Starting to receive streaming data (press Ctrl+C to stop)...")
        # You can add a breakpoint here to examine data as it comes in
        print("Set breakpoint here to examine streaming data")

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping...")
        data_link.disconnect()


# This allows both command-line and direct function call execution
if __name__ == "__main__":

    main(symbol='NVDA', timeframe='1m')
