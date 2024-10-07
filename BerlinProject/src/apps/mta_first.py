from environments.data_streamer_env import MTAEnv
import gymnasium as gym
from stable_baselines3 import SAC, TD3, A2C, PPO, DQN
import os
import argparse
import torch.nn as nn
import numpy as np
# from environments.reward_callback import RewardCallback
import time


model_config = {
    "feature_vector": [
        {"name": "open"},
        {"name": "close"},
        {"name": "SMA", "parameters": {"sma": 5}}
    ]
}

# Define your data configuration
data_config = [  {
    "profile_id": "6701cbcfbed728701fa3b767",
    "number": 1
  }]

current_time = time.strftime("%Y%m%d-%H%M%S")
log_dir = f"./tensorboard_logs/PPO-{current_time}"


env = MTAEnv(model_config, data_config, reward_model='x')

# Create and train the PPO model
model = PPO('MlpPolicy', env, verbose=1, tensorboard_log=log_dir, device='cuda')

num_episodes = 200
total_timesteps = num_episodes * 390

# Create an instance of RewardCallback
# callback = RewardCallback()

# Pass the callback instance to learn method
model.learn(total_timesteps=total_timesteps)

# Save the trained model
model.save("mta_model_test01_TB")
print("Model saved")


