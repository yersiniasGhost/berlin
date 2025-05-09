from stable_baselines3 import PPO, DQN
import time
from environments.mta_env import *
from environments.custom_networks import CustomNetwork

num_samples = 2


# Defining models

profile_data = [{
    "profile_id": "6701cbcfbed728701fa3b767",
    "number": num_samples
}]


prof_data_2 = [
  {
    "profile_id": "670d98445c9ef9a75c7281d9",
    "number": num_samples
  },
  {
    "profile_id": "670d98f95c9ef9a75c7281de",
    "number": num_samples
  }
]

model_config_norm = {"normalization": "min_max",

                     "feature_vector": [
                         {
                             "name": "SMA",
                             "parameters": {
                                 "sma": 5
                             }
                         }
                     ]
                     }

model_config_non_norm = {
    "feature_vector": [
        {"name": "SMA", "parameters": {"sma": 5}}
    ]
}

model_config_macd_norm = {"normalization": "min_max",

                          "feature_vector": [
                              {
                                  "name": "MACD",
                                  "parameters": {
                                      "fast_period": 12,
                                      "slow_period": 26,
                                      "signal_period": 9
                                  }
                              }
                          ]
                          }

model_config_macd_non_norm = {
    "feature_vector": [
        {
            "name": "MACD",
            "parameters": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            }
        }
    ]
}

macd_norm_discrete_3= {
  "preprocess_config": "macd_norm_discrete_3",
  "normalization": "min_max",
  "action_space":
    {
    "type": "Discrete",
    "actions":
    {"0" : "Buy",
     "1" : "Sell",
      "2" :"Hold"}
    }
  ,
  "feature_vector": [
    {
      "name": "MACD",
      "parameters": {
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9
      }
    }
  ]
}

new_model_config_macd_norm_d3 = {
    "preprocess_config": "macd_norm_discrete_3",
    "normalization": "min_max",
    "action_space":
        {
            "type": "Discrete",
            "actions":
                {"1": "Buy",
                 "2": "Sell",
                 "0": "Hold"}
        }
    ,
    "state": {
        "klass": "SimplePosition"
    },
    "feature_vector_dim": 12,
    "feature_vector": [
        {
            "name": "MACD",
            "history": 2,
            "parameters": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            }
        }, {
            "name": "close",
            "history": 3
        }
    ]
}

in_out_model = {
    "preprocess_config": "macd_norm_discrete_3",
    "normalization": "min_max",
    "action_space":
        {
            "type": "Discrete",
            "actions":
                {"1": "In",
                 "0": "Out"
                 }
        }
    ,
    "state": {
        "klass": "InoutPosition",
        "parameters": {"reward_type": "x"}
    },
    "feature_vector_dim": 12,
    "feature_vector": [
        {
            "name": "MACD",
            "history": 2,
            "parameters": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            }
        }, {
            "name": "close",
            "history": 3
        }
    ]
}
#
current_time = time.strftime("%Y%m%d-%H%M%S")
log_dir = f"./tensorboard_logs/in_out_model{current_time}"

env = MTAEnv(in_out_model, prof_data_2, reward_model='x')



# Configure the policy with custom network
policy_kwargs = dict(
    features_extractor_class=CustomNetwork,
    features_extractor_kwargs=dict(features_dim=3),
    net_arch=[dict(pi=[32, 32, 32], vf=[32, 32, 32])]
)



# Create and train the PPO model
model = PPO('MlpPolicy', env, verbose=1, tensorboard_log=log_dir,
             device='cuda') # , policy_kwargs=policy_kwargs,)
print(model.policy)

# If you want to see the specific parameters:
for name, param in model.policy.named_parameters():
    print(name, param.shape)

num_episodes = 100
total_timesteps = num_episodes * 390 * num_samples

model.learn(total_timesteps=total_timesteps)

model.save('/home/warnd/devel/berlin/BerlinProject/labs/saved_models/in_out_model')



# current_time = time.strftime("%Y%m%d-%H%M%S")
# log_dir = f"./tensorboard_logs/new_model_config_macd_norm_d3{current_time}_DQN"
#
# env = MTAEnv(new_model_config_macd_norm_d3, profile_data, reward_model='x')
#
#
# # Create and train the PPO model
# model = DQN('MlpPolicy', env, verbose=1, tensorboard_log=log_dir,
#              device='cuda') # , policy_kwargs=policy_kwargs,)
# print(model.policy)
#
# # If you want to see the specific parameters:
# for name, param in model.policy.named_parameters():
#     print(name, param.shape)
#
# num_episodes = 100
# total_timesteps = num_episodes * 390 * num_samples
#
# model.learn(total_timesteps=total_timesteps)
#
# model.save('/home/warnd/devel/berlin/BerlinProject/labs/saved_models/macd_model2')

