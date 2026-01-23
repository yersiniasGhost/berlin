"""
Tests for EMASlopeTrendIndicator from trend_indicators.py.

Tests cover:
1. Uptrend produces positive values
2. Downtrend produces negative values
3. Sideways market produces values near zero
4. Output bounded to [-1, 1]
5. Normalization works across different price levels
6. Edge cases (insufficient data)
"""

import unittest
import numpy as np
from datetime import datetime, timedelta

from models.tick_data import TickData
from indicator_triggers.indicator_base import IndicatorConfiguration
from indicator_triggers.trend_indicators import EMASlopeTrendIndicator


def create_ema_slope_indicator(name: str = "test_ema_slope", period: int = 20,
                               slope_period: int = 5, normalize_factor: float = 0.005,
                               smoothing: int = 3, direction_filter: str = "Both"):
    """Factory function to create EMASlopeTrendIndicator with custom parameters."""
    config = IndicatorConfiguration(
        indicator_name="EMASlopeTrendIndicator",
        display_name=name,
        parameters={
            "period": period,
            "slope_period": slope_period,
            "normalize_factor": normalize_factor,
            "smoothing": smoothing,
            "direction_filter": direction_filter
        }
    )
    return EMASlopeTrendIndicator(config)


def generate_linear_uptrend(base_price: float, periods: int, slope_per_bar: float) -> list:
    """
    Generate perfectly linear uptrend data.
    slope_per_bar: price increase per bar (e.g., 0.50 means +$0.50/bar)
    """
    tick_data = []
    timestamp = datetime.now()

    for i in range(periods):
        price = base_price + (slope_per_bar * i)
        # Minimal noise for linear trend
        noise = price * 0.001 * np.random.uniform(-1, 1)

        open_p = price + noise
        close_p = price + slope_per_bar * 0.5 + noise  # Close slightly above open
        high_p = max(open_p, close_p) + abs(noise)
        low_p = min(open_p, close_p) - abs(noise)

        tick_data.append(TickData(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=1000, timestamp=timestamp, symbol="TEST"
        ))
        timestamp = timestamp + timedelta(minutes=1)

    return tick_data


def generate_linear_downtrend(base_price: float, periods: int, slope_per_bar: float) -> list:
    """
    Generate perfectly linear downtrend data.
    slope_per_bar: price decrease per bar (positive value, e.g., 0.50 means -$0.50/bar)
    """
    tick_data = []
    timestamp = datetime.now()

    for i in range(periods):
        price = base_price - (slope_per_bar * i)
        noise = price * 0.001 * np.random.uniform(-1, 1)

        open_p = price + noise
        close_p = price - slope_per_bar * 0.5 + noise  # Close slightly below open
        high_p = max(open_p, close_p) + abs(noise)
        low_p = min(open_p, close_p) - abs(noise)

        tick_data.append(TickData(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=1000, timestamp=timestamp, symbol="TEST"
        ))
        timestamp = timestamp + timedelta(minutes=1)

    return tick_data


def generate_sideways_data(base_price: float, periods: int, volatility: float = 0.002) -> list:
    """
    Generate sideways/ranging market data with no clear trend.
    Uses mean-reverting oscillation around base price.
    """
    tick_data = []
    price = base_price
    timestamp = datetime.now()

    for i in range(periods):
        # Mean reversion toward base price
        revert_force = (base_price - price) * 0.15
        random_move = price * volatility * np.random.uniform(-1.0, 1.0)
        delta = revert_force + random_move

        open_p = price
        close_p = price + delta
        high_p = max(open_p, close_p) + abs(delta) * 0.2
        low_p = min(open_p, close_p) - abs(delta) * 0.2

        tick_data.append(TickData(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=1000, timestamp=timestamp, symbol="TEST"
        ))
        price = close_p
        timestamp = timestamp + timedelta(minutes=1)

    return tick_data


def generate_strong_trend_data(base_price: float, periods: int, direction: str = 'bull',
                               trend_strength: float = 0.01) -> list:
    """
    Generate strong trending data with some noise.
    """
    tick_data = []
    price = base_price
    timestamp = datetime.now()

    for i in range(periods):
        delta = price * trend_strength * np.random.uniform(0.7, 1.3)

        if direction == 'bull':
            open_p = price
            close_p = price + delta
        else:
            open_p = price
            close_p = price - delta

        high_p = max(open_p, close_p) + abs(delta) * 0.2
        low_p = min(open_p, close_p) - abs(delta) * 0.15

        tick_data.append(TickData(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=1000, timestamp=timestamp, symbol="TEST"
        ))
        price = close_p
        timestamp = timestamp + timedelta(minutes=1)

    return tick_data


