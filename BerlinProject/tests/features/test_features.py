import unittest
import numpy as np
import talib
from features.features import calculate_sma_tick, calculate_macd_tick
class TestCalculateSMATick(unittest.TestCase):
    def test_sma_with_history(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        # data= np.arange(0, 101, 1)
        result = calculate_sma_tick(2, data, history=2)
        expected = np.array([3.5, 4.5, 5.5])
        np.testing.assert_almost_equal(result, expected)


    def test_basic_sma_calculation(self):
        data = np.array([1.0, 2.0, 5.0, 4.0, 5.0])
        result = calculate_sma_tick(3, data)
        expected = np.array([4.66666667])  # SMA of last 3 values: (3 + 4 + 5) / 3
        np.testing.assert_almost_equal(result, expected)


    def test_sma_with_longer_data(self):
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = calculate_sma_tick(5, data)
        expected = np.array([8])  # SMA of last 5 values: (6 + 7 + 8 + 9 + 10) / 5
        np.testing.assert_almost_equal(result, expected)

    class TestMACDCalculation(unittest.TestCase):
        def test_macd_calculation_last_value(self):
            # Prepare test data
            data = np.arange(1, 45, dtype=float)

            # Calculate MACD values for the last value in the array
            macd, signal, hist = calculate_macd_tick(data, fast_period=12, slow_period=26, signal_period=9)

            # Check if the returned values are of the expected types
            self.assertIsInstance(macd, np.float64)
            self.assertIsInstance(signal, np.float64)
            self.assertIsInstance(hist, np.float64)


        def test_macd_calculation_with_history(self):
            # Prepare test data
            data = np.arange(1, 45, dtype=float)

            # Calculate MACD values with history
            macd, signal, hist = calculate_macd_tick(data, history=3)

            # Check if the returned values have the expected lengths
            self.assertEqual(len(macd), 4)
            self.assertEqual(len(signal), 4)
            self.assertEqual(len(hist), 4)
