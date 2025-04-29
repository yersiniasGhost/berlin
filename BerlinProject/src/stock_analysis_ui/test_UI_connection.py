# test_simulated_ui_data.py
import time
import json
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from data_streamer.data_link import DataLink
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from stock_analysis_ui.services.streaming_manager import StreamingManager
from stock_analysis_ui.services.ui_external_tool import UIExternalTool

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SimulatedDataTest")


class SimulatedDataLink(DataLink):
    """Simulated data link that generates fake OHLC data for testing"""

    def __init__(self, symbols=None):
        super().__init__()
        self.symbols = symbols or ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        self.is_running = False
        self.current_time = datetime.now()
        self.base_prices = {
            "AAPL": 150.0,
            "MSFT": 300.0,
            "GOOGL": 130.0,
            "AMZN": 125.0,
            "TSLA": 200.0
        }
        # Set defaults for non-specified symbols
        for symbol in self.symbols:
            if symbol not in self.base_prices:
                self.base_prices[symbol] = 100.0 + random.random() * 200.0

        self.historical_data = {}
        self.generate_historical_data()

    def generate_historical_data(self):
        """Generate historical data for each symbol"""
        for symbol in self.symbols:
            base_price = self.base_prices[symbol]
            candles = []

            # Generate 60 historical candles (1 hour)
            start_time = self.current_time - timedelta(minutes=60)

            for i in range(60):
                timestamp = start_time + timedelta(minutes=i)

                # Create some price movement
                price_change = (random.random() - 0.5) * base_price * 0.01
                close = base_price + price_change
                # Simulate some volatility
                high = close + random.random() * base_price * 0.005
                low = close - random.random() * base_price * 0.005
                # Open is previous close or something close to current close
                open_price = base_price if i == 0 else candles[-1].close

                # Create candle
                candle = TickData(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=int(random.random() * 10000)
                )
                candles.append(candle)

                # Update base price for next candle
                base_price = close

            self.historical_data[symbol] = candles
            self.base_prices[symbol] = base_price  # Update for live data

    def load_historical_data(self, symbol, timeframe="1m"):
        """Return generated historical data for a symbol"""
        if symbol in self.historical_data:
            logger.info(f"Loading {len(self.historical_data[symbol])} historical candles for {symbol}")
            return self.historical_data[symbol]
        return []

    def start_simulation(self):
        """Start the simulation thread"""
        self.is_running = True

    def generate_candle(self, symbol, timestamp):
        """Generate a new candle for the given symbol"""
        base_price = self.base_prices[symbol]

        # Create some price movement
        price_change = (random.random() - 0.5) * base_price * 0.01
        close = base_price + price_change

        # Simulate some volatility
        high = close + random.random() * base_price * 0.005
        low = close - random.random() * base_price * 0.005

        # Open is close from last candle
        open_price = base_price

        # Update base price for next candle
        self.base_prices[symbol] = close

        # Create candle data in format expected by chart_handler
        candle_data = {
            'key': symbol,
            '7': int(timestamp.timestamp() * 1000),  # timestamp in ms
            '2': open_price,  # open
            '3': high,  # high
            '4': low,  # low
            '5': close,  # close
            '6': int(random.random() * 10000)  # volume
        }

        return candle_data

    def subscribe_charts(self, symbols, timeframe="1m"):
        """Simulate subscribing to chart data"""
        logger.info(f"Subscribed to charts for: {symbols} with timeframe {timeframe}")
        # Nothing to do here in simulation
        return True

    def connect_stream(self):
        """Simulate connecting to stream"""
        self.is_running = True
        logger.info("Connected to simulated data stream")
        return True

    def get_stats(self):
        """Return statistics for normalization"""
        return {
            "close": {"min": 50.0, "max": 500.0, "mean": 200.0, "std": 50.0},
            "open": {"min": 50.0, "max": 500.0, "mean": 200.0, "std": 50.0},
            "high": {"min": 50.0, "max": 500.0, "mean": 200.0, "std": 50.0},
            "low": {"min": 50.0, "max": 500.0, "mean": 200.0, "std": 50.0},
            "volume": {"min": 0, "max": 10000, "mean": 5000, "std": 2000}
        }

    def reset_index(self):
        """Reset index for iteration"""
        pass

    def get_next2(self):
        """Get next tick without using iterator"""
        return None

    def serve_next_tick(self):
        """Iterator for ticks - not used in simulation"""
        yield None, 0, 0


