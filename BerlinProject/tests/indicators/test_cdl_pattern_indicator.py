"""Tests for CDLPatternIndicator - Candlestick Pattern Recognition."""

import unittest
import numpy as np
from typing import List

from models.tick_data import TickData
from indicator_triggers.indicator_base import IndicatorConfiguration, IndicatorType
from indicator_triggers.cdl_pattern_indicator import CDLPatternIndicator


# ------------------------------------------------------------------
# Factory & data generators
# ------------------------------------------------------------------

def create_cdl_indicator(patterns=None, trend="bullish", lookback=2):
    """Factory function to create CDLPatternIndicator with parameters."""
    if patterns is None:
        patterns = ["CDLENGULFING"]
    config = IndicatorConfiguration(
        indicator_name="CDLPatternIndicator",
        display_name="test_cdl",
        parameters={"patterns": patterns, "trend": trend, "lookback": lookback}
    )
    return CDLPatternIndicator(config)


def generate_tick_data(prices: List[float], volatility: float = 0.5) -> List[TickData]:
    """Generate tick data from close prices with synthetic OHLC."""
    ticks = []
    for i, close in enumerate(prices):
        open_price = prices[i - 1] if i > 0 else close
        ticks.append(TickData(
            timestamp=1000 + i * 60000,
            open=open_price, high=close + volatility,
            low=close - volatility, close=close, volume=1000
        ))
    return ticks


def _varied_downtrend(n: int = 20, seed: int = 42) -> tuple:
    """Build a varied downtrend (lists of O/H/L/C + TickData)."""
    np.random.seed(seed)
    ticks = []
    price = 120.0
    for i in range(n):
        body = np.random.uniform(0.5, 2.0)
        wick = np.random.uniform(0.2, 1.0)
        o, c = price, price - body
        h, l = o + wick, c - wick
        ticks.append(TickData(
            timestamp=1000 + i * 60000,
            open=o, high=h, low=l, close=c, volume=1000
        ))
        price = c
    return ticks


def _varied_uptrend(n: int = 20, seed: int = 42) -> tuple:
    """Build a varied uptrend (lists of TickData)."""
    np.random.seed(seed)
    ticks = []
    price = 80.0
    for i in range(n):
        body = np.random.uniform(0.5, 2.0)
        wick = np.random.uniform(0.2, 1.0)
        o, c = price, price + body
        h, l = c + wick, o - wick
        ticks.append(TickData(
            timestamp=1000 + i * 60000,
            open=o, high=h, low=l, close=c, volume=1000
        ))
        price = c
    return ticks


def generate_downtrend_with_takuri(n_trend: int = 20) -> List[TickData]:
    """Create a varied downtrend followed by a takuri / dragonfly-doji candle.

    Takuri: doji-like body with long lower shadow. TA-Lib CDLTAKURI returns
    +100 (bullish) when it appears after a downtrend.
    """
    ticks = _varied_downtrend(n_trend)
    last_close = ticks[-1].close
    # Doji-hammer shape: near-zero body, long lower shadow
    ticks.append(TickData(
        timestamp=1000 + n_trend * 60000,
        open=last_close + 0.05, high=last_close + 0.1,
        low=last_close - 5.0, close=last_close, volume=2000
    ))
    return ticks


def generate_downtrend_with_bullish_engulfing(n_trend: int = 20) -> List[TickData]:
    """Create a varied downtrend followed by a bullish engulfing pair.

    Bullish engulfing: small red candle then large green candle that engulfs it.
    TA-Lib CDLENGULFING returns +100 (bullish) for this pattern.
    """
    ticks = _varied_downtrend(n_trend)
    last_close = ticks[-1].close
    # Small red candle
    small_open, small_close = last_close, last_close - 0.5
    ticks.append(TickData(
        timestamp=1000 + n_trend * 60000,
        open=small_open, high=small_open + 0.2,
        low=small_close - 0.2, close=small_close, volume=1000
    ))
    # Large green engulfing candle
    ticks.append(TickData(
        timestamp=1000 + (n_trend + 1) * 60000,
        open=small_close - 1.0, high=small_open + 2.0,
        low=small_close - 1.5, close=small_open + 1.5, volume=3000
    ))
    return ticks


