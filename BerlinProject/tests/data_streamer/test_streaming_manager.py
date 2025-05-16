import os
import sys
import json
import ast
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MinimalManagerRealDataTest')

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from environments.tick_data import TickData
    from models.monitor_configuration import MonitorConfiguration
    from models.indicator_definition import IndicatorDefinition
    from stock_analysis_ui.services.streaming_manager import MinimalStreamingManager  # Use the correct import path
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    logger.error("Make sure all required modules are in the Python path")
    sys.exit(1)


class MockDataStreamer:
    """Minimal mock DataStreamer for testing"""

    def __init__(self, required_timeframes=None, name="test"):
        self.required_timeframes = required_timeframes or {"1m"}
        self.preprocessor = MockPreprocessor()
        self.indicators = MockIndicators()
        self.external_tool = []
        self.name = name  # For easier identification in logs

    def __str__(self):
        return f"MockDataStreamer({self.name})"


class MockPreprocessor:
    """Mock preprocessor that just stores history"""

    def __init__(self):
        self.history = []

    def next_tick(self, tick):
        """Add tick to history"""
        self.history.append(tick)


class MockIndicators:
    """Mock indicators that return fixed results"""

    def next_tick(self, preprocessor):
        """Return mock indicator results"""
        return {"test_indicator": 0.5}, {"test_indicator_raw": 42}


class MockExternalTool:
    """Mock external tool that records calls"""

    def __init__(self, name="test_tool"):
        self.indicator_calls = []
        self.candle_calls = []
        self.name = name

    def indicator_vector(self, indicators, tick, index, raw_indicators=None):
        """Record indicator call"""
        self.indicator_calls.append({
            "indicators": indicators,
            "tick": tick,
            "raw_indicators": raw_indicators
        })
        logger.debug(f"Tool {self.name} received indicators: {indicators}")

    def handle_completed_candle(self, symbol, candle):
        """Record completed candle"""
        self.candle_calls.append({
            "symbol": symbol,
            "candle": candle
        })
        logger.debug(f"Tool {self.name} received candle: {symbol} @ {candle.timestamp}")


def load_pip_data_from_txt(filepath):
    """Load PIP data from text file"""
    try:
        with open(filepath, 'r') as file:
            content = file.read()

            # Handle the txt format - assuming it's basically a string representation of JSON
            # Remove any trailing commas that would cause JSON parsing errors
            content = content.replace(",]", "]").replace(",}", "}")

            # Try to parse as JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # If that fails, try to parse as a Python list literal
                # This is less secure but might work for your specific file
                data = ast.literal_eval(content)

        logger.info(f"Loaded {len(data)} PIP records from {filepath}")
        return data
    except Exception as e:
        logger.error(f"Error loading text file: {e}")
        return []