class TestEMASlopeTrendIndicator(unittest.TestCase):
    """Tests for EMASlopeTrendIndicator."""

    def setUp(self):
        """Set up test fixtures."""
        np.random.seed(42)

    def test_insufficient_data_returns_zeros(self):
        """Test that insufficient data returns all zeros."""
        indicator = create_ema_slope_indicator()

        # period=20, slope_period=5, smoothing=3 -> need 28+ bars
        tick_data = generate_linear_uptrend(100.0, 20, 0.5)
        values, components = indicator.calculate(tick_data)

        np.testing.assert_array_equal(values, np.zeros(20))

    def test_uptrend_produces_positive_values(self):
        """Test that an uptrend produces positive output values."""
        indicator = create_ema_slope_indicator()

        # Generate strong uptrend: 60 bars with $0.50/bar rise on $100 stock
        tick_data = generate_linear_uptrend(100.0, 60, 0.5)
        values, components = indicator.calculate(tick_data)

        # After warmup, values should be positive
        warmup = 30  # EMA + slope + smoothing warmup
        final_values = values[warmup:]

        positive_count = np.sum(final_values > 0)
        total = len(final_values)

        self.assertGreater(positive_count / total, 0.9,
            f"Uptrend should be >90% positive, got {positive_count}/{total}")

        # Mean should be clearly positive
        mean_value = np.mean(final_values)
        self.assertGreater(mean_value, 0.1,
            f"Mean value should be positive, got {mean_value:.3f}")

    def test_downtrend_produces_negative_values(self):
        """Test that a downtrend produces negative output values."""
        indicator = create_ema_slope_indicator()

        # Generate strong downtrend
        tick_data = generate_linear_downtrend(100.0, 60, 0.5)
        values, components = indicator.calculate(tick_data)

        # After warmup, values should be negative
        warmup = 30
        final_values = values[warmup:]

        negative_count = np.sum(final_values < 0)
        total = len(final_values)

        self.assertGreater(negative_count / total, 0.9,
            f"Downtrend should be >90% negative, got {negative_count}/{total}")

        # Mean should be clearly negative
        mean_value = np.mean(final_values)
        self.assertLess(mean_value, -0.1,
            f"Mean value should be negative, got {mean_value:.3f}")

    def test_sideways_market_produces_values_near_zero(self):
        """Test that sideways market produces values closer to zero."""
        indicator = create_ema_slope_indicator()

        # Generate sideways data
        sideways_data = generate_sideways_data(100.0, 80)
        values_sideways, _ = indicator.calculate(sideways_data)

        # Compare with trending data
        uptrend_data = generate_strong_trend_data(100.0, 80, 'bull', trend_strength=0.015)
        values_uptrend, _ = indicator.calculate(uptrend_data)

        warmup = 35

        # Sideways should have lower absolute mean than uptrend
        mean_abs_sideways = np.mean(np.abs(values_sideways[warmup:]))
        mean_abs_uptrend = np.mean(np.abs(values_uptrend[warmup:]))

        self.assertLess(mean_abs_sideways, mean_abs_uptrend,
            f"Sideways ({mean_abs_sideways:.3f}) should have lower values than uptrend ({mean_abs_uptrend:.3f})")

    def test_output_bounded_to_unit_interval(self):
        """Test all output values are bounded between -1.0 and +1.0."""
        indicator = create_ema_slope_indicator()

        # Test with extreme uptrend
        uptrend_data = generate_linear_uptrend(100.0, 80, 1.0)  # $1/bar on $100 stock
        values_up, _ = indicator.calculate(uptrend_data)

        self.assertTrue(np.all(values_up >= -1.0) and np.all(values_up <= 1.0),
            f"Values should be in [-1, 1], got min={values_up.min()}, max={values_up.max()}")

        # Test with extreme downtrend
        downtrend_data = generate_linear_downtrend(200.0, 80, 1.0)
        values_down, _ = indicator.calculate(downtrend_data)

        self.assertTrue(np.all(values_down >= -1.0) and np.all(values_down <= 1.0),
            f"Values should be in [-1, 1], got min={values_down.min()}, max={values_down.max()}")

    def test_normalization_across_price_levels(self):
        """
        Test that normalization makes output independent of price level.
        Same percentage move on $100 vs $1000 stock should give similar output.
        """
        indicator = create_ema_slope_indicator()

        # Same percentage slope: 0.5% per bar
        # $100 stock: $0.50/bar
        # $1000 stock: $5.00/bar
        data_100 = generate_linear_uptrend(100.0, 60, 0.5)
        data_1000 = generate_linear_uptrend(1000.0, 60, 5.0)

        values_100, _ = indicator.calculate(data_100)
        values_1000, _ = indicator.calculate(data_1000)

        warmup = 35
        mean_100 = np.mean(values_100[warmup:])
        mean_1000 = np.mean(values_1000[warmup:])

        # Should be within 20% of each other
        ratio = mean_100 / mean_1000 if mean_1000 != 0 else float('inf')
        self.assertGreater(ratio, 0.8, f"Ratio too low: {ratio:.3f}")
        self.assertLess(ratio, 1.2, f"Ratio too high: {ratio:.3f}")

    def test_slope_period_affects_responsiveness(self):
        """Test that shorter slope_period responds faster to trend changes."""
        indicator_short = create_ema_slope_indicator(slope_period=3)
        indicator_long = create_ema_slope_indicator(slope_period=10)

        # Create data: sideways then uptrend
        sideways = generate_sideways_data(100.0, 30)
        uptrend = generate_linear_uptrend(sideways[-1].close, 40, 0.5)
        tick_data = sideways + uptrend

        values_short, _ = indicator_short.calculate(tick_data)
        values_long, _ = indicator_long.calculate(tick_data)

        # At transition point, short period should show trend faster
        # Check values around bar 40-50 (transition area)
        transition_values_short = values_short[35:50]
        transition_values_long = values_long[35:50]

        # Short period should have higher positive values sooner
        mean_short = np.mean(transition_values_short)
        mean_long = np.mean(transition_values_long)

        self.assertGreater(mean_short, mean_long,
            f"Short slope_period should respond faster: {mean_short:.3f} vs {mean_long:.3f}")

    def test_smoothing_reduces_noise(self):
        """Test that smoothing parameter reduces output noise."""
        indicator_no_smooth = create_ema_slope_indicator(smoothing=1)
        indicator_smoothed = create_ema_slope_indicator(smoothing=5)

        # Generate noisy trend data with significant volatility
        tick_data = []
        timestamp = datetime.now()
        price = 100.0

        for i in range(100):
            # Strong uptrend with significant noise
            trend_move = 0.3  # Base trend
            noise = np.random.uniform(-0.5, 0.5)  # Significant noise
            delta = trend_move + noise

            open_p = price
            close_p = price + delta
            high_p = max(open_p, close_p) + abs(np.random.uniform(0.1, 0.3))
            low_p = min(open_p, close_p) - abs(np.random.uniform(0.1, 0.3))

            tick_data.append(TickData(
                open=open_p, high=high_p, low=low_p, close=close_p,
                volume=1000, timestamp=timestamp, symbol="TEST"
            ))
            price = close_p
            timestamp = timestamp + timedelta(minutes=1)

        values_no_smooth, _ = indicator_no_smooth.calculate(tick_data)
        values_smoothed, _ = indicator_smoothed.calculate(tick_data)

        warmup = 40

        # Calculate standard deviation (measure of noise)
        std_no_smooth = np.std(values_no_smooth[warmup:])
        std_smoothed = np.std(values_smoothed[warmup:])

        self.assertLess(std_smoothed, std_no_smooth,
            f"Smoothed should have lower std: {std_smoothed:.4f} vs {std_no_smooth:.4f}")

    def test_component_data_structure(self):
        """Test that component data includes all expected keys."""
        indicator = create_ema_slope_indicator()

        tick_data = generate_linear_uptrend(100.0, 50, 0.3)
        values, components = indicator.calculate(tick_data)

        expected_keys = [
            "ema_slope_ema",
            "ema_slope_slope",
            "ema_slope_smoothed_slope",
            "ema_slope_normalized"
        ]

        for key in expected_keys:
            self.assertIn(key, components, f"Component '{key}' missing from output")
            self.assertEqual(len(components[key]), len(tick_data),
                f"Component '{key}' length mismatch")

    def test_indicator_type_is_trend(self):
        """Test that indicator is classified as TREND type."""
        from indicator_triggers.indicator_base import IndicatorType

        self.assertEqual(EMASlopeTrendIndicator.get_indicator_type(), IndicatorType.TREND)

    def test_layout_type_is_overlay(self):
        """Test that layout type is overlay (EMA on price chart)."""
        self.assertEqual(EMASlopeTrendIndicator.get_layout_type(), "overlay")

    def test_trend_reversal_detection(self):
        """Test that indicator detects trend reversals."""
        indicator = create_ema_slope_indicator()

        # Build combined data: uptrend -> downtrend
        uptrend = generate_linear_uptrend(100.0, 50, 0.4)
        last_price = uptrend[-1].close
        downtrend = generate_linear_downtrend(last_price, 50, 0.4)

        tick_data = uptrend + downtrend
        values, _ = indicator.calculate(tick_data)

        # Check uptrend portion has positive values
        uptrend_values = values[35:48]  # After warmup, during uptrend
        uptrend_positive = np.mean(uptrend_values > 0)

        # Check downtrend portion has negative values
        downtrend_values = values[-15:]  # End of downtrend
        downtrend_negative = np.mean(downtrend_values < 0)

        self.assertGreater(uptrend_positive, 0.7,
            f"Uptrend period should be mostly positive, got {uptrend_positive:.1%}")
        self.assertGreater(downtrend_negative, 0.7,
            f"Downtrend period should be mostly negative, got {downtrend_negative:.1%}")

    def test_default_instantiation(self):
        """Test that indicator can be instantiated with defaults (no config)."""
        indicator = EMASlopeTrendIndicator()

        tick_data = generate_linear_uptrend(100.0, 50, 0.3)
        values, components = indicator.calculate(tick_data)

        self.assertEqual(len(values), 50)
        self.assertIn("ema_slope_ema", components)


