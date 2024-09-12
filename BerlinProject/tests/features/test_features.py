import unittest
import numpy as np
import talib
from features.features import calculate_sma_tick  # Replace 'your_module' with the actual module name


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

