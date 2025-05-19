import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('StreamingManagerTest')

from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from data_streamer.candle_aggregator import CandleAggregator


class MockDataStreamer:
    """Mock DataStreamer for testing"""

    def __init__(self, symbol=None):
        self.preprocessor = MockPreprocessor()
        self.symbol = symbol
        self.candles_received = 0

    def __str__(self):
        return f"MockDataStreamer for {self.symbol}"


class MockPreprocessor:
    """Mock preprocessor that just counts candles"""

    def __init__(self):
        self.history = []

    def next_tick(self, tick):
        self.history.append(tick)
        return len(self.history)


def load_pip_data(file_path):
    """Load PIP data from text file"""
    try:
        with open(file_path, 'r') as file:
            content = file.read()

            # Handle the possibility of trailing commas
            content = content.replace(",]", "]").replace(",}", "}")

            # Try to parse as JSON
            try:
                # If it's a JSON array
                if content.strip().startswith('['):
                    data = json.loads(content)
                # If it's a JSON object
                elif content.strip().startswith('{'):
                    data = [json.loads(content)]
                # If it's a newline-separated JSON
                else:
                    data = []
                    for line in content.splitlines():
                        if line.strip():
                            try:
                                data.append(json.loads(line))
                            except:
                                pass
            except json.JSONDecodeError:
                # If that fails, try to evaluate it as Python literal
                import ast
                data = ast.literal_eval(content)

            if isinstance(data, dict):
                data = [data]

            logger.info(f"Loaded {len(data)} PIP records from {file_path}")
            return data
    except Exception as e:
        logger.error(f"Error loading PIP data: {e}")
        return []


def load_monitor_config(file_path):
    """Load monitor configuration from JSON file"""
    try:
        with open(file_path, 'r') as file:
            config = json.load(file)

        # Extract indicators from config
        indicators = []
        for indicator_dict in config.get('indicators', []):
            indicator = IndicatorDefinition(
                name=indicator_dict["name"],
                type=indicator_dict["type"],
                function=indicator_dict["function"],
                parameters=indicator_dict["parameters"],
                time_increment=indicator_dict.get("time_increment", "1m")
            )
            indicators.append(indicator)

        # Create monitor configuration
        monitor_config = MonitorConfiguration(
            name=config.get('test_name', 'Test Monitor'),
            indicators=indicators
        )

        # Add bars if present
        if 'monitor' in config and 'bars' in config['monitor']:
            monitor_config.bars = config['monitor']['bars']

        logger.info(f"Loaded monitor configuration: {monitor_config.name}")
        return monitor_config
    except Exception as e:
        logger.error(f"Error loading monitor configuration: {e}")
        return None


def test_streaming_manager():
    """Test the StreamingManager with PIP data"""
    from stock_analysis_ui.services.streaming_manager import StreamingManager

    pip_file = "/home/warnd/devel/berlin/BerlinProject/tests/data_streamer/quote_data/NVDA_quotes2.txt"
    config_file = "/home/warnd/devel/berlin/BerlinProject/src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    # Load data
    pip_data = load_pip_data(pip_file)
    monitor_config = load_monitor_config(config_file)

    if not pip_data or not monitor_config:
        logger.error("Failed to load test data")
        return

    # Extract symbol from pip data
    symbol = pip_data[0].get('key')
    if not symbol:
        logger.error("Could not determine symbol from PIP data")
        return

    logger.info(f"Testing with symbol: {symbol}")

    # Create streaming manager
    manager = StreamingManager()

    # Create mock DataStreamer
    streamer = MockDataStreamer(symbol)

    # Patch register_streamer to return our mock streamer
    original_register = manager.register_streamer

    def patched_register(streamer_id, symbols, monitor_config, model_config):
        # Register mock streamer directly
        for s in symbols:
            manager.streamers_by_symbol[s].append(streamer)

        # Initialize aggregators
        for s in symbols:
            if s not in manager.aggregators:
                manager.aggregators[s] = {}

                # Create aggregators for all standard timeframes
                for timeframe in manager.standard_timeframes:
                    aggregator = CandleAggregator(timeframe)

                    # Register handler for completed candles
                    aggregator.add_candle_handler(
                        lambda sym, candle, tf=timeframe: manager._route_completed_candle(sym, candle, tf)
                    )

                    # Store aggregator
                    manager.aggregators[s][timeframe] = aggregator

        return streamer

    # Replace the method
    manager.register_streamer = patched_register

    # Register streamer
    manager.register_streamer("test_streamer", [symbol], monitor_config, {})

    # Process a subset of PIPs for testing (using first 1000 for speed)
    test_pips = pip_data[:5000]
    logger.info(f"Processing {len(test_pips)} PIPs")

    # Process PIPs
    for i, pip in enumerate(test_pips):
        manager.route_chart_data(pip)

        # Log progress
        if (i + 1) % 100 == 0:
            logger.info(f"Processed {i + 1}/{len(test_pips)} PIPs")

    # Check results
    total_candles = len(streamer.preprocessor.history)
    logger.info(f"Test completed - Streamer received {total_candles} candles")

    # Analyze candles by timeframe
    candles_by_timeframe = {}
    for candle in streamer.preprocessor.history:
        timeframe = getattr(candle, 'time_increment', 'unknown')
        if timeframe not in candles_by_timeframe:
            candles_by_timeframe[timeframe] = []
        candles_by_timeframe[timeframe].append(candle)

    # Log candle counts by timeframe
    logger.info("Candles received by timeframe:")
    for timeframe, candles in candles_by_timeframe.items():
        logger.info(f"  {timeframe}: {len(candles)} candles")

        # Show first and last candle for each timeframe
        if candles:
            first_candle = candles[0]
            last_candle = candles[-1]

            first_time = first_candle.timestamp if hasattr(first_candle, 'timestamp') else 'unknown'
            last_time = last_candle.timestamp if hasattr(last_candle, 'timestamp') else 'unknown'

            logger.info(f"    First: {first_time}, Last: {last_time}")

    # Check if we received candles for all expected timeframes
    for timeframe in manager.standard_timeframes:
        if timeframe not in candles_by_timeframe:
            logger.warning(f"No candles received for timeframe {timeframe}")

    logger.info("Test completed successfully!")


if __name__ == "__main__":
    test_streaming_manager()
