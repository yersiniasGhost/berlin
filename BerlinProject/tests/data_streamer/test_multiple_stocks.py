# test_multi_symbol_streaming_complex.py
import time
import json
import logging
from datetime import datetime
from typing import Dict, Optional

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition

# Import the StreamingManager
from stock_analysis_ui.services.streaming_manager import StreamingManager


class DataMonitorTool(ExternalTool):
    """Monitor tool for tracking data processing in each DataStreamer"""

    def __init__(self, streamer_id, symbols):
        self.streamer_id = streamer_id
        self.symbols = symbols
        self.indicator_values = []
        self.candle_count = 0
        self.initial_history_size = 0
        self.current_history_size = 0
        self.data_streamer = None
        self.last_indicators = {}
        self.last_raw_indicators = {}
        self.last_indicator_time = None

    def feature_vector(self, fv: list, tick: TickData) -> None:
        # Not using feature vectors in this test
        pass

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        # Store the latest indicator values
        self.last_indicators = indicators.copy() if indicators else {}
        self.last_raw_indicators = raw_indicators.copy() if raw_indicators else {}
        self.last_indicator_time = datetime.now()

        # Store indicator values with timestamp for history
        self.indicator_values.append({
            'tick': tick,
            'indicators': indicators,
            'raw_indicators': raw_indicators,
            'timestamp': datetime.now() if hasattr(tick, 'timestamp') else None
        })

        # Print a report for this update
        self.print_indicator_report(tick)

    def handle_completed_candle(self, symbol: str, candle: TickData) -> None:
        """Handle completed candle notifications"""
        if symbol in self.symbols:
            self.candle_count += 1
            print(f"\n[{self.streamer_id}] Received candle #{self.candle_count} for {symbol}: "
                  f"OHLC({candle.open:.2f}, {candle.high:.2f}, {candle.low:.2f}, {candle.close:.2f})")

    def present_sample(self, sample: dict, index: int):
        pass

    def reset_next_sample(self):
        pass

    def print_indicator_report(self, tick):
        """Print a report of the latest indicator values"""
        print(f"\n{'-' * 30}")
        print(f"[{self.streamer_id}] INDICATOR UPDATE for {tick.symbol} @ {tick.timestamp}")
        print(f"{'-' * 30}")

        if self.last_indicators:
            for name, value in self.last_indicators.items():
                print(f"  • {name}: {value:.6f}")
                if name in self.last_raw_indicators:
                    raw_value = self.last_raw_indicators[name]
                    if isinstance(raw_value, (int, float)):
                        print(f"    Raw value: {raw_value:.6f}")

        print(f"{'-' * 30}")


def load_monitor_config_from_file(filepath):
    """Load a monitor configuration from a JSON file"""
    try:
        with open(filepath, 'r') as f:
            config_data = json.load(f)

        # Extract indicator definitions from the JSON
        indicators = []
        for indicator_dict in config_data.get('indicators', []):
            # Create a deep copy of the parameters
            parameters = indicator_dict.get("parameters", {}).copy()

            # Create indicator definition
            indicator = IndicatorDefinition(
                name=indicator_dict["name"],
                type=indicator_dict["type"],
                function=indicator_dict["function"],
                parameters=parameters
            )
            indicators.append(indicator)

        # Create MonitorConfiguration object
        monitor_config = MonitorConfiguration(
            name=config_data.get('test_name', 'Test Monitor'),
            indicators=indicators
        )

        return monitor_config
    except Exception as e:
        print(f"Error loading monitor config: {e}")
        return None


def create_variation_config(base_config, variation_name, params_to_modify):
    """Create a variation of a monitor configuration by modifying parameters"""
    # Create a copy of the indicators from the base config
    new_indicators = []

    for indicator in base_config.indicators:
        # Create a copy of the indicator with modified parameters
        new_params = indicator.parameters.copy() if indicator.parameters else {}

        # Apply modifications
        if indicator.name in params_to_modify:
            for param_key, param_value in params_to_modify[indicator.name].items():
                new_params[param_key] = param_value

        # Create new indicator definition
        new_indicator = IndicatorDefinition(
            name=indicator.name,
            type=indicator.type,
            function=indicator.function,
            parameters=new_params
        )

        new_indicators.append(new_indicator)

    # Create new monitor configuration
    return MonitorConfiguration(
        name=variation_name,
        indicators=new_indicators
    )


