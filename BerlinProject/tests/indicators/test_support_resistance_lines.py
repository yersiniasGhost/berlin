import os
import unittest
import yfinance as yf
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.features.indicators2 import calculate_support, calculate_resistance, support_level, resistance_level

from environments.tick_data import TickData


class TestCalculateLines(unittest.TestCase):

    def test_support(self):
        data = np.array([8, 7, 6, 5, 7, 7, 4, 5])
        check = calculate_support(data, sensitivity=1)
        self.assertEqual(check, np.array([3, 6]))

    def test_resistance(self):
        data = np.array([4, 5, 8, 7, 6, 5, 8, 5])
        check = calculate_resistance(data, sensitivity=1)
        self.assertEqual(check, np.array([2, 6]))

    def test_support_tigger(self):

        # Yfinance doesn't have great minute data
        end_time = datetime(2024, 11, 6, 23, 59)
        start_time = end_time - timedelta(days=30)

        # Yfinance doesn't have great minute data
        df = yf.download(
            "NVDA",
            start=start_time,
            end=end_time,
            interval="15m")
        close_prices = np.array(df['Close'])
        minutes = np.arange(len(close_prices))

        check2 = support_level(close_prices, 30, .05, .01, .0002, 'bull')
        signals, support_levels, support_indices = check2
        triggers = np.sum(signals)

        check3 = support_level(close_prices, 30, .005, .005, .005, 'bear')
        signals3, support_levels3, support_indices3 = check3
        triggers3 = np.sum(signals3)
        x

    def test_resistance_trigger(self):

        end_time = datetime(2024, 11, 6, 23, 59)
        start_time = end_time - timedelta(days=30)

        # Yfinance doesn't have great minute data
        df = yf.download(
            "NVDA",
            start=start_time,
            end=end_time,
            interval="15m")
        close_prices = np.array(df['Close'])
        minutes = np.arange(len(close_prices))

        check = resistance_level(close_prices, 30, .005, .01, .005, 'bull')
        signals, resistance_levels, resistance_indices = check
        triggers3 = np.sum(signals)

        check2 = resistance_level(close_prices, 30, .005, .009, .005, 'bear')
        signals, resistance_levels, resistance_indices = check2
        triggers4 = np.sum(signals)
        x
