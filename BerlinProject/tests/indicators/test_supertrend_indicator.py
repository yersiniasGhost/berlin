"""Tests for SuperTrendIndicator."""

import unittest
import numpy as np
from typing import List

from models.tick_data import TickData
from indicator_triggers.indicator_base import IndicatorConfiguration
from indicator_triggers.trend_indicators import SuperTrendIndicator


def create_supertrend_indicator(name: str = "test_supertrend", atr_period: int = 10,
                                 multiplier: float = 3.0, direction_filter: str = "Both"):
    """Factory function to create SuperTrendIndicator with parameters."""
    config = IndicatorConfiguration(
        indicator_name="SuperTrendIndicator",
        display_name=name,
        parameters={
            "atr_period": atr_period,
            "multiplier": multiplier,
            "direction_filter": direction_filter
        }
    )
    return SuperTrendIndicator(config)


def generate_tick_data(prices: List[float], volatility: float = 0.5) -> List[TickData]:
    """Generate tick data from close prices with OHLC structure."""
    ticks = []
    for i, close in enumerate(prices):
        high = close + volatility
        low = close - volatility
        open_price = prices[i - 1] if i > 0 else close
        ticks.append(TickData(
            timestamp=1000 + i * 60000,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=1000
        ))
    return ticks


def generate_uptrend_data(length: int = 100, start_price: float = 100.0,
                          trend_strength: float = 0.5) -> List[TickData]:
    """Generate data with clear uptrend."""
    prices = [start_price + i * trend_strength for i in range(length)]
    return generate_tick_data(prices, volatility=0.3)


def generate_downtrend_data(length: int = 100, start_price: float = 150.0,
                            trend_strength: float = 0.5) -> List[TickData]:
    """Generate data with clear downtrend."""
    prices = [start_price - i * trend_strength for i in range(length)]
    return generate_tick_data(prices, volatility=0.3)


def generate_sideways_data(length: int = 100, base_price: float = 100.0,
                           noise: float = 1.0) -> List[TickData]:
    """Generate sideways/ranging data with oscillation."""
    np.random.seed(42)
    prices = [base_price + np.sin(i * 0.3) * noise + np.random.uniform(-0.2, 0.2)
              for i in range(length)]
    return generate_tick_data(prices, volatility=0.5)


def generate_trend_reversal_data(length: int = 100) -> List[TickData]:
    """Generate data with trend reversal (up then down)."""
    mid = length // 2
    up_prices = [100.0 + i * 0.8 for i in range(mid)]
    peak = up_prices[-1]
    down_prices = [peak - i * 0.8 for i in range(length - mid)]
    prices = up_prices + down_prices
    return generate_tick_data(prices, volatility=0.4)


class TestSuperTrendIndicator(unittest.TestCase):
    """Test SuperTrendIndicator basic functionality."""

    def test_calculate_returns_tuple(self):
        """Calculate should return (values, components) tuple."""
        indicator = create_supertrend_indicator()
        tick_data = generate_uptrend_data()
        result = indicator.calculate(tick_data)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], np.ndarray)
        self.assertIsInstance(result[1], dict)

    def test_output_length_matches_input(self):
        """Output array length should match input length."""
        indicator = create_supertrend_indicator()
        tick_data = generate_uptrend_data(length=50)
        values, _ = indicator.calculate(tick_data)

        self.assertEqual(len(values), 50)

    def test_uptrend_produces_positive_values(self):
        """Clear uptrend should produce positive (+1) values."""
        indicator = create_supertrend_indicator()
        tick_data = generate_uptrend_data(length=100, trend_strength=1.0)
        values, _ = indicator.calculate(tick_data)

        # After warmup, most values should be +1 (bullish)
        valid_values = values[20:]  # Skip warmup period
        positive_count = np.sum(valid_values > 0)
        self.assertGreater(positive_count / len(valid_values), 0.7,
                          "Most values should be positive in uptrend")

    def test_downtrend_produces_negative_values(self):
        """Clear downtrend should produce negative (-1) values."""
        indicator = create_supertrend_indicator()
        tick_data = generate_downtrend_data(length=100, trend_strength=1.0)
        values, _ = indicator.calculate(tick_data)

        # After warmup, most values should be -1 (bearish)
        valid_values = values[20:]
        negative_count = np.sum(valid_values < 0)
        self.assertGreater(negative_count / len(valid_values), 0.7,
                          "Most values should be negative in downtrend")

    def test_output_is_binary(self):
        """SuperTrend output should be binary: +1, -1, or 0."""
        indicator = create_supertrend_indicator()
        tick_data = generate_uptrend_data()
        values, _ = indicator.calculate(tick_data)

        # All non-zero values should be exactly +1 or -1
        non_zero = values[values != 0]
        for val in non_zero:
            self.assertIn(val, [1.0, -1.0], f"Value {val} should be +1 or -1")

    def test_components_contain_expected_keys(self):
        """Components should contain supertrend line, bands, direction, and ATR."""
        indicator = create_supertrend_indicator()
        tick_data = generate_uptrend_data()
        _, components = indicator.calculate(tick_data)

        expected_keys = [
            "supertrend_line",
            "supertrend_upper",
            "supertrend_lower",
            "supertrend_direction",
            "supertrend_atr"
        ]
        for key in expected_keys:
            self.assertIn(key, components, f"Missing component: {key}")

    def test_supertrend_line_within_bands(self):
        """SuperTrend line should be at upper or lower band."""
        indicator = create_supertrend_indicator()
        tick_data = generate_uptrend_data()
        _, components = indicator.calculate(tick_data)

        line = components["supertrend_line"]
        upper = components["supertrend_upper"]
        lower = components["supertrend_lower"]

        # For valid values, line should equal either upper or lower band
        for i in range(20, len(line)):  # Skip warmup
            if line[i] != 0:
                is_at_upper = np.isclose(line[i], upper[i], rtol=1e-5)
                is_at_lower = np.isclose(line[i], lower[i], rtol=1e-5)
                self.assertTrue(is_at_upper or is_at_lower,
                               f"Line at {i} should equal upper or lower band")

    def test_trend_reversal_detection(self):
        """Should detect trend reversal in reversal data."""
        indicator = create_supertrend_indicator()
        tick_data = generate_trend_reversal_data(length=100)
        values, _ = indicator.calculate(tick_data)

        # Check for both positive and negative values (trend changed)
        has_positive = np.any(values > 0)
        has_negative = np.any(values < 0)
        self.assertTrue(has_positive and has_negative,
                       "Should detect both bullish and bearish trends in reversal")

    def test_insufficient_data_returns_zeros(self):
        """Should return zeros when data is insufficient."""
        indicator = create_supertrend_indicator(atr_period=10)
        tick_data = generate_uptrend_data(length=5)  # Less than atr_period + 1
        values, components = indicator.calculate(tick_data)

        self.assertTrue(np.all(values == 0))
        self.assertEqual(components, {})