def test_multi_symbol_complex():
    """Test multiple symbol/monitor configurations with real-world config"""
    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("\n====================================================")
    print("TESTING MULTI-SYMBOL COMPLEX CONFIGURATIONS")
    print("====================================================\n")

    # Create and authenticate SchwabDataLink
    print("\nStep 1: Creating and authenticating SchwabDataLink")
    data_link = SchwabDataLink()

    if not data_link.authenticate():
        print("Authentication failed, exiting")
        return

    # Connect to streaming API
    print("\nStep 2: Connecting to streaming API")
    if not data_link.connect_stream():
        print("Failed to connect to streaming API")
        return

    # Create StreamingManager
    print("\nStep 3: Creating StreamingManager")
    streaming_manager = StreamingManager(data_link)

    # Create model configuration
    model_config = {
        "feature_vector": [
            {"name": "open"},
            {"name": "high"},
            {"name": "low"},
            {"name": "close"},
        ],
        "normalization": None
    }

    # Load the base configuration file
    print("\nStep 4: Loading monitor configurations")
    base_config = load_monitor_config_from_file("../../src/stock_analysis_ui/monitor_config_example.json")

    if not base_config:
        print("Failed to load base configuration, exiting")
        return

    # Create NVDA configuration variations
    nvda_configs = [
        # Base configuration - use as is
        ("nvda_standard", ["NVDA"], base_config),

        # Modified configuration with faster MACD
        ("nvda_fast", ["NVDA"], create_variation_config(
            base_config,
            "NVDA Fast",
            {"macd_cross_bull": {"fast": 3, "slow": 10, "signal": 3}}
        )),

        # Modified configuration with tighter Bollinger bands
        ("nvda_tight", ["NVDA"], create_variation_config(
            base_config,
            "NVDA Tight",
            {"bollinger_bull": {"sd": 1.5, "bounce_trigger": 0.3}}
        ))
    ]

    # Create PLTR and INTC configurations (using base config)
    other_configs = [
        ("pltr_config", ["PLTR"], base_config),
        ("intc_config", ["INTC"], base_config)
    ]

    # Combine all configurations
    all_configs = nvda_configs + other_configs

    # Register streamers and monitor tools
    print("\nStep 5: Registering streamers and connecting monitors")
    monitor_tools = {}

    for streamer_id, symbols, config in all_configs:
        print(f"  • Creating streamer '{streamer_id}' for symbols: {', '.join(symbols)}")

        # Register with StreamingManager
        streamer = streaming_manager.register_streamer(
            streamer_id,
            symbols,
            config,
            model_config
        )

        # Create and connect monitor tool
        monitor = DataMonitorTool(streamer_id, symbols)
        monitor.data_streamer = streamer
        streamer.connect_tool(monitor)
        monitor_tools[streamer_id] = monitor

    # Start streaming
    print("\nStep 6: Starting streaming for all configurations")
    streaming_manager.start_streaming("1m")

    print("\nWaiting for initial historical data loading...")
    time.sleep(3)  # Give more time for historical data to load

    # Print initial state for each monitor
    print("\nInitial state after historical data loading:")
    for streamer_id, monitor in monitor_tools.items():
        if monitor.data_streamer and hasattr(monitor.data_streamer, 'preprocessor'):
            history_size = len(monitor.data_streamer.preprocessor.history)
            monitor.initial_history_size = history_size
            monitor.current_history_size = history_size
            print(f"  • {streamer_id}: Loaded {history_size} historical ticks")
        else:
            print(f"  • {streamer_id}: No history available")

    # Live streaming
    print("\nStep 7: Processing live data. Data reports will be printed as received.")
    print("Press Ctrl+C to stop the test.")
    print("=" * 70)

    try:
        # This will run until interruption
        while True:
            time.sleep(5)  # Check every 5 seconds

            # Print summary of activity
            print("\nCurrent status summary:")
            for streamer_id, monitor in monitor_tools.items():
                if not monitor.data_streamer or not hasattr(monitor.data_streamer, 'preprocessor'):
                    print(f"  • {streamer_id}: No history available")
                    continue

                history = monitor.data_streamer.preprocessor.history
                new_size = len(history)

                if new_size > monitor.current_history_size:
                    print(f"  • {streamer_id}: +{new_size - monitor.current_history_size} new ticks "
                          f"(total: {new_size})")
                    monitor.current_history_size = new_size
                else:
                    print(f"  • {streamer_id}: No new data (total: {new_size})")

                # Print last indicator time if available
                if monitor.last_indicator_time:
                    elapsed = (datetime.now() - monitor.last_indicator_time).total_seconds()
                    print(f"    Last indicator update: {elapsed:.1f} seconds ago")

    except KeyboardInterrupt:
        print("\n\nTest stopped by user")

    print("\nTest completed!")


if __name__ == "__main__":
    test_multi_symbol_complex()