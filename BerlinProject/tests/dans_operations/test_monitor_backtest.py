import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from bson import ObjectId

from config.types import INDICATOR_TYPE, CANDLE_STICK_PATTERN
from data_streamer import DataStreamer
from environments.tick_data import TickData
from models import IndicatorDefinition, MonitorConfiguration
from models.monitor_model import Monitor
from mongo_tools.tick_history_tools import TickHistoryTools
from operations.indicator_backtest import IndicatorBacktest, Trade
from operations.monitor_backtest import MonitorBacktest
from operations.monitor_backtest_results import MonitorResultsBacktest


class TestMonitorBackTest(unittest.TestCase):

    def test_1(self):
        data_config = {
            'type': 'TickHistory',
            'ticker': "NVDA",
            'start_date': datetime(2024, 5,1 ),
            'end_date': datetime(2024, 5, 30),
            'time_increment': 1

        }

        engulf_config = {
            'name': 'martins engulf',
            'type': CANDLE_STICK_PATTERN,
            'function': '',
            'parameters': {
                'talib': 'CDLENGULFING',

            }
        }
        engulf = IndicatorDefinition(**engulf_config)

        indicator_config_sma = {
            'name': 'my_silly_sma_cross',
            'function': 'sma_crossover',
            'type': INDICATOR_TYPE,
            'parameters': {
                'period': 10,
                'crossover_value': .0005,
                "lookback": 25
            }
        }
        sma = IndicatorDefinition(**indicator_config_sma)

        indicator_config_bol = {
            'name': 'my_silly_bol_bounce',
            'function': 'bol_bands_lower_band_bounce',
            'type': INDICATOR_TYPE,
            'parameters': {
                'period': 10,
                'sd': 2,
                'candle_bounce_number': 5,
                'bounce_trigger': .2}

        }
        bol = IndicatorDefinition(**indicator_config_bol)

        # Fake monitor configuration
        test_monitor = {
            "_id": ObjectId("65f2d5555555555555555555"),
            "user_id": ObjectId("65f2d6666666666666666666"),
            "name": "My Test Strategy",
            "description": "A test monitor using SMA and MACD",
            "threshold": 0.5,
            "triggers": {
                "my_silly_sma_cross": 1.0,  # SMA with weight 8
                "my_silly_bol_bounce": 1.0

            }  # MACD with weight 2
        }

        model_config = {
            "preprocess_config": "test_ds",
        }

        # Create Monitor instance
        monitor = Monitor(**test_monitor)
        ic = MonitorConfiguration(name='my test', indicators=[bol, sma])
        bt = MonitorResultsBacktest('My Test Strategy', monitor)

        streamer = DataStreamer(data_config, model_config, ic)
        streamer.connect_tool(bt)
        streamer.run()
        print()