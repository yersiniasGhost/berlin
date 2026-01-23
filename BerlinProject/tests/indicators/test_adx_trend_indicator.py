"""
Tests for ADXTrendIndicator from trend_indicators.py.

Tests cover:
1. No trend scenario (sideways/choppy market)
2. Weak bullish trend (ADX between threshold and strong threshold)
3. Strong bullish trend (ADX above strong threshold)
4. Weak bearish trend
5. Strong bearish trend
6. Edge cases (insufficient data)
"""

import unittest
import numpy as np
from datetime import datetime, timedelta

from models.tick_data import TickData
from indicator_triggers.indicator_base import IndicatorConfiguration
from indicator_triggers.trend_indicators import ADXTrendIndicator


def create_adx_indicator(name: str = "test_adx", period: int = 14,
                         trend_threshold: float = 25.0, strong_trend_threshold: float = 40.0,
                         direction_filter: str = "Both"):
    """Factory function to create ADXTrendIndicator with custom parameters."""
    config = IndicatorConfiguration(
        indicator_name="ADXTrendIndicator",
        display_name=name,
        parameters={
            "period": period,
            "trend_threshold": trend_threshold,
            "strong_trend_threshold": strong_trend_threshold,
            "direction_filter": direction_filter
        }
    )
    return ADXTrendIndicator(config)


def generate_sideways_data(base_price: float, periods: int, volatility: float = 0.01) -> list:
    """
    Generate sideways/choppy market data with no clear trend direction.
    Uses mean-reverting oscillation around base price to produce low ADX.
    """
    tick_data = []
    price = base_price
    timestamp = datetime.now()

    for i in range(periods):
        # Mean-reverting behavior: pull price back toward base
        revert_force = (base_price - price) * 0.1

        # Random component with equal up/down probability
        random_move = price * volatility * np.random.uniform(-1.0, 1.0)

        # Combine: some mean reversion + random noise
        delta = revert_force + random_move

        open_p = price
        close_p = price + delta

        # Small, balanced wicks
        wick = abs(delta) * 0.3
        high_p = max(open_p, close_p) + wick
        low_p = min(open_p, close_p) - wick

        tick_data.append(TickData(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=1000, timestamp=timestamp, symbol="TEST"
        ))
        price = close_p
        timestamp = timestamp + timedelta(minutes=1)

    return tick_data


def generate_strong_uptrend_data(base_price: float, periods: int, trend_strength: float = 0.015) -> list:
    """
    Generate strong uptrend data where price consistently moves higher.
    Creates high ADX with +DI > -DI.
    """
    tick_data = []
    price = base_price
    timestamp = datetime.now()

    for i in range(periods):
        # Strong upward movement with occasional small pullbacks
        if i % 7 == 6:  # Small pullback every 7 bars
            delta = price * trend_strength * 0.3
            open_p = price
            close_p = price - delta
        else:
            delta = price * trend_strength * np.random.uniform(0.8, 1.2)
            open_p = price
            close_p = price + delta

        high_p = max(open_p, close_p) + abs(close_p - open_p) * 0.3
        low_p = min(open_p, close_p) - abs(close_p - open_p) * 0.2

        tick_data.append(TickData(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=1000, timestamp=timestamp, symbol="TEST"
        ))
        price = close_p
        timestamp = timestamp + timedelta(minutes=1)

    return tick_data


def generate_strong_downtrend_data(base_price: float, periods: int, trend_strength: float = 0.015) -> list:
    """
    Generate strong downtrend data where price consistently moves lower.
    Creates high ADX with -DI > +DI.
    """
    tick_data = []
    price = base_price
    timestamp = datetime.now()

    for i in range(periods):
        # Strong downward movement with occasional small bounces
        if i % 7 == 6:  # Small bounce every 7 bars
            delta = price * trend_strength * 0.3
            open_p = price
            close_p = price + delta
        else:
            delta = price * trend_strength * np.random.uniform(0.8, 1.2)
            open_p = price
            close_p = price - delta

        high_p = max(open_p, close_p) + abs(close_p - open_p) * 0.2
        low_p = min(open_p, close_p) - abs(close_p - open_p) * 0.3

        tick_data.append(TickData(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=1000, timestamp=timestamp, symbol="TEST"
        ))
        price = close_p
        timestamp = timestamp + timedelta(minutes=1)

    return tick_data


