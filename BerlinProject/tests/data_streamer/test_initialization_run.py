# test_initialization_run.py
import time
from datetime import datetime
from typing import Dict, List, Optional
import logging

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_streamer import DataStreamer
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration


class DataMonitorTool(ExternalTool):
    """External tool for monitoring data flow and indicator calculations"""

    def __init__(self):
        self.indicator_values = []
        self.initial_history_size = 0
        self.current_history_size = 0
        self.last_checked_size = 0
        # Keep track of the data_streamer for reporting
        self.data_streamer = None
        # Store the last received indicator values
        self.last_indicators = {}
        self.last_raw_indicators = {}

    def feature_vector(self, fv: list, tick: TickData) -> None:
        # Not using feature vectors in this test
        pass

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        # Store the latest indicator values
        self.last_indicators = indicators.copy() if indicators else {}
        self.last_raw_indicators = raw_indicators.copy() if raw_indicators else {}

        # Store indicator values with timestamp for history
        self.indicator_values.append({
            'tick': tick,
            'indicators': indicators,
            'raw_indicators': raw_indicators,
            'timestamp': datetime.now() if hasattr(tick, 'timestamp') else None
        })

        # Check if we need to print a progress report
        if self.data_streamer:
            history = self.data_streamer.preprocessor.history
            self.current_history_size = len(history)

            # Only report when size changes
            if self.current_history_size > self.last_checked_size:
                try:
                    self.print_progress_report()
                except Exception as e:
                    print(f"Error in progress report: {e}")
                self.last_checked_size = self.current_history_size

    def present_sample(self, sample: dict, index: int):
        pass

    def reset_next_sample(self):
        pass

    def print_progress_report(self):
        """Print a report showing the current state of data processing"""
        if not self.data_streamer:
            return

        history = self.data_streamer.preprocessor.history
        self.current_history_size = len(history)

        added_ticks = self.current_history_size - self.initial_history_size

        print("\n" + "=" * 70)
        print("PROGRESS REPORT")
        print("=" * 70)
        print(f"Initial history size: {self.initial_history_size}")
        print(f"Current history size: {self.current_history_size}")
        print(f"Total added ticks: {added_ticks}")

        if history:
            first_tick = history[0]
            last_tick = history[-1]
            print(f"Time range: {first_tick.timestamp} to {last_tick.timestamp}")

            # Print indicator information
            print("\nLATEST INDICATOR VALUES:")
            if self.last_indicators:
                for name, value in self.last_indicators.items():
                    print(f"  • {name}: {value:.6f}")
                    # If we have raw indicator value, show it for comparison
                    if name in self.last_raw_indicators:
                        raw_value = self.last_raw_indicators[name]
                        if isinstance(raw_value, (int, float)):
                            print(f"    Raw value: {raw_value:.6f}")
                        else:
                            print(f"    Raw value: {raw_value}")

                print("\nINDICATOR CALCULATION DETAILS:")
                print("  Time-based metric appears to be applying these transformations:")
                if self.last_indicators and self.last_raw_indicators:
                    # Get the first indicator as an example
                    indicator_name = next(iter(self.last_indicators))
                    calc_value = self.last_indicators[indicator_name]
                    raw_value = self.last_raw_indicators.get(indicator_name)

                    if raw_value is not None and calc_value is not None:
                        if isinstance(raw_value, (int, float)) and isinstance(calc_value, (int, float)):
                            # Simple check for scaling/transformation
                            if raw_value != 0:
                                ratio = calc_value / raw_value if raw_value != 0 else 0
                                print(f"    • Scaling factor: {ratio:.4f} (calculated/raw)")

                            # Get indicator configuration if available
                            try:
                                # We don't know the exact structure of your indicators config
                                # So we'll just print what we know
                                print("    • Using lookback window (from params, if available)")

                                # Guess at whether it's using a decay
                                if abs(calc_value) < abs(raw_value) and raw_value != 0:
                                    decay = calc_value / raw_value
                                    print(f"    • Possible time decay factor: {decay:.4f}")
                                    print(f"    • This suggests indicator may be {int(decay * 100)}% of full strength")
                            except Exception as e:
                                # Just skip this part if it fails
                                pass

            if added_ticks > 0:
                print("\nLAST ADDED TICKS:")
                # Show the last few added ticks
                for i in range(max(self.initial_history_size, self.current_history_size - 3),
                               self.current_history_size):
                    if i < len(history):  # Safety check
                        tick = history[i]
                        print(
                            f"  {tick.symbol} @ {tick.timestamp}: OHLC({tick.open:.2f},{tick.high:.2f},{tick.low:.2f},{tick.close:.2f})")

        print("=" * 70)


def main():
    # Reduce logging verbosity to make our progress reports more visible
    logging.basicConfig(level=logging.WARNING)

    print("TESTING DATASTREAMER INITIALIZATION AND REAL-TIME DATA HANDLING")
    print("=" * 70)

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

    # Create indicator configuration
    indicator_config = MonitorConfiguration(
        name="Test Monitor",
        indicators=[
            {
                "name": "SMA Crossover",
                "type": "Indicator",
                "function": "sma_crossover",
                "parameters": {
                    "period": 10,
                    "crossover_value": 0.001,  # Adjusted to match your logs
                    "trend": "bullish",
                    "lookback": 10
                }
            }
        ]
    )

    # Create DataStreamer
    print("\nStep 3: Creating DataStreamer")
    data_streamer = DataStreamer(
        data_link=data_link,
        model_configuration=model_config,
        indicator_configuration=indicator_config
    )

    # Create and connect our monitoring tool
    monitor = DataMonitorTool()
    monitor.data_streamer = data_streamer  # Store reference to data_streamer
    data_streamer.connect_tool(monitor)

    # Define symbols to track
    symbols = ["NVDA"]
    timeframe = "1m"

    # Step 4: Initialize with historical data
    print(f"\nStep 4: Initializing DataStreamer with historical data for {symbols}")
    data_streamer.initialize(symbols, timeframe)

    # Record initial history size
    monitor.initial_history_size = len(data_streamer.preprocessor.history)
    monitor.last_checked_size = monitor.initial_history_size
    print(f"Initialization complete! Loaded {monitor.initial_history_size} historical ticks")

    # Step 5: Subscribe to real-time data
    print(f"\nStep 5: Subscribing to {symbols} with {timeframe} timeframe")
    data_link.subscribe_charts(symbols, timeframe)

    # Step 6: Run the DataStreamer - this will block until program is terminated
    print("\nStep 6: Starting DataStreamer run")
    print("Progress reports will be printed when new data is received")
    print("(Press Ctrl+C to stop the test)")
    print("=" * 70)

    # Print initial state
    monitor.print_progress_report()

    # Start the DataStreamer (will block until program termination)
    try:
        data_streamer.run()
    except KeyboardInterrupt:
        print("\nTest stopped by user")

    print("\nTest completed!")


if __name__ == "__main__":
    main()