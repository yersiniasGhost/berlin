from .state import State
from data_streamer import TickData
import numpy as np



class SimplePosition(State):
    def __init__(self):
        super().__init__()
        self.position = 0
        self.buy_price = 0

        # def set_reward_model(self, reward_model):
        #     if reward_model == 'x':
        #         self.reward_model = reward_model_x
        #     elif reward_model == 'y':
        #         self.reward_model = reward_model_y
        #     else:
        #         raise ValueError(f"Unknown reward model: {reward_model}")

    def reset(self):
        self.position = 0

    # Update our position based upon the trade action (BUY, SELL, HOLD)
    # Calculate the reward for training
    def update_and_calculate_reward(self, action: str, tick: TickData) -> float:
        step_reward = 0
        if action == "Buy":  # Buy
            if self.position == 0:
                step_reward = 0
                self.position = 1
                self.buy_price = tick.close
            else:
                step_reward = -2
        elif action == "Sell":  # Sell
            if self.position == 1:
                step_reward = tick.close - self.buy_price
                self.position = 0
            else:
                step_reward = -2
        return step_reward

    def get_state(self) -> np.array:
        return np.array([self.position]).astype(np.float32)

    def append_state_to_fv(self, feature_vector: np.array) -> np.array:
        return np.append(feature_vector, float(self.position)).astype(np.float32)

    def size(self) -> int:
        return 1
