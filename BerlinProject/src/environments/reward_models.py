def reward_model_x(position, action, tick, buy_price):
    step_reward = 0
    if action == 0:  # Buy
        if position == 0:
            step_reward = 0
        else:
            step_reward = -2
    elif action == 1:  # Sell
        if position == 1:
            step_reward = tick.close - buy_price
        else:
            step_reward = -2
    return step_reward


def reward_model_y(position, action, tick, buy_price):
    step_reward = 0
    if action == 0:  # Buy
        if position == 0:
            step_reward = 0
        else:
            step_reward = -0.5
    elif action == 1:  # Sell
        if position == 1:
            step_reward = tick.close - buy_price  # reward for a good trade
        else:
            step_reward = -0.5
    return step_reward

# def reward_model_z(position, action, tick, buy_price):
#     step_reward =0
#     if action