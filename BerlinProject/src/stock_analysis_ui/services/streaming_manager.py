# streaming_manager.py
import logging
from typing import Dict, List, Set, Optional
from data_streamer.data_streamer import DataStreamer
from data_streamer.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration

logger = logging.getLogger("StreamingManager")


class StreamingManager:
    def __init__(self, schwab_data_link):
        self.data_link = schwab_data_link
        self.streamers_by_id = {}  # id → DataStreamer
        self.streamers_by_symbol = {}  # symbol → [DataStreamer]
        self.symbol_set = set()  # unique set of all symbols
        self.timeframe_aggregators = {}  # timeframe → CandleAggregator
        self.required_timeframes = set()  # set of required timeframes

    def register_streamer(self, streamer_id, symbols, monitor_config, model_config):
        """Register a new DataStreamer for specific symbols with a configuration"""
        # Extract required timeframes from the monitor configuration
        self.required_timeframes.update(monitor_config.get_time_increments())

        # Create new DataStreamer
        streamer = DataStreamer(
            data_link=self.data_link,
            model_configuration=model_config,
            indicator_configuration=monitor_config
        )

        # Store symbols directly in the streamer
        streamer.configured_symbols = set(symbols)

        # Store timeframes required by this streamer
        streamer.required_timeframes = monitor_config.get_time_increments()

        # Register this streamer
        self.streamers_by_id[streamer_id] = streamer

        # Update symbol mapping
        for symbol in symbols:
            if symbol not in self.streamers_by_symbol:
                self.streamers_by_symbol[symbol] = []
            self.streamers_by_symbol[symbol].append(streamer)
            self.symbol_set.add(symbol)

        return streamer

    def start_streaming(self, base_timeframe="1m"):
        """
        Start streaming for all registered symbols with appropriate timeframes
        Args:
            base_timeframe: The base timeframe to subscribe to for real-time data
        """
        # Log all required timeframes
        logger.info(f"Required timeframes: {self.required_timeframes}")

        # Subscribe to all unique symbols
        if self.symbol_set:
            symbols_list = list(self.symbol_set)
            logger.info(f"Subscribing to symbols: {', '.join(symbols_list)}")

            # Always subscribe to the base timeframe for real-time data
            self.data_link.subscribe_charts(symbols_list, base_timeframe)

            # Create candle aggregators for each required timeframe
            for timeframe in self.required_timeframes:
                if timeframe != base_timeframe:
                    logger.info(f"Creating aggregator for timeframe: {timeframe}")
                    self.timeframe_aggregators[timeframe] = CandleAggregator(timeframe)

        # Register a chart handler that routes data to the right streamers
        self.data_link.add_chart_handler(self.route_chart_data)

        # Initialize historical data for each symbol
        for symbol in self.symbol_set:
            self.load_historical_data(symbol)

    def load_historical_data(self, symbol):
        """
        Load historical data for a symbol for all required timeframes
        and distribute to relevant streamers
        """
        logger.info(f"Loading historical data for {symbol} across all timeframes")

        # Keep track of historical data by timeframe
        historical_data_by_timeframe = {}

        # Load historical data for each required timeframe
        for timeframe in self.required_timeframes:
            logger.info(f"Loading {timeframe} historical data for {symbol}")
            historical_data = self.data_link.load_historical_data(symbol, timeframe)

            if historical_data:
                logger.info(f"Loaded {len(historical_data)} {timeframe} historical candles for {symbol}")
                historical_data_by_timeframe[timeframe] = historical_data
            else:
                logger.warning(f"No {timeframe} historical data found for {symbol}")

        # Distribute to all streamers for this symbol
        for streamer in self.streamers_by_symbol.get(symbol, []):
            # Get the timeframes that this streamer needs
            for timeframe in streamer.required_timeframes:
                if timeframe in historical_data_by_timeframe:
                    # Get historical data for this timeframe
                    candles = historical_data_by_timeframe[timeframe]
                    logger.info(f"Processing {len(candles)} {timeframe} candles for streamer {streamer}")

                    for tick in candles:
                        if not hasattr(tick, 'time_increment'):
                            # Add timeframe information to tick
                            tick.time_increment = timeframe

                        # Process the tick
                        streamer.preprocessor.next_tick(tick)

                        # Process indicators if configured
                        if streamer.indicators:
                            indicator_results, raw_indicators = streamer.indicators.next_tick(streamer.preprocessor)

    def route_chart_data(self, chart_data):
        """Route chart data to appropriate streamers based on symbol and timeframe"""
        # Extract symbol from the chart data
        symbol = chart_data.get('key', '')
        if not symbol or symbol not in self.streamers_by_symbol:
            return

        # Convert chart data to tick
        tick = self._convert_chart_to_tick(chart_data)
        if not tick:
            return

        # Process the tick through all necessary aggregators
        self._process_through_aggregators(symbol, tick)

        # Process the base timeframe tick directly
        self._route_tick_to_streamers(symbol, tick)

    def _convert_chart_to_tick(self, chart_data):
        """Convert chart data to TickData object"""
        from datetime import datetime
        from environments.tick_data import TickData

        try:
            # Extract symbol
            symbol = chart_data.get('key', '')

            # Extract timestamp
            timestamp_ms = int(chart_data.get('7', 0))
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

            # Extract OHLCV data
            open_price = float(chart_data.get('2', 0.0))
            high_price = float(chart_data.get('3', 0.0))
            low_price = float(chart_data.get('4', 0.0))
            close_price = float(chart_data.get('5', 0.0))
            volume = int(chart_data.get('6', 0))

            # Create tick with base timeframe (usually 1m)
            tick = TickData(
                symbol=symbol,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                time_increment="1m"  # Default timeframe for real-time data
            )

            return tick
        except Exception as e:
            logger.error(f"Error converting chart data to tick: {e}")
            return None

    def _process_through_aggregators(self, symbol, tick):
        """Process a tick through all required aggregators"""
        for timeframe, aggregator in self.timeframe_aggregators.items():
            # Process the tick through the aggregator
            current_candle, completed_candle = aggregator.process_tick(tick)

            # If a candle was completed, route it to streamers
            if completed_candle:
                # Add timeframe information to the completed candle
                completed_candle.time_increment = timeframe
                logger.info(f"Completed {timeframe} candle for {symbol} at {completed_candle.timestamp}")

                # Route the completed candle
                self._route_tick_to_streamers(symbol, completed_candle)

    def _route_tick_to_streamers(self, symbol, tick):
        """Route a tick to all appropriate streamers based on symbol and timeframe"""
        time_increment = getattr(tick, 'time_increment', '1m')

        # Find all streamers that need this symbol and timeframe
        for streamer in self.streamers_by_symbol.get(symbol, []):
            # Skip if the streamer doesn't need this symbol
            if symbol not in streamer.configured_symbols:
                continue

            # Skip if the streamer doesn't need this timeframe
            if time_increment not in streamer.required_timeframes:
                continue

            # Process the tick in the streamer
            try:
                # Use the preprocessor to add to history
                streamer.preprocessor.next_tick(tick)

                # Process indicators if available
                if streamer.indicators:
                    indicator_results, raw_indicators = streamer.indicators.next_tick(streamer.preprocessor)

                    # Notify external tools about the results
                    if indicator_results:
                        for external_tool in streamer.external_tool:
                            external_tool.indicator_vector(indicator_results, tick, 0, raw_indicators)

                # Notify about completed candle if this is a complete candle
                is_completed_candle = (hasattr(tick, 'open') and hasattr(tick, 'high') and
                                       hasattr(tick, 'low') and hasattr(tick, 'close'))

                if is_completed_candle:
                    for external_tool in streamer.external_tool:
                        if hasattr(external_tool, 'handle_completed_candle'):
                            external_tool.handle_completed_candle(symbol, tick)

            except Exception as e:
                logger.error(f"Error processing tick for {symbol} in streamer: {e}")