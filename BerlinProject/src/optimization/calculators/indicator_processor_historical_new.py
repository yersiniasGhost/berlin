import logging
from typing import Tuple
from datetime import datetime

from candle_aggregator.candle_aggregator import CandleAggregator
from candle_aggregator.candle_aggregator_normal import CANormal
from candle_aggregator.candle_aggregator_heiken import CAHeiken
from features.indicators2 import support_level, resistance_level
from models.monitor_configuration import MonitorConfiguration
from features.indicators import *
from models.tick_data import TickData


class IndicatorProcessorBackTest:

    def __init__(self):
