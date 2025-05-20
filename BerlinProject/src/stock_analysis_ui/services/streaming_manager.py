import logging
from typing import Dict, List, Tuple
from collections import defaultdict
from data_streamer.candle_aggregator import CandleAggregator

logger = logging.getLogger("StreamingManager")


class StreamingManager:
    """
    Manages multiple DataStreamers and CandleAggregators.
    Routes PIPs to aggregators and completed candles to streamers.
    """

    def __init__(self, data_link=None):
        # Data link for receiving PIPs
        self.data_link = data_link

        # Track DataStreamers by (symbol, timeframe)
        self.streamers_by_symbol_timeframe = defaultdict(list)

        # CandleAggregators nested by symbol then timeframe
        self.aggregators = defaultdict(dict)  # {symbol: {timeframe: CandleAggregator}}

        # Track active symbols and timeframes
        self.active_symbols = set()
        self.active_timeframes = set()

    def register_streamer(self, symbol: str, monitor_config, data_streamer):
        """
        Register a DataStreamer with its symbol and monitor configuration.
        Extract required timeframes from monitor config.
        """
        # Extract timeframes from monitor config indicators
        required_timeframes = self._extract_timeframes_from_config(monitor_config)

        logger.info(f"Registering DataStreamer for {symbol} with timeframes: {required_timeframes}")

        # Add to symbol tracking
        self.active_symbols.add(symbol)

        # Add to (symbol, timeframe) tracking and create aggregators
        for timeframe in required_timeframes:
            # Track streamer for this (symbol, timeframe)
            key = (symbol, timeframe)
            self.streamers_by_symbol_timeframe[key].append(data_streamer)
            self.active_timeframes.add(timeframe)

            # Create aggregator if it doesn't exist
            if timeframe not in self.aggregators[symbol]:
                aggregator = CandleAggregator(symbol, timeframe)
                self.aggregators[symbol][timeframe] = aggregator
                logger.info(f"Created CandleAggregator for {symbol}-{timeframe}")

        return data_streamer

    def _extract_timeframes_from_config(self, monitor_config) -> List[str]:
        """Extract unique timeframes from monitor configuration indicators"""
        timeframes = set()

        # Check if monitor_config has indicators
        if hasattr(monitor_config, 'indicators'):
            for indicator in monitor_config.indicators:
                # Check for time_increment attribute
                if hasattr(indicator, 'time_increment'):
                    timeframes.add(indicator.time_increment)
                else:
                    # Default to 1m if not specified
                    timeframes.add("1m")

        # If no indicators found, default to 1m
        if not timeframes:
            timeframes.add("1m")

        return list(timeframes)

    def route_pip_data(self, pip_data: Dict):
        """
        Route incoming PIP data to all relevant CandleAggregators.
        Handle completed candles returned by aggregators.
        """
        # Extract symbol from PIP
        symbol = pip_data.get('key')
        if not symbol or symbol not in self.active_symbols:
            return

        # Send PIP to all aggregators for this symbol
        if symbol in self.aggregators:
            for timeframe, aggregator in self.aggregators[symbol].items():
                # Process PIP and get any completed candle
                completed_candle = aggregator.process_pip(pip_data)

                # If candle completed, route to appropriate DataStreamers
                if completed_candle:
                    self._handle_completed_candle(symbol, timeframe, completed_candle)

    def _handle_completed_candle(self, symbol: str, timeframe: str, candle):
        """
        Route completed candle to all DataStreamers that need this (symbol, timeframe).
        """
        key = (symbol, timeframe)

        # Get DataStreamers interested in this (symbol, timeframe)
        interested_streamers = self.streamers_by_symbol_timeframe.get(key, [])

        logger.info(f"Routing completed {timeframe} candle for {symbol} to {len(interested_streamers)} DataStreamers")

        # Ensure candle has timestamp
        if not hasattr(candle, 'timestamp') or candle.timestamp is None:
            logger.warning(f"Candle missing timestamp: {candle}")
            return

        # Send candle to each interested DataStreamer
        for data_streamer in interested_streamers:
            try:
                if hasattr(data_streamer, 'preprocessor') and hasattr(data_streamer.preprocessor, 'next_tick'):
                    # Add debug info
                    logger.debug(f"Sending {timeframe} candle to DataStreamer: {candle.timestamp}")

                    # Call next_tick to add to preprocessor
                    data_streamer.preprocessor.next_tick(candle)

                    # Debug indicator processor directly
                    if hasattr(data_streamer, 'indicators') and data_streamer.indicators:
                        try:
                            # Try to explicitly call indicators.next_tick
                            indicator_results, raw_results = data_streamer.indicators.next_tick(
                                data_streamer.preprocessor)

                            if indicator_results:
                                logger.info(f"INDICATOR RESULTS: {symbol} {timeframe} - {indicator_results}")
                            else:
                                logger.debug(f"No indicator results calculated for {symbol} {timeframe}")

                        except Exception as e:
                            logger.error(f"Error calculating indicators: {e}")
                            import traceback
                            traceback.print_exc()
            except Exception as e:
                logger.error(f"Error sending candle to DataStreamer: {e}")
                import traceback
                traceback.print_exc()

    def start_streaming(self):
        """
        Start receiving PIP data from the data link.
        Register this manager as a chart handler.
        """
        if self.data_link:
            # Register as chart data handler
            self.data_link.add_chart_handler(self.route_pip_data)
            logger.info(
                f"Started streaming for {len(self.active_symbols)} symbols and {len(self.active_timeframes)} timeframes")
        else:
            logger.error("No data link configured")

    def stop_streaming(self):
        """Stop streaming and clear handlers"""
        if self.data_link and hasattr(self.data_link, 'chart_handlers'):
            # Remove this manager from chart handlers
            if self.route_pip_data in self.data_link.chart_handlers:
                self.data_link.chart_handlers.remove(self.route_pip_data)

        logger.info("Stopped streaming")

    def get_status(self) -> Dict:
        """Get current status of the streaming manager"""
        return {
            "active_symbols": list(self.active_symbols),
            "active_timeframes": list(self.active_timeframes),
            "total_streamers": len(self.streamers_by_symbol_timeframe),
            "total_aggregators": sum(len(timeframes) for timeframes in self.aggregators.values()),
            "aggregators_by_symbol": {symbol: list(timeframes.keys()) for symbol, timeframes in
                                      self.aggregators.items()}
        }