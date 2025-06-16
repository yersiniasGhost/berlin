from typing import Dict, List
from abc import ABC
from collections import defaultdict
from models.tick_data import TickData
from data_streamer.data_streamer import DataStreamer



class DataLink(ABC):
    """
    Abstract base class for data sources that provide market data.
    Subclasses will implement specific data sources like TickHistoryTools or SchwabDataLink.
    """

    def __init__(self):
        self.data_streamers: Dict[str, List[DataStreamer]] = defaultdict(list)
        """Initialize the DataLink with empty list of tick handlers."""
        # self.tick_handlers: List[Callable[[TickData, int, int], None]] = []
        # self.quote_handlers: List[Callable[[Dict], None]] =[]
        # self.chart_handlers: List[Callable[[Dict], None]] =[]

    def add_data_streamer(self, symbol: str, data_streamer: DataStreamer):
        self.data_streamers[symbol].append(data_streamer)
    #
    # def add_quote_handler(self, handler: Callable[[Dict], None]) -> None:
    #     self.quote_handlers.append(handler)
    #
    # def add_chart_handler(self, handler: Callable[[Dict], None]) -> None:
    #     self.chart_handlers.append(handler)
    #
    # def register_tick_handler(self, handler: Callable[[TickData, int, int], None]) -> None:
    #     self.tick_handlers.append(handler)
    #
    # # In src/data_streamer/data_link.py, enhance notify_handlers
    #
    # def notify_handlers(self, tick, tick_index, day_index):
    #     """Notify registered tick handlers"""
    #     if not tick:
    #         return
    #
    #     for handler in self.tick_handlers:
    #         try:
    #             handler(tick, tick_index, day_index)
    #         except Exception:
    #             import traceback
    #             traceback.print_exc()

    # @abstractmethod
    # def serve_next_tick(self) -> Iterator[Tuple[TickData, int, int]]:
    #     """
    #     Generator method that yields the next tick data along with indices.
    #
    #     Returns:
    #         Iterator yielding tuples of (tick_data, tick_index, day_index)
    #         Returns None when end of data is reached or to signal day boundary
    #     """
    #     pass
    #
    # @abstractmethod
    # def get_stats(self) -> Dict[str, Dict[str, float]]:
    #     """
    #     Returns statistics about the data for normalization purposes.
    #
    #     Returns:
    #         Dictionary with statistics about the data (min, max, std for relevant fields)
    #     """
    #     pass
    #
    # @abstractmethod
    # def reset_index(self) -> None:
    #     """
    #     Resets the internal index to start data iteration from the beginning.
    #     """
    #     pass
    #
    # @abstractmethod
    # def get_next2(self) -> Optional[TickData]:
    #     """
    #     Gets the next tick without using the iterator pattern.
    #     Used by the DataStreamer's get_next method.
    #
    #     Returns:
    #         TickData object or None if no more data
    #     """
    #     pass
    #
    # def get_present_sample_and_index(self) -> Tuple[dict, int]:
    #     """
    #     For sample data, returns the current sample and its index.
    #     Default implementation returns None, None.
    #
    #     Returns:
    #         Tuple of (sample_data, index) or (None, None) if not applicable
    #     """
    #     return None, None

    def load_historical_data(self, symbol: str, timeframe: str = "1m") -> List[TickData]:
        pass