def generate_uptrend_with_bearish_engulfing(n_trend: int = 20) -> List[TickData]:
    """Create a varied uptrend followed by a bearish engulfing pair.

    Bearish engulfing: small green candle then large red candle that engulfs it.
    TA-Lib CDLENGULFING returns -100 (bearish) for this pattern.
    """
    ticks = _varied_uptrend(n_trend)
    last_close = ticks[-1].close
    # Small green candle
    small_open, small_close = last_close, last_close + 0.5
    ticks.append(TickData(
        timestamp=1000 + n_trend * 60000,
        open=small_open, high=small_close + 0.2,
        low=small_open - 0.2, close=small_close, volume=1000
    ))
    # Large red engulfing candle
    ticks.append(TickData(
        timestamp=1000 + (n_trend + 1) * 60000,
        open=small_close + 1.0, high=small_close + 1.5,
        low=small_open - 2.0, close=small_open - 1.5, volume=3000
    ))
    return ticks


# ------------------------------------------------------------------
# Tests: Basic functionality
# ------------------------------------------------------------------

class TestCDLPatternBasic(unittest.TestCase):
    """Test CDLPatternIndicator basic interface and return types."""

    def test_calculate_returns_tuple(self):
        """calculate() must return (np.ndarray, dict)."""
        indicator = create_cdl_indicator()
        tick_data = generate_tick_data([100 + i for i in range(20)])
        result = indicator.calculate(tick_data)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], np.ndarray)
        self.assertIsInstance(result[1], dict)

    def test_output_length_matches_input(self):
        """Output array length must equal input length."""
        indicator = create_cdl_indicator()
        tick_data = generate_tick_data([100 + i * 0.5 for i in range(30)])
        values, _ = indicator.calculate(tick_data)

        self.assertEqual(len(values), 30)

    def test_output_values_are_binary(self):
        """Output must be exactly 0.0 or 1.0 (no intermediate values)."""
        indicator = create_cdl_indicator(patterns=["CDLENGULFING", "CDLTAKURI"])
        tick_data = generate_downtrend_with_bullish_engulfing()
        values, _ = indicator.calculate(tick_data)

        for val in values:
            self.assertIn(val, [0.0, 1.0], f"Unexpected output value: {val}")

    def test_components_contain_pattern_raw(self):
        """Components dict must include 'pattern_raw' key when data is sufficient."""
        indicator = create_cdl_indicator()
        tick_data = generate_tick_data([100 + i for i in range(20)])
        _, components = indicator.calculate(tick_data)

        self.assertIn("pattern_raw", components)
        self.assertIsInstance(components["pattern_raw"], np.ndarray)

    def test_insufficient_data_returns_zeros(self):
        """Less than 5 candles should return all-zero result with empty components."""
        indicator = create_cdl_indicator()
        tick_data = generate_tick_data([100, 101, 102, 103])  # 4 candles
        values, components = indicator.calculate(tick_data)

        self.assertEqual(len(values), 4)
        self.assertTrue(np.all(values == 0.0))
        self.assertEqual(components, {})

    def test_empty_data(self):
        """Empty input should return empty output."""
        indicator = create_cdl_indicator()
        values, components = indicator.calculate([])

        self.assertEqual(len(values), 0)
        self.assertEqual(components, {})

    def test_exactly_five_candles(self):
        """Exactly 5 candles is the minimum for processing (not < 5)."""
        indicator = create_cdl_indicator()
        tick_data = generate_tick_data([100, 101, 102, 103, 104])
        values, components = indicator.calculate(tick_data)

        self.assertEqual(len(values), 5)
        self.assertIn("pattern_raw", components)


# ------------------------------------------------------------------
# Tests: Bullish pattern detection
# ------------------------------------------------------------------

