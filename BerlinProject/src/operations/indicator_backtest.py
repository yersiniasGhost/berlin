from typing import Dict, Optional
from dataclasses import dataclass

import numpy as np

from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData


@dataclass
class Trade:
    size: int
    entry_price: float
    entry_index: int
    exit_price: Optional[float] = None
    exit_index: Optional[int] = None


class IndicatorBacktest(ExternalTool):

    def __init__(self, name: str):
        self.position = []
        self.target_profit = 1.5
        self.stop_loss = 0.5
        self.threshold = 1.0
        self.name = name
        self.trade: Optional[Trade] = None
        self.trade_history = []

    # CODE FOR SINGLE INDICATOR
    def indicator_vector(self, indicator: dict[str, float], tick: TickData, index: int) -> None:
        # Do our shit here

        value = indicator.get(self.name, None)
        if value is None:
            raise ValueError('You fucked up')

        if value >= self.threshold:
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
