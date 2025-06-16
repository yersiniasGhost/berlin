import sys
import os
import logging
from typing import List

# Simple logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PrepopulationTest')

# Add project path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..', '..', 'src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import required classes
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.candle_aggregator import CandleAggregator
from models.tick_data import TickData


def test_prepopulation():
    """Simple test for CandleAggregator prepopulation with NVDA 1m"""
    # Step 1: Authenticate with Charles Schwab
    logger.info("=== SCHWAB AUTHENTICATION REQUIRED ===")
    auth_manager = SchwabAuthManager()

    # Force authentication
    logger.info("Please log in to Charles Schwab and paste the full URL back here")
    success = auth_manager.authenticate()

    if not success:
        logger.error("Authentication failed! Cannot proceed.")
        return

    logger.info("Authentication successful!")

    # Step 2: Setup DataLink
    data_link = SchwabDataLink()
    data_link.access_token = auth_manager.access_token
    data_link.refresh_token = auth_manager.refresh_token
    data_link.user_prefs = auth_manager.user_prefs

    # Step 3: Create CandleAggregator for NVDA 1m
    symbol = "NVDA"
    timeframe = "30m"

    logger.info(f"Created CandleAggregator for {symbol} {timeframe}")
    aggregator = CandleAggregator(symbol, timeframe)

    # Step 4: Prepopulate with historical data
    logger.info("Prepopulating with historical data...")
    num_candles = aggregator.prepopulate_data(data_link)
    logger.info(f"Loaded {num_candles} historical candles")

    # Step 5: Analyze the prepopulated data
    history: List[TickData] = aggregator.get_history()
    current: TickData = aggregator.get_current_candle()

    logger.info(f"History contains {len(history)} completed candles")

    if history:
        # Print first candle
        first_candle = history[0]
        logger.info(f"First historical candle: {first_candle.timestamp}")
        logger.info(
            f"  OHLC: {first_candle.open:.2f}/{first_candle.high:.2f}/{first_candle.low:.2f}/{first_candle.close:.2f}")
        logger.info(f"  Volume: {first_candle.volume}")

        # Print last candle
        last_candle = history[-1]
        logger.info(f"Last historical candle: {last_candle.timestamp}")
        logger.info(
            f"  OHLC: {last_candle.open:.2f}/{last_candle.high:.2f}/{last_candle.low:.2f}/{last_candle.close:.2f}")
        logger.info(f"  Volume: {last_candle.volume}")

        # Calculate time range
        time_diff = last_candle.timestamp - first_candle.timestamp
        hours = time_diff.total_seconds() / 3600
        logger.info(f"Data spans {hours:.2f} hours ({time_diff})")

        # Check for time consistency
        if len(history) > 1:
            intervals = []
            for i in range(1, min(10, len(history))):
                interval = (history[i].timestamp - history[i - 1].timestamp).total_seconds() / 60
                intervals.append(interval)

            logger.info(f"Sample intervals between candles (minutes): {intervals}")

    if current:
        logger.info(f"Current candle: {current.timestamp}")
        logger.info(f"  OHLC: {current.open:.2f}/{current.high:.2f}/{current.low:.2f}/{current.close:.2f}")
        logger.info(f"  Volume: {current.volume}")
    else:
        logger.info("No current candle available")

    logger.info("Prepopulation test completed successfully!")


if __name__ == "__main__":
    test_prepopulation()