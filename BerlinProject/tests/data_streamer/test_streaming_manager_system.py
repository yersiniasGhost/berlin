

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
from models.monitor_configuration import MonitorConfiguration
from stock_analysis_ui.services.streaming_manager import StreamingManager


def main():
    symbols = ["AAPL", "MSFT", "NVDA", "QBTS", "TSLA"]
    config_file = "../../src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    print("🚀 Simple Aggregator Test")
    print(f"Symbols: {symbols}")

    # Load JSON config using existing MonitorConfiguration
    with open(config_file, 'r') as f:
        config_data = json.load(f)

    # Extract the monitor section and indicators
    monitor_data = config_data['monitor']
    monitor_data['indicators'] = config_data['indicators']  # Add indicators to monitor data

    monitor_config = MonitorConfiguration(**monitor_data)
    timeframes = monitor_config.get_time_increments()

    print(f"Timeframes needed: {list(timeframes)}")

    # Authenticate using existing auth manager
    auth = SchwabAuthManager()
    if not auth.authenticate():
        return

    # Setup data link using existing class
    data_link = SchwabDataLink()
    data_link.access_token = auth.access_token
    data_link.refresh_token = auth.refresh_token
    data_link.user_prefs = auth.user_prefs
    data_link.connect_stream()

    # Create aggregator dictionary using existing CandleAggregator
    aggregators = defaultdict(dict)
    for symbol in symbols:
        for timeframe in timeframes:
            aggregators[symbol][timeframe] = CandleAggregator(symbol, timeframe)

    print(f"\nCreated {len(symbols)} x {len(timeframes)} = {len(symbols) * len(timeframes)} aggregators")

    # Create StreamingManager and register aggregators
    streaming_manager = StreamingManager(data_link)
    for symbol in symbols:
        streaming_manager.aggregators[symbol] = aggregators[symbol]
        print(f"Registered {symbol} aggregators: {list(aggregators[symbol].keys())}")

    # Load historical data using existing prepopulate_data method
    print("\n=== Historical Data ===")
    for symbol in symbols:
        for timeframe in timeframes:
            aggregator = aggregators[symbol][timeframe]
            count = aggregator.prepopulate_data(data_link)
            history_size = len(aggregator.get_history())
            current = aggregator.get_current_candle()
            current_price = current.close if current else 0
            print(f"{symbol}-{timeframe}: {count} loaded, {history_size} in history, current: ${current_price:.2f}")

    # Use StreamingManager's existing route_pip_data method
    print(f"\n=== Live Streaming via StreamingManager ===")
    data_link.add_quote_handler(streaming_manager.route_pip_data)  # Use quotes not charts
    data_link.subscribe_quotes(symbols)  # Subscribe to rapid quote updates

    try:
        for i in range(300):  # 5 minutes
            time.sleep(1)
            if i % 30 == 0:  # Every 30 seconds
                print(f"Streaming for {i}s...")
                # Check aggregator states directly
                for symbol in symbols:
                    for timeframe in timeframes:
                        aggregator = streaming_manager.aggregators[symbol][timeframe]
                        history_size = len(aggregator.get_history())
                        current = aggregator.get_current_candle()
                        current_price = current.close if current else 0
                        print(f"  {symbol}-{timeframe}: {history_size} candles, current: ${current_price:.2f}")
                print()  # Add blank line for readability
    except KeyboardInterrupt:
        pass

    # Final status
    print(f"\n=== Final Status ===")
    for symbol in symbols:
        for timeframe in timeframes:
            aggregator = aggregators[symbol][timeframe]
            history_size = len(aggregator.get_history())
            current = aggregator.get_current_candle()
            current_price = current.close if current else 0
            print(f"{symbol}-{timeframe}: {history_size} candles, current: ${current_price:.2f}")

    data_link.disconnect()
    print("Done!")


if __name__ == "__main__":
    main()