import time
import logging
from datetime import datetime

# Import your SimpleQuoteStreamer
from data_streamer.historical_charles_schwab_link import SimpleQuoteStreamer
from data_streamer.candle_aggregator import CandleAggregator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CandleAggregatorTest')


def test_multi_timeframe():
    # Define the file path to your historical data
    file_path = "quote_data/NVDA_quotes2.txt"

    # Create the streamer
    streamer = SimpleQuoteStreamer(file_path, replay_speed=20.0)

    # Create aggregators for multiple timeframes
    aggregators = {
        "1m": CandleAggregator("1m"),
        "5m": CandleAggregator("5m"),
        "15m": CandleAggregator("15m"),
        "30m": CandleAggregator("30m")
    }

    # Track candle counts
    candle_counts = {tf: 0 for tf in aggregators.keys()}

    # Define candle completion handlers
    def create_handler(timeframe):
        def handler(symbol, candle):
            candle_counts[timeframe] += 1
            # Print all completed candles
            logger.info(f"Completed {timeframe} candle for {symbol} @ {candle.timestamp}: "
                        f"O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f} V:{candle.volume}")

        return handler

    # Register handlers for each timeframe
    for tf, aggregator in aggregators.items():
        aggregator.add_candle_handler(create_handler(tf))

    # Create a PIP handler that feeds data to all aggregators
    def process_quote(quote):
        # Process through all aggregators
        for aggregator in aggregators.values():
            aggregator.process_pip(quote)

    # Add the handler
    streamer.add_handler(process_quote)

    # Start streaming
    logger.info("Starting to stream quotes...")
    streamer.start()

    # Let it run until all quotes are processed
    while streamer.is_running:
        time.sleep(1)

    # Print summary
    logger.info("\n--- SUMMARY ---")
    for tf, count in candle_counts.items():
        logger.info(f"{tf} candles created: {count}")

    # Print the last few candles for each timeframe
    symbol = "NVDA"

    logger.info("\n--- LAST CANDLES BY TIMEFRAME ---")
    for tf, aggregator in aggregators.items():
        candles = aggregator.get_candle_history(symbol)
        if candles:
            logger.info(f"\nLast 3 {tf} candles:")
            for candle in candles[-3:]:
                logger.info(
                    f"  {candle.timestamp}: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f} V:{candle.volume}")

    # Example of accessing candle data in a combined format
    logger.info("\n--- COMBINED DATA STRUCTURE ---")
    combined_data = {symbol: {}}

    for tf, aggregator in aggregators.items():
        combined_data[symbol][tf] = aggregator.get_candle_history(symbol)

    # Show the first and last candle of each timeframe
    for tf, candles in combined_data[symbol].items():
        if candles:
            first_candle = candles[0]
            last_candle = candles[-1]
            logger.info(f"{tf} - {len(candles)} candles from {first_candle.timestamp} to {last_candle.timestamp}")


if __name__ == "__main__":
    test_multi_timeframe()