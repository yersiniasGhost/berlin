from typing import Optional

from environments.tick_data import TickData
from environments.state import State
from config import ACTION


class Backtester:

    def __init__(self):
        self.tick_count: int = 0
        self.state: Optional[State] = None

    def agent_actions(self, action: ACTION, tick: TickData):
        # TODO:  Make the random state as baseline test
        self.state.update_and_calculate_reward(action, tick)


