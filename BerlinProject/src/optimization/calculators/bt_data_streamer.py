import logging
from typing import Dict, List, Optional, Any

from indicator_processor_historical_new import IndicatorProcessorHistoricalNew
from models.monitor_configuration import MonitorConfiguration
from candle_aggregator.candle_aggregator import CandleAggregator
from optimization.calculators.yahoo_finance_historical import YahooFinanceHistorical

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


    # pass in a data config
    def __init__(self, symbol: str, monitor_config: MonitorConfiguration):
        # self.card_id = card_id
        self.symbol = symbol
        self.monitor_config = monitor_config

        self.aggregators: Dict[str, CandleAggregator] = {}

        self.indicator_processor_historical_new = IndicatorProcessorHistoricalNew(monitor_config)

        # self.external_tools: List[ExternalTool] = []

        logger.info(f"BacktestDataStreamer created for {symbol}")

    # returns bars, raw indicators, and indicators to be used for the trade exec?
    def load_historical_data(self, yahoo_source: YahooFinanceHistorical, ticker: str, start_date: str, end_date: str):
        """
        Load historical data from YahooFinanceHistorical

        Args:
            yahoo_source: YahooFinanceHistorical instance
            ticker: Stock symbol
            start_date: Start date string "YYYY-MM-DD"
            end_date: End date string "YYYY-MM-DD"

        """
        try:
            logger.info(f"Loading historical data for {ticker}")

            # Process data through YahooFinanceHistorical
            yahoo_source.process_historical_data(ticker, start_date, end_date, self.monitor_config)
            self.aggregators = yahoo_source.aggregators

    def _run_indicator_processor(self):
        try:
            # Calculate the indicators
            indicators, raw_indicators, bar_scores = self.indicator_processor_historical_new.calculate_indicators(
                self.aggregators)

            # STORE the results as class attributes
            self.indicators = indicators
            self.raw_indicators = raw_indicators
            self.bar_scores = bar_scores

            logger.info("Indicators completed and stored")

        except Exception as e:
            logger.error(f"Error in indicator processor: {e}")