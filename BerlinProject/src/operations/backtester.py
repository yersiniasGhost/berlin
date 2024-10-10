from typing import List
import random

from src.config.types import AgentActions
from src.data_streamer.tick_data import TickData

RANDOM_TRADER = "random"
MODEL_AGENT = "rl_agent"
BUY = 0, 'buy'
SELL = 1, 'sell'
HOLD = 2, 'hold'
ACTION = int



class Backtester:

    def __init__(self, ):
        self.tick_count: int = 0
        self.position: int = 0

        self.random_trade = 0.1
        self.cash = 100000.0
        self.trade_size = 10
        self.portfolio = [self.cash]


    def agent_actions(self, actions: List[AgentActions], tick: TickData):
        # This is the entry point that the
        # if self.mode == RANDOM_TRADER:
        #     if random.random() < self.random_trade:
        #         action = BUY if self.position == 0 else SELL
        #         self.make_trade(action, tick)

        # elif self.mode == MODEL_AGENT:
        #     action = actions  # Assuming single agent for simplicity
        #     self.make_trade(action, tick)

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
