import unittest
from dataclasses import dataclass
from typing import Optional

import numpy as np
from data_streamer.data_preprocessor import DataPreprocessor
from data_streamer.feature_vector_calculator import FeatureVectorCalculator
from models.tick_data import TickData

import talib


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
        self.feature_vector_calculator = FeatureVectorCalculator(self.model_config)

    def test_initialization(self):
        self.assertEqual(self.feature_vector_calculator.feature_vector, self.model_config["feature_vector"])
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

        self.feature_vector_calculator.tick = ticks[-1]  # Current tick
        self.feature_vector_calculator.history = ticks  # History of ticks

        # Test get_price_array
        close_array = self.feature_vector_calculator.get_price_array('close')
        expected_close = np.array([10.0, 11.0, 12.0])
        np.testing.assert_array_equal(close_array, expected_close)

    def test_next_tick_simple_feature(self):
        tick = TickData(close=10.0, open=9.0, high=11.0, low=8.0)
        self.preprocessor.next_tick(tick)
        output = self.feature_vector_calculator.next_tick(self.preprocessor)
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

@dataclass
class TickData:
    close: float
    open: float
    high: float
    low: float
    volume: Optional[int] = None


class TestMACDCalc(unittest.TestCase):
    def setUp(self):
        self.model_config = {
            "feature_vector": [
                {"name": "MACD", "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9}}
            ]
        }
        self.preprocessor = DataPreprocessor(self.model_config)

    def test_macd_calculation(self):
        prices = [10.0, 12.0, 15.0, 14.0, 13.0, 16.0, 18.0, 20.0, 19.0, 22.0, 25.0, 24.0, 26.0, 28.0, 27.0, 29.0, 30.0,
                  32.0, 31.0, 33.0, 35.0, 34.0, 36.0, 38.0, 37.0, 39.0, 40.0, 42.0, 41.0, 43.0, 45.0, 44.0, 46.0, 48.0,
                  47.0, 49.0, 50.0, 52.0, 51.0, 53.0]

        ticks = [TickData(close=price, open=price, high=price, low=price) for price in prices]
        outputs = [self.preprocessor.next_tick(tick) for tick in ticks]

        close_array = np.array(prices)
        expected_macd, expected_signal, expected_hist = talib.MACD(close_array, fastperiod=12, slowperiod=26, signalperiod=9)

        for i, output in enumerate(outputs):
            if i < 34:  # MACD should have valid values after 34 periods (26 + 9 - 1)
                self.assertEqual([(None, None, None)], output)
            else:
                j=i+1 #we are using j bc there was a problem with the index being 1 shifted forward compared to expected output
                self.assertIsNotNone(output[0])
                calculated_macd, calculated_signal, calculated_hist = output[0]
                self.assertAlmostEqual(calculated_macd, expected_macd[i], places=2)
                self.assertAlmostEqual(calculated_signal, expected_signal[i], places=2)
                self.assertAlmostEqual(calculated_hist, expected_hist[i], places=2)

    def test_insufficient_data_for_macd(self):
        prices = [10.0, 12.0, 15.0, 14.0, 13.0]
        ticks = [TickData(close=price, open=price, high=price, low=price) for price in prices]
        outputs = [self.preprocessor.next_tick(tick) for tick in ticks]

        for output in outputs:
            self.assertEqual([(None, None, None)], output) # MACD should be None due to insufficient data


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


class TestDataPreprocessorFeatureVectors(unittest.TestCase):
    def setUp(self):
        self.sample_stats = {
            'open': {'min': 50.0, 'max': 100.0, 'sd': 10.0},
            'high': {'min': 55.0, 'max': 105.0, 'sd': 10.0},
            'low': {'min': 45.0, 'max': 95.0, 'sd': 10.0},
            'close': {'min': 50.0, 'max': 100.0, 'sd': 10.0}
        }

    def test_next_tick_single_price_feature(self):
        model_config = {
            "feature_vector": [
                {"name": "close"}
            ]
        }
        preprocessor = DataPreprocessor(model_config)
        preprocessor.reset_state(self.sample_stats)

        tick = TickData(open=75.0, high=80.0, low=70.0, close=78.0)
        output = preprocessor.next_tick(tick)

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0], 78.0)

    def test_next_tick_multiple_price_features(self):
        model_config = {
            "feature_vector": [
                {"name": "open"},
                {"name": "high"},
                {"name": "low"},
                {"name": "close"}
            ]
        }
        preprocessor = DataPreprocessor(model_config)
        preprocessor.reset_state(self.sample_stats)

        tick = TickData(open=75.0, high=80.0, low=70.0, close=78.0)
        output = preprocessor.next_tick(tick)

        self.assertEqual(len(output), 4)
        self.assertEqual(output, [75.0, 80.0, 70.0, 78.0])

    def test_next_tick_sma_feature(self):
        model_config = {
            "feature_vector": [
                {"name": "SMA", "parameters": {"sma": 3}}
            ]
        }
        preprocessor = DataPreprocessor(model_config)
        preprocessor.reset_state(self.sample_stats)

        ticks = [
            TickData(open=75.0, high=80.0, low=70.0, close=78.0),
            TickData(open=76.0, high=81.0, low=71.0, close=79.0),
            TickData(open=77.0, high=82.0, low=72.0, close=80.0),
            TickData(open=78.0, high=83.0, low=73.0, close=81.0)
        ]

        outputs = [preprocessor.next_tick(tick) for tick in ticks]

        self.assertEqual(len(outputs), 4)
        self.assertIsNone(outputs[0][0])
        self.assertIsNone(outputs[1][0])
        self.assertAlmostEqual(outputs[2][0], 79.0)
        self.assertAlmostEqual(outputs[3][0], 80.0)

    def test_next_tick_macd_feature(self):
        model_config = {
            "feature_vector": [
                {"name": "MACD", "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9}}
            ]
        }
        preprocessor = DataPreprocessor(model_config)
        preprocessor.reset_state(self.sample_stats)

        # Generate 35 ticks (need at least 34 for MACD)
        ticks = [TickData(open=75.0 + i, high=80.0 + i, low=70.0 + i, close=78.0 + i) for i in range(35)]

        outputs = [preprocessor.next_tick(tick) for tick in ticks]

        self.assertEqual(len(outputs), 35)
        for i in range(33):
            self.assertEqual(outputs[i], [(None, None, None)])

        # Check that the last two outputs are not None
        self.assertIsNotNone(outputs[33][0])
        self.assertIsNotNone(outputs[34][0])

        # Check that the last output is a tuple of 3 floats
        self.assertIsInstance(outputs[34][0], tuple)
        self.assertEqual(len(outputs[34][0]), 3)
        for value in outputs[34][0]:
            self.assertIsInstance(value, float)

    def test_next_tick_multiple_features(self):
        model_config = {
            "feature_vector": [
                {"name": "close"},
                {"name": "SMA", "parameters": {"sma": 3}},
                {"name": "MACD", "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9}}
            ]
        }
        preprocessor = DataPreprocessor(model_config)
        preprocessor.reset_state(self.sample_stats)

        # Generate 35 ticks
        ticks = [TickData(open=75.0 + i, high=80.0 + i, low=70.0 + i, close=78.0 + i) for i in range(35)]

        outputs = [preprocessor.next_tick(tick) for tick in ticks]

        self.assertEqual(len(outputs), 35)

        # Check the last output
        last_output = outputs[-1]
        self.assertEqual(len(last_output), 3)
        self.assertIsInstance(last_output[0], float)  # close
        self.assertIsInstance(last_output[1], float)  # SMA
        self.assertIsInstance(last_output[2], tuple)  # MACD
        self.assertEqual(len(last_output[2]), 3)  # MACD tuple should have 3 values

    def test_next_tick_with_normalization(self):
        model_config = {
            "normalization": "min_max",
            "feature_vector": [
                {"name": "close"},
                {"name": "SMA", "parameters": {"sma": 3}}
            ]
        }
        preprocessor = DataPreprocessor(model_config)
        preprocessor.reset_state(self.sample_stats)

        ticks = [
            TickData(open=75.0, high=80.0, low=70.0, close=78.0),
            TickData(open=76.0, high=81.0, low=71.0, close=79.0),
            TickData(open=77.0, high=82.0, low=72.0, close=80.0),
            TickData(open=78.0, high=83.0, low=73.0, close=81.0)
        ]

        outputs = [preprocessor.next_tick(tick) for tick in ticks]

        self.assertEqual(len(outputs), 4)
        for output in outputs:
            self.assertEqual(len(output), 2)
            self.assertIsInstance(output[0], float)
            self.assertTrue(0 <= output[0] <= 1)  # Normalized close should be between 0 and 1

        # Check SMA (should be None for first two, then normalized value for last two)
        self.assertIsNone(outputs[0][1])
        self.assertIsNone(outputs[1][1])
        self.assertIsInstance(outputs[2][1], float)
        self.assertIsInstance(outputs[3][1], float)
        self.assertTrue(0 <= outputs[2][1] <= 1)
        self.assertTrue(0 <= outputs[3][1] <= 1)
    #
    # def test_next_tick_macd_normalized(self):
    #     model_config = {
    #         # "normalization": "min_max",
    #         "feature_vector": [
    #             {"name": "MACD", "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9}}
    #         ]
    #     }
    #     preprocessor = DataPreprocessor(model_config)
    #
    #     # Set up sample stats for normalization
    #     sample_stats = {
    #         'close': {'min': 50.0, 'max': 150.0},
    #         'open': {'min': 50.0, 'max': 150.0},
    #         'high': {'min': 50.0, 'max': 150.0},
    #         'low': {'min': 50.0, 'max': 150.0}
    #     }
    #     preprocessor.reset_state(sample_stats)
    #
    #     # Generate 40 ticks with increasing prices
    #     ticks = [TickData(open=50.0 + i, high=52.0 + i, low=49.0 + i, close=51.0 + i) for i in range(40)]
    #
    #     outputs = [preprocessor.next_tick(tick) for tick in ticks]
    #
    #     self.assertEqual(len(outputs), 40)
    #
    #     # First 33 outputs should be (None, None, None)
    #     for i in range(33):
    #         self.assertEqual(outputs[i], [(None, None, None)])
    #
    #     # From the 34th output onwards, we should have valid MACD values
    #     for i in range(33, 40):
    #         self.assertIsNotNone(outputs[i][0])
    #         macd, signal, hist = outputs[i][0]
    #
    #         # Check that all values are floats
    #         self.assertIsInstance(macd, float)
    #         self.assertIsInstance(signal, float)
    #         self.assertIsInstance(hist, float)
    #
    #         # Check that MACD and Signal are between 0 and 1 (normalized)
    #         self.assertTrue(0 <= macd <= 1, f"MACD value {macd} is not between 0 and 1")
    #         self.assertTrue(0 <= signal <= 1, f"Signal value {signal} is not between 0 and 1")
    #
    #         # Histogram can be negative, so we don't check its range
    #
    #     # Check that the last few values are different (showing that calculation is actually happening)
    #     last_values = [outputs[i][0] for i in range(-3, 0)]
    #     self.assertTrue(any(x != y for x, y in zip(last_values, last_values[1:])))
    #
    #     # Print the last few values for manual inspection
    #     print("Last few MACD values:")
    #     for i in range(-5, 0):
    #         print(f"Tick {i}: {outputs[i][0]}")