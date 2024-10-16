from stable_baselines3 import PPO  # or whatever algorithm you used
import numpy as np
from src.config.types import AgentActions
from environments.tick_data import TickData

class RLAgent:
    def __init__(self, saved_model: str, env):
        self.model = PPO.load(saved_model)
        self.env = env

    def get_action(self, observation: np.array) -> AgentActions:
        action, _ = self.model.predict(observation, deterministic=True)
        return self.env.get_trade_action(action)

    def agent_actions(self, fv: np.array, tick: TickData) -> AgentActions:
        observation = self.env._get_observation()
        action = self.get_action(observation)
        return action
