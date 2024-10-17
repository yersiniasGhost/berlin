from typing import List, Optional, Union
import numpy as np
from stable_baselines3 import PPO

from environments.inout_position import IN, OUT
from data_streamer.external_tool import ExternalTool
from operations import Backtester
from environments.get_state_class import get_state_class
from environments.tick_data import TickData


# This is the object that will contain a group of pretrained models and be associated with a DataStremer
# which will be configured with the same models (providing feature vectors) and a data stream (financial
# institution or sample test data)
# The outputs from this analytical tool will have to connect to a UI or can alternatively connect
# to a back testing suite.
class RuntimeAnalytics(ExternalTool):

    def __init__(self, model_config: dict, path: str):
        self.backtest: Optional[Backtester] = None
        self.action_space_def = model_config["action_space"]
        self.action_defs = self.action_space_def['actions']
        self.feature_dim = model_config["feature_vector_dim"]
        self.feature_vector_def= model_config["feature_vector"]
        # From the model configuration, create the following:  State, PPO (or whaterver)

        # TODO:  Make the state init dynamic (see the environment code) refactor the creating into common code
        self.state = get_state_class(model_config)
        self.model = PPO.load(path)

    def connect_backtest(self, backtest: Backtester):
        self.backtest = backtest
        self.backtest.state = self.state

    # TODO: REFACTORING See the Environment for reuse
    @staticmethod
    def _handle_none_values(feature_vector: np.array) -> np.array:
        output = []
        for f in feature_vector:
            if f is None:
                output.append(0.0)
            else:
                output.append(f)
        return np.array(output)

    # TODO Refactor into the State object
    def get_trade_action(self, action: Union[float, np.array]) -> str:
        # For the given configuration, determine the Bue/Sell/Hold trade action
        # for the given model action space
        if self.action_space_def['type'] == "Discrete":
            return self.action_defs[str(int(action[0]))]
        elif self.action_space_def['type'] == "NormalBox":
            return IN if action <= 0.5 else OUT
        raise ValueError(f"Undefined trade action configuration {action}")

    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        # For each of our models, calculate their actions and send off
        # to the UI (websocket) or backtester or other.
        # fv below is wrong should be results from the model, the actions.

        handle_fv = self._handle_none_values(fv)
        observations = self.state.append_state_to_fv(handle_fv, tick)
        actions, _ = self.model.predict(observations, deterministic=True)
        trade_action = self.get_trade_action(actions)
        # convert actions to "BUY" "SELL "HOLD"
        if self.backtest:
            self.backtest.agent_actions(trade_action, tick)
