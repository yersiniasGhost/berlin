
import gymnasium as gym
from stable_baselines3 import PPO, TD3, SAC
from stable_baselines3.common.vec_env import VecFrameStack, DummyVecEnv
from stable_baselines3.common.evaluation import evaluate_policy
import os
from stable_baselines3.common.monitor import Monitor

environment_name = "CarRacing-v2"
#
# env=gym.make(environment_name, render_mode='human')

# episodes = 5
#
# for episode in range(1, episodes + 1):
#     state, _ = env.reset()
#     terminated = truncated = False
#     score = 0
#
#     while not (terminated or truncated):
#         # Render is called automatically because we set render_mode="human"
#         action = env.action_space.sample()
#         state, reward, terminated, truncated, info = env.step(action)
#         score += reward
#
#     print('Episode:{} Score:{}'.format(episode, score))
#
# env.close()






'''Training Model!'''
'''For game, winning is getting 900+ score everytime.
Points for getting to end tile in quicker times.'''

# # $ tensorboard --logdir=/home/warnd/devel/pythonProject/Tutorials/Training/Logs/TD3_1
'''Training Process: Instantiate the env, create env, vectroize env if need be,
set up model, train model'''

env = gym.make(environment_name, render_mode="human")
env = Monitor(env)
env = DummyVecEnv([lambda: env])
#
# # log_path = os.path.join('Training', 'Logs')
# #
# # model = PPO("CnnPolicy", env, verbose=1, tensorboard_log=log_path)
# #
# # model.learn(total_timesteps=400000)
#
# ppo_path= os.path.join('Training', 'Saved Models', 'PPO_Driving_Model')
#
# # model.save(ppo_path)
#
# model=PPO.load(ppo_path, env)
#
# evaluate_policy(model, env,n_eval_episodes=10, render=True)


'''TESTING OUT TD3 instead of PPO'''
#
# env = gym.make(environment_name, render_mode="human")
# env = Monitor(env)
# env = DummyVecEnv([lambda: env])

# log_path = os.path.join('Training', 'Logs')
#
# model = TD3("CnnPolicy", env, verbose=1, tensorboard_log=log_path)
#
# model.learn(total_timesteps=400000)
#
# td3_path= os.path.join('Training', 'Saved Models', 'TD3_Driving_Model')
# #
# # model.save(td3_path)
#
# model=TD3.load(td3_path, env)
#
# evaluate_policy(model, env,n_eval_episodes=10, render=True)


