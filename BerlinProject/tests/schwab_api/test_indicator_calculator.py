#!/usr/bin/env python3
"""
Simple test to see indicators being calculated with streaming data
"""

import sys
import os
import time
import json
from collections import defaultdict

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..', 'src'))

from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.candle_aggregator import CandleAggregator
from data_streamer.data_streamer import DataStreamer
from models.monitor_configuration import MonitorConfiguration
from stock_analysis_ui.services.streaming_manager import StreamingManager


class SimpleIndicatorTool:
    def __init__(self):
        self.indicator_updates = 0

    def feature_vector(self, fv, tick):
        pass

    def indicator_vector(self, indicators, tick, index, raw_indicators=None, bar_scores=None):
        self.indicator_updates += 1
        symbol = getattr(tick, 'symbol', 'UNKNOWN') if tick else 'UNKNOWN'

        print(f"\n📊 Indicator Update #{self.indicator_updates} for {symbol}")

        # Show individual indicators
        for name, value in indicators.items():
            raw_val = raw_indicators.get(name, 'N/A') if raw_indicators else 'N/A'
            print(f"  {name}: {value:.4f} (raw: {raw_val})")

        # Show bar scores - THIS IS ALREADY THERE!
        if bar_scores:
            print(f"  🎯 Bar Scores:")
            for bar_name, score in bar_scores.items():
                print(f"    {bar_name}: {score:.4f}")

def main():
    symbols = ["NVDA", "PLTR"]
    config_file = "../../src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    print("🚀 Simple Indicator Test")
    print(f"Symbols: {symbols}")

    # Load monitor config
    with open(config_file, 'r') as f:
        config_data = json.load(f)

    monitor_data = config_data['monitor']
    monitor_data['indicators'] = config_data['indicators']
    monitor_config = MonitorConfiguration(**monitor_data)

    timeframes = monitor_config.get_time_increments()
    print(f"Timeframes: {list(timeframes)}")
    print(f"Indicators: {[ind.name for ind in monitor_config.indicators]}")

    # Authenticate
    auth = SchwabAuthManager()
    if not auth.authenticate():
        return

    # Setup data link
    data_link = SchwabDataLink()
    data_link.access_token = auth.access_token
    data_link.refresh_token = auth.refresh_token
    data_link.user_prefs = auth.user_prefs
    data_link.connect_stream()

    # Create aggregators
    aggregators = defaultdict(dict)
    for symbol in symbols:
        for timeframe in timeframes:
            aggregators[symbol][timeframe] = CandleAggregator(symbol, timeframe)

    # Create StreamingManager
    streaming_manager = StreamingManager(data_link)
    for symbol in symbols:
        streaming_manager.aggregators[symbol] = aggregators[symbol]

    # Load historical data
    print("\n=== Loading Historical Data ===")
    for symbol in symbols:
        for timeframe in timeframes:
            aggregator = aggregators[symbol][timeframe]
            count = aggregator.prepopulate_data(data_link)
            print(f"{symbol}-{timeframe}: {count} candles loaded")

    # Create DataStreamer with indicators
    print("\n=== Setting up DataStreamer with Indicators ===")
    model_config = {"feature_vector": [{"name": "close"}]}
    data_streamer = DataStreamer(model_config, monitor_config)

    # Connect indicator tool
    indicator_tool = SimpleIndicatorTool()
    data_streamer.connect_tool(indicator_tool)

    print("DataStreamer created with indicators")

    # Start streaming
    print("\n=== Starting Live Streaming with Indicators ===")
    data_link.add_quote_handler(streaming_manager.route_pip_data)
    data_link.subscribe_quotes(symbols)

    try:
        for i in range(180):  # 3 minutes
            time.sleep(1)

            # Process indicators every few seconds
            if i % 5 == 0:
                print(f"\n--- Processing Indicators at {i}s ---")
                # Process indicators for each symbol separately
                for symbol in symbols:
                    symbol_aggregators = streaming_manager.aggregators[symbol]
                    data_streamer.process_tick(symbol_aggregators)

            # Status every 30 seconds
            if i % 30 == 0:
                print(f"\n=== Status at {i}s ===")
                for symbol in symbols:
                    for timeframe in timeframes:
                        aggregator = streaming_manager.aggregators[symbol][timeframe]
                        history_size = len(aggregator.get_history())
                        current = aggregator.get_current_candle()
                        current_price = current.close if current else 0
                        print(f"{symbol}-{timeframe}: {history_size} candles, current: ${current_price:.2f}")

                print(f"Total indicator updates: {indicator_tool.indicator_updates}")

    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")

    finally:
        data_link.disconnect()
        print(f"\n🏁 Done! Total indicator updates: {indicator_tool.indicator_updates}")


if __name__ == "__main__":
    main()