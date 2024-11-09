from typing import Dict, Optional, List
from dataclasses import dataclass

import numpy as np

from config.pyobject_id import PyObjectId
from config.types import INDICATOR_COLLECTION
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration
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
    exit_type: Optional[str] = None


class MonitorResultsBacktest(ExternalTool):

    def __init__(self, name: str, monitor: Monitor):
        self.position = []
        self.target_profit = 2
        self.stop_loss = 1
        self.name = name
        self.trade: Optional[Trade] = None
        self.trade_history: List[Trade] = []
        self.monitor = monitor
        self.monitor_value = []
        self.monitor_value_bear = []
        self.cash = 100000
        self.size = float
        self.results = {"success": 0, "fail": 0, "bearish_signal success": 0, "bearish_signal fail": 0}
        self.gains = 0

    def get_total_percent_profits(self) -> float:
        pct = 0.0
        for trade in self.trade_history:
            if trade.exit_price:
                profit = (trade.exit_price - trade.entry_price) / trade.entry_price
                if profit > 0:
                    pct += profit
        return pct

    def get_total_percent_losses(self) -> float:
        pct = 0.0
        for trade in self.trade_history:
            if trade.exit_price:
                loss = -(trade.exit_price - trade.entry_price) / trade.entry_price
                if loss > 0:
                    pct += loss
        return pct

    @classmethod
    def get_indicator_config(cls, indicator_id: PyObjectId) -> MonitorConfiguration:
        """Get indicator config from MongoDB"""
        collection = Mongo().database[INDICATOR_COLLECTION]
        data = collection.find_one({"_id": indicator_id})
        if not data:
            raise ValueError(f"Indicator not found: {indicator_id}")
        return MonitorConfiguration(**data)

    def calculate_trigger(self, indicator_results: Dict[str, float], weights: Dict[str, float]) -> float:
        # indicator results is a dict of (for now) indicator name to the trigger value
        total_weight = 0.0
        trigger = 0.0
        for name, weight in weights.items():
            indicator_value = indicator_results[name]
            trigger += weight * indicator_value
            total_weight += weight

        if total_weight == 0.0:
            return 0.0
        normalized_trigger = trigger / total_weight
        return normalized_trigger

    def indicator_vector(self, indicator_results: Dict[str, float], tick: TickData, index: int) -> None:

        bull_trigger = self.calculate_trigger(indicator_results, self.monitor.triggers)
        self.monitor_value.append(bull_trigger)
        bear_trigger = self.calculate_trigger(indicator_results, self.monitor.bear_triggers)
        self.monitor_value_bear.append(bear_trigger)


        if bull_trigger >= self.monitor.threshold:
            if self.trade is None:
                self.trade = Trade(size=1, entry_price=tick.close, entry_index=index)
                self.size = self.cash / tick.close
                self.cash = 0

        # Hits reward or has bear signals
        if self.trade:

            exit_profit = self.trade.entry_price + ((self.target_profit / 100) * self.trade.entry_price)
            exit_loss = self.trade.entry_price - ((self.stop_loss / 100) * self.trade.entry_price)
            if tick.close >= exit_profit:
                self.trade.exit_price = tick.close
                self.trade.exit_index = index
                self.trade.exit_type = 'success'
                self.trade_history.append(self.trade)
                self.trade = None
                self.cash = self.size * tick.close
                self.size = 0
                self.results['success'] += 1
                self.gains =+ self.get_total_percent_profits()
            elif tick.close <= exit_loss:
                self.trade.exit_price = tick.close
                self.trade.exit_index = index
                self.trade.exit_type = 'fail'
                self.trade_history.append(self.trade)
                self.trade = None
                self.cash = self.size * tick.close
                self.size = 0
                self.results['fail'] += 1
                self.gains =- self.get_total_percent_losses()
            elif bear_trigger >= self.monitor.bear_threshold:
                self.trade.exit_price = tick.close
                self.trade.exit_index = index
                self.trade_history.append(self.trade)
                self.cash = self.size * tick.close
                self.size = 0
                result = "success" if self.trade.exit_price > self.trade.entry_price else "fail"
                self.trade.exit_type = f"bearish_signal {result}"
                self.results[self.trade.exit_type] += 1
                if result == 'success':
                    self.gains =+ self.get_total_percent_profits()
                if result == 'fail':
                    self.gains =- self.get_total_percent_losses()
                self.trade = None
        #     make it a choice if you want to end position at end of day
        if self.trade:
            if tick.close is None:
                self.trade.exit_price = tick.close
                self.trade.exit_index = index



    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        pass