class TestSuperTrendIndicatorDirectionFilter(unittest.TestCase):
    """Test direction_filter functionality."""

    def test_both_filter_returns_signed_values(self):
        """With Both filter, should return both positive and negative values."""
        indicator = create_supertrend_indicator(direction_filter="Both")
        tick_data = generate_trend_reversal_data()
        values, _ = indicator.calculate(tick_data)

        has_positive = np.any(values > 0)
        has_negative = np.any(values < 0)
        self.assertTrue(has_positive, "Both filter should include positive values")
        self.assertTrue(has_negative, "Both filter should include negative values")

    def test_bull_filter_only_positive_values(self):
        """With Bull filter, should only return non-negative values."""
        indicator = create_supertrend_indicator(direction_filter="Bull")
        tick_data = generate_trend_reversal_data()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.all(values >= 0),
                       "Bull filter should not return negative values")

    def test_bull_filter_zeros_bearish(self):
        """With Bull filter, bearish trends should be zeroed out."""
        indicator = create_supertrend_indicator(direction_filter="Bull")
        tick_data = generate_downtrend_data()
        values, _ = indicator.calculate(tick_data)

        # In a downtrend with Bull filter, most values should be zero
        valid_values = values[20:]
        zero_count = np.sum(valid_values == 0)
        self.assertGreater(zero_count / len(valid_values), 0.7,
                          "Bull filter should zero out bearish trends")

    def test_bear_filter_only_positive_values(self):
        """With Bear filter, output should always be non-negative (converted from negative)."""
        indicator = create_supertrend_indicator(direction_filter="Bear")
        tick_data = generate_trend_reversal_data()
        values, _ = indicator.calculate(tick_data)

        self.assertTrue(np.all(values >= 0),
                       "Bear filter should always return non-negative values")

    def test_bear_filter_converts_bearish_to_positive(self):
        """With Bear filter, bearish (-1) should become positive (+1)."""
        indicator = create_supertrend_indicator(direction_filter="Bear")
        tick_data = generate_downtrend_data()
        values, _ = indicator.calculate(tick_data)

        # In a downtrend with Bear filter, values should be +1 (converted from -1)
        valid_values = values[20:]
        positive_count = np.sum(valid_values > 0)
        self.assertGreater(positive_count / len(valid_values), 0.7,
                          "Bear filter should convert bearish to positive")

    def test_bear_filter_zeros_bullish(self):
        """With Bear filter, bullish trends should be zeroed out."""
        indicator = create_supertrend_indicator(direction_filter="Bear")
        tick_data = generate_uptrend_data()
        values, _ = indicator.calculate(tick_data)

        # In an uptrend with Bear filter, most values should be zero
        valid_values = values[20:]
        zero_count = np.sum(valid_values == 0)
        self.assertGreater(zero_count / len(valid_values), 0.7,
                          "Bear filter should zero out bullish trends")

    def test_direction_preserved_in_components(self):
        """Original direction should be preserved in components even with filter."""
        indicator = create_supertrend_indicator(direction_filter="Bull")
        tick_data = generate_trend_reversal_data()
        values, components = indicator.calculate(tick_data)

        direction = components["supertrend_direction"]
        # Original direction should have both +1 and -1
        has_positive = np.any(direction > 0)
        has_negative = np.any(direction < 0)
        self.assertTrue(has_positive and has_negative,
                       "Original direction should be preserved in components")


