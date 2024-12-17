import os
import unittest
from dataclasses import dataclass
from typing import List

import yfinance as yf
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.features.indicators2 import (calculate_support, calculate_resistance,
                                      support_level, resistance_level, calculate_fibonacci_levels, fib_trigger)

from environments.tick_data import TickData

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np


@dataclass
class TickData:
    close: float
    open: float
    high: float
    low: float
    volume: Optional[int] = None
    timestamp: Optional[datetime] = None


def generate_synthetic_fib_data() -> List[TickData]:
    # Create timestamp range for a trading day
    base_time = datetime(2024, 1, 1, 9, 30)  # Market open
    timestamps = [base_time + timedelta(minutes=i) for i in range(390)]

    # Initialize price array
    prices = np.zeros(390)

    # Starting price
    base_price = 100.0

    # Scale down all movements by factor of 10
    # Phase 1: Initial downward trend (0-100)
    x1 = np.linspace(0, 1, 100)
    prices[:100] = base_price - (2 * x1) + np.random.normal(0, 0.01, 100)

    # Phase 2: Upward trend to create high (100-200)
    x2 = np.linspace(0, 1, 100)
    prices[100:200] = (base_price - 2) + (4 * x2) + np.random.normal(0, 0.01, 100)

    # Phase 3: Retracement to Fibonacci level (200-300)
    # Target 0.618 Fibonacci level
    high_price = base_price + 2  # Peak price
    low_price = base_price - 2  # Previous low
    price_range = high_price - low_price
    fib_level = high_price - (price_range * 0.618)

    x3 = np.linspace(0, 1, 100)
    prices[200:300] = high_price - ((high_price - fib_level) * x3) + np.random.normal(0, 0.01, 100)

    # Phase 4: Final upward trend (300-390)
    x4 = np.linspace(0, 1, 90)
    prices[300:] = fib_level + (2.5 * x4) + np.random.normal(0, 0.01, 90)

    # Generate tick data
    tick_data_list = []
    for i in range(390):
        # Add small random variations for open/high/low (scaled down)
        current_price = float(prices[i])
        open_val = float(current_price + np.random.normal(0, 0.01))
        close_val = float(current_price)
        high_val = float(max(open_val, close_val) + abs(np.random.normal(0, 0.02)))
        low_val = float(min(open_val, close_val) - abs(np.random.normal(0, 0.02)))

        # Generate synthetic volume (as integer)
        volume = int(max(0, np.random.normal(100000, 20000)))

        tick_data_list.append(
            TickData(
                close=close_val,
                open=open_val,
                high=high_val,
                low=low_val,
                volume=volume,
                timestamp=timestamps[i]
            )
        )

    return tick_data_list

class TestCalculateLines(unittest.TestCase):

    def test_support(self):
        data = np.array([8, 7, 6, 5, 7, 7, 4, 5])
        check = calculate_support(data, sensitivity=1)
        self.assertTrue(np.array_equal(check, np.array([3, 6])))

    def test_resistance(self):
        data = np.array([4, 5, 8, 7, 6, 5, 8, 5])
        check = calculate_resistance(data, sensitivity=1)
        self.assertTrue(np.array_equal(check, np.array([2, 6])))

    def test_support_tigger(self):
        end_time = datetime(2024, 11, 6, 23, 59)
        start_time = end_time - timedelta(days=30)
        df = yf.download(
            "NVDA",
            start=start_time,
            end=end_time,
            interval="15m"
        )
        # Convert the DataFrame to a list of TickData objects
        tick_data_list: List[TickData] = [
            TickData(
                close=row['Close'],
                open=row['Open'],
                high=row['High'],
                low=row['Low'],
                volume=row['Volume'],
                timestamp=index
            )
            for index, row in df.iterrows()
        ]

        parameters = {"sensitivity": 30,
                      "local_max_sensitivity": 1,
                      "support_range": .05,
                      "bounce_level": .01,
                      "break_level": .0002,
                      "trend": "bullish"
                      }

        check2 = support_level(tick_data_list, parameters)
        signals, support_levels, support_indices = check2
        triggers = np.sum(signals)
        self.assertEqual(triggers, 11.0)

        parameters = {"sensitivity": 30,
                      "local_max_sensitivity": 1,
                      "support_range": .005,
                      "bounce_level": .005,
                      "break_level": .005,
                      "trend": "bearish"
                      }

        check3 = support_level(tick_data_list, parameters)
        signals3, support_levels3, support_indices3 = check3
        triggers3 = np.sum(signals3)
        self.assertEqual(triggers3, 2.0)

    def test_resistance_trigger(self):
        end_time = datetime(2024, 11, 6, 23, 59)
        start_time = end_time - timedelta(days=30)
        df = yf.download(
            "NVDA",
            start=start_time,
            end=end_time,
            interval="15m"
        )
        # Convert the DataFrame to a list of TickData objects
        tick_data_list: List[TickData] = [
            TickData(
                close=row['Close'],
                open=row['Open'],
                high=row['High'],
                low=row['Low'],
                volume=row['Volume'],
                timestamp=index
            )
            for index, row in df.iterrows()
        ]

        parameters = {"sensitivity": 30,
                      "local_min_sensitivity": 1,
                      "resistance_range": .005,
                      "bounce_level": .01,
                      "break_level": .005,
                      "trend": "bullish"
                      }

        check = resistance_level(tick_data_list, parameters)
        signals, resistance_levels, resistance_indices = check
        triggers3 = np.sum(signals)
        self.assertEqual(triggers3, 6.0)

        parameters = {"sensitivity": 30,
                      "local_min_sensitivity": 1,
                      "resistance_range": .005,
                      "bounce_level": .009,
                      "break_level": .005,
                      "trend": "bearish"
                      }

        check2 = resistance_level(tick_data_list, parameters)
        signals, resistance_levels, resistance_indices = check2
        triggers4 = np.sum(signals)
        self.assertEqual(triggers4, 3.0)



    def test_fib_calcs(self):
        tick_data_list = generate_synthetic_fib_data()

        parameters = {"sensitivity": 10,
                      "local_max_sensitivity": 1,
                      "resistance_range": .0005,
                      "bounce_level": .009,
                      "break_level": .005,
                      "trend": "bullish"
                      }

        # fib_data, fib_indices = calculate_fibonacci_levels(tick_data_list, parameters)
        fib_trigger(tick_data_list, parameters)
        x