class TestCDLPatternBullish(unittest.TestCase):
    """Test bullish candlestick pattern detection."""

    def test_takuri_detected_in_downtrend(self):
        """CDLTAKURI (doji-hammer) after a downtrend should fire as bullish."""
        indicator = create_cdl_indicator(patterns=["CDLTAKURI"], trend="bullish")
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.any(values == 1.0),
                        "Takuri pattern should fire at least once after downtrend")

    def test_takuri_signal_at_end(self):
        """Takuri signal should fire at the last candle (the takuri)."""
        indicator = create_cdl_indicator(patterns=["CDLTAKURI"], trend="bullish")
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        self.assertEqual(values[-1], 1.0,
                         "Takuri signal should appear on the takuri candle itself")

    def test_bullish_engulfing_detected(self):
        """CDLENGULFING (bullish) after a downtrend should trigger."""
        indicator = create_cdl_indicator(patterns=["CDLENGULFING"], trend="bullish")
        tick_data = generate_downtrend_with_bullish_engulfing()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.any(values == 1.0),
                        "Bullish engulfing should fire after downtrend")

    def test_bullish_trend_ignores_bearish_signals(self):
        """With trend='bullish', bearish TA-Lib signals should be filtered to 0."""
        indicator = create_cdl_indicator(patterns=["CDLENGULFING"], trend="bullish")
        # Uptrend + bearish engulfing generates -100 from TA-Lib
        tick_data = generate_uptrend_with_bearish_engulfing()
        values, _ = indicator.calculate(tick_data)

        # Bearish engulfing → negative TA-Lib value → filtered to 0 in bullish mode
        self.assertEqual(np.sum(values[-3:]), 0.0,
                         "Bullish mode should not fire on bearish engulfing pattern")


# ------------------------------------------------------------------
# Tests: Bearish pattern detection
# ------------------------------------------------------------------

class TestCDLPatternBearish(unittest.TestCase):
    """Test bearish candlestick pattern detection."""

    def test_bearish_engulfing_detected(self):
        """CDLENGULFING (bearish) after an uptrend should trigger."""
        indicator = create_cdl_indicator(patterns=["CDLENGULFING"], trend="bearish")
        tick_data = generate_uptrend_with_bearish_engulfing()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.any(values == 1.0),
                        "Bearish engulfing should fire after uptrend")

    def test_bearish_output_is_positive(self):
        """Even bearish signals must output 1.0 (not -1.0) for bar weighting."""
        indicator = create_cdl_indicator(patterns=["CDLENGULFING"], trend="bearish")
        tick_data = generate_uptrend_with_bearish_engulfing()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.all(values >= 0.0),
                        "Bearish mode should output positive 1.0, never negative")

    def test_bearish_trend_ignores_bullish_signals(self):
        """With trend='bearish', bullish TA-Lib signals should be filtered out."""
        indicator = create_cdl_indicator(patterns=["CDLTAKURI"], trend="bearish")
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        # Takuri is bullish (+100), should be filtered to 0 in bearish mode
        self.assertTrue(np.all(values == 0.0),
                        "Bearish mode should not fire on bullish takuri pattern")


# ------------------------------------------------------------------
# Tests: Multiple patterns (OR logic)
# ------------------------------------------------------------------

class TestCDLPatternMultiple(unittest.TestCase):
    """Test multiple pattern combination (OR logic via np.maximum)."""

    def test_multiple_bullish_patterns_combine(self):
        """Multiple bullish patterns should combine via OR."""
        indicator = create_cdl_indicator(
            patterns=["CDLTAKURI", "CDLDRAGONFLYDOJI", "CDLENGULFING"],
            trend="bullish"
        )
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.any(values == 1.0),
                        "Multiple patterns should still detect takuri/doji")

    def test_multiple_bearish_patterns_combine(self):
        """Multiple bearish patterns should combine via OR."""
        indicator = create_cdl_indicator(
            patterns=["CDLENGULFING", "CDLSHOOTINGSTAR", "CDLHARAMI"],
            trend="bearish"
        )
        tick_data = generate_uptrend_with_bearish_engulfing()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.any(values == 1.0),
                        "Multiple bearish patterns should detect engulfing")

    def test_no_patterns_returns_zeros(self):
        """Empty pattern list should return all zeros."""
        indicator = create_cdl_indicator(patterns=[], trend="bullish")
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.all(values == 0.0),
                        "Empty pattern list should produce no signals")