def generate_weak_trend_data(base_price: float, periods: int, direction: str = 'bull',
                             trend_strength: float = 0.005) -> list:
    """
    Generate weak trend data - some directional bias but mixed signals.
    Produces moderate ADX values (between threshold and strong threshold).
    """
    tick_data = []
    price = base_price
    timestamp = datetime.now()

    for i in range(periods):
        # 60% directional, 40% counter-directional moves (weak trend)
        is_trend_direction = np.random.random() < 0.6

        if direction == 'bull':
            if is_trend_direction:
                delta = price * trend_strength * np.random.uniform(0.8, 1.5)
                open_p = price
                close_p = price + delta
            else:
                delta = price * trend_strength * np.random.uniform(0.5, 1.0)
                open_p = price
                close_p = price - delta
        else:  # bear
            if is_trend_direction:
                delta = price * trend_strength * np.random.uniform(0.8, 1.5)
                open_p = price
                close_p = price - delta
            else:
                delta = price * trend_strength * np.random.uniform(0.5, 1.0)
                open_p = price
                close_p = price + delta

        high_p = max(open_p, close_p) + abs(close_p - open_p) * 0.25
        low_p = min(open_p, close_p) - abs(close_p - open_p) * 0.25

        tick_data.append(TickData(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=1000, timestamp=timestamp, symbol="TEST"
        ))
        price = close_p
        timestamp = timestamp + timedelta(minutes=1)

    return tick_data