class TestSuperTrendIndicatorParameters(unittest.TestCase):
    """Test parameter specifications."""

    def test_parameter_specs_exist(self):
        """Should have all required parameter specs."""
        specs = SuperTrendIndicator.get_parameter_specs()
        spec_names = [spec.name for spec in specs]

        required = ["atr_period", "multiplier", "direction_filter"]
        for name in required:
            self.assertIn(name, spec_names, f"Missing parameter spec: {name}")

    def test_default_parameters(self):
        """Default parameters should have expected values in specs."""
        specs = SuperTrendIndicator.get_parameter_specs()
        defaults = {spec.name: spec.default_value for spec in specs}

        self.assertEqual(defaults["atr_period"], 10)
        self.assertEqual(defaults["multiplier"], 3.0)
        self.assertEqual(defaults["direction_filter"], "Both")

    def test_indicator_type_is_trend(self):
        """Indicator type should be TREND."""
        from indicator_triggers.indicator_base import IndicatorType
        self.assertEqual(SuperTrendIndicator.get_indicator_type(), IndicatorType.TREND)

    def test_layout_type_is_overlay(self):
        """Layout type should be overlay (on price chart)."""
        self.assertEqual(SuperTrendIndicator.get_layout_type(), "overlay")

    def test_direction_filter_choices(self):
        """direction_filter should have Both, Bull, Bear choices."""
        specs = SuperTrendIndicator.get_parameter_specs()
        filter_spec = next(s for s in specs if s.name == "direction_filter")

        self.assertEqual(filter_spec.choices, ["Both", "Bull", "Bear"])


class TestSuperTrendIndicatorMultiplierEffect(unittest.TestCase):
    """Test ATR multiplier effect on bands."""

    def test_higher_multiplier_wider_bands(self):
        """Higher multiplier should produce wider bands."""
        tick_data = generate_sideways_data()

        indicator_narrow = create_supertrend_indicator(multiplier=2.0)
        indicator_wide = create_supertrend_indicator(multiplier=4.0)

        _, comp_narrow = indicator_narrow.calculate(tick_data)
        _, comp_wide = indicator_wide.calculate(tick_data)

        # Calculate average band width
        narrow_width = np.nanmean(comp_narrow["supertrend_upper"] - comp_narrow["supertrend_lower"])
        wide_width = np.nanmean(comp_wide["supertrend_upper"] - comp_wide["supertrend_lower"])

        self.assertGreater(wide_width, narrow_width,
                          "Higher multiplier should produce wider bands")

    def test_smaller_period_more_responsive(self):
        """Smaller ATR period should make indicator more responsive."""
        tick_data = generate_trend_reversal_data()

        indicator_fast = create_supertrend_indicator(atr_period=5)
        indicator_slow = create_supertrend_indicator(atr_period=15)

        values_fast, _ = indicator_fast.calculate(tick_data)
        values_slow, _ = indicator_slow.calculate(tick_data)

        # Count sign changes (trend flips)
        def count_sign_changes(arr):
            non_zero = arr[arr != 0]
            if len(non_zero) < 2:
                return 0
            signs = np.sign(non_zero)
            return np.sum(signs[1:] != signs[:-1])

        fast_changes = count_sign_changes(values_fast)
        slow_changes = count_sign_changes(values_slow)

        self.assertGreaterEqual(fast_changes, slow_changes,
                               "Faster indicator should have >= sign changes")


class TestSuperTrendIndicatorEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_empty_data(self):
        """Should handle empty data gracefully."""
        indicator = create_supertrend_indicator()
        values, components = indicator.calculate([])

        self.assertEqual(len(values), 0)
        self.assertEqual(components, {})

    def test_constant_price(self):
        """Should handle constant price data."""
        prices = [100.0] * 50
        tick_data = generate_tick_data(prices, volatility=0.01)

        indicator = create_supertrend_indicator()
        values, components = indicator.calculate(tick_data)

        self.assertEqual(len(values), 50)
        # With constant price, direction depends on initial setup

    def test_extreme_volatility(self):
        """Should handle high volatility data."""
        np.random.seed(42)
        prices = [100.0 + np.random.uniform(-20, 20) for _ in range(100)]
        tick_data = generate_tick_data(prices, volatility=5.0)

        indicator = create_supertrend_indicator()
        values, _ = indicator.calculate(tick_data)

        # Should still produce valid binary output
        non_zero = values[values != 0]
        for val in non_zero:
            self.assertIn(val, [1.0, -1.0])


if __name__ == "__main__":
    unittest.main()