class TestEMASlopeTrendIndicatorParameters(unittest.TestCase):
    """Test parameter specification and validation."""

    def test_parameter_specs_exist(self):
        """Test that parameter specs are properly defined."""
        specs = EMASlopeTrendIndicator.get_parameter_specs()

        param_names = [spec.name for spec in specs]
        self.assertIn("period", param_names)
        self.assertIn("slope_period", param_names)
        self.assertIn("normalize_factor", param_names)
        self.assertIn("smoothing", param_names)
        self.assertIn("direction_filter", param_names)

    def test_default_parameters(self):
        """Test default parameter values."""
        specs = EMASlopeTrendIndicator.get_parameter_specs()
        defaults = {spec.name: spec.default_value for spec in specs}

        self.assertEqual(defaults["period"], 20)
        self.assertEqual(defaults["slope_period"], 5)
        self.assertEqual(defaults["normalize_factor"], 0.005)
        self.assertEqual(defaults["smoothing"], 3)
        self.assertEqual(defaults["direction_filter"], "Both")

    def test_normalize_factor_effect(self):
        """Test that normalize_factor affects output magnitude."""
        # Higher normalize_factor = smaller output for same slope
        indicator_low_norm = create_ema_slope_indicator(normalize_factor=0.002)
        indicator_high_norm = create_ema_slope_indicator(normalize_factor=0.01)

        tick_data = generate_linear_uptrend(100.0, 60, 0.3)

        values_low, _ = indicator_low_norm.calculate(tick_data)
        values_high, _ = indicator_high_norm.calculate(tick_data)

        warmup = 35
        mean_low = np.mean(np.abs(values_low[warmup:]))
        mean_high = np.mean(np.abs(values_high[warmup:]))

        # Lower normalize_factor should produce higher values (more sensitive)
        self.assertGreater(mean_low, mean_high,
            f"Lower normalize_factor should give higher output: {mean_low:.3f} vs {mean_high:.3f}")


class TestEMASlopeTrendIndicatorEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        np.random.seed(42)

    def test_constant_price_produces_zero(self):
        """Test that constant price produces zero slope."""
        indicator = create_ema_slope_indicator()

        # Generate constant price data
        tick_data = []
        timestamp = datetime.now()
        price = 100.0

        for i in range(60):
            tick_data.append(TickData(
                open=price, high=price + 0.01, low=price - 0.01, close=price,
                volume=1000, timestamp=timestamp, symbol="TEST"
            ))
            timestamp = timestamp + timedelta(minutes=1)

        values, _ = indicator.calculate(tick_data)

        warmup = 35
        mean_abs = np.mean(np.abs(values[warmup:]))

        self.assertLess(mean_abs, 0.01,
            f"Constant price should produce near-zero values, got mean abs = {mean_abs:.4f}")

    def test_very_small_prices(self):
        """Test indicator works with very small prices (penny stocks)."""
        indicator = create_ema_slope_indicator()

        # $0.50 stock with proportional moves
        tick_data = generate_linear_uptrend(0.50, 60, 0.0025)  # 0.5% per bar
        values, _ = indicator.calculate(tick_data)

        # Should still produce valid bounded values
        self.assertTrue(np.all(values >= -1.0) and np.all(values <= 1.0))

        # Should detect the uptrend
        warmup = 35
        self.assertGreater(np.mean(values[warmup:]), 0)

    def test_very_large_prices(self):
        """Test indicator works with very large prices (like BRK.A)."""
        indicator = create_ema_slope_indicator()

        # $500,000 stock with proportional moves
        tick_data = generate_linear_uptrend(500000.0, 60, 2500.0)  # 0.5% per bar
        values, _ = indicator.calculate(tick_data)

        # Should still produce valid bounded values
        self.assertTrue(np.all(values >= -1.0) and np.all(values <= 1.0))

        # Should detect the uptrend
        warmup = 35
        self.assertGreater(np.mean(values[warmup:]), 0)


