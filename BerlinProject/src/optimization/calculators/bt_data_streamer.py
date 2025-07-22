import logging
import json
from typing import Dict, List, Optional, Any

from models.monitor_configuration import MonitorConfiguration
from candle_aggregator.candle_aggregator import CandleAggregator
from candle_aggregator.candle_aggregator_normal import CANormal
from candle_aggregator.candle_aggregator_heiken import CAHeiken
from optimization.calculators.yahoo_finance_historical import YahooFinanceHistorical
from data_streamer.indicator_processor import IndicatorProcessor
from portfolios.portfolio_tool import Portfolio
from portfolios.trade_executor import TradeExecutor
from portfolios.trade_executor_new import TradeExecutorNew
from models.tick_data import TickData

logger = logging.getLogger('BacktestDataStreamer')


#TODO: add candle chart in the details
#  filter out bad data from schwab pips
# TODO: changebar colors based on what the parameter types on each bar.
# TODO: add monitor creation/ edit page for UI / get into MONGO!

class BacktestDataStreamer:

    def __init__(self, monitor_config: MonitorConfiguration, data_config_file: str,
                 trade_executor: TradeExecutor):
        self.monitor_config = monitor_config

        # Load data config
        with open(data_config_file, 'r') as f:
            data_config = json.load(f)

        self.ticker = data_config['ticker']
        self.start_date = data_config['start_date']
        self.end_date = data_config['end_date']

        self.aggregators: Dict[str, CandleAggregator] = {}
        self.indicator_processor: IndicatorProcessor = IndicatorProcessor(monitor_config)

        # Use injected trade executor
        self.trade_executor = trade_executor
        self.load_historical_data()
        logger.info(f"BacktestDataStreamer created with {type(trade_executor).__name__}")

    def load_historical_data(self):
        """Load historical data into aggregators via YahooFinanceHistorical"""
        yahoo_source = YahooFinanceHistorical()
        yahoo_source.process_historical_data(self.ticker, self.start_date, self.end_date, self.monitor_config)

        # Get the fully populated aggregators from YahooFinanceHistorical
        self.aggregators = yahoo_source.aggregators
        logger.info(f"Got {len(self.aggregators)} aggregators from YahooFinanceHistorical:")

        for timeframe, aggregator in self.aggregators.items():
            history_count = len(aggregator.get_history())
            has_current = aggregator.get_current_candle() is not None
            agg_type = aggregator._get_aggregator_type()
            logger.info(
                f"  {timeframe} ({agg_type}): {history_count} completed + {1 if has_current else 0} current candles")

    def run_backtest(self):
        """Simple backtest simulation"""
        primary_timeframe = self._get_primary_timeframe()
        primary_aggregator = self.aggregators[primary_timeframe]
        all_candles = primary_aggregator.get_history()

        if len(all_candles) == 0:
            print("BAD! NO CANDLES")

        for i, candle in enumerate(all_candles):
            tick_data = TickData(
                symbol=self.ticker,
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                time_increment="BACKTEST"
            )

            for timeframe_key, aggregator in self.aggregators.items():
                aggregator.process_tick(tick_data)

            indicators, raw_indicators, bar_scores = (
                self.indicator_processor.calculate_indicators_new(self.aggregators))

            self.trade_executor.make_decision(
                tick=tick_data,
                indicators=indicators,
                bar_scores=bar_scores
            )

    def replace_monitor_config(self, monitor_config: MonitorConfiguration):

        #  reinit portfolio
        # reset indicator values for our streamer run method
        self.monitor_config = monitor_config
        self.indicator_processor = IndicatorProcessor(monitor_config)
        self.trade_executor.portfolio.reset()
        self.trade_executor.monitor_config = monitor_config

    def _get_primary_timeframe(self) -> str:

        timeframe_minutes = {key: self._timeframe_to_minutes(key) for key in self.aggregators.keys()}
        return min(timeframe_minutes.keys(), key=lambda x: timeframe_minutes[x])

    def _timeframe_to_minutes(self, aggregator_key: str) -> int:
        """Convert aggregator key to minutes"""
        base_timeframe = aggregator_key.split('-')[0] if '-' in aggregator_key else aggregator_key

        timeframe_map = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60
        }

        return timeframe_map.get(base_timeframe)

    def run(self) -> Portfolio:
        """Complete backtest process"""
        # self.load_historical_data()
        self.run_backtest()
        return self.trade_executor.portfolio
