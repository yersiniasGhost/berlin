import sys
import os
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AggregatorTest')

# Add project path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..', 'src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import required classes
try:
    from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
    from data_streamer.schwab_data_link import SchwabDataLink
    from data_streamer.candle_aggregator import CandleAggregator
except ImportError:
    try:
        from services.schwab_auth import SchwabAuthManager
        from data_streamer.schwab_data_link import SchwabDataLink
        from data_streamer.candle_aggregator import CandleAggregator
    except ImportError:
        logger.error("Failed to import required classes")
        sys.exit(1)


def authenticate():
    """Authenticate with Charles Schwab"""
    auth_manager = SchwabAuthManager()

    # Force authentication
    logger.info("=== AUTHENTICATION REQUIRED ===")
    logger.info("Please log in to Charles Schwab to continue...")
    success = auth_manager.authenticate()

    if not success:
        logger.error("Authentication failed! Cannot proceed.")
        return None

    logger.info("Authentication successful!")
    return auth_manager


def test_single_aggregator(auth_manager):
    """Test a single CandleAggregator with one symbol and one timeframe"""
    if not auth_manager:
        logger.error("No authentication, cannot proceed")
        return

    # Create data link and properly initialize it
    data_link = SchwabDataLink()
    data_link.access_token = auth_manager.access_token
    data_link.refresh_token = auth_manager.refresh_token
    data_link.user_prefs = auth_manager.user_prefs  # Add this line

    # Get streamer info if needed
    if not data_link.user_prefs:
        data_link._get_streamer_info()

    symbol = "AAPL"
    timeframe = "1m"

    logger.info(f"Testing CandleAggregator for {symbol} {timeframe}")

    # Create aggregator
    aggregator = CandleAggregator(symbol, timeframe)

    # Initial state
    logger.info("Initial state:")
    logger.info(f"  Symbol: {aggregator.symbol}")
    logger.info(f"  Timeframe: {aggregator.timeframe}")
    logger.info(f"  Current candle: None")
    logger.info(f"  History: 0 candles")

    # Prepopulate with historical data
    logger.info("\nPrepopulating with historical data...")
    num_candles = aggregator.prepopulate_data(data_link)

    # After prepopulation
    logger.info(f"Loaded {num_candles} historical candles")
    current = aggregator.get_current_candle()
    history = aggregator.get_history()

    logger.info(f"After prepopulation:")
    logger.info(f"  Current candle: {current.timestamp if current else None}")
    if current:
        logger.info(f"    OHLC: {current.open:.2f}/{current.high:.2f}/{current.low:.2f}/{current.close:.2f}")

    logger.info(f"  History: {len(history)} candles")
    if history:
        logger.info(f"    First candle: {history[0].timestamp}")
        logger.info(
            f"      OHLC: {history[0].open:.2f}/{history[0].high:.2f}/{history[0].low:.2f}/{history[0].close:.2f}")

        if len(history) > 1:
            logger.info(f"    Last candle: {history[-1].timestamp}")
            logger.info(
                f"      OHLC: {history[-1].open:.2f}/{history[-1].high:.2f}/{history[-1].low:.2f}/{history[-1].close:.2f}")

    # Subscribe to real-time data
    logger.info("\nSubscribing to real-time data and waiting for new candles...")

    # Connect to the WebSocket
    if hasattr(data_link, 'connect_stream') and callable(data_link.connect_stream):
        data_link.connect_stream()
        logger.info("Connected to streaming API")
    else:
        logger.warning("Data link doesn't have connect_stream method")

    # Subscribe to charts
    if hasattr(data_link, 'subscribe_charts') and callable(data_link.subscribe_charts):
        data_link.subscribe_charts([symbol])
        logger.info(f"Subscribed to {symbol} charts")
    else:
        logger.warning("Data link doesn't have subscribe_charts method")

    # Register chart handler
    def handle_chart_data(chart_data):
        # Only process if this is for our symbol
        if chart_data.get('key') == symbol:
            # Process through aggregator
            completed_candle = aggregator.process_pip(chart_data)

            # If a candle was completed, log it
            if completed_candle:
                logger.info(f"New candle completed at {completed_candle.timestamp}")
                logger.info(
                    f"  OHLC: {completed_candle.open:.2f}/{completed_candle.high:.2f}/{completed_candle.low:.2f}/{completed_candle.close:.2f}")
                logger.info(f"  History size: {len(aggregator.get_history())} candles")

    # Register the handler
    if hasattr(data_link, 'add_chart_handler') and callable(data_link.add_chart_handler):
        data_link.add_chart_handler(handle_chart_data)
        logger.info("Registered chart handler")
    else:
        logger.warning("Data link doesn't have add_chart_handler method")

    # Wait for real-time data
    import time
    try:
        logger.info("Waiting for real-time data... Press Ctrl+C to stop")

        # Initial history size
        initial_history_size = len(aggregator.get_history())

        # Wait until we get at least 2 new candles or 10 minutes passes
        start_time = time.time()
        max_wait_time = 600  # 10 minutes
        candles_needed = 2

        while time.time() - start_time < max_wait_time:
            # Current history size
            current_history_size = len(aggregator.get_history())
            new_candles = current_history_size - initial_history_size

            # Log status every minute
            if int(time.time() - start_time) % 60 == 0:
                logger.info(f"Waiting... Current history: {current_history_size} candles, New candles: {new_candles}")

            # Break if we got enough new candles
            if new_candles >= candles_needed:
                logger.info(f"Got {new_candles} new candles, continuing...")
                break

            # Sleep a bit to prevent busy waiting
            time.sleep(1)

        # Get final state
        final_history = aggregator.get_history()
        final_current = aggregator.get_current_candle()

        # Show final state
        logger.info("\nFinal state after real-time data:")
        logger.info(f"  History size: {len(final_history)} candles")
        logger.info(f"  New candles: {len(final_history) - initial_history_size}")

        if final_current:
            logger.info(f"  Current candle: {final_current.timestamp}")
            logger.info(
                f"    OHLC: {final_current.open:.2f}/{final_current.high:.2f}/{final_current.low:.2f}/{final_current.close:.2f}")

        # Show most recent historical candles
        logger.info("\nMost recent historical candles:")
        for i, candle in enumerate(final_history[-min(3, len(final_history)):]):
            logger.info(f"  {i + 1}: {candle.timestamp}")
            logger.info(f"    OHLC: {candle.open:.2f}/{candle.high:.2f}/{candle.low:.2f}/{candle.close:.2f}")

    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        # Disconnect
        if hasattr(data_link, 'disconnect') and callable(data_link.disconnect):
            data_link.disconnect()
            logger.info("Disconnected from streaming API")

    logger.info("\nTest completed successfully!")


