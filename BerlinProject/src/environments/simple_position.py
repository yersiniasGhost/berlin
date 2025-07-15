import numpy as np
from typing import List
from environments.state import State
from models.tick_data import TickData
from config import BUY, SELL, ACTION

HOLD_TIME_LIMIT = 20


class SimplePosition(State):
    def __init__(self, cash_position: float = 100000):
        super().__init__()
        self.cash = cash_position
        self.position = 0
        self.buy_price = 0
        self.initial_cash = cash_position
        self.portfolio: List[float] = [cash_position]
        self.in_position_steps = 0
        self.target_profit = 0.02
        self.lot_size = 10

    def reset(self):
        self.position = 0
        self.portfolio = [self.initial_cash]
        self.buy_price = 0

    # Update our position based upon the trade action (BUY, SELL, HOLD)
    # Calculate the reward for training

    def update_and_calculate_reward(self, action: str, tick: TickData) -> float:
        step_reward = 0
        if action == BUY:  # Buy
            if self.position > 0:
                step_reward = -2.1
        elif action == SELL:  # Sell
            if self.position == 0:
                step_reward = -2000
            else:
                gains = (tick.close - self.buy_price) / self.buy_price
                target = gains / self.target_profit
                step_reward += target * 2.0
        else:
            step_reward += 0.0005

        self.update_portfolio(action, tick)

        # Add in the value of the trade as a function of our target
        if self.position > 0:
            self.in_position_steps += 1
            gains = (tick.close - self.buy_price) / self.buy_price
            target = gains / self.target_profit
            step_reward += target
            if self.in_position_steps > HOLD_TIME_LIMIT:
                step_reward -= 0.1 * (self.in_position_steps-HOLD_TIME_LIMIT)

        return step_reward

    def update_portfolio(self, action: str, tick: TickData):
        if action == BUY:
            self.position += self.lot_size
            self.buy_price = tick.close
            self.cash -= self.buy_price * self.position
        elif action == SELL:
            self.in_position_steps = 0.0
            self.position = 0
            self.cash += self.buy_price * self.position

        self.portfolio.append(self.cash + self.position * tick.close)


    def get_state(self) -> np.array:
        return np.array([self.position]).astype(np.float32)

    def append_state_to_fv(self, feature_vector: np.array, tick: TickData) -> np.array:
        # Append the present position and the position hold times
        hold_time = self.in_position_steps / HOLD_TIME_LIMIT
        position = 1.0 if self.position > 0 else 0.0
        if tick:
            gains = 1.0 - (self.cash + self.position*tick.close) / self.initial_cash
            target = gains / self.target_profit
        else:
            target = 0.0
        state_observation = np.array([position, hold_time, target])
        return np.append(feature_vector, state_observation).astype(np.float32)

    def size(self) -> int:
        return 3

    def make_trade(self, action: ACTION, tick: TickData):
        if action == BUY:
            self.position += self.lot_size
            self.cash -= self.lot_size * tick.close
        elif action == SELL:
            self.position -= self.lot_size
            self.cash += self.lot_size * tick.close
