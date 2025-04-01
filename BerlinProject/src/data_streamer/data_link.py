from typing import Dict, List, Optional, Tuple, Iterator, Any, Callable
from abc import ABC, abstractmethod
from datetime import datetime
from environments.tick_data import TickData
from logging import logger


class DataLink(ABC):
    """
    Abstract base class for data sources that provide market data.
    Subclasses will implement specific data sources like TickHistoryTools or SchwabDataLink.
    """

    def __init__(self):
        """Initialize the DataLink with empty list of tick handlers."""
        self.tick_handlers: List[Callable[[TickData, int, int], None]] = []

    def register_tick_handler(self, handler: Callable[[TickData, int, int], None]) -> None:
        """
        Register a callback function to handle new tick data.

        Args:
            handler: Function that takes (tick_data, tick_index, day_index) as arguments
        """
        self.tick_handlers.append(handler)

    def notify_handlers(self, tick, tick_index, day_index):
        """Notify registered tick handlers"""
        if not tick:
            return

        logger.info(f"Notifying handlers: {len(self.tick_handlers)} handlers registered")

        for handler in self.tick_handlers:
            try:
                handler(tick, tick_index, day_index)
            except Exception as e:
                logger.error(f"Error in tick handler: {str(e)}", exc_info=True)

    @abstractmethod
    def serve_next_tick(self) -> Iterator[Tuple[TickData, int, int]]:
        """
        Generator method that yields the next tick data along with indices.

        Returns:
            Iterator yielding tuples of (tick_data, tick_index, day_index)
            Returns None when end of data is reached or to signal day boundary
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Returns statistics about the data for normalization purposes.

        Returns:
            Dictionary with statistics about the data (min, max, std for relevant fields)
        """
        pass

    @abstractmethod
    def reset_index(self) -> None:
        """
        Resets the internal index to start data iteration from the beginning.
        """
        pass

    @abstractmethod
    def get_next2(self) -> Optional[TickData]:
        """
        Gets the next tick without using the iterator pattern.
        Used by the DataStreamer's get_next method.

        Returns:
            TickData object or None if no more data
        """
        pass

    def get_present_sample_and_index(self) -> Tuple[dict, int]:
        """
        For sample data, returns the current sample and its index.
        Default implementation returns None, None.

        Returns:
            Tuple of (sample_data, index) or (None, None) if not applicable
        """
        return None, None