"""
Shared Chart Data Service for consistent data extraction across Flask apps.

This service is used by both:
- stock_analysis_ui (live trading dashboard)
- visualization_apps (replay/backtest tool)

Ensures DRY principle: single source of truth for chart data formatting.
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

import numpy as np

from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("ChartDataService")


@dataclass
class TradeEntry:
    """Standardized trade entry for frontend consumption."""
    timestamp: int
    type: str  # 'buy' or 'sell'
    price: float
    size: float
    reason: str
    pnl: float  # Percentage P&L (for sell trades)
    pnl_dollars: float  # Dollar P&L (for sell trades)


class ChartDataService:
    """
    Unified service for extracting and formatting chart data.

    Provides consistent data structures for:
    - Candlestick charts (Highcharts OHLC format)
    - Trade history tables (with P&L calculations)
    - Bar scores charts (weighted indicator scores)
    - Indicator analysis charts (raw values, triggers)
    - Trade details (for modal popups)
    """

    @staticmethod
    def format_candlestick_data(candles: List[Any]) -> List[List]:
        """
        Format candle data for Highcharts OHLC series.

        Args:
            candles: List of candle objects with timestamp, open, high, low, close

        Returns:
            List of [timestamp_ms, open, high, low, close] arrays
        """
        candlestick_data = []
        for candle in candles:
            timestamp_ms = int(candle.timestamp.timestamp() * 1000)
            candlestick_data.append([
                timestamp_ms,
                float(candle.open),
                float(candle.high),
                float(candle.low),
                float(candle.close)
            ])
        return candlestick_data

    @staticmethod
    def format_all_aggregator_candles(all_candle_data: Dict[str, List[Any]]) -> Dict[str, List[List]]:
        """
        Format candlestick data for all aggregators.

        Args:
            all_candle_data: Dict mapping aggregator key to list of candles

        Returns:
            Dict mapping aggregator key to formatted candlestick data
        """
        per_aggregator_candles = {}
        for agg_key, candles in all_candle_data.items():
            per_aggregator_candles[agg_key] = ChartDataService.format_candlestick_data(candles)
            logger.debug(f"Prepared {len(per_aggregator_candles[agg_key])} candles for {agg_key}")
        return per_aggregator_candles

    @staticmethod
    def extract_trade_history(portfolio, trade_details_history: Optional[Dict] = None) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Extract trade history with P&L calculations from portfolio.

        Matches the format expected by the Replay tool's trade history table.

        Args:
            portfolio: Portfolio object with trade_history
            trade_details_history: Optional dict mapping timestamp -> trade details

        Returns:
            Tuple of (trade_history, triggers, pnl_history)
            - trade_history: List of trade entries for table display
            - triggers: List of trigger markers for chart overlay
            - pnl_history: List of cumulative P&L points
        """
        trade_history = []
        triggers = []
        pnl_history = []

        if not portfolio or not hasattr(portfolio, 'trade_history') or not portfolio.trade_history:
            logger.debug("No trade history found in portfolio")
            return trade_history, triggers, pnl_history

        trade_details = trade_details_history or {}

        # Track for P&L calculations
        cumulative_pnl_pct = 0.0
        last_entry_price = 0.0
        last_entry_size = 0.0

        logger.info(f"Extracting {len(portfolio.trade_history)} trades from portfolio")

        for trade in portfolio.trade_history:
            # Determine trade type
            trade_type = 'sell' if trade.reason.is_exit() else 'buy'

            # Convert timestamp to milliseconds
            timestamp_ms = int(trade.time) if isinstance(trade.time, (int, float)) else int(trade.time.timestamp() * 1000)

            # Calculate P&L for sell trades
            pnl_pct = 0.0
            pnl_dollars = 0.0

            if trade_type == 'sell' and last_entry_price > 0:
                pnl_pct = ((trade.price - last_entry_price) / last_entry_price) * 100.0
                pnl_dollars = last_entry_size * (trade.price - last_entry_price)

            # Override with detailed P&L if available from trade executor
            if timestamp_ms in trade_details:
                detail = trade_details[timestamp_ms]
                if 'pnl_pct' in detail:
                    pnl_pct = detail['pnl_pct']
                if 'pnl_dollars' in detail:
                    pnl_dollars = detail['pnl_dollars']

            # Build trade entry
            trade_entry = {
                'timestamp': timestamp_ms,
                'type': trade_type,
                'price': float(trade.price),
                'quantity': float(trade.size),
                'size': float(trade.size),  # Alias for frontend compatibility
                'reason': trade.reason.value if hasattr(trade.reason, 'value') else str(trade.reason),
                'pnl': pnl_pct,
                'pnl_dollars': pnl_dollars
            }
            trade_history.append(trade_entry)

            # Track entry for next sell calculation
            if trade_type == 'buy':
                last_entry_price = trade.price
                last_entry_size = trade.size

            # Add trigger marker for chart overlay
            triggers.append({
                'timestamp': timestamp_ms,
                'type': trade_type,
                'price': float(trade.price),
                'reason': trade_entry['reason']
            })

            # Update cumulative P&L for sell trades
            if trade_type == 'sell':
                cumulative_pnl_pct += pnl_pct
                pnl_history.append({
                    'timestamp': timestamp_ms,
                    'cumulative_pnl': cumulative_pnl_pct,
                    'trade_pnl': pnl_pct
                })

        logger.info(f"Extracted {len(trade_history)} trades, {len(triggers)} triggers, {len(pnl_history)} P&L points")
        return trade_history, triggers, pnl_history

    @staticmethod
    def extract_bar_scores_history(bar_score_history_dict: Dict[str, List[float]],
                                    timestamps: List[int]) -> List[Dict]:
        """
        Extract bar scores history for chart visualization.

        Args:
            bar_score_history_dict: Dict mapping bar name to list of scores
            timestamps: List of timestamps in milliseconds

        Returns:
            List of {timestamp, scores: {bar_name: score}} entries
        """
        bar_scores_history = []

        if not bar_score_history_dict or not timestamps:
            return bar_scores_history

        timeline_length = len(timestamps)

        for i in range(timeline_length):
            scores = {}
            for bar_name, bar_values in bar_score_history_dict.items():
                if i < len(bar_values) and bar_values[i] is not None:
                    try:
                        float_val = float(bar_values[i])
                        # Replace NaN/Inf with 0.0
                        scores[bar_name] = 0.0 if (math.isnan(float_val) or math.isinf(float_val)) else float_val
                    except (ValueError, TypeError):
                        scores[bar_name] = 0.0
                else:
                    scores[bar_name] = 0.0

            bar_scores_history.append({
                'timestamp': timestamps[i],
                'scores': scores
            })

        logger.info(f"Generated {len(bar_scores_history)} bar score history entries")
        return bar_scores_history

    @staticmethod
    def build_trade_details_for_ui(trade_details_history: Dict[int, Dict]) -> Dict[int, Dict]:
        """
        Format trade details for the UI modal popup.

        The trade details include entry/exit info, trigger reasons,
        bar scores at trade time, and indicator values.

        Args:
            trade_details_history: Dict mapping timestamp -> trade detail dict

        Returns:
            Formatted trade details dict
        """
        # The trade_details_history from TradeExecutorUnified is already
        # in the correct format, so we just return it with any needed sanitization
        return ChartDataService.sanitize_data(trade_details_history)

    @staticmethod
    def build_indicator_chart_data(indicator_processor, monitor_config, all_candle_data: Dict[str, List]) -> Dict[str, Any]:
        """
        Build indicator data for chart visualization.

        Args:
            indicator_processor: IndicatorProcessor instance
            monitor_config: MonitorConfiguration with indicator definitions
            all_candle_data: Dict of aggregator key -> candle list

        Returns:
            Dict with indicator_history, raw_indicator_history, component_history, etc.
        """
        indicator_history = {}
        raw_indicator_history = {}
        component_history = {}

        # Build indicator -> aggregator mapping
        indicator_agg_mapping = {}
        for indicator_def in monitor_config.indicators:
            timeframe = indicator_def.get_timeframe()
            agg_type = indicator_def.get_aggregator_type()
            agg_key = f"{timeframe}-{agg_type}"
            indicator_agg_mapping[indicator_def.name] = agg_key

        # Extract trigger history (0/1 values)
        if hasattr(indicator_processor, 'indicator_trigger_history'):
            for ind_name, history in indicator_processor.indicator_trigger_history.items():
                # Extract actual indicator name from internal key
                actual_name = ind_name.split('_', 1)[-1] if '_' in ind_name else ind_name

                # Get aggregator key for timestamps
                agg_key = indicator_agg_mapping.get(actual_name)
                if not agg_key and '_' in ind_name:
                    agg_key = ind_name.rsplit('_', 1)[0]

                # Get timestamps from aggregator
                timestamps = []
                if agg_key and agg_key in all_candle_data:
                    candles = all_candle_data[agg_key]
                    timestamps = [int(c.timestamp.timestamp() * 1000) for c in candles[-len(history):]]

                # Pad timestamps if needed
                while len(timestamps) < len(history):
                    base_ts = timestamps[0] if timestamps else 0
                    timestamps.insert(0, base_ts - (len(history) - len(timestamps)) * 60000)

                # Format as [[timestamp, value], ...]
                series = []
                for i, value in enumerate(history):
                    if i < len(timestamps) and value is not None:
                        series.append([timestamps[i], float(value)])

                if series:
                    raw_indicator_history[actual_name] = series

        # Extract current indicator values
        if hasattr(indicator_processor, 'indicators'):
            for ind_name, value in indicator_processor.indicators.items():
                agg_key = indicator_agg_mapping.get(ind_name)
                if agg_key and agg_key in all_candle_data:
                    candles = all_candle_data[agg_key]
                    if candles:
                        timestamp = int(candles[-1].timestamp.timestamp() * 1000)
                        indicator_history[ind_name] = [[timestamp, float(value)]]

        # Extract component history (MACD line, signal, histogram, SMA values, etc.)
        # Prefer historical component data if available, otherwise fall back to current values
        if hasattr(indicator_processor, 'component_history') and indicator_processor.component_history:
            # Use full component history with timestamps from indicator_processor
            timestamps = []
            if hasattr(indicator_processor, 'timestamp_history') and indicator_processor.timestamp_history:
                timestamps = [int(ts.timestamp() * 1000) for ts in indicator_processor.timestamp_history]

            for comp_name, comp_values in indicator_processor.component_history.items():
                series = []
                for i, value in enumerate(comp_values):
                    if i < len(timestamps):
                        # Check for None and NaN values (np.nan is not None, so explicit check needed)
                        if value is None:
                            continue
                        try:
                            float_val = float(value)
                            if math.isnan(float_val) or math.isinf(float_val):
                                continue
                            series.append([timestamps[i], float_val])
                        except (ValueError, TypeError):
                            continue
                if series:
                    component_history[comp_name] = series

            logger.info(f"Component history: {len(component_history)} components with historical data")
        elif hasattr(indicator_processor, 'component_data'):
            # Fallback: use current component values (single point)
            for comp_name, comp_value in indicator_processor.component_data.items():
                indicator_name = comp_name.rsplit('_', 1)[0] if '_' in comp_name else comp_name
                agg_key = indicator_agg_mapping.get(indicator_name)

                if agg_key and agg_key in all_candle_data:
                    candles = all_candle_data[agg_key]
                    if candles:
                        timestamp = int(candles[-1].timestamp.timestamp() * 1000)
                        component_history[comp_name] = [[timestamp, float(comp_value)]]
            logger.info(f"Component history: {len(component_history)} components (current values only)")

        return {
            'indicator_history': indicator_history,
            'raw_indicator_history': raw_indicator_history,
            'component_history': component_history,
            'indicator_agg_mapping': indicator_agg_mapping
        }

    @staticmethod
    def build_class_to_layout_mapping(monitor_config) -> Dict[str, str]:
        """
        Build mapping of indicator NAME to chart layout type.

        Args:
            monitor_config: MonitorConfiguration with indicator definitions

        Returns:
            Dict mapping indicator NAME to layout type ('stacked', 'overlay', etc.)
            Uses indicator name (e.g., "MACD5m Bear") as key for frontend compatibility.
        """
        class_to_layout = {}

        try:
            import indicator_triggers.refactored_indicators
            from indicator_triggers.indicator_base import IndicatorRegistry
            registry = IndicatorRegistry()

            for indicator_def in monitor_config.indicators:
                indicator_class_name = indicator_def.indicator_class
                indicator_name = indicator_def.name  # Use name as key for frontend
                if indicator_class_name:
                    try:
                        indicator_cls = registry.get_indicator_class(indicator_class_name)
                        layout_type = indicator_cls.get_layout_type()
                        # Map indicator NAME to layout, not class name
                        class_to_layout[indicator_name] = layout_type
                        # Also keep class name mapping for backwards compatibility
                        if indicator_class_name not in class_to_layout:
                            class_to_layout[indicator_class_name] = layout_type
                    except (ValueError, AttributeError):
                        # Default based on name heuristics
                        layout_type = 'stacked' if 'macd' in indicator_class_name.lower() else 'overlay'
                        class_to_layout[indicator_name] = layout_type
                        class_to_layout[indicator_class_name] = layout_type
        except Exception as e:
            logger.warning(f"Could not build class_to_layout mapping: {e}")

        return class_to_layout

    @staticmethod
    def build_indicators_list(monitor_config) -> List[Dict]:
        """
        Build list of indicator definitions for frontend.

        Args:
            monitor_config: MonitorConfiguration

        Returns:
            List of indicator definition dicts
        """
        indicators_list = []
        for indicator_def in monitor_config.indicators:
            indicators_list.append({
                'name': indicator_def.name,
                'indicator_class': indicator_def.indicator_class,
                'type': indicator_def.type,
                'agg_config': {
                    'timeframe': indicator_def.get_timeframe(),
                    'aggregator_type': indicator_def.get_aggregator_type()
                },
                'parameters': indicator_def.parameters
            })
        return indicators_list

    @staticmethod
    def build_chart_configs(monitor_config) -> Dict[str, Dict]:
        """
        Build self-describing chart configurations from indicator classes.

        This collects chart_config from each indicator class, which specifies:
        - chart_type: Type identifier (e.g., "adx", "macd", "ema_slope")
        - components: List of component configs with keys, colors, line styles
        - y_axis: Y-axis configuration
        - reference_lines: Horizontal reference lines

        Same pattern as visualization_apps/replay_routes.py

        Args:
            monitor_config: MonitorConfiguration

        Returns:
            Dict mapping indicator class name to chart config
        """
        chart_configs = {}

        try:
            # Ensure indicators are registered
            import indicator_triggers.refactored_indicators
            import indicator_triggers.trend_indicators
            from indicator_triggers.indicator_base import IndicatorRegistry
            registry = IndicatorRegistry()

            for indicator_def in monitor_config.indicators:
                indicator_class_name = indicator_def.indicator_class

                # Collect chart config for this indicator class (once per class)
                if indicator_class_name and indicator_class_name not in chart_configs:
                    try:
                        indicator_cls = registry.get_indicator_class(indicator_class_name)
                        if hasattr(indicator_cls, 'get_chart_config'):
                            chart_configs[indicator_class_name] = indicator_cls.get_chart_config()
                            logger.debug(f"Collected chart config for '{indicator_class_name}'")
                    except ValueError:
                        pass  # Skip if indicator class not found

        except Exception as e:
            logger.warning(f"Could not build chart configs: {e}")

        return chart_configs

    @staticmethod
    def sanitize_data(data: Any) -> Any:
        """
        Recursively sanitize data for JSON serialization.
        Handles NaN, Infinity, numpy types.

        Args:
            data: Any data structure

        Returns:
            Sanitized data safe for JSON serialization
        """
        if isinstance(data, dict):
            return {k: ChartDataService.sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [ChartDataService.sanitize_data(item) for item in data]
        elif isinstance(data, float):
            if math.isnan(data) or math.isinf(data):
                return None
            return data
        elif isinstance(data, np.floating):
            if np.isnan(data) or np.isinf(data):
                return None
            return float(data)
        elif isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, np.ndarray):
            return ChartDataService.sanitize_data(data.tolist())
        return data

    @staticmethod
    def get_unified_chart_data(data_streamer, monitor_config, card_id: str, symbol: str,
                                test_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get complete unified chart data package for Card Details page.

        UNIFIED APPROACH: Uses the same data extraction pattern as visualization_apps/replay_routes.py
        by calling IndicatorProcessorHistoricalNew directly on the aggregators. This ensures
        complete data including all trend indicators and their components.

        Args:
            data_streamer: DataStreamer instance
            monitor_config: MonitorConfiguration
            card_id: Card identifier
            symbol: Trading symbol
            test_name: Optional test/config name

        Returns:
            Complete chart data dict ready for JSON response
        """
        from optimization.calculators.indicator_processor_historical_new import IndicatorProcessorHistoricalNew

        test_name = test_name or monitor_config.name

        # Get all candle data from aggregators
        all_candle_data = data_streamer._get_all_candle_data()

        # Format candlestick data for all aggregators
        per_aggregator_candles = ChartDataService.format_all_aggregator_candles(all_candle_data)

        # Get primary candlestick data (first/shortest timeframe)
        primary_agg_key = list(all_candle_data.keys())[0] if all_candle_data else None
        candlestick_data = per_aggregator_candles.get(primary_agg_key, []) if primary_agg_key else []
        primary_candles = all_candle_data.get(primary_agg_key, []) if primary_agg_key else []

        # Build primary timestamps (same pattern as visualization_apps)
        primary_timestamps = [int(c.timestamp.timestamp() * 1000) for c in primary_candles]

        # === UNIFIED INDICATOR CALCULATION ===
        # Use IndicatorProcessorHistoricalNew directly (same as visualization_apps/replay_routes.py)
        # This ensures ALL indicators including trend indicators are processed consistently
        historical_processor = IndicatorProcessorHistoricalNew(monitor_config)
        (indicator_history_raw, raw_indicator_history_raw, bar_score_history_raw,
         component_history_raw, indicator_agg_mapping) = historical_processor.calculate_indicators(
            data_streamer.aggregators
        )

        logger.info(f"Historical processor returned: {len(indicator_history_raw)} indicators, "
                   f"{len(component_history_raw)} components, {len(bar_score_history_raw)} bar scores")
        if component_history_raw:
            logger.info(f"Component keys: {list(component_history_raw.keys())}")

        # === FORMAT INDICATOR DATA (same as visualization_apps) ===
        # Format raw_indicator_history (trigger values: 0, 1)
        raw_indicator_history_formatted = {}
        for ind_name, ind_values in raw_indicator_history_raw.items():
            series = []
            for i, value in enumerate(ind_values):
                if i < len(primary_timestamps) and value is not None:
                    try:
                        float_val = float(value)
                        if not (math.isnan(float_val) or math.isinf(float_val)):
                            series.append([primary_timestamps[i], float_val])
                    except (ValueError, TypeError):
                        pass
            if series:
                raw_indicator_history_formatted[ind_name] = series

        # Format indicator_history (time-decayed values)
        indicator_history_formatted = {}
        for ind_name, ind_values in indicator_history_raw.items():
            series = []
            for i, value in enumerate(ind_values):
                if i < len(primary_timestamps) and value is not None:
                    try:
                        float_val = float(value)
                        if not (math.isnan(float_val) or math.isinf(float_val)):
                            series.append([primary_timestamps[i], float_val])
                    except (ValueError, TypeError):
                        pass
            if series:
                indicator_history_formatted[ind_name] = series

        # Format component_history (MACD components, ADX lines, EMA slope, etc.)
        component_history_formatted = {}
        for comp_name, comp_values in component_history_raw.items():
            series = []
            for i, value in enumerate(comp_values):
                if i < len(primary_timestamps) and value is not None:
                    try:
                        float_val = float(value)
                        if not (math.isnan(float_val) or math.isinf(float_val)):
                            series.append([primary_timestamps[i], float_val])
                    except (ValueError, TypeError):
                        pass
            if series:
                component_history_formatted[comp_name] = series

        # Format bar_scores_history
        bar_scores_formatted = []
        if bar_score_history_raw and primary_timestamps:
            bar_scores_formatted = ChartDataService.extract_bar_scores_history(
                bar_score_history_raw, primary_timestamps
            )

        # === TRADE DATA ===
        trade_executor = data_streamer.trade_executor
        portfolio = trade_executor.portfolio
        trade_details_history = getattr(trade_executor, 'trade_details_history', {})

        trade_history, triggers, pnl_history = ChartDataService.extract_trade_history(
            portfolio, trade_details_history
        )

        # === BUILD MAPPINGS AND CONFIGS ===
        # Build class to layout mapping (maps indicator NAME to layout type)
        class_to_layout = ChartDataService.build_class_to_layout_mapping(monitor_config)

        # Build indicators list
        indicators_list = ChartDataService.build_indicators_list(monitor_config)

        # Build chart_configs (self-describing visualization configs from indicators)
        # This is what visualization_apps does and stock_analysis_ui was missing
        chart_configs = ChartDataService.build_chart_configs(monitor_config)

        # Build threshold config
        threshold_config = {
            'enter_long': monitor_config.enter_long,
            'exit_long': monitor_config.exit_long
        }

        # Get current values from live indicator processor
        indicator_processor = data_streamer.indicator_processor
        current_values = {
            'indicators': getattr(indicator_processor, 'indicators', {}),
            'raw_indicators': getattr(indicator_processor, 'raw_indicators', {}),
            'bar_scores': getattr(data_streamer, 'bar_scores', {})
        }

        # Get portfolio metrics
        portfolio_metrics = {}
        if hasattr(data_streamer, 'get_portfolio_metrics'):
            portfolio_metrics = data_streamer.get_portfolio_metrics()

        # Get data status
        data_status = {}
        if hasattr(indicator_processor, 'get_data_status'):
            data_status = indicator_processor.get_data_status()

        # === BUILD COMPLETE RESPONSE ===
        chart_data = {
            'success': True,
            'ticker': symbol,
            'test_name': test_name,
            'card_id': card_id,

            # Candlestick data
            'candlestick_data': candlestick_data,
            'per_aggregator_candles': per_aggregator_candles,

            # Indicator data (unified with visualization_apps)
            'indicator_agg_mapping': indicator_agg_mapping,
            'indicator_history': indicator_history_formatted,
            'raw_indicator_history': raw_indicator_history_formatted,
            'component_history': component_history_formatted,
            'class_to_layout': class_to_layout,
            'chart_configs': chart_configs,  # NEW: self-describing chart configs
            'indicators': indicators_list,

            # Trade data
            'trades': trade_history,
            'trade_details': ChartDataService.build_trade_details_for_ui(trade_details_history),
            'triggers': triggers,

            # P&L data
            'pnl_data': pnl_history,
            'pnl_history': pnl_history,

            # Bar scores
            'bar_score_history': bar_score_history_raw,
            'bar_scores_formatted': bar_scores_formatted,

            # Config
            'threshold_config': threshold_config,
            'bars_config': monitor_config.bars,  # NEW: bar definitions for frontend
            'current_values': current_values,
            'portfolio_metrics': portfolio_metrics,
            'data_status': data_status,

            # Stats
            'total_candles': len(candlestick_data),
            'total_trades': len(trade_history)
        }

        # Sanitize for JSON
        chart_data = ChartDataService.sanitize_data(chart_data)

        logger.info(f"Chart data for {card_id}: {len(candlestick_data)} candles, "
                    f"{len(indicators_list)} indicators, {len(trade_history)} trades")

        return chart_data
