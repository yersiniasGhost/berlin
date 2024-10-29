from typing import Dict, Optional
from dataclasses import dataclass

import numpy as np
import talib

from config.pyobject_id import PyObjectId
from config.types import INDICATOR_COLLECTION
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models import IndicatorConfiguration
from models.monitor_model import Monitor
from mongo_tools.mongo import Mongo

# TODO: Add day to tickdata so it can query and know what day it is on for backtesting and resetting indicator values
@dataclass
class Trade:
    size: int
    entry_price: float
    entry_index: int
    exit_price: Optional[float] = None
    exit_index: Optional[int] = None


class MonitorBacktest(ExternalTool):

    def __init__(self, name: str, monitor: Monitor):
        self.position = []
        self.target_profit = 1.0
        self.stop_loss = 0.5
        self.name = name
        self.trade: Optional[Trade] = None
        self.trade_history = []
        self.monitor = monitor
        self.monitor_value = []

    @classmethod
    def get_indicator_config(cls, indicator_id: PyObjectId) -> IndicatorConfiguration:
        """Get indicator config from MongoDB"""
        collection = Mongo().database[INDICATOR_COLLECTION]
        data = collection.find_one({"_id": indicator_id})
        if not data:
            raise ValueError(f"Indicator not found: {indicator_id}")
        return IndicatorConfiguration(**data)

    def indicator_vector(self, indicator_results: Dict[str, float], tick: TickData, index: int) -> None:

        # indicator results is a dict of (for now) indicator name to the trigger value
        total_weight = 0.0
        trigger = 0.0
        for t_name, t_value in indicator_results.items():
            # find our trigger in our monitor:
            weight = self.monitor.triggers[t_name]
            trigger += weight * t_value
            total_weight += weight
        normalized_trigger = trigger / total_weight
        self.monitor_value.append(normalized_trigger)

        if normalized_trigger >= self.monitor.threshold:
            if self.trade is None:
                self.trade = Trade(size=1, entry_price=tick.close, entry_index=index)

        # Hits reward
        if self.trade:
            exit_profit = self.trade.entry_price + ((self.target_profit / 100) * self.trade.entry_price)
            exit_loss = self.trade.entry_price - ((self.stop_loss / 100) * self.trade.entry_price)
            if tick.close >= exit_profit or tick.close <= exit_loss:
                self.trade.exit_price = tick.close
                self.trade.exit_index = index
                self.trade_history.append(self.trade)
                self.trade = None

    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        pass