class TestADXTrendIndicator(unittest.TestCase):
    """Tests for ADXTrendIndicator."""

    def setUp(self):
        """Set up test fixtures."""
        np.random.seed(42)  # For reproducibility

    def test_insufficient_data_returns_zeros(self):
        """Test that insufficient data returns all zeros."""
        indicator = create_adx_indicator()

        # Only 10 bars, but period is 14
        tick_data = generate_strong_uptrend_data(100.0, 10)
        values, components = indicator.calculate(tick_data)

        np.testing.assert_array_equal(values, np.zeros(10))

    def test_sideways_market_low_trend_values(self):
        """
        Test sideways/choppy market produces lower trend values than trending markets.
        ADX should stay below or near the trend_threshold more often.
        """
        indicator = create_adx_indicator()

        # Generate 80 bars of sideways data (more bars for ADX to stabilize)
        tick_data = generate_sideways_data(100.0, 80)
        values, components = indicator.calculate(tick_data)

        # Also generate uptrend data for comparison
        uptrend_data = generate_strong_uptrend_data(100.0, 80, trend_strength=0.02)
        uptrend_values, _ = indicator.calculate(uptrend_data)

        # After warmup period, sideways should have lower mean absolute values than uptrend
        warmup = 25  # ADX needs warmup
        sideways_abs = np.abs(values[warmup:])
        uptrend_abs = np.abs(uptrend_values[warmup:])

        mean_sideways = np.mean(sideways_abs)
        mean_uptrend = np.mean(uptrend_abs)

        # Sideways should have meaningfully lower values than trending
        self.assertLess(mean_sideways, mean_uptrend,
            f"Sideways ({mean_sideways:.3f}) should have lower values than uptrend ({mean_uptrend:.3f})")

        # Sideways should have more zero values (times when ADX < threshold)
        zero_count_sideways = np.sum(values[warmup:] == 0)
        zero_count_uptrend = np.sum(uptrend_values[warmup:] == 0)

        self.assertGreaterEqual(zero_count_sideways, zero_count_uptrend,
            f"Sideways should have >= zero values: {zero_count_sideways} vs {zero_count_uptrend}")

        # Check components are populated
        self.assertIn("adx_trend_adx", components)
        self.assertIn("adx_trend_plus_di", components)
        self.assertIn("adx_trend_minus_di", components)

    def test_strong_uptrend_positive_values(self):
        """
        Test strong uptrend produces positive values close to +1.0.
        ADX should be high and +DI > -DI.
        """
        indicator = create_adx_indicator()

        # Generate 80 bars of strong uptrend
        tick_data = generate_strong_uptrend_data(100.0, 80, trend_strength=0.02)
        values, components = indicator.calculate(tick_data)

        # After trend establishes, values should be positive
        # Use last 20 bars where trend should be well-established
        final_values = values[-20:]

        # Should have positive values (bullish)
        positive_count = np.sum(final_values > 0)
        self.assertGreater(positive_count, 15,
            f"Strong uptrend should have mostly positive values, got {positive_count}/20")

        # Should have some values with significant strength
        strong_values = np.sum(final_values > 0.3)
        self.assertGreater(strong_values, 5,
            f"Strong uptrend should have some values > 0.3, got {strong_values}")

        # Verify direction consistency
        adx = components["adx_trend_adx"]
        plus_di = components["adx_trend_plus_di"]
        minus_di = components["adx_trend_minus_di"]

        # At end of strong uptrend, +DI should generally exceed -DI
        self.assertGreater(plus_di[-1], minus_di[-1],
            f"+DI ({plus_di[-1]:.2f}) should be > -DI ({minus_di[-1]:.2f}) in uptrend")

    def test_strong_downtrend_negative_values(self):
        """
        Test strong downtrend produces negative values close to -1.0.
        ADX should be high and -DI > +DI.
        """
        indicator = create_adx_indicator()

        # Generate 80 bars of strong downtrend
        tick_data = generate_strong_downtrend_data(100.0, 80, trend_strength=0.02)
        values, components = indicator.calculate(tick_data)

        # After trend establishes, values should be negative
        final_values = values[-20:]

        # Should have negative values (bearish)
        negative_count = np.sum(final_values < 0)
        self.assertGreater(negative_count, 15,
            f"Strong downtrend should have mostly negative values, got {negative_count}/20")

        # Should have some values with significant strength
        strong_values = np.sum(final_values < -0.3)
        self.assertGreater(strong_values, 5,
            f"Strong downtrend should have some values < -0.3, got {strong_values}")

        # Verify direction
        plus_di = components["adx_trend_plus_di"]
        minus_di = components["adx_trend_minus_di"]

        # At end of strong downtrend, -DI should generally exceed +DI
        self.assertGreater(minus_di[-1], plus_di[-1],
            f"-DI ({minus_di[-1]:.2f}) should be > +DI ({plus_di[-1]:.2f}) in downtrend")

    def test_value_range_bounded(self):
        """Test all output values are bounded between -1.0 and +1.0."""
        indicator = create_adx_indicator()

        # Test with extreme uptrend
        uptrend_data = generate_strong_uptrend_data(100.0, 100, trend_strength=0.03)
        values_up, _ = indicator.calculate(uptrend_data)

        self.assertTrue(np.all(values_up >= -1.0) and np.all(values_up <= 1.0),
            f"Values should be in [-1, 1], got min={values_up.min()}, max={values_up.max()}")

        # Test with extreme downtrend
        downtrend_data = generate_strong_downtrend_data(100.0, 100, trend_strength=0.03)
        values_down, _ = indicator.calculate(downtrend_data)

        self.assertTrue(np.all(values_down >= -1.0) and np.all(values_down <= 1.0),
            f"Values should be in [-1, 1], got min={values_down.min()}, max={values_down.max()}")

    def test_threshold_behavior(self):
        """
        Test that trend_threshold parameter controls when trending starts.
        Values should be 0 when ADX < trend_threshold.
        """
        indicator_low_threshold = create_adx_indicator(
            name="test_adx_low",
            trend_threshold=15.0,
            strong_trend_threshold=40.0
        )
        indicator_high_threshold = create_adx_indicator(
            name="test_adx_high",
            trend_threshold=35.0,
            strong_trend_threshold=50.0
        )

        # Same data, different thresholds
        tick_data = generate_weak_trend_data(100.0, 60, direction='bull')

        values_low, comp_low = indicator_low_threshold.calculate(tick_data)
        values_high, comp_high = indicator_high_threshold.calculate(tick_data)

        # Lower threshold should produce more non-zero values
        nonzero_low = np.sum(values_low[-30:] != 0)
        nonzero_high = np.sum(values_high[-30:] != 0)

        # Low threshold should have at least as many non-zero values
        self.assertGreaterEqual(nonzero_low, nonzero_high,
            f"Lower threshold should have >= non-zero values: {nonzero_low} vs {nonzero_high}")

    def test_strength_interpolation(self):
        """
        Test linear interpolation of strength between threshold and strong_threshold.
        When ADX is exactly at trend_threshold, strength should be 0.
        When ADX is at strong_trend_threshold, strength should be 1.0.
        """
        indicator = create_adx_indicator()

        # Generate data that produces moderate trend
        tick_data = generate_strong_uptrend_data(100.0, 80, trend_strength=0.012)
        values, components = indicator.calculate(tick_data)

        adx = components["adx_trend_adx"]
        strength = components["adx_trend_strength"]

        # Find indices where ADX is between thresholds
        valid_mask = ~np.isnan(adx)
        for i in range(len(values)):
            if valid_mask[i]:
                adx_val = adx[i]
                strength_val = strength[i]

                if adx_val < 25.0:
                    self.assertEqual(strength_val, 0.0,
                        f"ADX={adx_val:.1f} < threshold, strength should be 0")
                elif adx_val >= 40.0:
                    self.assertAlmostEqual(strength_val, 1.0, places=5,
                        msg=f"ADX={adx_val:.1f} >= strong threshold, strength should be 1.0")
                else:
                    # Linear interpolation check
                    expected_strength = (adx_val - 25.0) / (40.0 - 25.0)
                    self.assertAlmostEqual(strength_val, expected_strength, places=5,
                        msg=f"ADX={adx_val:.1f}, expected strength={expected_strength:.4f}, got {strength_val:.4f}")

    def test_component_data_structure(self):
        """Test that component data includes all expected keys."""
        indicator = create_adx_indicator(name="my_adx")

        tick_data = generate_strong_uptrend_data(100.0, 50)
        values, components = indicator.calculate(tick_data)

        # Note: The indicator uses self.name() which is the class method "adx_trend"
        expected_keys = [
            "adx_trend_adx",
            "adx_trend_plus_di",
            "adx_trend_minus_di",
            "adx_trend_strength",
            "adx_trend_direction"
        ]

        for key in expected_keys:
            self.assertIn(key, components, f"Component '{key}' missing from output")
            self.assertEqual(len(components[key]), len(tick_data),
                f"Component '{key}' length mismatch")

    def test_indicator_type_is_trend(self):
        """Test that indicator is classified as TREND type."""
        from indicator_triggers.indicator_base import IndicatorType

        self.assertEqual(ADXTrendIndicator.get_indicator_type(), IndicatorType.TREND)

    def test_trend_reversal_detection(self):
        """
        Test that indicator detects trend reversals.
        Start with uptrend, transition to downtrend.
        """
        indicator = create_adx_indicator()

        # Build combined data: uptrend -> downtrend
        uptrend = generate_strong_uptrend_data(100.0, 50, trend_strength=0.015)
        last_price = uptrend[-1].close
        downtrend = generate_strong_downtrend_data(last_price, 50, trend_strength=0.015)

        tick_data = uptrend + downtrend
        values, components = indicator.calculate(tick_data)

        # Check beginning (uptrend period) has positive values
        uptrend_values = values[30:45]  # After warmup, during uptrend
        uptrend_positive = np.mean(uptrend_values > 0)

        # Check end (downtrend period) has negative values
        downtrend_values = values[-15:]  # End of downtrend
        downtrend_negative = np.mean(downtrend_values < 0)

        self.assertGreater(uptrend_positive, 0.6,
            f"Uptrend period should be mostly positive, got {uptrend_positive:.1%}")
        self.assertGreater(downtrend_negative, 0.6,
            f"Downtrend period should be mostly negative, got {downtrend_negative:.1%}")


