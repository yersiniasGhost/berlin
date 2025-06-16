from abc import ABC, abstractmethod
from typing import Dict
import logging

from models.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration
from portfolios.portfolio_tool import Portfolio

logger = logging.getLogger('TradeExecutor')


class TradeExecutor(ABC):
    """
    Abstract base class for trade execution strategies
    """

    def __init__(self,
                 monitor_config: MonitorConfiguration,
                 default_position_size: float,
                 stop_loss_pct: float):
        self.monitor_config = monitor_config
        self.default_position_size = default_position_size
        self.stop_loss_pct = stop_loss_pct
        self.portfolio = Portfolio()

    @abstractmethod
    def make_decision(self,
                      tick: TickData,
                      indicators: Dict[str, float],
                      bar_scores: Dict[str, float] = None) -> None:
        pass
