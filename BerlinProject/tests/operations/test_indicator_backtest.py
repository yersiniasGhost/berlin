import unittest
from datetime import datetime

from environments.tick_data import TickData
from mongo_tools.tick_history_tools import TickHistoryTools
from operations.indicator_backtest import IndicatorBacktest, Trade


class TestIndicatorBackTest(unittest.TestCase):

    def test_indicator_vector(self):
        backtest = IndicatorBacktest('CDL')

        tick = TickData(close=100.0, open=100.0, high=100.0, low=100.0)
        tick2 = TickData(close=100.2, open=100.0, high=100.0, low=100.0)

        reward_sell_tick = TickData(close=102.0, open=102.0, high=102.0, low=102.0)
        stop_sell_tick = TickData(close=99.0, open=99.0, high=99.0, low=99.0)

        indicators = {"CDL": 1.0}
        indicator_no_trigger = {"CDL": 0.0}

        backtest.indicator_vector(indicators, tick, index=1)
        self.assertIsNotNone(backtest.trade)
        self.assertTrue(backtest.trade.entry_price == 100)
        self.assertTrue(backtest.trade.entry_index == 1)

        # Test it doesn't buy twice

        backtest.indicator_vector(indicators, tick2, index=2)
        self.assertTrue(backtest.trade.entry_index == 1)

        # Test it gets out of the position after price rise
        backtest.indicator_vector(indicator_no_trigger, reward_sell_tick, index=3)
        self.assertIsNone(backtest.trade)
        self.assertEqual(1, len(backtest.trade_history))
        trade = backtest.trade_history[0]
        self.assertEqual(trade.exit_index, 3)
        self.assertEqual(trade.entry_index, 1)

        backtest.indicator_vector(indicators, tick, index=4)
        self.assertIsNotNone(backtest.trade)
        backtest.indicator_vector(indicator_no_trigger, stop_sell_tick, index=5)
        self.assertIsNone(backtest.trade)
        self.assertEqual(2, len(backtest.trade_history))
        trade_loss = backtest.trade_history[1]
        self.assertEqual(5, trade_loss.exit_index)


#  Call multiple indicators and use them with real data from the data history tool.
#  See if it properly identifies the triggers and buys and sells appropriately.

class TestIndicatorBackTestRealData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tools = TickHistoryTools.get_tools(
            ticker="AAPL",
            start_date=datetime(2024, 10, 15),
            end_date=datetime(2024, 10, 20),
            time_increments=1
        )

        x
