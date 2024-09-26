import unittest
import numpy as np
from data_preprocessor.data_preprocessor import DataPreprocessor, TickData


#Should test that it can use the sample tools to retrieve a given number of samples given an ID
#Check that the list is the same length as we specify
#Set up JSON model configs that takes close or moving averages for example

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


