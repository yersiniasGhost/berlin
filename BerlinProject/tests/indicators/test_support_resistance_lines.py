import os
import unittest
from typing import List

import yfinance as yf
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.features.indicators2 import (calculate_support, calculate_resistance,
                                      support_level, resistance_level, calculate_fibonacci_levels, fib_trigger)

from environments.tick_data import TickData


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
        end_time = datetime(2024, 11, 6, 23, 59)
        start_time = end_time - timedelta(days=30)
        df = yf.download(
            "NVDA",
            start=start_time,
            end=end_time,
            interval="15m"
        )

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
                      "resistance_range": .005,
                      "bounce_level": .009,
                      "break_level": .005,
                      "trend": "bullish"
                      }

        # fib_data, fib_indices = calculate_fibonacci_levels(tick_data_list, parameters)
        grub= fib_trigger(tick_data_list, parameters)
        x