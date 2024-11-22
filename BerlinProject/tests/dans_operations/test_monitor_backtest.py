import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from bson import ObjectId

from config.types import INDICATOR_TYPE, CANDLE_STICK_PATTERN
from data_streamer import DataStreamer
from environments.tick_data import TickData
from models import IndicatorDefinition
from models.monitor_configuration import MonitorConfiguration
from models.monitor_model import Monitor
from mongo_tools.tick_history_tools import RANDOM_MODE
from operations.monitor_backtest_results import MonitorResultsBacktest


class TestMonitorBackTest(unittest.TestCase):

    def test_1(self):
        data_config = {
            'type': 'TickHistory',
            'ticker': "NVDA",
            'start_date': '2024-05-01',
            'end_date': '2024-05-30',
            'time_increment': 1

        }

        indicator_config_sma_bull = {
            'name': 'my_silly_sma_cross_bull',
            'function': 'sma_crossover',
            'type': INDICATOR_TYPE,
            'parameters': {
                'period': 5,
                'crossover_value': .0008,
                "lookback": 10,
                'trend': 'bullish'

            }
        }
        sma_bull = IndicatorDefinition(**indicator_config_sma_bull)

        indicator_config_sma_bear = {
            'name': 'my_silly_sma_cross_bear',
            'function': 'sma_crossover',
            'type': INDICATOR_TYPE,
            'parameters': {
                'period': 5,
                'crossover_value': -.001,
                "lookback": 10,
                'trend': 'bearish'

            }
        }
        sma_bear = IndicatorDefinition(**indicator_config_sma_bear)

        indicator_config_bol_bull = {
            'name': 'my_silly_bol_bounce_lower',
            'function': 'bol_bands_lower_band_bounce',
            'type': INDICATOR_TYPE,
            'parameters': {
                'period': 25,
                'sd': 2,
                'candle_bounce_number': 3,
                'bounce_trigger': 0.3,
                "lookback": 10,
                "trend": 'bullish'
            }

        }
        bol_bull = IndicatorDefinition(**indicator_config_bol_bull)

        indicator_config_bol_bear = {
            'name': 'my_silly_bol_bounce_upper',
            'function': 'bol_bands_lower_band_bounce',
            'type': INDICATOR_TYPE,
            'parameters': {
                'period': 25,
                'sd': 2,
                'candle_bounce_number': 3,
                'bounce_trigger': 0.5,
                "lookback": 10,
                'trend': 'bearish'
            }

        }
        bol_bear = IndicatorDefinition(**indicator_config_bol_bear)

        indicator_config_macd_bull = {
            'name': 'my_silly_macd_cross',
            'function': 'macd_histogram_crossover',
            'type': INDICATOR_TYPE,
            'parameters': {
                'slow': 13,
                'fast': 5,
                'signal': 3,
                'histogram_threshold': 0.08,
                "lookback": 10,
                "trend": 'bullish'
            }
        }
        macd_bull = IndicatorDefinition(**indicator_config_macd_bull)

        indicator_config_support_bounce = {"name": "silly_support_level",
                                           'function': 'support_level',
                                           'type': INDICATOR_TYPE,
                                           "parameters":
                                               {"sensitivity": 30,
                                                "local_max_sensitivity": 1,
                                                "support_range": .01,
                                                "bounce_level": .005,
                                                "break_level": .0002,
                                                "trend": "bullish",
                                                "lookback": 10
                                                }}

        support_bounce = IndicatorDefinition(**indicator_config_support_bounce)

        indicator_config_resistance_break = {"name": "silly_resistance_level",
                                             'function': 'resistance_level',
                                             'type': INDICATOR_TYPE,
                                             "parameters":
                                                 {"sensitivity": 20,
                                                  "local_min_sensitivity": 1,
                                                  "resistance_range": .005,
                                                  "bounce_level": .005,
                                                  "break_level": .003,
                                                  "trend": "bullish",
                                                  "lookback": 10
                                                  }}

        resistance_break = IndicatorDefinition(**indicator_config_resistance_break)

        # Fake monitor configuration
        test_monitor = {
            "_id": ObjectId("65f2d5555555555555555555"),
            "user_id": ObjectId("65f2d6666666666666666666"),
            "name": "My Test Strategy",
            "description": "A test monitor using SMA and MACD",
            'target_reward': 2,
            'stop_loss': 1,
            "threshold": 0.8,
            "bear_threshold": 0.8,
            "triggers": {
                "my_silly_bol_bounce_lower": 1.0,
                'my_silly_sma_cross_bull': 1.0,
                'my_silly_macd_cross': 1.0,
                'silly_resistance_level': 1.0
                # SMA with weight 8
            }
        }

        model_config = {
            "preprocess_config": "test_ds",
        }

        # Create Monitor instance
        monitor = Monitor(**test_monitor)
        ic = MonitorConfiguration(name='my test',
                                  indicators=[sma_bull, bol_bull, macd_bull, resistance_break])
        bt = MonitorResultsBacktest('My Test Strategy', monitor)
        streamer = DataStreamer(data_config, model_config, ic)
        streamer.connect_tool(bt)
        streamer.replace_monitor_configuration(ic, historical=True)
        streamer.data_link.set_iteration_mode(RANDOM_MODE, 2)
        streamer.run()
        print()