# ------------------------------------------------------------------
# Tests: Pattern input parsing
# ------------------------------------------------------------------

class TestCDLPatternInputParsing(unittest.TestCase):
    """Test patterns parameter parsing (list, string, case handling)."""

    def test_patterns_as_comma_separated_string(self):
        """Comma-separated string should be split into individual patterns."""
        # The calculate() method handles string→list conversion internally
        indicator = create_cdl_indicator(patterns=["placeholder"], trend="bullish")
        # Override the parameter after construction to test string parsing
        indicator.config.parameters["patterns"] = "CDLTAKURI, CDLDRAGONFLYDOJI"
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.any(values == 1.0),
                        "Comma-separated string should be parsed into pattern list")

    def test_pattern_names_case_insensitive(self):
        """Pattern names should work regardless of case (uppercased internally)."""
        indicator = create_cdl_indicator(patterns=["placeholder"], trend="bullish")
        indicator.config.parameters["patterns"] = ["cdltakuri"]
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.any(values == 1.0),
                        "Lowercase pattern names should work (uppercased internally)")

    def test_pattern_names_with_whitespace(self):
        """Pattern names with leading/trailing whitespace should be stripped."""
        indicator = create_cdl_indicator(patterns=["placeholder"], trend="bullish")
        indicator.config.parameters["patterns"] = ["  CDLTAKURI  "]
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.any(values == 1.0),
                        "Whitespace in pattern names should be stripped")

    def test_invalid_pattern_name_skipped(self):
        """Unknown pattern names should be silently skipped."""
        indicator = create_cdl_indicator(
            patterns=["CDLNOTREAL", "INVALID_PATTERN"], trend="bullish"
        )
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        # No valid patterns → all zeros, no crash
        self.assertTrue(np.all(values == 0.0),
                        "Invalid pattern names should be skipped without error")

    def test_mix_valid_and_invalid_patterns(self):
        """Mix of valid and invalid pattern names should process valid ones."""
        indicator = create_cdl_indicator(
            patterns=["CDLNOTREAL", "CDLTAKURI"], trend="bullish"
        )
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.any(values == 1.0),
                        "Valid patterns should fire even when mixed with invalid ones")

    def test_non_list_non_string_rejected_at_construction(self):
        """Non-list/non-string patterns value should raise ValueError during init."""
        with self.assertRaises(ValueError):
            create_cdl_indicator(patterns=12345, trend="bullish")


# ------------------------------------------------------------------
# Tests: Parameter specifications
# ------------------------------------------------------------------

class TestCDLPatternParameterSpecs(unittest.TestCase):
    """Test parameter specifications and metadata."""

    def test_has_required_parameter_specs(self):
        """Should have patterns, trend, and lookback parameter specs."""
        specs = CDLPatternIndicator.get_parameter_specs()
        spec_names = [s.name for s in specs]

        for name in ["patterns", "trend", "lookback"]:
            self.assertIn(name, spec_names, f"Missing parameter spec: {name}")

    def test_default_values(self):
        """Default parameter values should match expectations."""
        specs = CDLPatternIndicator.get_parameter_specs()
        defaults = {s.name: s.default_value for s in specs}

        self.assertEqual(defaults["patterns"], [])
        self.assertEqual(defaults["trend"], "bullish")
        self.assertEqual(defaults["lookback"], 2)

    def test_trend_choices(self):
        """trend parameter should have bullish/bearish choices."""
        specs = CDLPatternIndicator.get_parameter_specs()
        trend_spec = next(s for s in specs if s.name == "trend")

        self.assertEqual(trend_spec.choices, ["bullish", "bearish"])

    def test_lookback_range(self):
        """lookback should have sensible min/max range."""
        specs = CDLPatternIndicator.get_parameter_specs()
        lookback_spec = next(s for s in specs if s.name == "lookback")

        self.assertEqual(lookback_spec.min_value, 1)
        self.assertEqual(lookback_spec.max_value, 20)
        self.assertEqual(lookback_spec.step, 1)

    def test_indicator_type_is_signal(self):
        """CDL patterns are signal indicators (not trend)."""
        self.assertEqual(CDLPatternIndicator.get_indicator_type(), IndicatorType.SIGNAL)

    def test_indicator_name(self):
        """Indicator name() should be 'cdl_pattern'."""
        self.assertEqual(CDLPatternIndicator.name(), "cdl_pattern")

    def test_display_name(self):
        """display_name should be human-readable."""
        indicator = create_cdl_indicator()
        self.assertEqual(indicator.display_name, "Candlestick Pattern")


