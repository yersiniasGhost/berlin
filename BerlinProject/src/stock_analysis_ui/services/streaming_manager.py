# streaming_manager.py
import logging
from typing import Dict, List, Set, Optional
from data_streamer.data_streamer import DataStreamer

logger = logging.getLogger("StreamingManager")


class StreamingManager:
    def __init__(self, schwab_data_link):
        self.data_link = schwab_data_link
        self.streamers_by_id = {}        # id → DataStreamer
        self.streamers_by_symbol = {}    # symbol → [DataStreamer]
        self.symbol_set = set()          # unique set of all symbols

    def register_streamer(self, streamer_id, symbols, monitor_config, model_config):
        """Register a new DataStreamer for specific symbols with a configuration"""
        # Create new DataStreamer
        streamer = DataStreamer(
            data_link=self.data_link,
            model_configuration=model_config,
            indicator_configuration=monitor_config
        )

        # Store symbols directly in the streamer
        streamer.configured_symbols = set(symbols)

        # Register this streamer
        self.streamers_by_id[streamer_id] = streamer

        # Update symbol mapping
        for symbol in symbols:
            if symbol not in self.streamers_by_symbol:
                self.streamers_by_symbol[symbol] = []
            self.streamers_by_symbol[symbol].append(streamer)
            self.symbol_set.add(symbol)

        return streamer

    def start_streaming(self, timeframe="1m"):
        """Start streaming for all registered symbols"""
        # Subscribe to all unique symbols
        if self.symbol_set:
            symbols_list = list(self.symbol_set)
            logger.info(f"Subscribing to symbols: {', '.join(symbols_list)}")
            self.data_link.subscribe_charts(symbols_list, timeframe)

        # Register a chart handler that routes data to the right streamers
        self.data_link.add_chart_handler(self.route_chart_data)

        # Initialize historical data for each streamer
        for symbol in self.symbol_set:
            self.load_historical_data(symbol, timeframe)

    def load_historical_data(self, symbol, timeframe):
        """Load historical data for a symbol and distribute to relevant streamers"""
        logger.info(f"Loading historical data for {symbol}")
        historical_data = self.data_link.load_historical_data(symbol, timeframe)

        if not historical_data:
            logger.warning(f"No historical data found for {symbol}")
            return

        logger.info(f"Loaded {len(historical_data)} historical candles for {symbol}")

        # Distribute to all streamers for this symbol
        for streamer in self.streamers_by_symbol.get(symbol, []):
            for tick in historical_data:
                streamer.preprocessor.next_tick(tick)
                # Process indicators if configured
                if streamer.indicators:
                    indicator_results, raw_indicators = streamer.indicators.next_tick(streamer.preprocessor)

    def route_chart_data(self, chart_data):
        """Route chart data to appropriate streamers based on symbol"""
        # Extract symbol from the chart data
        symbol = chart_data.get('key', '')
        if not symbol or symbol not in self.streamers_by_symbol:
            return

        # ONLY route this data to streamers that are registered for this symbol
        for streamer in self.streamers_by_symbol[symbol]:
            # Only call chart_handler if this symbol is configured for this streamer
            if symbol in streamer.configured_symbols:
                streamer.chart_handler(chart_data)