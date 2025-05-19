import logging
from typing import Dict, List
from collections import defaultdict
from data_streamer.candle_aggregator import CandleAggregator

logger = logging.getLogger("StreamingManager")


class StreamingManager:
    """
    Simple streaming manager that:
    1. Maintains mappings between symbols, DataStreamers, and CandleAggregators
    2. Routes PIPs to CandleAggregators
    3. Routes completed candles to the appropriate DataStreamers
    """

    def __init__(self, data_link=None):
        """Initialize with empty mappings and data link"""
        # Mapping of symbols to DataStreamers using defaultdict
        self.streamers_by_symbol = defaultdict(list)

        # Mapping of symbols to timeframe-specific CandleAggregators
        self.aggregators = {}

        # Store data link
        self.data_link = data_link

        # Standard timeframes
        self.standard_timeframes = ["1m", "5m", "15m", "30m", "1h"]

    def register_streamer(self, streamer_id, symbols, monitor_config, model_config):
        """
        Register a DataStreamer with the symbols it needs
        """
        # Import here to avoid circular imports
        from data_streamer.data_streamer import DataStreamer

        # Create streamer
        streamer = DataStreamer(
            data_link=self.data_link,
            model_configuration=model_config,
            indicator_configuration=monitor_config
        )

        # Register streamer for each symbol
        for symbol in symbols:
            # Add streamer to symbol's list
            self.streamers_by_symbol[symbol].append(streamer)

            # Initialize aggregators for this symbol if needed
            if symbol not in self.aggregators:
                self.aggregators[symbol] = {}

                # Create aggregators for all standard timeframes
                for timeframe in self.standard_timeframes:
                    aggregator = CandleAggregator(timeframe)

                    # Register handler for completed candles
                    aggregator.add_candle_handler(
                        lambda s, candle, tf=timeframe: self._route_completed_candle(s, candle, tf)
                    )

                    # Store aggregator
                    self.aggregators[symbol][timeframe] = aggregator

        logger.info(f"Registered streamer {streamer_id} for symbols: {symbols}")
        return streamer

    def route_chart_data(self, chart_data):
        """
        Route chart data to the appropriate aggregators
        """
        # Extract symbol
        symbol = chart_data.get('key')
        if not symbol or symbol not in self.aggregators:
            return

        # Process through all aggregators for this symbol
        for aggregator in self.aggregators[symbol].values():
            aggregator.process_pip(chart_data)

    def _route_completed_candle(self, symbol, candle, timeframe):
        """
        Route a completed candle to all DataStreamers for this symbol
        """
        # Ensure candle has timeframe information
        if not hasattr(candle, 'time_increment'):
            setattr(candle, 'time_increment', timeframe)

        # Get streamers for this symbol
        streamers = self.streamers_by_symbol[symbol]

        # Route candle to all streamers for this symbol
        for streamer in streamers:
            # Simply pass the candle to the streamer's preprocessor
            if hasattr(streamer, 'preprocessor') and hasattr(streamer.preprocessor, 'next_tick'):
                streamer.preprocessor.next_tick(candle)