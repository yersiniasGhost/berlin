import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class TickData:
    close: float
    open: float
    high: float
    low: float
    volume: Optional[int] = None
    timestamp: Optional[datetime.datetime] = None
