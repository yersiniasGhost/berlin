import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('StreamingManagerTest')

from stock_analysis_ui.services.streaming_manager import StreamingManager
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from data_streamer.data_streamer import DataStreamer


def load_pip_data(file_path):
    """Load PIP data from file"""
    with open(file_path, 'r') as file:
        content = file.read()

    # Handle trailing commas
    content = content.replace(",]", "]").replace(",}", "}")

    # Parse JSON
    if content.strip().startswith('['):
        data = json.loads(content)
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


def load_monitor_config(file_path):
    """Load monitor configuration from JSON file"""
    try:
        with open(file_path, 'r') as f:
            config_data = json.load(f)

        # Extract indicators
        indicators = []
        for ind_dict in config_data['indicators']:
            indicator = IndicatorDefinition(
                name=ind_dict['name'],
                type=ind_dict['type'],
                function=ind_dict['function'],
                parameters=ind_dict['parameters'],
                time_increment=ind_dict.get('time_increment', '1m')
            )
            indicators.append(indicator)

        # Create monitor config
        monitor_config = MonitorConfiguration(
            name=config_data['test_name'],
            indicators=indicators
        )

        return monitor_config
    except Exception as e:
        logger.error(f"Could not load {file_path}: {e}")
        return None


def test_simple():
    """Test with 3 different symbols and monitor combinations"""

    # Define the 3 symbol/file combinations
    test_combinations = [
        {
            "symbol": "INTC",
            "pip_file": "quote_data/INTC_quotes2.txt",
            "config_file": "../../src/stock_analysis_ui.monitor_config_example_time_intervals.json",
            "name": "INTC_Config1"
        },
        {
            "symbol": "NVDA",
            "pip_file": "quote_data/NVDA_quotes2.txt",
            "config_file": "../../src/stock_analysis_ui.monitor_config_example_time_intervals.json",
            "name": "NVDA_Config2"
        },
        {
            "symbol": "PLTR",
            "pip_file": "quote_data/PLTR_quotes2.txt",
            "config_file": "../../src/stock_analysis_ui.monitor_config_example_time_intervals.json",
            "name": "PLTR_Config3"
        }
    ]

    # Create streaming manager
    manager = StreamingManager()

    # Mock data link
    class MockDataLink:
        def add_chart_handler(self, handler):
            pass

    # Store data streamers and PIP data for each combination
    data_streamers = {}
    pip_data_sets = {}

    # Load and register each combination
    logger.info("=== SETTING UP COMBINATIONS ===")
    for combo in test_combinations:
        symbol = combo["symbol"]

        # Load PIP data for this symbol
        try:
            pip_data = load_pip_data(combo["pip_file"])
            pip_data_sets[symbol] = pip_data
            logger.info(f"Loaded {len(pip_data)} PIPs for {symbol}")
        except:
            logger.warning(f"Could not load {combo['pip_file']}, skipping...")
            continue

        # Load monitor config
        try:
            monitor_config = load_monitor_config(combo["config_file"])
            logger.info(f"Loaded config for {symbol}:")
            for indicator in monitor_config.indicators:
                logger.info(f"  {indicator.name} - {indicator.time_increment}")
        except:
            # If file doesn't exist, create a simple config
            logger.warning(f"Could not load {combo['config_file']}, creating simple config")
            from models.indicator_definition import IndicatorDefinition
            indicator = IndicatorDefinition(
                name="simple_sma",
                type="Indicator",
                function="sma_crossover",
                parameters={"period": 20},
                time_increment="1m"
            )
            monitor_config = MonitorConfiguration(
                name=combo["name"],
                indicators=[indicator]
            )

        # Create DataStreamer for this combination
        model_config = {"feature_vector": [{"name": "close"}]}
        data_streamer = DataStreamer(
            data_link=MockDataLink(),
            model_configuration=model_config,
            indicator_configuration=monitor_config
        )

        # Register with manager
        manager.register_streamer(symbol, monitor_config, data_streamer)
        data_streamers[symbol] = data_streamer

        logger.info(f"Registered {symbol} with StreamingManager")

    # Show what the manager created
    logger.info("\n=== STREAMING MANAGER STATE ===")
    status = manager.get_status()
    logger.info(f"Active symbols: {status['active_symbols']}")
    logger.info(f"Active timeframes: {status['active_timeframes']}")
    logger.info(f"Total aggregators: {status['total_aggregators']}")

    logger.info("\nAggregators by symbol:")
    for symbol, timeframes in status['aggregators_by_symbol'].items():
        logger.info(f"  {symbol}: {timeframes}")

    logger.info("\nDataStreamer mappings:")
    for (symbol, timeframe), streamers in manager.streamers_by_symbol_timeframe.items():
        logger.info(f"  ({symbol}, {timeframe}): {len(streamers)} streamers")

    # Track indicator values for each streamer
    indicator_values = {symbol: {} for symbol in data_streamers}

    # Process PIPs for each symbol
    logger.info("\n=== PROCESSING PIPS ===")
    for symbol, pip_data in pip_data_sets.items():
        logger.info(f"\nProcessing {symbol} PIPs...")
        test_pips = pip_data[:5000]  # Use subset for testing

        for i, pip in enumerate(test_pips):
            manager.route_pip_data(pip)

            # Every 100 PIPs, check candle counts
            if (i + 1) % 100 == 0:
                logger.info(f"  Processed {i + 1} {symbol} PIPs")

                # Check candle counts for all streamers
                for sym, streamer in data_streamers.items():
                    candle_count = len(streamer.preprocessor.history)
                    # Group by timeframe
                    candles_by_tf = {}
                    for candle in streamer.preprocessor.history:
                        tf = candle.time_increment
                        if tf not in candles_by_tf:
                            candles_by_tf[tf] = []
                        candles_by_tf[tf].append(candle)

                    logger.info(f"  {sym} has {candle_count} candles:")
                    for tf, candles in candles_by_tf.items():
                        logger.info(f"    {tf}: {len(candles)} candles")

                # Check if indicators are being calculated
                for sym, streamer in data_streamers.items():
                    try:
                        if hasattr(streamer.indicators, 'results_by_timeframe'):
                            # Store the indicator results for this check point
                            for timeframe, results in streamer.indicators.results_by_timeframe.items():
                                if results:  # If we have results
                                    if timeframe not in indicator_values[sym]:
                                        indicator_values[sym][timeframe] = {}
                                    indicator_values[sym][timeframe][i] = results

                                    logger.info(f"  {sym} {timeframe} indicators at pip {i + 1}:")
                                    for name, value in results.items():
                                        logger.info(f"    {name}: {value}")
                                else:
                                    logger.info(f"  {sym} {timeframe}: No indicator results available")
                    except Exception as e:
                        logger.error(f"Error checking indicators for {sym}: {e}")
                        import traceback
                        traceback.print_exc()

    # Check results for each DataStreamer
    logger.info("\n=== RESULTS BY SYMBOL ===")
    for symbol, data_streamer in data_streamers.items():
        history_len = len(data_streamer.preprocessor.history)
        logger.info(f"\n{symbol} DataStreamer received {history_len} candles:")

        # Group candles by timeframe
        candles_by_tf = {}
        for candle in data_streamer.preprocessor.history:
            tf = candle.time_increment
            if tf not in candles_by_tf:
                candles_by_tf[tf] = []
            candles_by_tf[tf].append(candle)

        # Show breakdown by timeframe
        for tf, candles in candles_by_tf.items():
            logger.info(f"  {tf}: {len(candles)} candles")
            if candles:
                sample = candles[0]
                last = candles[-1]
                logger.info(f"    First: {sample.timestamp} O:{sample.open} C:{sample.close}")
                logger.info(f"    Last:  {last.timestamp} O:{last.open} C:{last.close}")

        # Show indicator results for this symbol
        logger.info(f"\n  Indicator Results for {symbol}:")
        if symbol in indicator_values:
            for timeframe, values_by_pip in indicator_values[symbol].items():
                logger.info(f"    {timeframe} indicators:")
                # Just show the last PIP's indicator values
                if values_by_pip:
                    last_pip = max(values_by_pip.keys())
                    logger.info(f"      Final values (pip {last_pip}):")
                    for name, value in values_by_pip[last_pip].items():
                        logger.info(f"        {name}: {value}")
                else:
                    logger.info(f"      No indicator values calculated")

        # Check final indicator state in DataStreamer
        if hasattr(data_streamer.indicators, 'results_by_timeframe'):
            logger.info(f"\n  Final indicator state:")
            for timeframe, results in data_streamer.indicators.results_by_timeframe.items():
                if results:
                    logger.info(f"    {timeframe}:")
                    for name, value in results.items():
                        logger.info(f"      {name}: {value}")

        # Verify all candles are for the correct symbol
        for candle in data_streamer.preprocessor.history:
            assert candle.symbol == symbol, f"Wrong symbol! Expected {symbol}, got {candle.symbol}"

    # Final verification
    logger.info("\n=== FINAL VERIFICATION ===")
    total_candles = sum(len(ds.preprocessor.history) for ds in data_streamers.values())
    logger.info(f"Total candles processed across all symbols: {total_candles}")

    # Verify each symbol only received its own candles
    for symbol, data_streamer in data_streamers.items():
        symbol_candles = [c for c in data_streamer.preprocessor.history if c.symbol == symbol]
        total_candles_for_symbol = len(data_streamer.preprocessor.history)
        assert len(symbol_candles) == total_candles_for_symbol, f"{symbol} received candles for other symbols!"
        logger.info(f"✓ {symbol} correctly received only its own candles")

    logger.info("\n✓ All tests passed! StreamingManager correctly handled multiple symbols and configurations.")


if __name__ == "__main__":
    test_simple()