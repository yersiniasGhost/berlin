from typing import Optional, List, Dict, Tuple
from environments.tick_data import TickData
import traceback
import numpy as np
from features.features import calculate_sma_tick, calculate_macd_tick


class DataPreprocessor:

    def __init__(self, model_config: dict):
        self.model_config = model_config
        self.history: List[TickData] = []
        self.normalized_data: List[TickData] = []
        self.tick: Optional[TickData] = None
        self.normalized_tick: Optional[TickData] = None
        self.sample_stats = None

    def initialize(self, data_link, symbols: List[str], timeframe: str = "1m") -> bool:
        """
        Initialize the preprocessor with historical data for the given symbols.
        Simply loads historical data and sets it as the history.

        Args:
            data_link: The data link to use for loading historical data
            symbols: List of stock symbols to initialize
            timeframe: Candle timeframe (e.g., "1m", "5m")

        Returns:
            bool: Success status
        """
        if not hasattr(data_link, 'load_historical_data'):
            return False

        success = True
        all_historical_ticks = []

        # Load historical data for each symbol
        for symbol in symbols:
            try:
                # Get historical data from data link
                historical_data = data_link.load_historical_data(symbol, timeframe)

                if not historical_data:
                    continue

                # Historical data should already be TickData objects
                all_historical_ticks.extend(historical_data)

            except Exception:
                import traceback
                traceback.print_exc()
                success = False

        # Sort all historical ticks by timestamp
        all_historical_ticks.sort(key=lambda x: x.timestamp)

        if all_historical_ticks:
            self.history = all_historical_ticks

            # Set the current tick to the last one in history
            if all_historical_ticks:
                self.tick = all_historical_ticks[-1]
        else:
            success = False

        return success

    def get_normalized_data(self) -> Tuple[TickData, List[TickData]]:
        return self.normalized_tick, self.normalized_data

    def get_data(self) -> Tuple[TickData, List[TickData]]:
        return self.tick, self.history

    def next_tick(self, tick: TickData):
        # Perform any required normalization on historical data
        # If no normalization use raw tick
        self.history.append(tick)
        self.normalize_data(tick)
        self.tick = tick

    def normalize_data(self, tick: TickData):
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

            normalized_tick = TickData(
                open=normalized_open,
                high=normalized_high,
                low=normalized_low,
                close=normalized_close,
                volume=tick.volume
            )
        else:
            normalized_tick = tick

        self.normalized_data.append(normalized_tick)
        self.normalized_tick = normalized_tick

    def reset_state(self, stats: Dict):
        self.history = []
        self.tick = None
        self.normalized_tick = None
        self.sample_stats = stats
        self.normalized_data = []
