'''
Spaces in Gymnasium:
Box: AA range of continuous values. eg BoX(0,1,shape(3,3))
Dsicrete : set of items, used for actions
Tuple: tuples of boxes of discrete...
eg Tuple((Discrete(2), Box(0,100,shape=(1,))))


'''

import os
import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.monitor import Monitor
environment_name = 'CartPole-v1'  # Note: Using v1 as it's more common in Gymnasiuenv = gym.make(environment_name, render_mode="human")

# episodes = 5
#
# for episode in range(1, episodes + 1):
#     state, _ = env.reset()
#     done = False
#     truncated = False
#     score = 0
#
#     while not (done or truncated):
#         env.render()
#         action = env.action_space.sample()
#         n_state, reward, done, truncated, info = env.step(action)
#         score += reward
#
#     print('Episode:{} Score:{}'.format(episode, score))
#
# env.close()

# env.action_space to see the type of action space. env.action_space.sample() for a sample
# env.observation_space.sample shows you a tuple of the values regarding cart position, cart veolicty,
# pole angle, pole angular velocity

'''RL Algorithms -> Model Free RL -> Q-Learning -> A2C, PPO, DQN
See https://stable-baselines3.readthedocs.io/en/master/ for which algo to use.
'''

# Training RL model

log_path = os.path.join('Training', 'Logs')
#
# env = gym.make(environment_name)
# env = DummyVecEnv([lambda: env])
# defining our model- Multi layer perceptrons policy: using a NN units.
''' Look into LSTM policies for trading. (stable_baselines2)'''
# model = PPO('MlpPolicy', env, verbose=1, tensorboard_log=log_path)
#
# '''more timesteps when more complicated'''
# model.learn(total_timesteps=100000)
# '''saving model to saved_model folder then reloading it'''
# PPO_path = os.path.join('Training', 'Saved Models', 'PPO_Model_cartpole')
# #
# # model.save(PPO_path)
#
# model= PPO.load(PPO_path, env=env)
#
#
# # Evaluation Metrics: rollout/ ep_len_mean: how long each ep lasted on avg.
# # reward mean: average reward
#
#
# evaluate_policy(model, env, n_eval_episodes=10, render=True)


# Create and wrap the environment
# env = gym.make(environment_name, render_mode="human")
# env = Monitor(env)
# env = DummyVecEnv([lambda: env])
#
# # Train the model (if not already trained)
# model = PPO('MlpPolicy', env, verbose=1)
# model.learn(total_timesteps=100000)
#
# # Save the model
# PPO_path = os.path.join('Training', 'Saved Models', 'PPO_Model_cartpole')
# model.save(PPO_path)
#
# Load the model
# loaded_model = PPO.load(PPO_path, env=env)
#
# # Evaluate the model
# mean_reward, std_reward = evaluate_policy(loaded_model, env, n_eval_episodes=10, render=True)
# print(f"Mean reward: {mean_reward:.2f} +/- {std_reward:.2f}")

# model = PPO.load(PPO_path, env=env)

# episodes=5
# for episode in range(1, episodes + 1):
#     obs = env.reset()
#     done = False
#     truncated = False
#     score = 0
#     while True:
#         action, _states = model.predict(obs)
#         obs, rewards, done, info = env.step(action)
#         env.render()
#         if done:
#             print('info', info)
#             break

# obs = env.reset()
#
# print(model.predict(obs))
#
# env.step(action)
#
# training_log_path = os.path.join(log_path, 'PPO_4')

# In terminal type the below line to open tensorboard:
# $ tensorboard --logdir=/home/warnd/devel/pythonProject/Tutorials/Training/Logs/PPO_6

#Core metrics: Average Reward, Average episode length.
'''Strategies for improvement
Train for longer
Hyperparameter tuning
Try different Algos'''

from stable_baselines3.common.callbacks import EvalCallback, StopTrainingOnRewardThreshold


save_path = os.path.join('Training', 'Saved Models')
log_path = os.path.join('Training', 'Logs')

env = gym.make(environment_name)
env = DummyVecEnv([lambda: env])


stop_callback = StopTrainingOnRewardThreshold(reward_threshold=400, verbose=1)
eval_callback = EvalCallback(env,
                             callback_on_new_best=stop_callback,
                             eval_freq=10000,
                             best_model_save_path=save_path,
                             verbose=1)
#
# model= PPO('MlpPolicy', env,verbose=1, tensorboard_log=log_path)
#
# model.learn(total_timesteps=20000,callback= eval_callback)


#If you want to set up your own custome NN specifications
#
# net_arch= [dict(pi=[128, 128, 128, 128], vf=[128, 128, 128, 128])]
#
# # same as other model loads but passing in the net_arch dictionary for NN specs.
# model = PPO('MlpPolicy', env, verbose = 1, policy_kwargs={'net_arch': net_arch})
# model.learn(total_timesteps=50000,callback=eval_callback)


from stable_baselines3 import DQN
model = DQN('MlpPolicy', env, verbose = 1,tensorboard_log=log_path)

model.learn(total_timesteps=40000)

DQN.load

