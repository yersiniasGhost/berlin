import unittest
from datetime import datetime

from environments.tick_data import TickData
from mongo_tools.tick_history_tools import TickHistoryTools
from operations.indicator_backtest import IndicatorBacktest, Trade
from data_streamer.data_streamer import DataStreamer


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

    def test_real_data_init(self):
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 10, 16),
            end_date=datetime(2024, 10, 23),
            time_increments=1
        )

        ticks = list(tools.serve_next_tick())
        self.assertEqual(len(ticks), 390,
                         f"Expected 390 ticks for one trading day, got {len(ticks)}")

    def test_indicator_trigger(self):
        data_config = {
            'type': 'TickHistory',
            'ticker': "NVDA",
            'start_date': datetime(2024, 10, 23),
            'end_date': datetime(2024, 10, 23),
            'time_increment': 1

        }
        from config.types import PyObjectId, CANDLE_STICK_PATTERN, INDICATOR_TYPE

        indicator_config_macd = {
            'name': 'my_silly_macd_cross',
            'function': 'macd_histogram_crossover',
            'type': INDICATOR_TYPE,
            'parameters': {
                'fast': 6,
                'slow': 14,
                'signal': 5,
                'histogram_threshold': .05
            }
        }

        indicator_config_sma = {
            'name': 'my_silly_sma_cross',
            'function': 'sma_crossover',
            'type': INDICATOR_TYPE,
            'parameters': {
                'period': 10,
                'crossover_value': .0005
            }
        }

        indicator_config_bol = {
            'name': 'my_silly_bol_bounce',
            'function': 'bol_bands_lower_band_bounce',
            'type': INDICATOR_TYPE,
            'parameters': {
                'period': 10,
                'sd': 2,
                'candle_bounce_number': 5,
                'bounce_trigger': .2}

        }

        from models.indicator_configuration import IndicatorDefinition, IndicatorConfiguration
        sma = IndicatorDefinition(**indicator_config_macd)
        ind_config = IndicatorConfiguration(name="test", indicators=[sma])

        model_config = {
            "preprocess_config": "test_ds",
        }

        bt = IndicatorBacktest('my_silly_macd_cross')
        streamer = DataStreamer(data_config, model_config, ind_config)
        streamer.connect_tool(bt)
        streamer.run()
        x
        # self.assertEqual(0, len(bt.trade_history))