class TestEMASlopeTrendIndicatorDirectionFilter(unittest.TestCase):
    """Test direction_filter parameter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        np.random.seed(42)

    def test_bull_filter_zeros_negative_and_keeps_positive(self):
        """Test that Bull filter zeros out negative values and keeps positive."""
        indicator_both = create_ema_slope_indicator(direction_filter="Both")
        indicator_bull = create_ema_slope_indicator(direction_filter="Bull")

        # Generate downtrend data (produces negative values with Both)
        tick_data = generate_linear_downtrend(100.0, 80, 0.5)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bull, _ = indicator_bull.calculate(tick_data)

        warmup = 35

        # Both should have negative values in downtrend
        negative_both = np.sum(values_both[warmup:] < 0)
        self.assertGreater(negative_both, 10,
            f"Downtrend with Both filter should have negative values, got {negative_both}")

        # Bull filter should have NO negative values
        negative_bull = np.sum(values_bull < 0)
        self.assertEqual(negative_bull, 0,
            f"Bull filter should have NO negative values, got {negative_bull}")

        # Bull filter should be all zeros (downtrend has no bullish signals)
        nonzero_bull = np.sum(values_bull[warmup:] != 0)
        self.assertEqual(nonzero_bull, 0,
            f"Bull filter on downtrend should be all zeros, got {nonzero_bull} non-zero")

    def test_bear_filter_converts_negative_to_positive(self):
        """Test that Bear filter converts negative values to positive (always positive trigger)."""
        indicator_both = create_ema_slope_indicator(direction_filter="Both")
        indicator_bear = create_ema_slope_indicator(direction_filter="Bear")

        # Generate downtrend data (produces negative values with Both)
        tick_data = generate_linear_downtrend(100.0, 80, 0.5)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bear, _ = indicator_bear.calculate(tick_data)

        warmup = 35

        # Both should have negative values
        has_negative_both = np.any(values_both[warmup:] < 0)
        self.assertTrue(has_negative_both,
            "Downtrend with Both filter should have negative values")

        # Bear filter should have NO negative values (converted to positive)
        negative_bear = np.sum(values_bear < 0)
        self.assertEqual(negative_bear, 0,
            f"Bear filter should have NO negative values, got {negative_bear}")

        # Bear filter should have POSITIVE values (from the bearish trend)
        positive_bear = np.sum(values_bear[warmup:] > 0)
        self.assertGreater(positive_bear, 10,
            f"Bear filter on downtrend should have positive values, got {positive_bear}")

        # Bear values should be absolute value of Both negative values
        for i in range(warmup, len(values_both)):
            if values_both[i] < 0:
                self.assertAlmostEqual(values_bear[i], abs(values_both[i]), places=10,
                    msg=f"Bear should be abs of Both negative at index {i}")

    def test_bear_filter_zeros_positive_values(self):
        """Test that Bear filter zeros out positive (bullish) values."""
        indicator_both = create_ema_slope_indicator(direction_filter="Both")
        indicator_bear = create_ema_slope_indicator(direction_filter="Bear")

        # Generate uptrend data (produces positive values)
        tick_data = generate_linear_uptrend(100.0, 80, 0.5)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bear, _ = indicator_bear.calculate(tick_data)

        warmup = 35

        # Both should have positive values
        positive_both = np.sum(values_both[warmup:] > 0)
        self.assertGreater(positive_both, 10,
            f"Uptrend with Both filter should have positive values, got {positive_both}")

        # Bear filter should have all zeros (uptrend has no bearish signals)
        nonzero_bear = np.sum(values_bear[warmup:] != 0)
        self.assertEqual(nonzero_bear, 0,
            f"Bear filter on uptrend should be all zeros, got {nonzero_bear} non-zero")

    def test_both_filter_preserves_signed_values(self):
        """Test that Both filter preserves both positive and negative values."""
        indicator = create_ema_slope_indicator(direction_filter="Both")

        # Build combined data: uptrend -> downtrend
        uptrend = generate_linear_uptrend(100.0, 50, 0.4)
        last_price = uptrend[-1].close
        downtrend = generate_linear_downtrend(last_price, 50, 0.4)

        tick_data = uptrend + downtrend
        values, _ = indicator.calculate(tick_data)

        # Should have both positive and negative values
        has_positive = np.any(values > 0)
        has_negative = np.any(values < 0)

        self.assertTrue(has_positive, "Both filter should preserve positive values")
        self.assertTrue(has_negative, "Both filter should preserve negative values")

    def test_bull_filter_always_non_negative(self):
        """Test Bull filter output is always >= 0."""
        indicator = create_ema_slope_indicator(direction_filter="Bull")

        # Build combined data with both trends
        uptrend = generate_linear_uptrend(100.0, 50, 0.4)
        last_price = uptrend[-1].close
        downtrend = generate_linear_downtrend(last_price, 50, 0.4)

        tick_data = uptrend + downtrend
        values, _ = indicator.calculate(tick_data)

        # All values should be >= 0
        self.assertTrue(np.all(values >= 0),
            f"Bull filter should never be negative, min={values.min()}")

    def test_bear_filter_always_non_negative(self):
        """Test Bear filter output is always >= 0 (trigger always positive)."""
        indicator = create_ema_slope_indicator(direction_filter="Bear")

        # Build combined data with both trends
        uptrend = generate_linear_uptrend(100.0, 50, 0.4)
        last_price = uptrend[-1].close
        downtrend = generate_linear_downtrend(last_price, 50, 0.4)

        tick_data = uptrend + downtrend
        values, _ = indicator.calculate(tick_data)

        # All values should be >= 0
        self.assertTrue(np.all(values >= 0),
            f"Bear filter should never be negative, min={values.min()}")

    def test_direction_filter_choices(self):
        """Test that direction_filter has correct choices."""
        specs = EMASlopeTrendIndicator.get_parameter_specs()
        filter_spec = next(s for s in specs if s.name == "direction_filter")

        self.assertEqual(filter_spec.default_value, "Both")
        self.assertEqual(filter_spec.choices, ["Both", "Bull", "Bear"])

    def test_bull_filter_preserves_bullish_strength(self):
        """Test Bull filter preserves the magnitude of bullish signals."""
        indicator_both = create_ema_slope_indicator(direction_filter="Both")
        indicator_bull = create_ema_slope_indicator(direction_filter="Bull")

        tick_data = generate_linear_uptrend(100.0, 60, 0.5)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bull, _ = indicator_bull.calculate(tick_data)

        warmup = 35

        # Positive values from Both should match Bull exactly
        for i in range(warmup, len(values_both)):
            if values_both[i] > 0:
                self.assertAlmostEqual(values_bull[i], values_both[i], places=10,
                    msg=f"Bull should preserve positive values at index {i}")


if __name__ == "__main__":
    unittest.main()
