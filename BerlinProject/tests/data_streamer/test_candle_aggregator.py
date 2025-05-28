import json
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CandleAggregatorTest')

from data_streamer.candle_aggregator import CandleAggregator


def load_pip_data(file_path):
    """Load PIP data from text file"""
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        # Handle trailing commas
        content = content.replace(",]", "]").replace(",}", "}")

        # Parse JSON
        if content.strip().startswith('['):
            data = json.loads(content)
        elif content.strip().startswith('{'):
            data = [json.loads(content)]
        else:
            # Try newline-separated JSON
            data = []
            for line in content.splitlines():
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except:
                        pass

        logger.info(f"Loaded {len(data)} PIP records")
        return data
    except Exception as e:
        logger.error(f"Error loading PIP data: {e}")
        return []


def test_single_timeframe_aggregators():
    """Test multiple CandleAggregators each handling one timeframe"""
    # Load test data
    pip_file = "quote_data/NVDA_quotes2.txt"
    pip_data = load_pip_data(pip_file)

    if not pip_data:
        logger.error("Failed to load test data")
        return

    # Extract symbol from first PIP
    symbol = pip_data[0].get('key', 'NVDA')
    logger.info(f"Testing with symbol: {symbol}")

    # Create aggregators for different timeframes
    timeframes = ["15m"]
    aggregators = {}
    completed_candles = {}

    for tf in timeframes:
        aggregators[tf] = CandleAggregator(symbol, tf)
        completed_candles[tf] = []

    # Inspect first few PIPs
    logger.info("\n--- SAMPLE PIP DATA ---")
    for i, pip in enumerate(pip_data[:3]):
        timestamp_ms = pip.get('38', 0)
        price = pip.get('3', 0)
        volume = pip.get('8', 0)
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000) if timestamp_ms > 0 else "INVALID"
        logger.info(f"PIP {i + 1}: timestamp={timestamp}, price={price}, volume={volume}")

    # Process subset of PIPs
    test_pips = pip_data[:3000]
    logger.info(f"Processing {len(test_pips)} PIPs across {len(timeframes)} timeframes")

    processed_count = 0

    # Process each PIP through all aggregators
    for i, pip in enumerate(test_pips):
        pip_processed = False

        # Send to each timeframe aggregator
        for tf in timeframes:
            completed_candle = aggregators[tf].process_pip(pip)
            if completed_candle:
                completed_candles[tf].append(completed_candle)
                pip_processed = True

        if pip_processed:
            processed_count += 1

        # Log progress
        if (i + 1) % 200 == 0:
            logger.info(f"Processed {i + 1}/{len(test_pips)} PIPs")

    logger.info(f"Processed {processed_count} valid PIPs")

    # Print results
    logger.info("\n--- TEST RESULTS ---")
    for tf in timeframes:
        count = len(completed_candles[tf])
        logger.info(f"{tf} candles completed: {count}")

        # Show first few candles
        if count > 0:
            logger.info(f"  Sample {tf} candles:")
            for i, candle in enumerate(completed_candles[tf][:2]):
                logger.info(
                    f"    {i + 1}. {candle.timestamp}: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f} V:{candle.volume}")

    # Test current candles
    logger.info("\n--- CURRENT CANDLES ---")
    for tf in timeframes:
        current = aggregators[tf].get_current_candle()
        if current:
            logger.info(
                f"{tf} current: {current.timestamp}: O:{current.open:.2f} H:{current.high:.2f} L:{current.low:.2f} C:{current.close:.2f}")
        else:
            logger.info(f"{tf} current: None")

    # Validation
    logger.info("\n--- VALIDATION ---")
    for tf in timeframes:
        if completed_candles[tf]:
            candle = completed_candles[tf][0]
            assert candle.symbol == symbol, f"Symbol mismatch in {tf}"
            assert candle.time_increment == tf, f"Timeframe mismatch in {tf}"
            logger.info(f"{tf}: ✓ Symbol and timeframe correct")

    logger.info("Test completed successfully!")


if __name__ == "__main__":
    test_single_timeframe_aggregators()