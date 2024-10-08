import unittest
from dataclasses import dataclass
from typing import Optional

import numpy as np
from data_preprocessor.data_preprocessor import DataPreprocessor, TickData


# Should test that it can use the sample tools to retrieve a given number of samples given an ID
# Check that the list is the same length as we specify
# Set up JSON model configs that takes close or moving averages for example

class TestDataPreprocessor(unittest.TestCase):
    def setUp(self):
        self.model_config = {
            "feature_vector": [
                {"name": "close"},
                {"name": "SMA", "parameters": {"sma": 3}}
            ]
        }
        self.preprocessor = DataPreprocessor(self.model_config)

    def test_initialization(self):
        self.assertEqual(self.preprocessor.feature_vector, self.model_config["feature_vector"])
        self.assertEqual(len(self.preprocessor.history), 0)
        self.assertIsNone(self.preprocessor.tick)

    def test_next_tick_history_update(self):
        preprocessor = DataPreprocessor(self.model_config)
        tick1 = TickData(close=10.0, open=9.0, high=11.0, low=8.0)
        tick2 = TickData(close=11.0, open=10.0, high=12.0, low=9.0)

        preprocessor.next_tick(tick1)
        self.assertEqual(len(preprocessor.history), 1)
        self.assertEqual(preprocessor.tick, tick1)

        preprocessor.next_tick(tick2)
        self.assertEqual(len(preprocessor.history), 2)
        self.assertEqual(preprocessor.tick, tick2)

    def test_get_price_array(self):
        ticks = [
            TickData(close=10.0, open=9.0, high=11.0, low=8.0),
            TickData(close=11.0, open=10.0, high=12.0, low=9.0),
            TickData(close=12.0, open=11.0, high=13.0, low=10.0)
        ]
        for tick in ticks:
            self.preprocessor.next_tick(tick)

        close_array = self.preprocessor.get_price_array('close')
        expected_close = np.array([10.0, 11.0, 12.0])
        np.testing.assert_array_equal(close_array, expected_close)

    def test_next_tick_simple_feature(self):
        tick = TickData(close=10.0, open=9.0, high=11.0, low=8.0)
        output = self.preprocessor.next_tick(tick)
        self.assertEqual(output[0], 10.0)  # Check if close price is correctly returned

    def test_next_tick_sma_feature(self):
        ticks = [
            TickData(close=10.0, open=9.0, high=11.0, low=8.0),
            TickData(close=11.0, open=10.0, high=12.0, low=9.0),
            TickData(close=12.0, open=11.0, high=13.0, low=10.0),
            TickData(close=13.0, open=12.0, high=14.0, low=11.0),
            TickData(close=14.0, open=13.0, high=15.0, low=12.0)
        ]
        outputs = [self.preprocessor.next_tick(tick) for tick in ticks]

        self.assertIsNone(outputs[0][1])  # SMA should be None for first two ticks
        self.assertIsNone(outputs[1][1])
        self.assertAlmostEqual(outputs[2][1], 11.0)  # SMA should be (10+11+12)/3 = 11.0
        self.assertAlmostEqual(outputs[3][1], 12.0)  # SMA should be (11+12+13)/3 = 12.0
        self.assertAlmostEqual(outputs[4][1], 13.0)  # SMA should be (12+13+14)/3 = 13.0

    def test_calculate_method(self):
        ticks = [
            TickData(close=10.0, open=9.0, high=11.0, low=8.0),
            TickData(close=11.0, open=10.0, high=12.0, low=9.0),
            TickData(close=12.0, open=11.0, high=13.0, low=10.0)
        ]
        for tick in ticks:
            self.preprocessor.next_tick(tick)

        close_feature = {"name": "close"}
        self.assertEqual(self.preprocessor._calculate(close_feature), 12.0)

        sma_feature = {"name": "SMA", "parameters": {"sma": 3}}
        self.assertAlmostEqual(self.preprocessor._calculate(sma_feature), 11.0)


