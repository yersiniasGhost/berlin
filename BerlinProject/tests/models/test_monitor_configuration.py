import unittest
from models import MonitorConfiguration
from config.types import CANDLE_STICK_PATTERN
from pydantic_core import ValidationError


class TestMonitorConfiguration(unittest.TestCase):

    def test_valid_config(self):
        indicators = [{"name":"CROWS", "parameters": {"talib":"xxx"}, "type": CANDLE_STICK_PATTERN}]
        config = {"name": "CDL Test", "indicators": indicators}
        config = MonitorConfiguration(**config)
        self.assertEqual(config.name, "CDL Test")
        self.assertEqual(len(config.indicators), 1)
        self.assertEqual(config.indicators[0].name, "CROWS")
        self.assertEqual(config.indicators[0].type, CANDLE_STICK_PATTERN)
        self.assertEqual(config.indicators[0].parameters['talib'], 'xxx')
        self.assertEqual(config.indicators[0].description, "")


    def test_invalid_config(self):
        config = {"name": "Three Black Crows", "parameters": {"talib": "CDL3BLACKCROWS"},
                       "type": CANDLE_STICK_PATTERN}

        with self.assertRaises(ValidationError):
            config = MonitorConfiguration(**config)

    def test_invalid_indicator_type(self):
        indicators = {"name": "CROWS", "parameters": {}, "type": "invalid type"}
        config = {"name": "CDL Test", "indicators": indicators}
        with self.assertRaises(ValidationError):
            config = MonitorConfiguration(**config)