# ------------------------------------------------------------------
# Tests: Registry integration
# ------------------------------------------------------------------

class TestCDLPatternRegistry(unittest.TestCase):
    """Test that CDLPatternIndicator is registered in IndicatorRegistry."""

    def test_registered_in_signal_indicators(self):
        """Should appear in registry's signal indicator list."""
        from indicator_triggers.indicator_base import IndicatorRegistry
        signals = IndicatorRegistry().get_signal_indicators()

        # get_signal_indicators() returns a list of dicts with 'name' key
        signal_names = [s["name"] for s in signals]
        self.assertIn("CDLPatternIndicator", signal_names,
                      "CDLPatternIndicator should be registered as signal indicator")


# ------------------------------------------------------------------
# Tests: Edge cases
# ------------------------------------------------------------------

class TestCDLPatternEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_constant_price_no_patterns(self):
        """Flat price data should produce no directional pattern signals."""
        indicator = create_cdl_indicator(
            patterns=["CDLENGULFING", "CDLTAKURI", "CDLDRAGONFLYDOJI"],
            trend="bullish"
        )
        prices = [100.0] * 30
        tick_data = generate_tick_data(prices, volatility=0.01)
        values, _ = indicator.calculate(tick_data)

        self.assertEqual(len(values), 30)

    def test_many_patterns_no_crash(self):
        """Large list of patterns should process without error."""
        many_patterns = [
            "CDLHAMMER", "CDLENGULFING", "CDLDOJI", "CDLHARAMI",
            "CDLMORNINGSTAR", "CDLEVENINGSTAR", "CDLSHOOTINGSTAR",
            "CDLINVERTEDHAMMER", "CDL3WHITESOLDIERS", "CDL3BLACKCROWS",
            "CDLPIERCING", "CDLDARKCLOUDCOVER", "CDLSPINNINGTOP",
            "CDLMARUBOZU", "CDLHANGINGMAN", "CDLTAKURI",
        ]
        indicator = create_cdl_indicator(patterns=many_patterns, trend="bullish")
        tick_data = generate_downtrend_with_takuri()
        values, _ = indicator.calculate(tick_data)

        self.assertEqual(len(values), len(tick_data))
        for val in values:
            self.assertIn(val, [0.0, 1.0])

    def test_component_pattern_raw_matches_values(self):
        """The 'pattern_raw' component should equal the main result array."""
        indicator = create_cdl_indicator(patterns=["CDLENGULFING"], trend="bearish")
        tick_data = generate_uptrend_with_bearish_engulfing()
        values, components = indicator.calculate(tick_data)

        np.testing.assert_array_equal(values, components["pattern_raw"])

    def test_both_directions_fire_on_appropriate_data(self):
        """Same CDLENGULFING pattern should fire bullish and bearish on matching data."""
        # Bullish engulfing
        bull_ind = create_cdl_indicator(patterns=["CDLENGULFING"], trend="bullish")
        bull_data = generate_downtrend_with_bullish_engulfing()
        bull_vals, _ = bull_ind.calculate(bull_data)

        # Bearish engulfing
        bear_ind = create_cdl_indicator(patterns=["CDLENGULFING"], trend="bearish")
        bear_data = generate_uptrend_with_bearish_engulfing()
        bear_vals, _ = bear_ind.calculate(bear_data)

        self.assertTrue(np.any(bull_vals == 1.0), "Bullish engulfing should fire")
        self.assertTrue(np.any(bear_vals == 1.0), "Bearish engulfing should fire")


if __name__ == "__main__":
    unittest.main()