def load_monitor_config_from_file(filepath):
    """Load a monitor configuration from a JSON file or create default if not found"""
    try:
        with open(filepath, 'r') as f:
            config_data = json.load(f)

        # Extract indicator definitions from the JSON
        indicators = []
        for indicator_dict in config_data.get('indicators', []):
            # Create indicator definition
            indicator = IndicatorDefinition(
                name=indicator_dict["name"],
                type=indicator_dict["type"],
                function=indicator_dict["function"],
                parameters=indicator_dict.get("parameters", {}).copy()
            )
            indicators.append(indicator)

        # Create MonitorConfiguration object
        monitor_config = MonitorConfiguration(
            name=config_data.get('test_name', 'Test Monitor'),
            indicators=indicators
        )

        return monitor_config
    except Exception as e:
        # Create a default configuration if file not found
        logger.warning(f"Could not load config file: {e}, creating default")

        # Create default indicators
        indicators = [
            IndicatorDefinition(
                name="macd_cross_bull",
                type="Indicator",
                function="macd_histogram_crossover",
                parameters={
                    "slow": 26,
                    "fast": 12,
                    "signal": 9,
                    "histogram_threshold": 0.1,
                    "lookback": 15,
                    "trend": "bullish"
                }
            ),
            IndicatorDefinition(
                name="bollinger_bull",
                type="Indicator",
                function="bol_bands_lower_band_bounce",
                parameters={
                    "period": 20,
                    "sd": 2,
                    "candle_bounce_number": 3,
                    "bounce_trigger": 0.3,
                    "lookback": 10,
                    "trend": "bullish"
                }
            ),
            IndicatorDefinition(
                name="sma_cross_bull",
                type="Indicator",
                function="sma_crossover",
                parameters={
                    "period": 20,
                    "crossover_value": 0.002,
                    "lookback": 10,
                    "trend": "bullish"
                }
            )
        ]

        return MonitorConfiguration(
            name="Default Monitor Config",
            indicators=indicators
        )


def run_simulation_with_ui(socketio, symbols=None):
    """
    Run a simulation that feeds data to the UI

    Args:
        socketio: Flask-SocketIO instance
        symbols: List of symbols to simulate
    """
    if symbols is None:
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    logger.info(f"Starting simulation with symbols: {symbols}")

    # Create simulated data link
    data_link = SimulatedDataLink(symbols)

    # Create streaming manager
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

    # Load or create configuration
    base_config = load_monitor_config_from_file("monitor_config_example.json")

    # Create configuration for each symbol
    configs = []
    for symbol in symbols:
        # Create a slightly different config for each symbol for variety
        configs.append((f"{symbol}_config", [symbol], base_config))

    # Register streamers and connect UI tools
    for streamer_id, symbol_list, config in configs:
        logger.info(f"Creating streamer '{streamer_id}' for symbols: {', '.join(symbol_list)}")

        # Register with StreamingManager
        streamer = streaming_manager.register_streamer(
            streamer_id,
            symbol_list,
            config,
            model_config
        )

        # Create and connect UI tool
        ui_tool = UIExternalTool(socketio)
        streamer.connect_tool(ui_tool)

    # Start streaming (load historical data)
    logger.info("Starting streaming with historical data")
    streaming_manager.start_streaming("1m")

    # Give time for historical data to process
    time.sleep(1)

    # Start simulation loop in a separate thread
    import threading

    def simulation_loop():
        logger.info("Starting simulation loop for live data")

        # Current time starts at the end of historical data
        current_time = datetime.now()

        try:
            # Send a new candle every minute
            while data_link.is_running:
                current_time += timedelta(minutes=1)

                # Generate and send a candle for each symbol
                for symbol in symbols:
                    # Generate candle
                    candle_data = data_link.generate_candle(symbol, current_time)

                    time.sleep(0.3)
                    # Route candle to appropriate streamers
                    streaming_manager.route_chart_data(candle_data)

                # Wait a few seconds between updates for visualization
                time.sleep(3)

        except Exception as e:
            logger.error(f"Error in simulation loop: {e}")
            import traceback
            traceback.print_exc()

    # Start simulation thread
    data_link.start_simulation()
    sim_thread = threading.Thread(target=simulation_loop)
    sim_thread.daemon = True
    sim_thread.start()

    return {
        "data_link": data_link,
        "streaming_manager": streaming_manager,
        "simulation_thread": sim_thread
    }


# If run directly, this would execute a console-based test
if __name__ == "__main__":
    # This version would be for testing outside Flask
    class MockSocketIO:
        def emit(self, event, data):
            print(f"SOCKET.IO: {event}")


    # Run simulation with mock socketio
    run_simulation_with_ui(MockSocketIO())

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Simulation stopped by user")