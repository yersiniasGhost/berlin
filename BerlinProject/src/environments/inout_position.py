from typing import Optional
import numpy as np
from typing import List
from .state import State
from environments.tick_data import TickData
from config import IN, OUT, ACTION

HOLD_TIME_LIMIT = 20


# class InoutPosition(State):
#     def __init__(self, cash_position: float = 100000):
#         super().__init__()
#         self.cash = cash_position
#         self.position = 0
#         self.buy_price = 0
#         self.last_trade: Optional[float] = None
#         self.initial_cash = cash_position
#         self.portfolio: List[float] = [cash_position]
#         self.in_position_steps = 0
#         self.out_position_steps = 0
#         self.target_profit = 0.02
#         self.lot_size = 10
#         self.num_trades = 0
#         self.local_high = 0
#
#     def reset(self):
#         self.position = 0
#         self.portfolio = [self.initial_cash]
#         self.buy_price, self.local_high = 0, 0
#         self.last_trade = None
#         self.num_trades = 0
#         self.in_position_steps, self.out_position_steps = 0, 0
#
#     # Update our position based upon the trade action (BUY, SELL, HOLD)
#     # Calculate the reward for training
#     def update_and_calculate_reward(self, action: str, tick: TickData) -> float:
#         step_reward = 0
#         self.update_portfolio(action, tick)
#         if not self.last_trade:
#             self.last_trade = tick.close
#
#         # Calculate position value change
#         if self.position > 0:
#             value_change = (tick.close - self.buy_price) / self.buy_price
#         else:
#             value_change = (self.last_trade - tick.close) / self.last_trade
#
#         # Reward based on value change
#         step_reward += value_change * 100  # Scale factor can be adjusted
#
#         # Try to reward a sale.
#         if (self.position == 0 and self.in_position_steps > 2):
#             step_reward += value_change * 1000
#
#         # Penalize frequent trading
#         if (self.position > 0 and self.out_position_steps == 1) or \
#                 (self.position == 0 and self.in_position_steps <= 3):
#             step_reward -= 0.5  # Smaller penalty, can be adjusted
#
#         # Reward for holding profitable positions
#         if self.position > 0 and value_change > 0:
#             step_reward += 0.1 * self.in_position_steps  # Incremental reward for holding
#
#         # Penalize for holding losing positions
#         if self.position > 0 and value_change < 0:
#             step_reward -= 0.2 * self.in_position_steps  # Incremental penalty for holding
#
#         # Update state variables
#         if self.position > 0:
#             self.in_position_steps += 1
#             self.out_position_steps = 0
#             if tick.close > self.local_high:
#                 self.local_high = tick.close
#         else:
#             self.in_position_steps = 0
#             self.out_position_steps += 1
#         return step_reward
#
#
#     def update_and_calculate_reward2(self, action: str, tick: TickData) -> float:
#         step_reward = 0
#         self.update_portfolio(action, tick)
#         if not self.last_trade:
#             self.last_trade = tick.close
#
#         # Add in the value of the trade as a function of our target
#         if self.position > 0:
#             if tick.close > self.local_high:
#                 self.local_high = tick.close
#             if self.out_position_steps == 1:
#                 step_reward -= 10000
#             self.in_position_steps += 1
#             self.out_position_steps = 0
#             gains = (tick.close - self.buy_price) / self.buy_price
#             target = gains / self.target_profit
#             if target < -1.0:
#                 step_reward -= 10000
#             step_reward += target
#             if self.in_position_steps == 1:
#                 step_reward += 1.0
#             # if self.in_position_steps > HOLD_TIME_LIMIT:
#             #     step_reward -= 0.1 * (self.in_position_steps-HOLD_TIME_LIMIT)
#         else:
#             if self.in_position_steps == 1:
#                 step_reward -= 10000.0
#             if self.in_position_steps > 2:
#                 gains = (tick.close - self.buy_price) / self.buy_price
#                 target = gains / self.target_profit
#                 step_reward += target * 100.0
#             else:
#                 avoided = -1.0 * (tick.close - self.last_trade) / self.last_trade
#                 avoided_target = avoided / (self.target_profit * 2)
#                 step_reward += avoided_target
#             self.in_position_steps = 0
#             self.out_position_steps += 1
#
#         if self.num_trades > 50:
#             step_reward = -2000.0
#         if step_reward < -20 and step_reward > -500:
#             print('here')
#         return step_reward
#
#     def update_portfolio(self, action: str, tick: TickData):
#         if action == IN:
#             if self.position == 0:
#                 self.num_trades += 1
#                 self.position += self.lot_size
#                 self.buy_price = tick.close
#                 self.last_trade = tick.close
#                 self.cash -= self.buy_price * self.position
#         elif action == OUT:
#             if self.position > 0:
#                 self.num_trades += 1
#                 self.cash += tick.close * self.position
#                 self.position = 0
#                 self.last_trade = tick.close
#
#         self.portfolio.append(self.cash + self.position * tick.close)
#
#
#     def get_state(self) -> np.array:
#         return np.array([self.position]).astype(np.float32)
#
#     def append_state_to_fv(self, feature_vector: np.array, tick: TickData) -> np.array:
#         # Append the present position and the position hold times
#         hold_time = self.in_position_steps / HOLD_TIME_LIMIT
#         position = 1.0 if self.position > 0 else 0.0
#         if tick:
#             gains = 1.0 - (self.cash + self.position*tick.close) / self.initial_cash
#             target = gains / self.target_profit
#         else:
#             target = 0.0
#         state_observation = np.array([position, hold_time, target])
#         return np.append(feature_vector, state_observation).astype(np.float32)
#
#     def size(self) -> int:
#         return 3

    # def make_trade(self, action: ACTION, tick: TickData):
    #     if action == BUY:
    #         self.position += self.trade_size
    #         self.cash -= self.trade_size * tick.close
    #     elif action == SELL:
    #         self.position -= self.trade_size
    #         self.cash += self.trade_size * tick.close

