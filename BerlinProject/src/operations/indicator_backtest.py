from typing import Dict

import numpy as np

from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData


class IndicatorBacktest(ExternalTool):

    def __init__(self):
        self.cash = 100000
        self.cash_history = []
        self.position = []
        self.target_profit = 1.5
        self.stop_loss = 0.5

        self.indicator_weighted = []



    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        pass

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData) -> None:
        # Do our shit here

        self.cash_history.append(self.cash)
        pass



