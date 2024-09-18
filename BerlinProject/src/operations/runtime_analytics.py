from typing import List, Optional
import numpy as np

from src.models.agent_model import AgentModel
from src.data_streamer import ExternalTool, TickData
from backtester import Backtester


# This is the object that will contain a group of pretrained models and be associated with a DataStremer
# which will be configured with the same models (providing feature vectors) and a data stream (financial
# institution or sample test data)
# The outputs from this analytical tool will have to connect to a UI or can alternatively connect
# to a back testing suite.
class RuntimeAnalytics(ExternalTool):

    def __init__(self, agents: List[AgentModel]):
        self.backtest: Optional[Backtester] = None
        ...


    def connect_backtest(self, backtest: Backtester):
        self.backtest = backtest


    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        # For each of our models, calculate their actions and send off
        # to the UI (websocket) or backtester or other.

        if self.backtest:
            self.backtest.agent_actions(fv, tick)