def load_monitor_config(file_path):
    """Load MonitorConfiguration from JSON file"""
    try:
        with open(file_path, 'r') as f:
            config_data = json.load(f)

        # Debug - log the config data structure
        logger.info(f"Loaded config data type: {type(config_data)}")

        # If config_data is a list (not a dict), try to use the first item
        if isinstance(config_data, list) and len(config_data) > 0:
            logger.warning("Config data is a list, using the first item")
            config_data = config_data[0]
            if not isinstance(config_data, dict):
                logger.error("First item in config data is not a dictionary")
                return None

        # Create indicator definitions
        indicators = []
        for indicator_dict in config_data.get('indicators', []):
            indicator = IndicatorDefinition(
                name=indicator_dict["name"],
                type=indicator_dict["type"],
                function=indicator_dict["function"],
                parameters=indicator_dict["parameters"].copy(),
                time_increment=indicator_dict.get("time_increment", "1m")
            )
            indicators.append(indicator)

        # Create monitor configuration
        monitor_config = MonitorConfiguration(
            name=config_data.get('test_name', 'Test Monitor'),
            indicators=indicators
        )

        # Add bars if present
        if 'monitor' in config_data and 'bars' in config_data['monitor']:
            monitor_config.bars = config_data['monitor']['bars']

        return monitor_config

    except Exception as e:
        logger.error(f"Error loading monitor configuration: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_minimal_manager_with_real_data(pip_filepath, config_filepath):
    """Test minimal StreamingManager with real PIP data and config"""
    # Load PIP data
    pip_data = load_pip_data_from_txt(pip_filepath)
    if not pip_data:
        logger.error("No PIP data loaded")
        return

    # Determine symbol from first PIP
    symbol = pip_data[0].get('key')
    if not symbol:
        logger.error("First PIP doesn't have a symbol")
        return

    logger.info(f"Using symbol {symbol} from PIP data")

    # Load monitor configuration
    monitor_config = load_monitor_config(config_filepath)
    if not monitor_config:
        logger.error("Failed to load monitor configuration")
        return

    # Get required timeframes
    timeframes = monitor_config.get_time_increments()
    logger.info(f"Monitor config requires timeframes: {timeframes}")

    # Create minimal manager
    manager = MinimalStreamingManager()

    # Create mock streamer
    streamer = MockDataStreamer(required_timeframes=timeframes, name=f"streamer_{symbol}")
    tool = MockExternalTool(name=f"tool_{symbol}")
    streamer.external_tool.append(tool)

    # Register streamer
    manager.register_datastreamer_from_config(streamer, [symbol], monitor_config)

    # Verify registration
    assert symbol in manager.streamers_by_symbol
    assert streamer in manager.streamers_by_symbol[symbol]

    # Check aggregators
    symbol_aggregators = manager.get_aggregators_for_symbol(symbol)
    logger.info(f"Aggregators for {symbol}: {list(symbol_aggregators.keys())}")

    # Process PIP data
    logger.info(f"Processing {len(pip_data)} PIPs")

    # Limit to a reasonable subset for testing if there are too many
    max_pips = 5000
    if len(pip_data) > max_pips:
        logger.info(f"Using first {max_pips} PIPs for testing")
        pip_data = pip_data[:max_pips]

    # Process PIPs
    for i, pip in enumerate(pip_data):
        manager.process_pip(pip)

        # Log progress
        if (i + 1) % 1000 == 0:
            logger.info(f"Processed {i + 1} PIPs")

    # Check results
    logger.info("PIP processing complete, analyzing results...")

    # Check indicator calls
    logger.info(f"External tool received {len(tool.indicator_calls)} indicator calls")

    # Check candle calls by timeframe
    if not tool.candle_calls:
        logger.warning("No candles were received by the external tool")
    else:
        # Group candles by timeframe
        candles_by_timeframe = {}
        for call in tool.candle_calls:
            timeframe = call["candle"].time_increment
            if timeframe not in candles_by_timeframe:
                candles_by_timeframe[timeframe] = []
            candles_by_timeframe[timeframe].append(call["candle"])

        # Log candle counts
        logger.info(f"Received candles by timeframe:")
        for timeframe, candles in candles_by_timeframe.items():
            logger.info(f"  {timeframe}: {len(candles)} candles")

            # Print first and last candle for each timeframe
            if candles:
                first_candle = candles[0]
                last_candle = candles[-1]

                logger.info(f"  First {timeframe} candle: {first_candle}")
                logger.info(f"  Last {timeframe} candle: {last_candle}")

        # Verify we got candles for all required timeframes
        for timeframe in timeframes:
            assert timeframe in candles_by_timeframe, f"No candles received for timeframe {timeframe}"

    logger.info("Test with real data complete!")


def find_file(base_name, directories=None):
    """Find a file in possible directories"""
    if directories is None:
        directories = [
            script_dir,
            os.path.join(script_dir, "quote_data"),
            os.path.join(parent_dir, "quote_data"),
            os.path.join(parent_dir, "stock_analysis_ui"),
            os.path.join(parent_dir, "src", "stock_analysis_ui"),
            parent_dir
        ]

    # First check if the base_name itself is a valid path
    if os.path.exists(base_name):
        return base_name

    # Check each directory
    for directory in directories:
        path = os.path.join(directory, base_name)
        if os.path.exists(path):
            return path

    return None


if __name__ == "__main__":
    logger.info("=== Testing Minimal StreamingManager with Real Data ===")

    # Get file paths
    pip_filepath = None
    config_filepath = None

    # Check command line arguments
    if len(sys.argv) > 1:
        pip_filepath = sys.argv[1]

    if len(sys.argv) > 2:
        config_filepath = sys.argv[2]

    # If not provided, try to find the files
    if not pip_filepath or not os.path.exists(pip_filepath):
        pip_filepath = find_file("NVDA_quotes2.txt")
        if not pip_filepath:
            logger.error("Cannot find PIP data file. Please provide the path as the first argument.")
            sys.exit(1)

    if not config_filepath or not os.path.exists(config_filepath):
        # FIXED: Look for the monitor config JSON, not the quotes file
        config_filepath = find_file("../stock_analysis_ui/monitor_config_example_time_intervals.json")
        if not config_filepath:
            logger.error("Cannot find config file. Please provide the path as the second argument.")
            sys.exit(1)

    logger.info(f"Using PIP data file: {pip_filepath}")
    logger.info(f"Using config file: {config_filepath}")

    # Run test
    test_minimal_manager_with_real_data(pip_filepath, config_filepath)