def test_multiple_aggregators(auth_manager):
    """Test multiple aggregators for different symbol/timeframe combinations"""
    if not auth_manager:
        logger.error("No authentication, cannot proceed")
        return

    # Create data link
    data_link = SchwabDataLink()
    data_link.access_token = auth_manager.access_token

    # Define test combinations
    combinations = [
        {"symbol": "AAPL", "timeframe": "1m"},
        {"symbol": "AAPL", "timeframe": "5m"},
        {"symbol": "MSFT", "timeframe": "1m"}
    ]

    logger.info("Testing multiple CandleAggregators with different symbol/timeframe combinations")

    # Create aggregators
    aggregators = {}
    for combo in combinations:
        symbol = combo["symbol"]
        timeframe = combo["timeframe"]
        key = f"{symbol}_{timeframe}"

        logger.info(f"\nCreating aggregator for {symbol} {timeframe}")
        aggregator = CandleAggregator(symbol, timeframe)
        aggregators[key] = aggregator

        # Prepopulate
        num_candles = aggregator.prepopulate_data(data_link)
        logger.info(f"  Loaded {num_candles} historical candles")

        # Check current state
        current = aggregator.get_current_candle()
        logger.info(f"  Current candle: {current.timestamp if current else None}")
        logger.info(f"  History size: {len(aggregator.get_history())} candles")

    # Final state
    logger.info("\nFinal state of all aggregators:")
    for key, aggregator in aggregators.items():
        current = aggregator.get_current_candle()
        history = aggregator.get_history()

        logger.info(f"\n{aggregator.symbol} {aggregator.timeframe}:")
        logger.info(f"  Current candle: {current.timestamp if current else None}")
        logger.info(f"  History size: {len(history)} candles")
        logger.info(
            f"  Latest candle: {aggregator.get_latest_candle().timestamp if aggregator.get_latest_candle() else None}")

    logger.info("\nMultiple aggregators test completed successfully!")


if __name__ == "__main__":
    logger.info("=== STARTING CANDLE AGGREGATOR TESTS ===")

    # Authenticate first
    auth_manager = authenticate()
    if not auth_manager:
        sys.exit(1)

    logger.info("\n=== TESTING SINGLE AGGREGATOR ===")
    test_single_aggregator(auth_manager)

    # logger.info("\n\n=== TESTING MULTIPLE AGGREGATORS ===")
    # test_multiple_aggregators(auth_manager)