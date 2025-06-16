import pandas as pd
import os
import unittest
from models import MonitorConfiguration
from data_streamer.indicator_processor import IndicatorProcessor
from config.types import CANDLE_STICK_PATTERN
from models.tick_data import TickData


class TestIndicatorProcessor(unittest.TestCase):

    def download_data(self):
        import yfinance as yf
        from datetime import datetime, timedelta

        end_time = datetime.now()
        start_time = end_time - timedelta(days=5)

        # Yfinance doesn't have great minute data
        data = yf.download(
            "BTC-USD",
            start=start_time,
            end=end_time,
            interval="1h")
        TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), '../test_data')
        data.to_csv(f'{TESTS_DATA_DIR}/btc.csv', index=False)

    def test_indicator_sma_cross(self):
        pass


    def test_candles(self):
        TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), '../test_data')

        data = pd.read_csv(f'{TESTS_DATA_DIR}/btc.csv')

        indicators = [
            {"name": "Three Black Crows", "parameters": {"talib": "CDL3BLACKCROWS", "lookback": 50}, "type": CANDLE_STICK_PATTERN},
            {"name": "Hammer", "parameters": {"talib": "CDLHAMMER", "lookback": 120}, "type": CANDLE_STICK_PATTERN},
            {"name": "Shooting Star", "parameters": {"talib": "CDLSHOOTINGSTAR", "lookback": 120}, "type": CANDLE_STICK_PATTERN},
            {"name": "Doji", "parameters": {"talib": "CDLDOJI", "lookback": 120}, "type": CANDLE_STICK_PATTERN},
            {"name": "Engulfing Bull", "parameters": {"talib": "CDLENGULFING", "lookback": 120, "bull": True}, "type": CANDLE_STICK_PATTERN},
            {"name": "Engulfing Bear", "parameters": {"talib": "CDLENGULFING", "lookback": 120, "bull": False}, "type": CANDLE_STICK_PATTERN},
            {"name": "Morning Star", "parameters": {"talib": "CDLMORNINGSTAR", "lookback": 120}, "type": CANDLE_STICK_PATTERN},
            {"name": "Evening Star", "parameters": {"talib": "CDLEVENINGSTAR", "lookback": 120}, "type": CANDLE_STICK_PATTERN},
            {"name": "Piercing Line", "parameters": {"talib": "CDLPIERCING", "lookback": 120}, "type": CANDLE_STICK_PATTERN},
            {"name": "Dark Cloud Cover", "parameters": {"talib": "CDLDARKCLOUDCOVER", "lookback": 120}, "type": CANDLE_STICK_PATTERN},
            {"name": "Hammer pattern", "parameters": {"talib": "CDLHAMMER", "lookback": 50}, "type": CANDLE_STICK_PATTERN}
        ]
        config = {"name": "CDL Test", "indicators": indicators}
        config = MonitorConfiguration(**config)

        processor = IndicatorProcessor(config)
        tick = TickData(open=62589, high=62597, low=62550, close=62557)
        history = [
            TickData(row['Close'], row['Open'], row['High'], row['Low'])
            for _, row in data.iterrows()
        ]
        result = processor.next_tick(tick, history)
        self.assertAlmostEqual(0.82, result['Hammer pattern'])
        self.assertAlmostEqual(0.925, result['Hammer'])
        self.assertAlmostEqual(-0.658333333, result['Dark Cloud Cover'])



    def test_single_candle(self):
        indicators = [
            {"name": "Three Black Crows", "parameters": {"talib": "CDL3BLACKCROWS"},"type": CANDLE_STICK_PATTERN},
        {"name": "Hammer pattern", "parameters": {"talib": "CDLHAMMER"}, "type": CANDLE_STICK_PATTERN}]
        config = {"name": "CDL Test", "indicators": indicators}
        config = MonitorConfiguration(**config)

        processor = IndicatorProcessor(config)

        # Create simple data
        history = [
            TickData(open=1.20, high=1.22, low=1.14, close=1.15),  # First black candle
            TickData(open=1.15, high=1.16, low=1.10, close=1.11),  # Second black candle
            TickData(open=1.11, high=1.12, low=1.05, close=1.06),  # Third black candle
            TickData(open=1.05, high=1.06, low=0.95, close=1.04),
            TickData(open=62589, high=62597, low=62470, close=62557)  # CDLHAMMER
        ]
        tick = TickData(open=62589, high=62597, low=62470, close=62557)  # CDLHAMMER

        opens, highs, lows, closes = [], [], [], []
        for history_tick in history:
            opens.append(history_tick.open)
            highs.append(history_tick.high)
            lows.append(history_tick.low)
            closes.append(history_tick.close)

        result = processor.next_tick(tick, history)
        import talib
        import numpy as np
        hammer = talib.CDLHAMMER(np.array(opens), np.array(highs), np.array(lows), np.array(closes))
        print(hammer)
        # test result
