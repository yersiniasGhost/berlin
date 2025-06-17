import datetime
from typing import Optional, Literal
from dataclasses import dataclass


class TickData:
    """
    Extended TickData class with symbol and time_increment support.
    """

    def __init__(self, open=None, high=None, low=None, close=None, volume=None, timestamp=None, symbol=None, time_increment=None):
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.timestamp = timestamp
        self.symbol = symbol  # Add symbol attribute
        self.time_increment = time_increment
        # Add time_increment attribute with default of "1m"

    def __str__(self):
        return f"{self.symbol} @ {self.timestamp} [{self.time_increment}]: OHLC({self.open},{self.high},{self.low},{self.close}) Vol:{self.volume}"