"""Manipulation Candle indicator - detects institutional stop-hunt candles and reversal entries.

Strategy:
1. Box the opening range from the first N minutes after market open
2. Confirm it's a manipulation/liquidity candle if range >= threshold of daily ATR
3. Detect reversal candlestick patterns outside the box on the entry timeframe

ATR sourcing (in priority order):
  - daily_atr_value parameter > 0: use the externally-provided value directly
  - Multi-day data available: compute proper daily ATR from previous days
  - Single-day fallback: compute ATR from available intraday candles
"""

from datetime import datetime, time as dt_time
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import talib as ta

from models.tick_data import TickData
from indicator_triggers.indicator_base import (
    BaseIndicator, ParameterSpec, ParameterType, IndicatorRegistry
)


class ManipulationCandleIndicator(BaseIndicator):
    """Detects institutional liquidity/manipulation candles and reversal entry signals."""

    MARKET_OPEN = dt_time(9, 30)

    @classmethod
    def name(cls) -> str:
        return "manipulation_candle"

    @property
    def display_name(self) -> str:
        return "Manipulation Candle"

    @property
    def description(self) -> str:
        return ("Detects institutional manipulation candles via opening range ATR analysis "
                "and generates reversal entry signals")

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
                name="second_chart_minutes", display_name="Entry Timeframe (min)",
                parameter_type=ParameterType.INTEGER,
                default_value=5, min_value=1, max_value=15, step=1,
                description="Candle resolution for reversal entry detection (should match input data)",
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
                name="max_setup_minutes", display_name="Max Setup Window (min)",
                parameter_type=ParameterType.INTEGER,
                default_value=90, min_value=30, max_value=240, step=15,
                description="Maximum minutes after market open to find a reversal setup",
                ui_group="Signal Settings"
            ),
            ParameterSpec(
                name="lookback", display_name="Lookback Period",
                parameter_type=ParameterType.INTEGER,
                default_value=2, min_value=1, max_value=20, step=1,
                description="Number of candles for trigger decay (1.0 -> 0.0)",
                ui_group="Signal Settings"
            ),
        ]

    @classmethod
    def get_layout_type(cls) -> str:
        return "overlay"

    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        return {
            "chart_type": "manipulation_candle",
            "title_suffix": "Manipulation Candle Detection",
            "components": [
                {"key_suffix": "box_high", "name": "Box High", "color": "#EF5350",
                 "line_width": 2, "dash_style": "Dash"},
                {"key_suffix": "box_low", "name": "Box Low", "color": "#26A69A",
                 "line_width": 2, "dash_style": "Dash"},
            ],
            "y_axis": {},
            "reference_lines": []
        }

    # ------------------------------------------------------------------
    # Main calculation
    # ------------------------------------------------------------------

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Calculate manipulation candle signals.

        Returns:
            - Signal array: 1.0 at reversal entry, 0.0 otherwise
            - Component data: box_high / box_low arrays for chart overlay
        """
        first_chart_min = self.get_parameter("first_chart_minutes")
        second_chart_min = self.get_parameter("second_chart_minutes")
        atr_period = self.get_parameter("atr_period")
        daily_atr_override = self.get_parameter("daily_atr_value")
        atr_threshold = self.get_parameter("atr_threshold_pct")
        max_setup_min = self.get_parameter("max_setup_minutes")

        n = len(tick_data)
        signals = np.zeros(n)
        box_high_arr = np.full(n, np.nan)
        box_low_arr = np.full(n, np.nan)
        empty = self._make_components(box_high_arr, box_low_arr)

        if n < 2:
            return signals, empty

        # Pre-compute OHLC arrays
        opens = np.array([t.open for t in tick_data])
        highs = np.array([t.high for t in tick_data])
        lows = np.array([t.low for t in tick_data])
        closes = np.array([t.close for t in tick_data])

        # Pre-compute TA-Lib reversal patterns across all data
        hammer = ta.CDLHAMMER(opens, highs, lows, closes)
        engulfing = ta.CDLENGULFING(opens, highs, lows, closes)
        inv_hammer = ta.CDLINVERTEDHAMMER(opens, highs, lows, closes)

        # Intraday ATR (always available as last-resort fallback)
        intraday_atr = ta.ATR(highs, lows, closes, timeperiod=atr_period)

        # Group candles by trading day
        day_groups = self._group_by_trading_day(tick_data)

        # Daily ATR from multi-day OHLC (may be all NaN if insufficient days)
        daily_atr = self._compute_daily_atr(tick_data, day_groups, atr_period)

        candles_per_or = max(1, first_chart_min // second_chart_min)
        max_candles = max_setup_min // second_chart_min

        for day_idx, (_day_date, day_indices) in enumerate(day_groups):
            # Market-hours candles starting at 9:30 AM
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

            # Direction: red (bearish) candle -> expect bullish reversal
            is_red = tick_data[or_indices[-1]].close < tick_data[or_indices[0]].open

            # Paint the box for visualisation
            vis_end = min(len(mkt_indices), candles_per_or + max_candles)
            for idx in mkt_indices[:vis_end]:
                box_high_arr[idx] = or_high
                box_low_arr[idx] = or_low

            # --- Step 3: Find reversal entry outside the box ---
            for mi in range(candles_per_or, vis_end):
                idx = mkt_indices[mi]
                if is_red:
                    # Bullish: candle must wick below the box
                    if tick_data[idx].low >= or_low:
                        continue
                    if hammer[idx] > 0 or engulfing[idx] > 0:
                        signals[idx] = 1.0
                        break
                else:
                    # Bearish: candle must wick above the box
                    if tick_data[idx].high <= or_high:
                        continue
                    if inv_hammer[idx] > 0 or engulfing[idx] < 0:
                        signals[idx] = 1.0
                        break

        return signals, self._make_components(box_high_arr, box_low_arr)

    # ------------------------------------------------------------------
    # Target / stop-loss levels
    # ------------------------------------------------------------------

    def calculate_levels(self, tick_data: List[TickData], signals: np.ndarray,
                         component_data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Calculate target and stop-loss levels for each signal.

        Bullish reversal (below box after red manipulation candle):
          target    = box high  (opposite side of the range)
          stop_loss = signal candle's low

        Bearish reversal (above box after green manipulation candle):
          target    = box low
          stop_loss = signal candle's high
        """
        n = len(tick_data)
        targets = np.full(n, np.nan)
        stop_losses = np.full(n, np.nan)

        box_high = component_data.get(f"{self.name()}_box_high", np.full(n, np.nan))
        box_low = component_data.get(f"{self.name()}_box_low", np.full(n, np.nan))

        first_chart_min = self.get_parameter("first_chart_minutes")
        second_chart_min = self.get_parameter("second_chart_minutes")
        candles_per_or = max(1, first_chart_min // second_chart_min)

        day_groups = self._group_by_trading_day(tick_data)

        for _day_idx, (_day_date, day_indices) in enumerate(day_groups):
            mkt_indices = self._get_market_open_indices(tick_data, day_indices)
            if len(mkt_indices) < candles_per_or + 1:
                continue

            or_indices = mkt_indices[:candles_per_or]
            is_red = tick_data[or_indices[-1]].close < tick_data[or_indices[0]].open

            for idx in mkt_indices[candles_per_or:]:
                if signals[idx] != 1.0:
                    continue
                bh = box_high[idx]
                bl = box_low[idx]
                if np.isnan(bh) or np.isnan(bl):
                    continue

                if is_red:
                    # Bullish reversal -> target the box high, stop below entry candle
                    targets[idx] = bh
                    stop_losses[idx] = tick_data[idx].low
                else:
                    # Bearish reversal -> target the box low, stop above entry candle
                    targets[idx] = bl
                    stop_losses[idx] = tick_data[idx].high

        return {"target": targets, "stop_loss": stop_losses}

    # ------------------------------------------------------------------
    # Helpers
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
        result = []
        for idx in day_indices:
            if tick_data[idx].timestamp is None:
                continue
            if self._parse_timestamp(tick_data[idx].timestamp).time() >= self.MARKET_OPEN:
                result.append(idx)
        return result

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
        """Resolve ATR value in priority order: override > daily > intraday."""
        if override > 0:
            return override

        # Daily ATR from the *previous* day (avoids look-ahead bias)
        if (day_idx > 0 and day_idx - 1 < len(daily_atr)
                and not np.isnan(daily_atr[day_idx - 1])):
            return float(daily_atr[day_idx - 1])

        # Intraday fallback
        if or_end_idx < len(intraday_atr) and not np.isnan(intraday_atr[or_end_idx]):
            return float(intraday_atr[or_end_idx])

        return None


IndicatorRegistry().register(ManipulationCandleIndicator)
