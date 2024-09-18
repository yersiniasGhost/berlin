import unittest
import numpy as np
import talib
from features.features import calculate_macd_tick
from mongo_tools.sample_tools import SampleTools


class TestCalculateMACDTick(unittest.TestCase):
    def test_macd_calculation_last_value(self):
        # Prepare test data
        sample_tools = SampleTools.get_specific_sample("66e1f09f7c6789752c190ca0")

        close_array = np.array([tick.close for tick in sample_tools.serve_next_tick()])

        # Calculate MACD values for the last value in the array
        macd, signal, hist = calculate_macd_tick(close_array, fast_period=12, slow_period=26, signal_period=9)

        macd1, signal1, hist1 = calculate_macd_tick(close_array, fast_period=6, slow_period=20, signal_period=4)

        self.assertNotEqual(macd, macd1)
        self.assertNotEqual(signal, signal1)
        self.assertNotEqual(hist, hist1)


    def test_macd_calculation_with_history(self):
        # Prepare test data
        data = np.arange(1, 45, dtype=float)

        # Calculate MACD values with history
        macd, signal, hist = calculate_macd_tick(data, history=3)

        # Check if the returned values have the expected lengths
        self.assertEqual(len(macd), 4)
        self.assertEqual(len(signal), 4)
        self.assertEqual(len(hist), 4)

    def test_macd_error(self):
        # Prepare test data
        data = np.arange(1, 5, dtype=float)

        # Calculate MACD values with history
        with self.assertRaises(ValueError):
            macd, signal, hist = calculate_macd_tick(data, history=30)
