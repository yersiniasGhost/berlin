"""ManipulationCandle Trend indicator - time-limited trend gate based on manipulation candle detection.

Activates a binary trend gate (1.0 ON / 0.0 OFF) when institutional manipulation candle
conditions are met:
1. Opening range candle has width >= ATR threshold of daily ATR
2. Subsequent candles trade outside the box (any price action beyond the opening range)

The trend remains active from detection until first_chart_minutes + trend_duration_minutes
after market open (default: 15 + 90 = 105 minutes). Designed to gate other signal indicators
that handle the actual trade entry.

Shares detection logic with ManipulationCandleIndicator (ATR resolution, day grouping,
market open detection). Helper methods are duplicated here to avoid tight coupling since
the two indicators have different IndicatorTypes and independent lifecycles.
"""

from datetime import datetime, time as dt_time, timedelta
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import talib as ta

from models.tick_data import TickData
from indicator_triggers.indicator_base import (
    BaseIndicator, ParameterSpec, ParameterType, IndicatorType, IndicatorRegistry
)


class ManipulationCandleTrend(BaseIndicator):
    """Trend gate that activates when manipulation candle conditions are met.

    Output range: 0.0 to 1.0 (binary gate)
    - 1.0: Manipulation candle setup is active (conditions met, within time window)
    - 0.0: No active setup (conditions not met or time window expired)

    Use signal_mode to select which direction to detect:
    - "bull": Triggers on red (bearish) manipulation candles (expect bullish reversal)
    - "bear": Triggers on green (bullish) manipulation candles (expect bearish reversal)
    - "both": Triggers on either direction

    Configure separate instances for bull/bear bars with the appropriate signal_mode.
    """

    MARKET_OPEN = dt_time(9, 30)

    @classmethod
    def name(cls) -> str:
        return "manipulation_candle_trend"

    @property
    def display_name(self) -> str:
        return "Manipulation Candle Trend"

    @property
    def description(self) -> str:
        return ("Time-limited trend gate based on manipulation candle detection. "
                "Outputs 1.0 when opening range exceeds ATR threshold and price breaks the box.")

    @classmethod
    def get_indicator_type(cls) -> IndicatorType:
        return IndicatorType.TREND

    @classmethod
    def get_layout_type(cls) -> str:
        return "overlay"

    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        return {
            "chart_type": "manipulation_candle_trend",
            "title_suffix": "Manipulation Candle Trend Gate",
            "components": [
                {"key_suffix": "box_high", "name": "Box High", "color": "#EF5350",
                 "line_width": 2, "dash_style": "Dash"},
                {"key_suffix": "box_low", "name": "Box Low", "color": "#26A69A",
                 "line_width": 2, "dash_style": "Dash"},
            ],
            "y_axis": {},
            "reference_lines": []
        }

    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="first_chart_minutes", display_name="Opening Range (min)",
                parameter_type=ParameterType.INTEGER,
                default_value=15, min_value=5, max_value=60, step=5,
                description="Timeframe for the opening range candle (minutes)",
                ui_group="Timeframe Settings"
            ),
            ParameterSpec(
                name="candle_minutes", display_name="Input Candle Resolution (min)",
                parameter_type=ParameterType.INTEGER,
                default_value=5, min_value=1, max_value=15, step=1,
                description="Resolution of input candles (should match agg_config)",
                ui_group="Timeframe Settings"
            ),
            ParameterSpec(
                name="trend_duration_minutes", display_name="Trend Duration (min)",
                parameter_type=ParameterType.INTEGER,
                default_value=90, min_value=30, max_value=240, step=15,
                description="Minutes the trend stays active after the opening range ends",
                ui_group="Timeframe Settings"
            ),
            ParameterSpec(
                name="atr_period", display_name="ATR Period",
                parameter_type=ParameterType.INTEGER,
                default_value=14, min_value=5, max_value=30, step=1,
                description="Period for ATR calculation (days if multi-day data, candles otherwise)",
                ui_group="ATR Settings"
            ),
            ParameterSpec(
                name="daily_atr_value", display_name="Daily ATR Override",
                parameter_type=ParameterType.FLOAT,
                default_value=0.0, min_value=0.0, max_value=10000.0, step=0.01,
                description="Externally-provided daily ATR (0 = auto-compute from available data)",
                ui_group="ATR Settings"
            ),
            ParameterSpec(
                name="atr_threshold_pct", display_name="ATR Threshold",
                parameter_type=ParameterType.FLOAT,
                default_value=0.25, min_value=0.05, max_value=5.0, step=0.05,
                description="Min opening range as fraction of ATR (0.25 = 25% of daily ATR)",
                ui_group="ATR Settings"
            ),
            ParameterSpec(
                name="signal_mode", display_name="Signal Mode",
                parameter_type=ParameterType.CHOICE,
                default_value="both", choices=["both", "bull", "bear"],
                description="bull = red candle setups, bear = green candle setups, both = either",
                ui_group="Signal Settings"
            ),
        ]

    # ------------------------------------------------------------------
    # Main calculation
    # ------------------------------------------------------------------

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Calculate manipulation candle trend gate values.

        Returns:
            - values: Array of trend values (1.0 = active, 0.0 = inactive)
            - components: Dict with box_high/box_low for chart overlay
        """
        first_chart_min = self.get_parameter("first_chart_minutes")
        candle_min = self.get_parameter("candle_minutes")
        trend_dur = self.get_parameter("trend_duration_minutes")
        atr_period = self.get_parameter("atr_period")
        daily_atr_override = self.get_parameter("daily_atr_value")
        atr_threshold = self.get_parameter("atr_threshold_pct")
        signal_mode = self.get_parameter("signal_mode")

        n = len(tick_data)
        result = np.zeros(n)
        box_high_arr = np.full(n, np.nan)
        box_low_arr = np.full(n, np.nan)
        empty = self._make_components(box_high_arr, box_low_arr)

        if n < 2:
            return result, empty

        # Pre-compute OHLC arrays
        highs = np.array([t.high for t in tick_data])
        lows = np.array([t.low for t in tick_data])
        closes = np.array([t.close for t in tick_data])

        # ATR calculations
        intraday_atr = ta.ATR(highs, lows, closes, timeperiod=atr_period)
        day_groups = self._group_by_trading_day(tick_data)
        daily_atr = self._compute_daily_atr(tick_data, day_groups, atr_period)

        candles_per_or = max(1, first_chart_min // candle_min)
        total_window_min = first_chart_min + trend_dur
        cutoff_delta = timedelta(minutes=total_window_min)

        for day_idx, (_day_date, day_indices) in enumerate(day_groups):
            mkt_indices = self._get_market_open_indices(tick_data, day_indices)
            if len(mkt_indices) < candles_per_or + 1:
                continue

            # --- Step 1: Box the opening range ---
            or_indices = mkt_indices[:candles_per_or]
            or_high = max(tick_data[i].high for i in or_indices)
            or_low = min(tick_data[i].low for i in or_indices)
            or_range = or_high - or_low
            if or_range <= 0:
                continue

            # --- Step 2: Confirm manipulation candle via ATR ---
            atr_val = self._resolve_atr(
                daily_atr_override, daily_atr, day_idx, intraday_atr, or_indices[-1]
            )
            if atr_val is None or atr_val <= 0:
                continue
            if or_range < atr_threshold * atr_val:
                continue

            # Direction of the opening range candle
            is_red = tick_data[or_indices[-1]].close < tick_data[or_indices[0]].open

            # Skip if signal_mode doesn't match this candle direction
            if signal_mode == "bull" and not is_red:
                continue  # Bull mode needs a red manipulation candle
            if signal_mode == "bear" and is_red:
                continue  # Bear mode needs a green manipulation candle

            # Wall-clock cutoff for trend window
            cutoff_time = (datetime.combine(datetime.min, self.MARKET_OPEN)
                           + cutoff_delta).time()

            # --- Step 3: Find price outside box and activate trend ---
            trend_activated = False

            for mi in range(candles_per_or, len(mkt_indices)):
                idx = mkt_indices[mi]
                candle_time = self._parse_timestamp(tick_data[idx].timestamp).time()
                if candle_time > cutoff_time:
                    break

                if not trend_activated:
                    # Any price action outside the box triggers the trend
                    if is_red and tick_data[idx].low < or_low:
                        trend_activated = True
                    elif not is_red and tick_data[idx].high > or_high:
                        trend_activated = True

                if trend_activated:
                    result[idx] = 1.0
                    box_high_arr[idx] = or_high
                    box_low_arr[idx] = or_low

        return result, self._make_components(box_high_arr, box_low_arr)

    # ------------------------------------------------------------------
    # Helpers (shared logic with ManipulationCandleIndicator)
    # ------------------------------------------------------------------

    def _make_components(self, box_high: np.ndarray, box_low: np.ndarray) -> Dict[str, np.ndarray]:
        return {
            f"{self.name()}_box_high": box_high,
            f"{self.name()}_box_low": box_low,
        }

    @staticmethod
    def _parse_timestamp(ts) -> datetime:
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts)
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        raise ValueError(f"Cannot parse timestamp: {ts}")

    def _group_by_trading_day(self, tick_data: List[TickData]) -> List[Tuple[Any, List[int]]]:
        """Group candle indices by calendar date."""
        days: List[Tuple[Any, List[int]]] = []
        current_date = None
        current_indices: List[int] = []

        for i, tick in enumerate(tick_data):
            if tick.timestamp is None:
                continue
            tick_date = self._parse_timestamp(tick.timestamp).date()
            if tick_date != current_date:
                if current_indices:
                    days.append((current_date, current_indices))
                current_date = tick_date
                current_indices = [i]
            else:
                current_indices.append(i)

        if current_indices:
            days.append((current_date, current_indices))
        return days

    def _get_market_open_indices(self, tick_data: List[TickData], day_indices: List[int]) -> List[int]:
        """Return indices of candles at or after market open for a given day."""
        return [idx for idx in day_indices
                if tick_data[idx].timestamp is not None
                and self._parse_timestamp(tick_data[idx].timestamp).time() >= self.MARKET_OPEN]

    def _compute_daily_atr(self, tick_data: List[TickData],
                           day_groups: List[Tuple[Any, List[int]]], atr_period: int) -> np.ndarray:
        """Compute daily ATR from per-day OHLC. Returns one value per day."""
        n_days = len(day_groups)
        if n_days < atr_period + 1:
            return np.full(n_days, np.nan)

        d_highs = np.zeros(n_days)
        d_lows = np.zeros(n_days)
        d_closes = np.zeros(n_days)

        for di, (_day_date, day_indices) in enumerate(day_groups):
            mkt = self._get_market_open_indices(tick_data, day_indices)
            if not mkt:
                mkt = day_indices
            d_highs[di] = max(tick_data[i].high for i in mkt)
            d_lows[di] = min(tick_data[i].low for i in mkt)
            d_closes[di] = tick_data[mkt[-1]].close

        return ta.ATR(d_highs, d_lows, d_closes, timeperiod=atr_period)

    @staticmethod
    def _resolve_atr(override: float, daily_atr: np.ndarray, day_idx: int,
                     intraday_atr: np.ndarray, or_end_idx: int) -> Optional[float]:
        """Resolve ATR value in priority order: override > daily (prev day) > intraday."""
        if override > 0:
            return override
        if (day_idx > 0 and day_idx - 1 < len(daily_atr)
                and not np.isnan(daily_atr[day_idx - 1])):
            return float(daily_atr[day_idx - 1])
        if or_end_idx < len(intraday_atr) and not np.isnan(intraday_atr[or_end_idx]):
            return float(intraday_atr[or_end_idx])
        return None


IndicatorRegistry().register(ManipulationCandleTrend)
