'''Creating your own custom enviornments'''

import gymnasium as gym
from gymnasium import Env
from gymnasium.spaces import Discrete, Box, Dict, Tuple, MultiBinary, MultiDiscrete
import numpy as np
import random
import os
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import VecFrameStack
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.callbacks import EvalCallback, StopTrainingOnRewardThreshold
from stable_baselines3.common.monitor import Monitor


'''Types of spaces
Discrete: Discrete(3).sample() ... Gives you a value 1-3. If you had an action mapped to
numbers 1-3 (buy, sell, hold) actions for example
Box: Box(0,1, shape(3,3)) ... Gives us an array of random digits 0-1 in a 3x3 matrix. good for continous numbers

Grouping Spaces:
Tuple: ((Discrete(3),Box(0,1, shape(3,3)) Lets us combine types
Dict: Dict({'height':Discrete(2), "speed":Box(0,100, shape=(1,))}).sample() ,
similar to tuple but a dict...

Multibinary: MultiBinary(4) ... 4 0 or 1 values in a list.
MultiDiscrete([5,2,2]) 3 values depending your parameters (0-4,0-1,0-1)'''

# Building an Environment
# Build an agent to give us the best shower possible, Randomly temperature, 37 and 39 degrees

'''Pass env from gymnasium,
 init function
 '''


class ShowerEnv(Env):
    def __init__(self):
        super().__init__()
        self.action_space = Discrete(3)
        self.observation_space = Box(low=np.array([0]), high=np.array([100]), dtype=np.float32)
        self.state = None
        self.shower_length = None
        self.reset()

    def step(self, action):
        self.state += action - 1
        self.shower_length -= 1

        if 37 <= self.state <= 39:
            reward = 1
        else:
            reward = -1

        terminated = self.shower_length <= 0
        truncated = False

        return np.array([self.state], dtype=np.float32), reward, terminated, truncated, {}

    def render(self):
        # Implement rendering if needed
        pass

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.state = 38 + random.randint(-3, 3)
        self.shower_length = 60
        return np.array([self.state], dtype=np.float32), {}  # Return state and an empty info dict

# Create the environment
env = ShowerEnv()

# Set up callbacks
callback_on_best = StopTrainingOnRewardThreshold(reward_threshold=200, verbose=1)
eval_callback = EvalCallback(env,
                             callback_on_new_best=callback_on_best,
                             eval_freq=10000,
                             best_model_save_path='./logs/',
                             verbose=1)

# Test the environment
episodes = 5
for episode in range(1, episodes + 1):
    state, _ = env.reset()
    terminated = truncated = False
    score = 0

    while not (terminated or truncated):
        action = env.action_space.sample()
        state, reward, terminated, truncated, _ = env.step(action)
        score += reward
    print(f'Episode: {episode} Score: {score}')

# Set up and train the model
log_path = os.path.join('Training', 'Logs')
model = PPO("MlpPolicy", env, verbose=1, tensorboard_log=log_path)
model.learn(total_timesteps=100000, callback=eval_callback)


# Save the model
model_path = os.path.join('Training', 'Saved Models', 'PPO_Shower_Model')
model.save(model_path)

# Evaluate the model
mean_reward, std_reward = evaluate_policy(model, env, n_eval_episodes=10, render=False)
print(f"Mean reward: {mean_reward:.2f} +/- {std_reward:.2f}")

# Optional: Load and re-evaluate the model
# loaded_model = PPO.load(model_path, env=env)
# mean_reward, std_reward = evaluate_policy(loaded_model, env, n_eval_episodes=10, render=False)
# print(f"Mean reward (loaded model): {mean_reward:.2f} +/- {std_reward:.2f}")

# env.close()

# tensorboard --logdir=/home/warnd/devel/pythonProject/Tutorials/Training/Logs/PPO_13

