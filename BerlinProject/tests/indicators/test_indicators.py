import os
import unittest
import numpy as np
import pandas as pd

from src.features.indicators import sma_crossover, macd_calculation, macd_histogram_crossover, create_bol_bands, \
    bol_bands_lower_band_bounce
from environments.tick_data import TickData


class TestSMATriggerCrossover(unittest.TestCase):

    def test_crossover(self):

        parameters= {
            'period': 3,
            'crossover_value': .005
        }

        tick_data = [
            TickData(close=100.0, open=99.0, high=101.0, low=98.0),
            TickData(close=102.5, open=100.0, high=102.0, low=99.0),
            TickData(close=101.0, open=101.0, high=103.0, low=100.0),
            TickData(close=105.0, open=101.0, high=102.0, low=94.0),  # SMA will be above close * (1 + crossover_value)
            TickData(close=108.0, open=95.0, high=97.0, low=94.0),
            TickData(close=110.0, open=101.0, high=103.0, low=100.0),
            TickData(close=115.0, open=101.0, high=102.0, low=94.0),  # SMA will be above close * (1 + crossover_value)
            TickData(close=90.0, open=95.0, high=97.0, low=94.0),
            TickData(close=125.0, open=101.0, high=102.0, low=94.0),
        ]
        result = sma_crossover(tick_data, parameters, lookback=10)
        expected = np.array([0, 0, 0, 1, 0, 0, 0, 0, 1])
        np.testing.assert_array_equal(result, expected)

    def test_macd_calc(self):
        num_steps = 40
        base_price = 100.0
        tick_data = [TickData(close=base_price + i,
                              open=base_price + i - 0.5,
                              high=base_price + i + 0.2,
                              low=base_price + i - 0.7) for i in range(num_steps)]

        macd, signal, histogram = macd_calculation(tick_data, 12, 26, 9)
        expected_histogram = np.array([np.nan] * 33 + [0.0] * 7)
        np.testing.assert_array_equal(histogram, expected_histogram)

    def test_macd_histogram_crossover(self):

        parameters = {
            'fast': 12,
            'slow': 26,
            'signal': 9,
            'histogram_threshold': 20.0
        }

        TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), '../test_data')

        data = pd.read_csv(f'{TESTS_DATA_DIR}/btc.csv')

        tick = TickData(open=62589, high=62597, low=62550, close=62557)
        history = [
            TickData(row['Close'], row['Open'], row['High'], row['Low'])
            for _, row in data.iterrows()
        ]

        check = macd_histogram_crossover(history, parameters)
        expected_last_10 = np.array([0, 0, 0, 0, 0, 0, 1, 0, 0, 1])
        np.testing.assert_array_equal(check[-10:], expected_last_10)

    def test_create_bol_bands(self):

        parameters = {
            'period': 10,
            'sd': 2
        }

        num_steps = 40
        base_price = 100.0
        tick_data = [TickData(close=base_price + i,
                              open=base_price + i - 0.5,
                              high=base_price + i + 0.2,
                              low=base_price + i - 0.7) for i in range(num_steps)]

        check = create_bol_bands(tick_data, parameters)
        np.testing.assert_array_equal

    def test_bol_bands_lower_band_bounce(self):
        parameters = {
            'period': 10,
            'sd': 2,
            'candle_bounce_number': 3,
            'bounce_trigger': .25

        }

        TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), '../test_data')

        data = pd.read_csv(f'{TESTS_DATA_DIR}/btc.csv')

        tick = TickData(open=62589, high=62597, low=62550, close=62557)
        history = [
            TickData(row['Close'], row['Open'], row['High'], row['Low'])
            for _, row in data.iterrows()
        ]

        sap = bol_bands_lower_band_bounce(history, parameters)
        x
