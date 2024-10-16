from typing import List, Union
import random
from src.config.types import AgentActions
from environments.tick_data import TickData


class Backtester:
    def __init__(self, mode: str = "rl_agent", random_trade: float = 0.01):
        self.mode: str = mode
        self.tick_count: int = 0
        self.position: int = 0
        self.random_trade = random_trade
        self.cash = 100000.0
        self.trade_size = 10
        self.portfolio = [self.cash]

    def agent_actions(self, actions: List[Union[AgentActions, str]], tick: TickData):
        if self.mode == "random_trader":
            if random.random() < self.random_trade:
                action = "Buy" if self.position == 0 else "Sell"
                self.make_trade(action, tick)
        elif self.mode == "rl_agent":
            action = actions[0]  # Assuming single agent for simplicity
            self.make_trade(action, tick)

        self.update_portfolio(tick)

    def make_trade(self, action: Union[AgentActions, str], tick: TickData):
        if isinstance(action, AgentActions):
            action = action.value

        if action == "Buy":
            self.position += self.trade_size
            self.cash -= self.trade_size * tick.close
        elif action == "Sell":
            self.position -= self.trade_size
            self.cash += self.trade_size * tick.close

    def update_portfolio(self, tick: TickData):
        self.portfolio.append(self.cash + self.position * tick.close)