class TestADXTrendIndicatorDirectionFilter(unittest.TestCase):
    """Test direction_filter parameter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        np.random.seed(42)  # For reproducibility

    def test_bull_filter_zeros_negative_values(self):
        """Test that Bull filter zeros out negative (bearish) values."""
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bull = create_adx_indicator(direction_filter="Bull")

        # Generate downtrend data (produces negative values)
        tick_data = generate_strong_downtrend_data(100.0, 80, trend_strength=0.02)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bull, _ = indicator_bull.calculate(tick_data)

        # Both should have negative values
        negative_both = np.sum(values_both < 0)
        self.assertGreater(negative_both, 10,
            f"Downtrend with Both filter should have negative values, got {negative_both}")

        # Bull filter should have NO negative values
        negative_bull = np.sum(values_bull < 0)
        self.assertEqual(negative_bull, 0,
            f"Bull filter should have NO negative values, got {negative_bull}")

        # Bull filter should have all zeros (since downtrend produces only negative)
        nonzero_bull = np.sum(values_bull != 0)
        self.assertEqual(nonzero_bull, 0,
            f"Bull filter on downtrend should be all zeros, got {nonzero_bull} non-zero")

    def test_bear_filter_zeros_positive_values(self):
        """Test that Bear filter zeros out positive (bullish) values."""
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bear = create_adx_indicator(direction_filter="Bear")

        # Generate uptrend data (produces positive values)
        tick_data = generate_strong_uptrend_data(100.0, 80, trend_strength=0.02)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bear, _ = indicator_bear.calculate(tick_data)

        # Both should have positive values
        positive_both = np.sum(values_both > 0)
        self.assertGreater(positive_both, 10,
            f"Uptrend with Both filter should have positive values, got {positive_both}")

        # Bear filter should have NO positive values
        positive_bear = np.sum(values_bear > 0)
        self.assertEqual(positive_bear, 0,
            f"Bear filter should have NO positive values, got {positive_bear}")

        # Bear filter should have all zeros (since uptrend produces only positive)
        nonzero_bear = np.sum(values_bear != 0)
        self.assertEqual(nonzero_bear, 0,
            f"Bear filter on uptrend should be all zeros, got {nonzero_bear} non-zero")

    def test_both_filter_preserves_all_values(self):
        """Test that Both filter preserves both positive and negative values."""
        indicator = create_adx_indicator(direction_filter="Both")

        # Build combined data: uptrend -> downtrend
        uptrend = generate_strong_uptrend_data(100.0, 50, trend_strength=0.015)
        last_price = uptrend[-1].close
        downtrend = generate_strong_downtrend_data(last_price, 50, trend_strength=0.015)

        tick_data = uptrend + downtrend
        values, _ = indicator.calculate(tick_data)

        # Should have both positive and negative values
        has_positive = np.any(values > 0)
        has_negative = np.any(values < 0)

        self.assertTrue(has_positive, "Both filter should preserve positive values")
        self.assertTrue(has_negative, "Both filter should preserve negative values")

    def test_bull_filter_preserves_positive_in_mixed_market(self):
        """Test Bull filter preserves positive values in mixed trend market."""
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bull = create_adx_indicator(direction_filter="Bull")

        # Build combined data: uptrend -> downtrend
        uptrend = generate_strong_uptrend_data(100.0, 50, trend_strength=0.015)
        last_price = uptrend[-1].close
        downtrend = generate_strong_downtrend_data(last_price, 50, trend_strength=0.015)

        tick_data = uptrend + downtrend
        values_both, _ = indicator_both.calculate(tick_data)
        values_bull, _ = indicator_bull.calculate(tick_data)

        # Bull filter should preserve positive values from uptrend portion
        positive_both = values_both[values_both > 0]
        positive_bull = values_bull[values_bull > 0]

        # All positive values from Both should be preserved in Bull
        np.testing.assert_array_almost_equal(
            np.sort(positive_both), np.sort(positive_bull),
            decimal=10,
            err_msg="Bull filter should preserve all positive values"
        )

    def test_bear_filter_preserves_negative_in_mixed_market(self):
        """Test Bear filter preserves negative values in mixed trend market."""
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bear = create_adx_indicator(direction_filter="Bear")

        # Build combined data: uptrend -> downtrend
        uptrend = generate_strong_uptrend_data(100.0, 50, trend_strength=0.015)
        last_price = uptrend[-1].close
        downtrend = generate_strong_downtrend_data(last_price, 50, trend_strength=0.015)

        tick_data = uptrend + downtrend
        values_both, _ = indicator_both.calculate(tick_data)
        values_bear, _ = indicator_bear.calculate(tick_data)

        # Bear filter should preserve negative values from downtrend portion
        negative_both = values_both[values_both < 0]
        negative_bear = values_bear[values_bear < 0]

        # All negative values from Both should be preserved in Bear
        np.testing.assert_array_almost_equal(
            np.sort(negative_both), np.sort(negative_bear),
            decimal=10,
            err_msg="Bear filter should preserve all negative values"
        )

    def test_direction_filter_default_is_both(self):
        """Test that direction_filter default value is 'Both'."""
        specs = ADXTrendIndicator.get_parameter_specs()
        filter_spec = next(s for s in specs if s.name == "direction_filter")

        self.assertEqual(filter_spec.default_value, "Both")
        self.assertEqual(filter_spec.choices, ["Both", "Bull", "Bear"])


class TestADXTrendIndicatorParameterValidation(unittest.TestCase):
    """Test parameter specification and validation."""

    def test_parameter_specs_exist(self):
        """Test that parameter specs are properly defined."""
        specs = ADXTrendIndicator.get_parameter_specs()

        param_names = [spec.name for spec in specs]
        self.assertIn("period", param_names)
        self.assertIn("trend_threshold", param_names)
        self.assertIn("strong_trend_threshold", param_names)
        self.assertIn("direction_filter", param_names)

    def test_default_parameters(self):
        """Test default parameter values."""
        specs = ADXTrendIndicator.get_parameter_specs()
        defaults = {spec.name: spec.default_value for spec in specs}

        self.assertEqual(defaults["period"], 14)
        self.assertEqual(defaults["trend_threshold"], 25.0)
        self.assertEqual(defaults["strong_trend_threshold"], 40.0)
        self.assertEqual(defaults["direction_filter"], "Both")

    def test_custom_period(self):
        """Test indicator works with custom period values."""
        indicator_short = create_adx_indicator(name="test_short", period=7)
        indicator_long = create_adx_indicator(name="test_long", period=21)

        tick_data = generate_strong_uptrend_data(100.0, 60)

        values_short, _ = indicator_short.calculate(tick_data)
        values_long, _ = indicator_long.calculate(tick_data)

        # Shorter period should respond faster (more non-zero values earlier)
        nonzero_short_early = np.sum(values_short[15:25] != 0)
        nonzero_long_early = np.sum(values_long[15:25] != 0)

        self.assertGreater(nonzero_short_early, nonzero_long_early,
            f"Shorter period should react faster: {nonzero_short_early} vs {nonzero_long_early}")

    def test_default_instantiation(self):
        """Test that indicator can be instantiated with defaults (no config)."""
        indicator = ADXTrendIndicator()

        # Should work with default values
        tick_data = generate_strong_uptrend_data(100.0, 50)
        values, components = indicator.calculate(tick_data)

        self.assertEqual(len(values), 50)
        self.assertIn("adx_trend_adx", components)


if __name__ == "__main__":
    unittest.main()
