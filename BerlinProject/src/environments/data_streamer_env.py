import numpy as np
from gymnasium import Env
from gymnasium import spaces
from data_streamer.data_streamer import DataStreamer
from data_preprocessor.data_preprocessor import DataPreprocessor, TickData
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback, EvalCallback


# Figure out how many episodes are in an epoch. Maybe for each full 390 days it goes through or Trade it makes and gets
# out of is an episode. batches of 1000. update the average or total reward and keep going?

# Start by just passing in one single sample to itterate over

class MTAEnv(Env):
    def __init__(self, model_config, data_config):
        self.streamer = DataStreamer(data_config, model_config)
        self.feature_dim = len(model_config["feature_vector"])
        self.action_space = spaces.Discrete(3)  # 0: Buy, 1: Sell, 2: Hold

        obs_dim = self.feature_dim + 1
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )

        self.position = 0
        self.buy_price = 0
        self.episode_reward = 0
        self.episode_count = 0
        self.step_count = 0

        self.reset()

    def _handle_none_values(self, feature_vector):
        if feature_vector is None:
            return [0.0] * self.feature_dim
        return [0.0 if v is None else v for v in feature_vector]

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

    def step(self, action):
        step_reward = 0
        if action == 1:  # Buy
            if self.position == 0:
                self.position = 1
                self.buy_price = self.tick.close
            else:
                step_reward -= 2
        elif action == -1:  # Sell
            if self.position == 1:
                step_reward = (self.tick.close - self.buy_price) * 10 # reward for a good trade
                self.position = 0
            else:
                step_reward -= 2

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

        if done:
            print(f"Episode {self.episode_count} finished, "
                  f"Reward: {self.episode_reward:.2f}, Steps: {self.step_count}")

        return self._get_observation(), step_reward, done, False, info

    def _get_observation(self):
        if self.fv is None:
            return np.append(np.zeros(self.feature_dim), float(self.position)).astype(np.float32)
        return np.append(self.fv, float(self.position)).astype(np.float32)

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
