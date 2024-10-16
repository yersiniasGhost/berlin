import math
import unittest
import numpy as np

from models import IndicatorDefinition
from src.features.indicators import sma_indicator, sma_trigger_crossover
from environments.tick_data import TickData


class TestSMATriggerCrossover(unittest.TestCase):
    def test_insufficient_data(self):
        tick_data = [TickData(close=100, open=99, high=101, low=98)]
        result = sma_trigger_crossover(tick_data, period=3, crossover_value=0.005)
        np.testing.assert_array_equal(result, np.array([0]))

    def test_crossover(self):
        tick_data = [
            TickData(close=100.0, open=99.0, high=101.0, low=98.0),
            TickData(close=101.0, open=100.0, high=102.0, low=99.0),
            TickData(close=102.0, open=101.0, high=103.0, low=100.0),
            TickData(close=95.0, open=101.0, high=102.0, low=94.0),  # SMA will be above close * (1 + crossover_value)
            TickData(close=96.0, open=95.0, high=97.0, low=94.0),
        ]
        result = sma_trigger_crossover(tick_data, period=3, crossover_value=0.005, lookback=10)
        expected = np.array([0, 0, 0, 1, 1])
        np.testing.assert_array_equal(result, expected)
    #
    # def test_one_index_after_crossover(self):
    #     tick_data = [
    #         TickData(close=100.0, open=99.0, high=101.0, low=98.0),
    #         TickData(close=101.0, open=100.0, high=102.0, low=99.0),
    #         TickData(close=95.0, open=101.0, high=102.0, low=94.0),
    #         TickData(close=98.0, open=95.0, high=97.0, low=94.0),
    #     ]
    #     result = sma_trigger_crossover(tick_data, period=3, crossover_value=0.005, lookback=10)
    #     self.assertAlmostEqual(result, .9, places=6)
    #
    # def test_multiple_indices_after_crossover(self):
    #     tick_data = [
    #         TickData(close=100.0, open=99.0, high=101.0, low=98.0),
    #         TickData(close=101.0, open=100.0, high=102.0, low=99.0),
    #         TickData(close=95.0, open=101.0, high=102.0, low=94.0),
    #         TickData(close=98.0, open=95.0, high=97.0, low=94.0),
    #         TickData(close=97.0, open=96.0, high=98.0, low=95.0),
    #         TickData(close=98.0, open=97.0, high=99.0, low=96.0),
    #     ]
    #     result = sma_trigger_crossover(tick_data, period=3, crossover_value=0.005, lookback=10)
    #     self.assertAlmostEqual(result, 0.7, places=6)
    #
    # def test_beyond_lookback_period(self):
    #     tick_data = [TickData(close=100.0, open=99.0, high=101.0, low=98.0) for _ in range(15)]
    #     tick_data[2].close = 95.0  # Create a crossover
    #     result = sma_trigger_crossover(tick_data, period=3, crossover_value=0.005, lookback=10)
    #     self.assertEqual(result, 0)
    #
    # def test_different_lookback(self):
    #     tick_data = [
    #         TickData(close=100.0, open=99.0, high=101.0, low=98.0),
    #         TickData(close=101.0, open=100.0, high=102.0, low=99.0),
    #         TickData(close=95.0, open=101.0, high=102.0, low=94.0),
    #         TickData(close=98.0, open=95.0, high=97.0, low=94.0),
    #         TickData(close=97.0, open=96.0, high=98.0, low=95.0),
    #         TickData(close=98.0, open=97.0, high=99.0, low=96.0),
    #     ]
    #     result = sma_trigger_crossover(tick_data, period=3, crossover_value=0.005, lookback=20)
    #     self.assertAlmostEqual(result, 0.85, places=6)



