from typing import Optional, List, Dict, Tuple
from models.tick_data import TickData
import logging

logger = logging.getLogger('DataPreprocessor')


class DataPreprocessor:

    def __init__(self, model_config: dict):
        self.model_config = model_config
        self.history: List[TickData] = []
        self.normalized_data: List[TickData] = []
        self.tick: Optional[TickData] = None
        self.normalized_tick: Optional[TickData] = None
        self.sample_stats = None

        # Add dictionaries to track history by timeframe
        self.history_by_timeframe: Dict[str, List[TickData]] = {}
        self.current_tick_by_timeframe: Dict[str, TickData] = {}

    def get_normalized_data(self) -> Tuple[TickData, List[TickData]]:
        return self.normalized_tick, self.normalized_data

    def get_data(self) -> Tuple[TickData, List[TickData]]:
        return self.tick, self.history

    def get_data_by_timeframe(self, timeframe: str) -> Tuple[Optional[TickData], List[TickData]]:
        """
        Get data for a specific timeframe

        Args:
            timeframe: The timeframe to get data for (e.g., "1m", "5m")

        Returns:
            Tuple of (current_tick, history) for the specified timeframe
        """
        current_tick = self.current_tick_by_timeframe.get(timeframe)
        history = self.history_by_timeframe.get(timeframe, [])
        return current_tick, history

    def next_tick(self, tick: TickData):
        """
        Process the next tick and organize it by timeframe

        Args:
            tick: The tick to process
        """
        # Skip duplicate ticks (same symbol and timestamp)
        if self.history and hasattr(tick, 'symbol') and hasattr(tick, 'timestamp'):
            last_tick = self.history[-1]
            if (hasattr(last_tick, 'symbol') and hasattr(last_tick, 'timestamp') and
                    last_tick.symbol == tick.symbol and last_tick.timestamp == tick.timestamp):
                logger.debug(f"Skipping duplicate tick for {tick.symbol} @ {tick.timestamp}")
                return

        # Get the timeframe of the tick (default to "1m")
        timeframe = getattr(tick, 'time_increment', "1m")

        # Ensure we have a list for this timeframe
        if timeframe not in self.history_by_timeframe:
            self.history_by_timeframe[timeframe] = []

        # Add to main history and timeframe-specific history
        self.history.append(tick)
        self.history_by_timeframe[timeframe].append(tick)

        # Update current tick for this timeframe
        self.current_tick_by_timeframe[timeframe] = tick

        # Also update the main current tick (always the most recent one)
        self.tick = tick

        # Perform normalization
        self.normalize_data(tick)

    def normalize_data(self, tick: TickData):
        """
        Normalize data based on model configuration

        Args:
            tick: The tick to normalize
        """
        norm_method = self.model_config.get("normalization", None)
        if norm_method == "min_max":
            if not self.sample_stats:
                raise ValueError("No stats available for normalization")

            close_stats = self.sample_stats['close']
            min_close = close_stats['min']
            max_close = close_stats['max']
            normalized_close = (tick.close - min_close) / (max_close - min_close)
            normalized_open = (tick.open - min_close) / (max_close - min_close)
            normalized_high = (tick.high - min_close) / (max_close - min_close)
            normalized_low = (tick.low - min_close) / (max_close - min_close)

            # Create a normalized version of the tick, preserving timeframe
            normalized_tick = TickData(
                open=normalized_open,
                high=normalized_high,
                low=normalized_low,
                close=normalized_close,
                volume=tick.volume,
                time_increment=getattr(tick, 'time_increment', "1m")  # Preserve timeframe
            )
        else:
            normalized_tick = tick

        self.normalized_data.append(normalized_tick)
        self.normalized_tick = normalized_tick

    def reset_state(self, stats: Dict):
        """
        Reset the state of the preprocessor

        Args:
            stats: Statistics for normalization
        """
        self.history = []
        self.tick = None
        self.normalized_tick = None
        self.sample_stats = stats
        self.normalized_data = []
        self.history_by_timeframe = {}
        self.current_tick_by_timeframe = {}