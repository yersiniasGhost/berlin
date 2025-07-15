import unittest
from pydantic import ValidationError
from models.tick_history import TickHistory
from models.tick_data import TickData


class TestTickHistory(unittest.TestCase):
    def test_valid_tick_history(self):
        data = {
            "month": 1,
            "year": 2024,
            "ticker": "AAPL",
            "time_increments": 5,
            "data": {
                20240101: TickData(open=150.0, high=151.0, low=149.0, close=150.5)
            }
        }
        tick_history = TickHistory(**data)
        self.assertEqual(tick_history.month, 1)
        self.assertEqual(tick_history.year, 2024)
        self.assertEqual(tick_history.ticker, "AAPL")
        self.assertEqual(tick_history.time_increments, 5)
        self.assertIsInstance(tick_history.data[20240101], TickData)

    def test_data_conversion(self):
        data = {
            "month": 1,
            "year": 2024,
            "ticker": "AAPL",
            "time_increments": 5,
            "data": [
                {"time": 930, "open": 150.0, "high": 151.0, "low": 149.0, "close": 150.5}
            ]
        }
        tick_history = TickHistory(**data)
        self.assertIsInstance(list(tick_history.data.values())[0], TickData)

    def test_missing_required_fields(self):
        with self.assertRaises(ValidationError):
            TickHistory(month=1, year=2024)  # Missing ticker, time_increments, and data

    def test_additional_fields(self):
        data = {
            "month": 1,
            "year": 2024,
            "ticker": "AAPL",
            "time_increments": 5,
            "data": {},
            "extra_field": "This should be ignored"
        }
        tick_history = TickHistory(**data)
        self.assertFalse(hasattr(tick_history, "extra_field"))