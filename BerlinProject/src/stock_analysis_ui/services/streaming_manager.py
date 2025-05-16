import logging
from typing import Dict, List, Set, Optional
from data_streamer.data_link import DataLink
from data_streamer.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from environments.tick_data import TickData

logger = logging.getLogger("StreamingManager")


class StreamingManager:
    """
    streaming manager that does ONLY:
    1. Maintain mappings between symbols, timeframes, DataStreamers, and CandleAggregators
    2. Route PIPs to CandleAggregators
    3. Route completed candles to the appropriate DataStreamers

    """

    def __init__(self):
        """Initialize with empty mappings"""
        # Mapping of symbols to DataStreamers
        self.streamers_by_symbol = {}  # {symbol: [streamer1, streamer2, ...]}

        # Mapping of symbols to timeframe-specific CandleAggregators
        self.aggregators = {}  # {symbol: {timeframe: aggregator}}

    #     Use a default dict for streamers_by_symbols

    def register_datastreamer(self, streamer, symbols: List[str], timeframes: Set[str]) -> None:
        """
        Register a DataStreamer with the symbols and timeframes it needs

        Args:
            streamer: DataStreamer instance
            symbols: List of symbols the streamer needs
            timeframes: Set of timeframes the streamer needs
        """
        # Create aggregators for each symbol/timeframe combination
        for symbol in symbols:
            # Initialize symbol entries if needed
            if symbol not in self.streamers_by_symbol:
                self.streamers_by_symbol[symbol] = []

            if symbol not in self.aggregators:
                self.aggregators[symbol] = {}

            # Add streamer to symbol's list
            if streamer not in self.streamers_by_symbol[symbol]:
                self.streamers_by_symbol[symbol].append(streamer)

            # Create needed aggregators
            for timeframe in timeframes:
                if timeframe not in self.aggregators[symbol]:
                    # Create new aggregator
                    aggregator = CandleAggregator(timeframe)

                    # Register handler for completed candles
                    aggregator.add_candle_handler(
                        lambda s, candle: self._route_completed_candle(s, candle, timeframe)
                    )

                    # Store aggregator
                    self.aggregators[symbol][timeframe] = aggregator

    def register_datastreamer_from_config(self, streamer, symbols: List[str], config: MonitorConfiguration) -> None:
        """
        Register a DataStreamer using a MonitorConfiguration to determine timeframes

        Args:
            streamer: DataStreamer instance
            symbols: List of symbols the streamer needs
            config: MonitorConfiguration defining required timeframes
        """
        timeframes = config.get_time_increments()
        self.register_datastreamer(streamer, symbols, timeframes)

    def process_pip(self, pip_data: Dict) -> None:
        """
        Process a PIP data point

        Args:
            pip_data: Dictionary with PIP data
        """
        # Extract symbol
        symbol = pip_data.get('key')
        if not symbol or symbol not in self.aggregators:
            return

        # Process through all aggregators for this symbol
        for aggregator in self.aggregators[symbol].values():
            aggregator.process_pip(pip_data)


    #         2

    def _route_completed_candle(self, symbol: str, candle: TickData, timeframe: str) -> None:
        """
        Route a completed candle to the appropriate DataStreamers

        Args:
            symbol: Symbol for the candle
            candle: The completed candle
            timeframe: Timeframe of the candle
        """
        # Ensure candle has timeframe information
        if not hasattr(candle, 'time_increment'):
            setattr(candle, 'time_increment', timeframe)

        # Get streamers for this symbol
        streamers = self.streamers_by_symbol.get(symbol, [])

        # Route candle to each streamer that needs this timeframe
        for streamer in streamers:
            # Skip if streamer doesn't need this timeframe
            if not hasattr(streamer, 'required_timeframes') or \
                    timeframe not in streamer.required_timeframes:
                continue

            # Process candle through streamer
            self._process_candle_through_streamer(streamer, candle)

    def _process_candle_through_streamer(self, streamer, candle: TickData) -> None:
        """
        Process a candle through a DataStreamer

        Args:
            streamer: DataStreamer to process through
            candle: Candle to process
        """
        # First, add to preprocessor history
        if hasattr(streamer, 'preprocessor') and hasattr(streamer.preprocessor, 'next_tick'):
            streamer.preprocessor.next_tick(candle)

        # Calculate indicators if available
        if hasattr(streamer, 'indicators') and streamer.indicators:
            indicator_results, raw_indicators = streamer.indicators.next_tick(streamer.preprocessor)

            # Notify external tools
            if hasattr(streamer, 'external_tool'):
                for tool in streamer.external_tool:
                    # Send indicator results
                    if hasattr(tool, 'indicator_vector'):
                        history_index = len(streamer.preprocessor.history) - 1 if hasattr(streamer.preprocessor,
                                                                                          'history') else 0
                        tool.indicator_vector(indicator_results, candle, history_index, raw_indicators)

                    # Send completed candle notification
                    if hasattr(tool, 'handle_completed_candle'):
                        tool.handle_completed_candle(candle.symbol, candle)

    def get_aggregators_for_symbol(self, symbol: str) -> Dict[str, CandleAggregator]:
        """
        Get all aggregators for a symbol

        Args:
            symbol: Symbol to get aggregators for

        Returns:
            Dictionary of {timeframe: aggregator}
        """
        return self.aggregators.get(symbol, {})

    def get_aggregator(self, symbol: str, timeframe: str) -> Optional[CandleAggregator]:
        """
        Get a specific aggregator for a symbol and timeframe

        Args:
            symbol: Symbol to get aggregator for
            timeframe: Timeframe to get aggregator for

        Returns:
            CandleAggregator or None if not found
        """
        return self.aggregators.get(symbol, {}).get(timeframe)
