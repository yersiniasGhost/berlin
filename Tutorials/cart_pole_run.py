from cart_pole_tool import DeepQLearning

import gymnasium as gym

# create environment
env = gym.make('CartPole-v1')

# select the parameters
gamma = 1
# probability parameter for the epsilon-greedy approach
epsilon = 0.1
# number of training episodes
# NOTE HERE THAT AFTER CERTAIN NUMBERS OF EPISODES, WHEN THE PARAMTERS ARE LEARNED
# THE EPISODE WILL BE LONG, AT THAT POINT YOU CAN STOP THE TRAINING PROCESS BY PRESSING CTRL+C
# DO NOT WORRY, THE PARAMETERS WILL BE MEMORIZED
numberEpisodes = 1000

# create an object
LearningQDeep = DeepQLearning(env, gamma, epsilon, numberEpisodes)
# run the learning process
LearningQDeep.trainingEpisodes()
# get the obtained rewards in every episode
rewards = LearningQDeep.sumRewardsEpisode
print("Rewards per episode:", rewards)

#  summarize the model
LearningQDeep.mainNetwork.summary()
# save the model, this is important, since it takes long time to train the model
# and we will need model in another file to visualize the trained model performance
LearningQDeep.mainNetwork.save("trained_model_temp.h5")