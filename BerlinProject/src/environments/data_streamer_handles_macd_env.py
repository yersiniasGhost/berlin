from typing import Union
import numpy as np
from gymnasium import Env
from gymnasium import spaces
from data_streamer.data_streamer import DataStreamer
from environments.simple_position import SimplePosition
from environments.inout_position import InoutPosition, IN, OUT

# Figure out how many episodes are in an epoch. Maybe for each full 390 days it goes through or Trade it makes and gets
# out of is an episode. batches of 1000. update the average or total reward and keep going?

# Start by just passing in one single sample to itterate over

#  This environment is changing the observation space thus that it is continuous or has a [0.1, 0.3, 0.6]
# Potential one hot encoding

class MTAEnv(Env):
    def __init__(self, model_config, data_config, reward_model):
        self.streamer = DataStreamer(data_config, model_config)
        self.feature_vector = model_config["feature_vector"]
        self.feature_dim = model_config["feature_vector_dim"]
        self.model_config = model_config  # Store model_config as an instance variable

        # Initialize action space and action number
        self.action_space_def = model_config["action_space"]
        self.action_defs = self.action_space_def['actions']
        action_type = model_config["action_space"]["type"]
        action_count = len(model_config["action_space"]["actions"])

        # The gym model queries the action space of the environment
        if action_type == "Discrete":
            self.action_space = spaces.Discrete(action_count)
        elif action_type == "NormalBox":
            # TODO:  Decide how to add action defintions
            action_count = 1
            self.action_space = spaces.Box(low=0, high=1, shape=(action_count,), dtype=np.float32)

        else:
            raise ValueError(f"Unsupported action type: {action_type}")
        # This is where we add more supported action types (continuous, one hot)

        # Get the name of the state class in the model configuration
        # for now using SimplePosition
        # TODO:  Make this dynamic.  Move to common code so Runtime analytics can use it
        self.state = InoutPosition()
        # self.state = SimplePosition()
        obs_dim = self.feature_dim + self.state.size()
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )

        self.episode_reward = 0
        self.episode_count = 0
        self.step_count = 0
        self.reset()

    def _handle_none_values(self, feature_vector) -> np.array:
        output = []
        for f in feature_vector:
            if f is None:
                output.append(0.0)
            else:
                output.append(f)
        return np.array(output)





    def reset(self, seed=None, options=None):
        self.streamer.reset()
        self.fv, self.tick = self.streamer.get_next()
        self.fv = self._handle_none_values(self.fv)

        self.state.reset()
        self.episode_reward = 0
        self.step_count = 0

        self.episode_count += 1
        print(f"*****************\nStarting new episode {self.episode_count}")
        return self._get_observation(), {}



    # TODO:  Refactor this code into the State?
    def get_trade_action(self, action: Union[float, np.array]) -> str:
        # For the given configuration, determine the Bue/Sell/Hold trade action
        # for the given model action space
        if self.action_space_def['type'] == "Discrete":
            return self.action_defs[str(action)]
        elif self.action_space_def['type'] == "NormalBox":
            return IN if action <= 0.5 else OUT
        raise ValueError(f"Undefined trade action configuration {action}")

    def step(self, action: Union[float, np.array]):
        # old_position = self.position
        # old_buy_price = self.buy_price
        # old_close = self.tick.close if self.tick else None

        trade_action = self.get_trade_action(action)
        # Calculate reward using the selected reward model
        step_reward = self.state.update_and_calculate_reward(trade_action, self.tick)
#        step_reward = self.reward_model(self.position, action, self.tick, self.buy_price)
        self.episode_reward += step_reward
        self.step_count += 1

        # Get next observation
        self.fv, self.tick = self.streamer.get_next()
        done = self.tick == None or step_reward < -1000

        if not done:
            self.fv = self._handle_none_values(self.fv)

        info = {
            "position": self.state.position,
            "buy_price": self.state.buy_price,
            "episode_reward": self.episode_reward,
            "step_count": self.step_count
        }


        #
        # Print step information
        print(f"{self.episode_count}\t{self.step_count}\t{self.episode_reward:.3f}\t{step_reward:.4f}\t{trade_action}")
        # print(f"Step Reward: {step_reward}")
        # print(f"Episode Reward: {self.episode_reward}")
        # print("-------------------")

        if done:
            print(f"Episode {self.episode_count} finished, "
                  f"Reward: {self.episode_reward:.2f}, Steps: {self.step_count}")

        return self._get_observation(), step_reward, done, False, info

    def _get_observation(self):
        if self.fv is None:
            handled_fv = np.zeros(self.feature_dim)
        else:
            handled_fv = self._handle_none_values(self.fv)
        return self.state.append_state_to_fv(handled_fv, self.tick)
        # return np.append(handled_fv, float(self.position)).astype(np.float32)

    def render(self):
        print(f"Close: {self.tick.close if self.tick else None}, "
              f"Position: {self.state.position}, "
              f"Buy Price: {self.state.buy_price:.2f}, Episode Reward: {self.episode_reward:.2f}")

    #  For action space, probably still buy sell hold to start
    # Observation space will be streaming in the feature vectors we calculate e.g. [sma,high,low,close,open]

    # When a sample runs through all 390 time steps or when we have bought and sold the episode ends?
    # we are recording what step we are on, prices, has sold/ has bought. buy/sell price for reward calc.

    # We Choose 1000 samples for each sample we run through one episode, have the reward calculated. Then when the
    # sample ends we start on the next one and when all 1000 are done we run through them again with our updated info
