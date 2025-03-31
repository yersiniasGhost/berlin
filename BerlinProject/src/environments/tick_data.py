import datetime
from typing import Optional
from dataclasses import dataclass


class TickData:
    """
    Extended TickData class with symbol support.
    """

    def __init__(self, open=None, high=None, low=None, close=None, volume=None, timestamp=None, symbol=None):
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.timestamp = timestamp
        self.symbol = symbol  # Add symbol attribute

    def __str__(self):
        return f"{self.symbol} @ {self.timestamp}: OHLC({self.open},{self.high},{self.low},{self.close}) Vol:{self.volume}"