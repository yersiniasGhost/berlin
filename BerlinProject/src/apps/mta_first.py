from environments.data_streamer_env import MTAEnv
import gymnasium as gym
from stable_baselines3 import SAC, TD3, A2C, PPO, DQN
import os
import argparse
import torch.nn as nn
import numpy as np
from environments.reward_callback import RewardCallback


model_config = {
    "feature_vector": [
        {"name": "open"},
        {"name": "close"},
        {"name": "SMA", "parameters": {"sma": 5}}
    ]
}

# Define your data configuration
data_config = [
    {
        "profile_id": "66f33390175e7d95b66bf9cf",
        "number": 3  # Number of samples to use
    }
]

env = MTAEnv(model_config, data_config)

# Create and train the PPO model
model = PPO('MlpPolicy', env, verbose=1, device='cuda')

num_episodes = 100
total_timesteps = num_episodes * 390

# Create an instance of RewardCallback
callback = RewardCallback()

# Pass the callback instance to learn method
model.learn(total_timesteps=total_timesteps, callback=callback)

# Save the trained model
model.save("mta_model_test01")
print("Model saved")


