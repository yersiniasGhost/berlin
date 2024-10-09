from typing import Union
import numpy as np
from gymnasium import Env
from gymnasium import spaces
from data_streamer.data_streamer import DataStreamer
from data_preprocessor.data_preprocessor import DataPreprocessor, TickData
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback, EvalCallback
from environments.reward_models import *


# Figure out how many episodes are in an epoch. Maybe for each full 390 days it goes through or Trade it makes and gets
# out of is an episode. batches of 1000. update the average or total reward and keep going?

# Start by just passing in one single sample to itterate over

#  This environment is changing the observation space thus that it is continuous or has a [0.1, 0.3, 0.6]
# Potential one hot encoding

class MTAEnv(Env):
    def __init__(self, model_config, data_config, reward_model):
        self.streamer = DataStreamer(data_config, model_config)
        self.feature_vector = model_config["feature_vector"]
        self.feature_dim = self._calculate_feature_dim()
        self.model_config = model_config  # Store model_config as an instance variable

        # Initialize action space and action number
        self.action_space_def = model_config["action_space"]
        self.action_defs = self.action_space_def['actions']
        action_type = model_config["action_space"]["type"]
        action_count = len(model_config["action_space"]["actions"])

        if action_type == "Discrete":
            self.action_space = spaces.Discrete(action_count)
        else:
            raise ValueError(f"Unsupported action type: {action_type}")
        # This is where we add more supported action types (continuous, one hot)

        obs_dim = self.feature_dim + 1
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )

        self.position = 0
        self.buy_price = 0
        self.episode_reward = 0
        self.episode_count = 0
        self.step_count = 0

        # Set the reward model
        self.set_reward_model(reward_model)

        self.reset()

    def _calculate_feature_dim(self):
        dim = 0
        for feature in self.feature_vector:
            if feature["name"] == "MACD":
                dim += 3  # MACD, signal, and histogram
            else:
                dim += 1
        return dim

    def _handle_none_values(self, feature_vector):
        if feature_vector is None:
            return [0.0] * self.feature_dim

        handled_vector = []
        for feature, value in zip(self.feature_vector, feature_vector):
            if feature["name"] == "MACD":
                if value is None:
                    handled_vector.extend([0.0, 0.0, 0.0])
                elif isinstance(value, (float, np.float64)):
                    # If MACD returns a single value, extend it with two zeros
                    handled_vector.extend([value, 0.0, 0.0])
                else:
                    # Assume it's an iterable with three values
                    handled_vector.extend(value)
            else:
                handled_vector.append(0.0 if value is None else value)

        return handled_vector

    def set_reward_model(self, reward_model):
        if reward_model == 'x':
            self.reward_model = reward_model_x
        elif reward_model == 'y':
            self.reward_model = reward_model_y
        else:
            raise ValueError(f"Unknown reward model: {reward_model}")

    def reset(self, seed=None, options=None):
        self.streamer.reset()
        self.fv, self.tick = self.streamer.get_next()
        self.fv = self._handle_none_values(self.fv)

        self.position = 0
        self.buy_price = 0
        self.episode_reward = 0
        self.step_count = 0

        self.episode_count += 1
        print(f"Starting new episode {self.episode_count}")
        return self._get_observation(), {}


    # TO be refeactored for backtest use etc.
    def get_trade_action(self, action: Union[float, np.array]) -> str:
        # For the given configuration, determine the Bue/Sell/Hold trade action
        # for the given model action space
        if self.action_space_def['type'] == "Discrete":
            return self.action_defs[str(action)]

        raise ValueError(f"Undefined trade action configuration {action}")


    def step(self, action: Union[float, np.array]):
        old_position = self.position
        old_buy_price = self.buy_price
        old_close = self.tick.close if self.tick else None

        trade_action = self.get_trade_action(action)
        # Calculate reward using the selected reward model
        step_reward = self.reward_model(self.position, action, self.tick, self.buy_price)

        # Update position and buy price
        if trade_action == "Buy":
            if self.position == 0:
                self.position = 1
                self.buy_price = self.tick.close
        elif trade_action == "Sell":  # Sell
            if self.position == 1:
                self.position = 0

        self.episode_reward += step_reward
        self.step_count += 1

        # Get next observation
        self.fv, self.tick = self.streamer.get_next()
        done = self.fv is None

        if not done:
            self.fv = self._handle_none_values(self.fv)

        info = {
            "position": self.position,
            "buy_price": self.buy_price,
            "episode_reward": self.episode_reward,
            "step_count": self.step_count
        }


        #
        # Print step information
        print(f"Step: {self.step_count}")
        print(f"Action: {trade_action}")
        print(f"Old Position: {old_position}, New Position: {self.position}")
        print(f"Old Close: {old_close}, New Close: {self.tick.close if self.tick else None}")
        print(f"Old Buy Price: {old_buy_price}, New Buy Price: {self.buy_price}")
        print(f"Step Reward: {step_reward}")
        print(f"Episode Reward: {self.episode_reward}")
        print(f"Feature Vector: {self.fv}")
        print("-------------------")

        if done:
            print(f"Episode {self.episode_count} finished, "
                  f"Reward: {self.episode_reward:.2f}, Steps: {self.step_count}")

        return self._get_observation(), step_reward, done, False, info

    def _get_observation(self):
        if self.fv is None:
            return np.append(np.zeros(self.feature_dim), float(self.position)).astype(np.float32)
        handled_fv = self._handle_none_values(self.fv)
        return np.append(handled_fv, float(self.position)).astype(np.float32)

    def render(self):
        print(f"Close: {self.tick.close if self.tick else None}, "
              f"Position: {self.position}, "
              f"Buy Price: {self.buy_price:.2f}, Episode Reward: {self.episode_reward:.2f}")

    #  For action space, probably still buy sell hold to start
    # Observation space will be streaming in the feature vectors we calculate e.g. [sma,high,low,close,open]

    # When a sample runs through all 390 time steps or when we have bought and sold the episode ends?
    # we are recording what step we are on, prices, has sold/ has bought. buy/sell price for reward calc.

    # We Choose 1000 samples for each sample we run through one episode, have the reward calculated. Then when the
    # sample ends we start on the next one and when all 1000 are done we run through them again with our updated info
