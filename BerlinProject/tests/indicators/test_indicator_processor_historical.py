from datetime import timedelta, datetime
from typing import Tuple, List
import numpy as np
import pandas as pd
import yfinance as yf
import os
import unittest
from models.monitor_configuration import MonitorConfiguration
from data_streamer.indicator_processor_historical import IndicatorProcessorHistorical
from config.types import CANDLE_STICK_PATTERN, INDICATOR_TYPE
from environments.tick_data import TickData
from features.indicators2 import support_level, resistance_level


class MockTickHistoryTools:
    def __init__(self):
        self.history = None

    def set_dataframe(self, data: pd.DataFrame):
        self.history = [
            TickData(row['Close'], row['Open'], row['High'], row['Low'])
            for _, row in data.iterrows()
        ]

    def set_history(self, history: List[TickData]):
        self.history = history

    def get_history(self) -> Tuple[np.array, np.array]:
        return self.history


class TestIndicatorProcessorHistorical(unittest.TestCase):

    def test_candles(self):
        TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), '../test_data')

        data = pd.read_csv(f'{TESTS_DATA_DIR}/btc.csv')

        indicators = [
            {
                "name": "my_silly_sma_cross",
                "function": "sma_crossover",
                "type": "Indicator",
                "parameters": {
                    "period": 10,
                    "crossover_value": 0.0005,
                    "lookback": 25,
                    'trend': 'bullish'
                }
            }
        ]
        config = {"name": "CDL Test", "indicators": indicators}
        config = MonitorConfiguration(**config)
        mock_tick_history = MockTickHistoryTools()
        mock_tick_history.set_dataframe(data)
        processor = IndicatorProcessorHistorical(config, mock_tick_history)
        self.assertTrue(len(processor.indicator_values), len(data))

        result = processor.next_tick(None)
        self.assertAlmostEqual(0.0, result['my_silly_sma_cross'])

    def test_single_candle(self):
        indicators = [
            {"name": "Three Black Crows", "parameters": {"talib": "CDL3BLACKCROWS"}, "type": CANDLE_STICK_PATTERN},
            {"name": "Hammer pattern", "parameters": {"talib": "CDLHAMMER"}, "type": CANDLE_STICK_PATTERN}
        ]
        config = {"name": "CDL Test", "indicators": indicators}
        config = MonitorConfiguration(**config)

        # Create simple data
        history = [
            TickData(open=1.20, high=1.22, low=1.14, close=1.15),  # First black candle
            TickData(open=1.15, high=1.16, low=1.10, close=1.11),  # Second black candle
            TickData(open=1.11, high=1.12, low=1.05, close=1.06),  # Third black candle
            TickData(open=1.05, high=1.06, low=0.95, close=1.04),
            TickData(open=62589, high=62597, low=62470, close=62557)  # CDLHAMMER
        ]
        mock_tick_history = MockTickHistoryTools()
        mock_tick_history.set_history(history)
        processor = IndicatorProcessorHistorical(config, mock_tick_history)

        tick = TickData(open=62589, high=62597, low=62470, close=62557)  # CDLHAMMER

        result = processor.next_tick(tick)
        self.assertTrue('Hammer pattern' in result.keys())
        self.assertTrue('Three Black Crows' in result.keys())

    def test_support_resistance(self):
        indicators = [
            {"name": "silly_support_level",
             'function': 'support_level',
             'type': INDICATOR_TYPE,
             "parameters":
                 {"sensitivity": 30,
                  "local_max_sensitivity": 1,
                  "support_range": .05,
                  "bounce_level": .01,
                  "break_level": .0002,
                  "trend": "bullish"
                  }}
        ]
        config = {"name": "silly_support_line", "indicators": indicators}
        config = MonitorConfiguration(**config)

        # Create simple data for two sine waves
        end_time = datetime(2024, 11, 6, 23, 59)
        start_time = end_time - timedelta(days=30)
        df = yf.download(
            "NVDA",
            start=start_time,
            end=end_time,
            interval="15m"
        )
        # Convert the DataFrame to a list of TickData objects
        history: List[TickData] = [
            TickData(
                close=row['Close'],
                open=row['Open'],
                high=row['High'],
                low=row['Low'],
                volume=row['Volume'],
                timestamp=index
            )
            for index, row in df.iterrows()
        ]

        mock_tick_history = MockTickHistoryTools()
        mock_tick_history.set_history(history)
        processor = IndicatorProcessorHistorical(config, mock_tick_history)

        results = []  # To store results for each tick
        for tick in history:
            result = processor.next_tick(tick)  # Process the current tick
            results.extend(result.values())  # Add the values directly to the results

