import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from models.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration
from candle_aggregator.candle_aggregator import CandleAggregator
from candle_aggregator.candle_aggregator_normal import CANormal
from candle_aggregator.candle_aggregator_heiken import CAHeiken
from data_streamer.external_tool import ExternalTool

logger = logging.getLogger('BacktestDataStreamer')


class BacktestDataStreamer:
    """
    Simple backtest data streamer

    Lego Brick Responsibilities:
    1. Get historical data from data source
    2. Own and manage aggregators
    3. Process data through aggregators
    4. Run indicator processor
    5. Send results to external tools
    """

    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration):
        self.card_id = card_id
        self.symbol = symbol
        self.monitor_config = monitor_config

        self.aggregators: Dict[str, CandleAggregator] = {}
        self.indicator_processor = None
        self.external_tools: List[ExternalTool] = []

        logger.info(f"BacktestDataStreamer created for {symbol} with {len(self.aggregators)} aggregators")

    def load_historical_data(self, yahoo_source, ticker: str, start_date: str, end_date: str) -> bool:
        """
        Load historical data from YahooFinanceHistorical

        Args:
            yahoo_source: YahooFinanceHistorical instance
            ticker: Stock symbol
            start_date: Start date string "YYYY-MM-DD"
            end_date: End date string "YYYY-MM-DD"

        Returns:
            bool: Success status
        """
        try:
            logger.info(f"Loading historical data for {ticker}")

            # Process data through YahooFinanceHistorical
            success = yahoo_source.process_historical_data(ticker, start_date, end_date, self.monitor_config)

            if not success:
                logger.error("YahooFinanceHistorical processing failed")
                return False

            # Simply copy the processed aggregators from YahooFinanceHistorical
            self.aggregators = yahoo_source.get_all_aggregators()

            logger.info(f"✅ Successfully loaded aggregators with processed data")

            # Report aggregator results
            self._report_aggregator_results()

            # Run indicator processor
            self._run_indicator_processor()

            return True

        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            return False

    def _report_aggregator_results(self):
        """
        Report candle counts for each aggregator
        """
        logger.info("Aggregator Results:")

        for timeframe, aggregator in self.aggregators.items():
            history = aggregator.get_history()
            current = aggregator.get_current_candle()
            total = len(history) + (1 if current else 0)

            logger.info(f"  {timeframe}: {len(history)} completed + {1 if current else 0} current = {total} candles")

    def _run_indicator_processor(self):
        """
        PLACEHOLDER: Run indicator processor on aggregated data
        """
        logger.info("Running indicator processor...")

        try:
            # indicators, raw_indicators, bar_scores = self.indicator_processor.calculate_indicators(self.aggregators)

            logger.info(f"Aggregators ready for indicator processing:")
            for timeframe, aggregator in self.aggregators.items():
                history_count = len(aggregator.get_history())
                current = aggregator.get_current_candle()
                logger.info(f"  {timeframe}: {history_count} completed + {1 if current else 0} current candles")

            logger.info("Indicators completed")

        except Exception as e:
            logger.error(f"Error in indicator processor: {e}")
