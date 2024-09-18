from typing import List
import random

from src.config.types import AgentActions
from src.data_streamer.tick_data import TickData

RANDOM_TRADER = "random"
BUY = 1
SELL = -1
ACTION = int


class Backtester:

    def __init__(self, mode: str = RANDOM_TRADER, random_trade: float = 0.01):
        self.mode: str = mode
        self.tick_count: int = 0
        self.position: int = 0

        self.random_trade = random_trade
        self.cash = 100000.0
        self.trade_size = 10
        self.portfolio = [self.cash]


    def agent_actions(self, actions: List[AgentActions], tick: TickData):
        if self.mode == RANDOM_TRADER:
            if random.random() < self.random_trade:
                action = BUY if self.position == 0 else SELL
                self.make_trade(action, tick)

        self.update_portfolio(tick)


    def make_trade(self, action: ACTION, tick: TickData):
        if action == BUY:
            self.position += self.trade_size
            self.cash -= self.trade_size * tick.close
        else:
            self.position -= self.trade_size
            self.cash += self.trade_size * tick.close


    def update_portfolio(self, tick: TickData):
        self.portfolio.append(self.cash + self.position * tick.close)