class InoutPosition(State):
    def __init__(self, cash_position: float = 100000):
        super().__init__()
        self.cash = cash_position
        self.position = 0
        self.buy_price = 0
        self.last_trade: Optional[float] = None
        self.initial_cash = cash_position
        self.portfolio: List[float] = [cash_position]
        self.in_position_steps = 0
        self.out_position_steps = 0
        self.target_profit = 0.02
        self.lot_size = 10
        self.num_trades = 0
        self.local_high = 0
        self.unrealized_profit = 0

    def reset(self):
        self.position = 0
        self.portfolio = [self.initial_cash]
        self.buy_price, self.local_high = 0, 0
        self.last_trade = None
        self.num_trades = 0
        self.in_position_steps, self.out_position_steps = 0, 0
        self.unrealized_profit = 0

    def update_and_calculate_reward(self, action: str, tick: TickData) -> float:
        old_position = self.position
        self.update_portfolio(action, tick)

        step_reward = 0

        if not self.last_trade:
            self.last_trade = tick.close

        # Calculate position value change
        if self.position > 0:
            self.unrealized_profit = (tick.close - self.buy_price) * self.position
        else:
            self.unrealized_profit = 0

        # Reward only when exiting a position
        if old_position > 0 and self.position == 0:
            realized_profit = (tick.close - self.buy_price) * old_position
            step_reward = realized_profit

        # Update state variables
        if self.position > 0:
            self.in_position_steps += 1
            self.out_position_steps = 0
            if tick.close > self.local_high:
                self.local_high = tick.close
        else:
            self.in_position_steps = 0
            self.out_position_steps += 1

        return step_reward

    def update_portfolio(self, action: str, tick: TickData):
        if action == IN:
            if self.position == 0:
                self.num_trades += 1
                self.position += self.lot_size
                self.buy_price = tick.close
                self.last_trade = tick.close
                self.cash -= self.buy_price * self.position
        elif action == OUT:
            if self.position > 0:
                self.num_trades += 1
                self.cash += tick.close * self.position
                self.position = 0
                self.last_trade = tick.close

        self.portfolio.append(self.cash + self.position * tick.close)

    def get_state(self) -> np.array:
        return np.array([self.position]).astype(np.float32)

    def append_state_to_fv(self, feature_vector: np.array, tick: TickData) -> np.array:
        hold_time = self.in_position_steps / HOLD_TIME_LIMIT
        position = 1.0 if self.position > 0 else 0.0
        if tick and self.position > 0:
            unrealized_profit_pct = self.unrealized_profit / (self.buy_price * self.position)
            target = unrealized_profit_pct / self.target_profit
        else:
            target = 0.0
        state_observation = np.array([position, hold_time, target])
        return np.append(feature_vector, state_observation).astype(np.float32)

    def size(self) -> int:
        return 3

    # def make_trade(self, action: ACTION, tick: TickData):
    #     if action == BUY:
    #         self.position += self.trade_size
    #         self.cash -= self.trade_size * tick.close
    #     elif action == SELL:
    #         self.position -= self.trade_size
    #         self.cash += self.trade_size * tick.close

