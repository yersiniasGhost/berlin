# optimization/calculators/bt_data_streamer.py - Parallel processing compatible version

import logging
import json
from typing import Dict, List, Optional, Any

from models.monitor_configuration import MonitorConfiguration
from candle_aggregator.candle_aggregator import CandleAggregator
from mongo_tools.mongo_db_connect import MongoDBConnect
from optimization.calculators.indicator_processor_historical_new import IndicatorProcessorHistoricalNew
from portfolios.portfolio_tool import Portfolio
from portfolios.trade_executor_unified import TradeExecutorUnified
from models.tick_data import TickData

logger = logging.getLogger('BacktestDataStreamer')


class BacktestDataStreamer:
    """
    Optimized backtest streamer for genetic algorithms using unified trade executor.
    Modified for parallel processing compatibility:
    1. Constructor doesn't require arguments (for pickling)
    2. Data loading separated from initialization
    3. All attributes are pickle-friendly
    """

    def __init__(self):
        self.monitor_config: Optional[dict] = None
        self.ticker: Optional[str] = None
        self.start_date: Optional[str] = None
        self.end_date: Optional[str] = None

        # Core data attributes
        self.aggregators: Optional[list] = None
        self.tick_history: List[TickData] = []
        self.primary_timeframe = None
        self.primary_aggregator = None

        # Create unified trade executor from monitor config
        self.trade_executor: Optional[TradeExecutorUnified] = None



    def initialize(self, aggregators: Dict[str, CandleAggregator], data_config: Dict[str, Any], monitor_config: MonitorConfiguration):
        """
        Initialize BacktestDataStreamer with pre-built aggregators and data config.
        """
        self.monitor_config = monitor_config
        self.ticker = data_config['ticker']
        self.start_date = data_config['start_date']
        self.end_date = data_config['end_date']

        # Core data attributes
        self.aggregators = aggregators
        self.tick_history: List[TickData] = []
        self.primary_timeframe = None
        self.primary_aggregator = None

        # Create unified trade executor from monitor config
        self.trade_executor = TradeExecutorUnified(self.monitor_config)

        # Build tick history from provided aggregators
        self._build_tick_history()

        logger.info(f"🔄 BacktestDataStreamer initialized: {self.ticker} {self.start_date} to {self.end_date}")
        logger.info(f"   Got {len(self.aggregators)} aggregators with {len(self.tick_history)} ticks")



    def _initialize_from_config(self, data_config_file: str):
        """Initialize from config file (original initialization logic)"""
        # Load data config
        with open(data_config_file, 'r') as f:
            data_config = json.load(f)

        self.ticker = data_config['ticker']
        self.start_date = data_config['start_date']
        self.end_date = data_config['end_date']
        
        logger.info(f"🔄 BacktestDataStreamer initializing with ticker: {self.ticker}")
        logger.info(f"   Date range: {self.start_date} to {self.end_date}")

        # Create unified trade executor from monitor config
        self.trade_executor = TradeExecutorUnified(self.monitor_config)

        # Clear any existing aggregators to force fresh data load
        self.aggregators.clear()
        self.tick_history.clear()

        # Load all historical data once
        # self.load_historical_data()
        self._build_tick_history()


    def _build_tick_history(self):
        """Build tick history from primary timeframe aggregator"""
        if not self.aggregators:
            logger.error("No aggregators available to build tick history")
            self.tick_history = []
            return

        # Build tick history once from primary timeframe
        self.primary_timeframe = self._get_primary_timeframe()
        self.primary_aggregator = self.aggregators[self.primary_timeframe]
        all_candles = self.primary_aggregator.get_history()

        if len(all_candles) == 0:
            logger.error("No historical candles loaded!")
            self.tick_history = []
            return

        # Convert candles to tick history once
        self.tick_history = []
        for candle in all_candles:
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
            self.tick_history.append(tick_data)

        logger.info(f"BacktestDataStreamer created with {len(self.tick_history)} ticks")



    def copy_data_from(self, source_streamer: 'BacktestDataStreamer'):
        """
        Copy precomputed data from a source streamer (for parallel processing).
        This avoids reloading data in each worker process.
        """
        self.ticker = source_streamer.ticker
        self.start_date = source_streamer.start_date
        self.end_date = source_streamer.end_date
        self.aggregators = source_streamer.aggregators  # Shared read-only data
        self.tick_history = source_streamer.tick_history  # Shared read-only data
        self.primary_timeframe = source_streamer.primary_timeframe
        self.primary_aggregator = source_streamer.primary_aggregator

        logger.debug(f"Copied data: {len(self.tick_history)} ticks, {len(self.aggregators)} aggregators")



    def run_backtest(self):
        """
        OPTIMIZED: Calculate ALL indicators at once, then execute trades
        This is the key change for GA performance
        """
        if not self.tick_history:
            logger.error("No tick history available for backtest")
            raise ValueError("Expected Tick History")

        if not self.trade_executor:
            logger.error("No trade executor available - call replace_monitor_config() first")
            raise ValueError("Requires TradeExecutor")

        logger.debug(f"Running optimized backtest with {len(self.tick_history)} ticks")

        # STEP 1: Calculate ALL indicators for entire timeline at once (batch processing)
        indicator_processor = IndicatorProcessorHistoricalNew(self.monitor_config)
        indicator_history, raw_indicator_history, bar_score_history, component_history = (
            indicator_processor.calculate_indicators(self.aggregators)
        )

        # STEP 2: Execute trades using pre-calculated indicators
        for i, tick_data in enumerate(self.tick_history):
            # Get pre-calculated indicators for this time point
            indicators = {}
            bar_scores = {}

            # Extract indicators for this tick
            for indicator_name, values in indicator_history.items():
                indicators[indicator_name] = values[i] if i < len(values) else 0.0

            # Extract bar scores for this tick
            for bar_name, values in bar_score_history.items():
                bar_scores[bar_name] = values[i] if i < len(values) else 0.0

            # Execute trading decision with pre-calculated data
            self.trade_executor.make_decision(
                tick=tick_data,
                indicators=indicators,
                bar_scores=bar_scores
            )



    def replace_monitor_config(self, monitor_config: MonitorConfiguration):
        """Replace configuration - data stays loaded, just reset portfolio and trade executor"""
        self.monitor_config = monitor_config

        # Create new trade executor with new configuration
        self.trade_executor = TradeExecutorUnified(monitor_config)



    def _get_primary_timeframe(self) -> str:
        """Get the shortest timeframe as primary"""
        if not self.aggregators:
            return None

        timeframe_minutes = {key: self._timeframe_to_minutes(key) for key in self.aggregators.keys()}
        return min(timeframe_minutes.keys(), key=lambda x: timeframe_minutes[x])



    def _timeframe_to_minutes(self, aggregator_key: str) -> int:
        """Convert aggregator key to minutes"""
        base_timeframe = aggregator_key.split('-')[0] if '-' in aggregator_key else aggregator_key
        timeframe_map = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60
        }
        return timeframe_map.get(base_timeframe, 1)



    def run(self) -> Portfolio:
        """Complete backtest process"""
        self.run_backtest()
        return self.trade_executor.portfolio



    def __getstate__(self):
        """Custom pickling to handle any non-pickleable attributes"""
        state = self.__dict__.copy()
        # Remove any non-pickleable attributes if needed
        # (Add any problematic attributes here)
        return state



    def __setstate__(self, state):
        """Custom unpickling"""
        self.__dict__.update(state)