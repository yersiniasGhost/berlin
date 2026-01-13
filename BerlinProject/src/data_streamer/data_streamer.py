# data_streamer/data_streamer.py - Minimal change: just swap trade executor
"""
DataStreamer with simple aggregator selection logic - MINIMAL CHANGE VERSION
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from models.tick_data import TickData
from data_streamer.indicator_processor import IndicatorProcessor
from candle_aggregator.candle_aggregator import CandleAggregator
from candle_aggregator.candle_aggregator_normal import CANormal
from candle_aggregator.candle_aggregator_heiken import CAHeiken
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool
# ONLY CHANGE: Import unified trade executor instead of simple
from portfolios.trade_executor_unified import TradeExecutorUnified
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("DataStreamer")


class DataStreamer:
    """
    DataStreamer with simple aggregator type selection
    """

    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration, include_extended_hours: bool = True):
        self.card_id = card_id
        self.symbol = symbol
        self.monitor_config = monitor_config
        self.include_extended_hours = include_extended_hours

        aggregator_configs = monitor_config.get_aggregator_configs()
        self.aggregators: Dict[str, CandleAggregator] = {}

        for agg_key, agg_type in aggregator_configs.items():
            timeframe = agg_key.split('-')[0]  # Extract timeframe from key
            aggregator = self._create_aggregator(agg_type, symbol, timeframe)
            self.aggregators[agg_key] = aggregator  # ← Store with unique key!
            logger.info(f"Created {agg_type} aggregator for {timeframe}")

        # Processing components
        self.indicator_processor: IndicatorProcessor = IndicatorProcessor(monitor_config)
        self.external_tools: List[ExternalTool] = []

        # ONLY CHANGE: Use unified TradeExecutor with configuration from monitor_config
        self.trade_executor: TradeExecutorUnified = TradeExecutorUnified(monitor_config)

        # Initialize tracking variables
        self.indicators: Dict[str, float] = {}
        self.raw_indicators: Dict[str, float] = {}
        self.bar_scores: Dict[str, float] = {}

        logger.info(f"DataStreamer initialized for {symbol}")
        logger.info(f"Trade Executor Config: {monitor_config.trade_executor}")

    def process_tick(self, tick_data: TickData) -> None:
        """
        Process incoming TickData and execute trading logic
        """
        if tick_data.symbol != self.symbol:
            return

        # Process tick through all aggregators
        for timeframe, aggregator in self.aggregators.items():
            completed_candle = aggregator.process_tick(tick_data)
            if completed_candle is not None:
                logger.debug(f"Completed {timeframe} {aggregator._get_aggregator_type()} candle")

        # Calculate indicators based on current aggregator state
        self.indicators, self.raw_indicators, self.bar_scores = (
            self.indicator_processor.calculate_indicators_new(self.aggregators))

        # Execute trading logic
        self.trade_executor.make_decision(
            tick=tick_data,
            indicators=self.indicators,
            bar_scores=self.bar_scores
        )

        # Get portfolio performance metrics
        portfolio_metrics = self.trade_executor.portfolio.get_performance_metrics(tick_data.close)

        # Get data status for UI warnings
        data_status = self.indicator_processor.get_data_status()

        # Send data to external tools (including component data and data status)
        for tool in self.external_tools:
            tool.process_tick(
                card_id=self.card_id,
                symbol=self.symbol,
                tick_data=tick_data,
                indicators=self.indicators,
                raw_indicators=self.raw_indicators,
                bar_scores=self.bar_scores,
                portfolio_metrics=portfolio_metrics,
                component_data=self.indicator_processor.component_data,
                data_status=data_status
            )

    def _create_aggregator(self, agg_type: str, symbol: str, timeframe: str) -> CandleAggregator:
        """
        Create appropriate aggregator based on type
        """
        if agg_type == "heiken":
            return CAHeiken(symbol, timeframe, self.include_extended_hours)
        else:  # Default to normal
            return CANormal(symbol, timeframe, self.include_extended_hours)

    def _calculate_bar_scores(self) -> Dict[str, float]:
        """
        Calculate bar scores based on indicators and bar configurations with trend gating support.

        Trend gating allows trend indicators to filter/gate signal indicators:
        - If trend_indicators are configured, they act as multipliers on signal scores
        - If no trend_indicators are configured, bar score is calculated normally
        """
        bar_scores = {}

        for bar_name, bar_config in self.monitor_config.bars.items():
            if 'indicators' not in bar_config:
                continue

            # Get bar type for trend direction alignment
            bar_type = bar_config.get('type', 'bull')

            # Calculate signal score (weighted average of signal indicators)
            total_score = 0.0
            total_weight = 0.0

            for indicator_name, weight in bar_config['indicators'].items():
                if indicator_name in self.indicators:
                    indicator_value = self.indicators[indicator_name]
                    weighted_score = indicator_value * weight
                    total_score += weighted_score
                    total_weight += weight

            signal_score = total_score / total_weight if total_weight > 0 else 0.0

            # Calculate trend gate (NEW)
            trend_config = bar_config.get('trend_indicators', {})
            trend_logic = bar_config.get('trend_logic', 'AND')
            trend_threshold = bar_config.get('trend_threshold', 0.0)

            trend_gate = self._calculate_trend_gate(
                trend_config, bar_type, trend_logic, trend_threshold
            )

            # Apply trend gate to signal score
            bar_scores[bar_name] = signal_score * trend_gate

        return bar_scores

    def _calculate_trend_gate(self, trend_config: Dict, bar_type: str,
                              trend_logic: str, trend_threshold: float) -> float:
        """Calculate trend gate multiplier for bar scores.

        Args:
            trend_config: Dict of trend_indicator_name -> {weight, mode}
            bar_type: "bull" or "bear"
            trend_logic: "AND", "OR", or "AVG"
            trend_threshold: Minimum gate value required

        Returns:
            Trend gate multiplier (0.0 to 1.0)
        """
        if not trend_config:
            return 1.0  # No trend indicators - pass through

        trend_values = []

        for trend_name, config in trend_config.items():
            if trend_name not in self.indicators:
                continue

            trend_value = self.indicators[trend_name]

            # Get config options
            if isinstance(config, dict):
                weight = config.get('weight', 1.0)
                mode = config.get('mode', 'soft')
            else:
                weight = float(config)
                mode = 'soft'

            # Align direction with bar type
            if bar_type.lower() == 'bear':
                trend_value = -trend_value

            # Apply gating mode
            if mode == 'hard':
                gated_value = 1.0 if trend_value > 0 else 0.0
            else:  # 'soft'
                gated_value = max(0.0, min(1.0, trend_value))

            trend_values.append((gated_value, weight))

        if not trend_values:
            return 1.0

        # Combine based on logic
        if trend_logic.upper() == 'AND':
            gate = min(v for v, w in trend_values)
        elif trend_logic.upper() == 'OR':
            gate = max(v for v, w in trend_values)
        else:  # 'AVG'
            total_weight = sum(w for v, w in trend_values)
            gate = sum(v * w for v, w in trend_values) / total_weight if total_weight > 0 else 1.0

        return gate if gate >= trend_threshold else 0.0

    def get_portfolio_status(self) -> Dict:
        """Get current portfolio and trade executor status"""
        return {
            'portfolio': self.trade_executor.portfolio.get_summary(),
            'trade_executor': self.trade_executor.get_status(),
            'indicators': self.indicators,
            'bar_scores': self.bar_scores
        }

    def get_portfolio_metrics(self) -> Dict:
        """Get current portfolio performance metrics"""
        # Get the latest price from the most recent tick or candle data
        current_price = None
        for agg_key, aggregator in self.aggregators.items():
            if aggregator.get_current_candle():
                current_price = aggregator.get_current_candle().close
                break
        
        if current_price is None:
            # Fallback: try to get from history
            for agg_key, aggregator in self.aggregators.items():
                history = aggregator.get_history()
                if history:
                    current_price = history[-1].close
                    break
        
        return self.trade_executor.portfolio.get_performance_metrics(current_price)

    def enable_debug_mode(self):
        """Enable debug mode for trade executor"""
        pass

    def load_historical_data(self, data_link) -> None:
        """
        Load historical data for all aggregators using the provided data_link

        Args:
            data_link: Data link object with load_historical_data method
        """
        try:
            for agg_key, aggregator in self.aggregators.items():
                # Use prepopulate_data method from base CandleAggregator class
                candles_loaded = aggregator.prepopulate_data(data_link)
                logger.info(f"Loaded {candles_loaded} historical candles for {agg_key}")

            # After loading historical data, calculate initial indicators
            self._calculate_initial_indicators()

        except Exception as e:
            logger.error(f"Error loading historical data: {e}")

    def _calculate_initial_indicators(self) -> None:
        """
        Calculate indicators based on historical data loaded into aggregators.
        This is called after load_historical_data to initialize indicator state.
        """
        try:
            # Log aggregator state before calculating
            for agg_key, aggregator in self.aggregators.items():
                history_count = len(aggregator.get_history())
                has_current = aggregator.get_current_candle() is not None
                logger.info(f"Aggregator {agg_key}: history={history_count}, has_current={has_current}")

            # Calculate indicators from current aggregator state
            self.indicators, self.raw_indicators, self.bar_scores = (
                self.indicator_processor.calculate_indicators_new(self.aggregators))

            logger.info(f"Calculated initial indicators: {len(self.indicators)} indicators, "
                       f"{len(self.bar_scores)} bar scores")
            if self.indicators:
                logger.info(f"Indicator values: {self.indicators}")
            if self.bar_scores:
                logger.info(f"Bar scores: {self.bar_scores}")

        except Exception as e:
            logger.error(f"Error calculating initial indicators: {e}")
            import traceback
            traceback.print_exc()

    def emit_current_state(self) -> None:
        """
        Emit current state (indicators, bar_scores, data_status) to all external tools.
        Used to push initial state after historical data is loaded.
        """
        try:
            # Get the latest candle from any aggregator to use as tick_data
            tick_data = None
            for agg_key, aggregator in self.aggregators.items():
                current = aggregator.get_current_candle()
                if current:
                    tick_data = current
                    logger.info(f"Using current candle from {agg_key} for emit_current_state")
                    break
                # If no current candle, try history
                history = aggregator.get_history()
                if history:
                    tick_data = history[-1]
                    logger.info(f"Using last history candle from {agg_key} for emit_current_state")
                    break

            if not tick_data:
                # Create synthetic tick data for initial display
                logger.warning("No candle data available - creating synthetic tick for initial display")
                tick_data = TickData(
                    symbol=self.symbol,
                    timestamp=datetime.now(),
                    open=0.0,
                    high=0.0,
                    low=0.0,
                    close=0.0,
                    volume=0,
                    time_increment="PIP"
                )

            # Get portfolio metrics
            portfolio_metrics = self.trade_executor.portfolio.get_performance_metrics(tick_data.close)

            # Get data status for UI warnings
            data_status = self.indicator_processor.get_data_status()

            logger.info(f"emit_current_state for {self.symbol}: "
                       f"indicators={len(self.indicators)}, bar_scores={len(self.bar_scores)}, "
                       f"data_status={data_status.get('has_sufficient_data', 'N/A')}, "
                       f"tools={len(self.external_tools)}")

            # Send to all external tools
            for tool in self.external_tools:
                tool.process_tick(
                    card_id=self.card_id,
                    symbol=self.symbol,
                    tick_data=tick_data,
                    indicators=self.indicators,
                    raw_indicators=self.raw_indicators,
                    bar_scores=self.bar_scores,
                    portfolio_metrics=portfolio_metrics,
                    component_data=self.indicator_processor.component_data,
                    data_status=data_status
                )

            logger.info(f"Emitted current state for {self.symbol}: {len(self.indicators)} indicators")

        except Exception as e:
            logger.error(f"Error emitting current state: {e}")
            import traceback
            traceback.print_exc()

    def connect_tool(self, external_tool) -> None:
        """
        Connect an external tool to receive updates

        Args:
            external_tool: External tool to add to the list
        """
        if external_tool not in self.external_tools:
            self.external_tools.append(external_tool)
            logger.info(f"Connected external tool: {type(external_tool).__name__}")

    def _get_all_candle_data(self) -> Dict[str, List[TickData]]:
        """Get all candle data from aggregators - needed for API routes"""
        all_data: Dict[str, List[TickData]] = {}

        for agg_key, aggregator in self.aggregators.items():
            history: List[TickData] = aggregator.get_history().copy()
            current: Optional[TickData] = aggregator.get_current_candle()

            if current:
                history.append(current)

            all_data[agg_key] = history

        return all_data