class TestDataPreprocessorNormalization(unittest.TestCase):
    def setUp(self):
        self.model_config = {
            "normalization": "min_max",
            "feature_vector": [
                {"name": "close"},
                {"name": "SMA", "parameters": {"sma": 3}}
            ]
        }
        self.sample_stats = {
            'open': {'min': 50.0, 'max': 100.0, 'sd': 10.0},
            'high': {'min': 55.0, 'max': 105.0, 'sd': 10.0},
            'low': {'min': 45.0, 'max': 95.0, 'sd': 10.0},
            'close': {'min': 50.0, 'max': 100.0, 'sd': 10.0}
        }

    def test_initialization(self):
        preprocessor = DataPreprocessor(self.model_config)
        self.assertEqual(preprocessor.model_config, self.model_config)
        self.assertEqual(preprocessor.normalized_data, [])
        self.assertIsNone(preprocessor.tick)
        self.assertIsNone(preprocessor.sample_stats)


    def test_reset(self):
        preprocessor = DataPreprocessor(self.model_config)
        preprocessor.reset_state(self.sample_stats)
        self.assertEqual(preprocessor.sample_stats, self.sample_stats)
        self.assertEqual(preprocessor.normalized_data, [])
        self.assertIsNone(preprocessor.tick)

    def test_normalize_close_min_value(self):
        preprocessor = DataPreprocessor(self.model_config)
        preprocessor.reset_state(self.sample_stats)

        tick = TickData(open=50.0, high=55.0, low=45.0, close=50.0)
        preprocessor.normalize_data(tick)

        # Check the normalized_data list
        self.assertEqual(len(preprocessor.normalized_data), 1)
        normalized_tick = preprocessor.normalized_data[0]
        self.assertAlmostEqual(normalized_tick.close, 0.0)
        self.assertEqual(normalized_tick.open, 0.0)
        self.assertEqual(normalized_tick.high, 0.1)
        self.assertEqual(normalized_tick.low, -0.1)

    def test_normalize_close_max_value(self):
        preprocessor = DataPreprocessor(self.model_config)
        preprocessor.reset_state(self.sample_stats)

        tick = TickData(open=100.0, high=105.0, low=95.0, close=100.0)
        preprocessor.normalize_data(tick)

        self.assertAlmostEqual(preprocessor.tick.close, 1.0)
        self.assertEqual(preprocessor.tick.open, 1.0)
        self.assertEqual(preprocessor.tick.high, 1.1)
        self.assertEqual(preprocessor.tick.low, .9)

    def test_normalize_close_mid_value(self):
        preprocessor = DataPreprocessor(self.model_config)
        preprocessor.reset_state(self.sample_stats)

        tick = TickData(open=75.0, high=80.0, low=70.0, close=75.0)
        preprocessor.normalize_data(tick)

        self.assertAlmostEqual(preprocessor.tick.close, 0.5)
        self.assertEqual(preprocessor.tick.open, 0.5)
        self.assertEqual(preprocessor.tick.high, 0.6)
        self.assertEqual(preprocessor.tick.low, 0.4)


@dataclass
class TickData:
    close: float
    open: float
    high: float
    low: float
    volume: Optional[int] = None


@dataclass
class TickData:
    close: float
    open: float
    high: float
    low: float
    volume: Optional[int] = None


class TestDataPreprocessorSMA(unittest.TestCase):
    def setUp(self):
        self.model_config = {
            "normalization": "min_max",
            "feature_vector": [
                {"name": "close"},
                {"name": "SMA", "parameters": {"sma": 3}}
            ]
        }
        self.sample_stats = {
            'open': {'min': 0.0, 'max': 10.0, 'sd': 2.0},
            'high': {'min': 0.0, 'max': 10.0, 'sd': 2.0},
            'low': {'min': 0.0, 'max': 10.0, 'sd': 2.0},
            'close': {'min': 0.0, 'max': 10.0, 'sd': 2.0}
        }
        self.preprocessor = DataPreprocessor(self.model_config)
        self.preprocessor.reset_state(self.sample_stats)

    def test_sma_calculation(self):
        # Test SMA calculation over multiple ticks
        ticks = [
            TickData(open=1.0, high=2.0, low=0.0, close=1.0),
            TickData(open=2.0, high=3.0, low=1.0, close=2.0),
            TickData(open=3.0, high=4.0, low=2.0, close=3.0),
            TickData(open=4.0, high=5.0, low=3.0, close=4.0),
            TickData(open=5.0, high=6.0, low=4.0, close=5.0)
        ]

        expected_close_values = [0.1, 0.2, 0.3, 0.4, 0.5]
        expected_sma_values = [None, None, 0.2, 0.3, 0.4]

        for tick, expected_close, expected_sma in zip(ticks, expected_close_values, expected_sma_values):
            output_vector = self.preprocessor.next_tick(tick)

            # Check that the output vector has the expected length
            self.assertEqual(len(output_vector), 2)

            # Check the close price (should be normalized)
            self.assertAlmostEqual(output_vector[0], expected_close, places=6)

            # Check the SMA value
            if expected_sma is None:
                self.assertIsNone(output_vector[1])
            else:
                self.assertAlmostEqual(output_vector[1], expected_sma, places=6)

    def test_sma_calculation_edge_cases(self):
        # Test SMA calculation with edge cases (min, mid, and max values)
        ticks = [
            TickData(open=0.0, high=1.0, low=0.0, close=0.0),  # min value
            TickData(open=5.0, high=6.0, low=4.0, close=5.0),  # mid value
            TickData(open=10.0, high=10.0, low=9.0, close=10.0),  # max value
        ]

        expected_close_values = [0.0, 0.5, 1.0]
        expected_sma_values = [None, None, 0.5]

        for tick, expected_close, expected_sma in zip(ticks, expected_close_values, expected_sma_values):
            output_vector = self.preprocessor.next_tick(tick)

            # Check the close price (should be normalized)
            self.assertAlmostEqual(output_vector[0], expected_close, places=6)

            # Check the SMA value
            if expected_sma is None:
                self.assertIsNone(output_vector[1])
            else:
                self.assertAlmostEqual(output_vector[1], expected_sma, places=6)



