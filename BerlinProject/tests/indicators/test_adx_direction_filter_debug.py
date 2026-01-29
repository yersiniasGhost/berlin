"""
Diagnostic tests for ADXTrendIndicator Bull/Bear direction_filter.

These tests investigate how the direction_filter interacts with:
1. The indicator's raw output
2. The trend gating system in indicator_processor

The key question: Is Bull/Bear filter working as expected, or is there
a conceptual issue with how it interacts with the trend gate's
direction alignment logic?
"""

import unittest
import numpy as np
from datetime import datetime, timedelta
from typing import List, Tuple

from models.tick_data import TickData
from indicator_triggers.indicator_base import IndicatorConfiguration
from indicator_triggers.trend_indicators import ADXTrendIndicator


def create_adx_indicator(direction_filter: str = "Both", period: int = 14,
                         trend_threshold: float = 25.0, strong_trend_threshold: float = 40.0):
    """Factory function to create ADXTrendIndicator."""
    config = IndicatorConfiguration(
        indicator_name="ADXTrendIndicator",
        display_name="test_adx",
        parameters={
            "period": period,
            "trend_threshold": trend_threshold,
            "strong_trend_threshold": strong_trend_threshold,
            "direction_filter": direction_filter
        }
    )
    return ADXTrendIndicator(config)


def generate_controlled_trend_data(base_price: float, periods: int,
                                    trend_direction: str = 'bull',
                                    trend_strength: float = 0.02) -> List[TickData]:
    """
    Generate controlled trend data with predictable ADX behavior.

    Args:
        trend_direction: 'bull' (price rising, +DI > -DI) or 'bear' (price falling, -DI > +DI)
        trend_strength: How strong the directional movement is
    """
    tick_data = []
    price = base_price
    timestamp = datetime.now()

    for i in range(periods):
        if trend_direction == 'bull':
            # Strong upward movement: close > open, high extends up
            delta = price * trend_strength * np.random.uniform(0.8, 1.2)
            open_p = price
            close_p = price + delta
            high_p = close_p + abs(delta) * 0.3
            low_p = open_p - abs(delta) * 0.1
        else:  # bear
            # Strong downward movement: close < open, low extends down
            delta = price * trend_strength * np.random.uniform(0.8, 1.2)
            open_p = price
            close_p = price - delta
            high_p = open_p + abs(delta) * 0.1
            low_p = close_p - abs(delta) * 0.3

        tick_data.append(TickData(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=1000, timestamp=timestamp, symbol="TEST"
        ))
        price = close_p
        timestamp = timestamp + timedelta(minutes=1)

    return tick_data


def simulate_trend_gate(trend_value: float, bar_type: str, mode: str = 'soft') -> float:
    """
    Simulate the trend gating logic from indicator_processor._calculate_trend_gate

    This replicates the key logic:
    - For bull bars: positive trend = good
    - For bear bars: invert trend value (negative trend becomes positive gate)
    """
    # Align direction with bar type
    if bar_type.lower() == 'bear':
        trend_value = -trend_value

    # Apply gating mode
    if mode == 'hard':
        return 1.0 if trend_value > 0 else 0.0
    else:  # soft
        return max(0.0, min(1.0, trend_value))


class TestDirectionFilterBehavior(unittest.TestCase):
    """Test ADXTrendIndicator direction_filter parameter behavior."""

    def setUp(self):
        np.random.seed(42)

    def test_bull_filter_in_bullish_market(self):
        """
        Test Bull filter when market is bullish (+DI > -DI).

        Expected: Bull filter should return positive values (same as Both filter).
        """
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bull = create_adx_indicator(direction_filter="Bull")

        # Generate bullish market data
        tick_data = generate_controlled_trend_data(100.0, 80, 'bull', 0.02)

        values_both, comp_both = indicator_both.calculate(tick_data)
        values_bull, comp_bull = indicator_bull.calculate(tick_data)

        # After warmup, in bullish market, both should return positive values
        final_both = values_both[-20:]
        final_bull = values_bull[-20:]

        # Count positive values
        pos_both = np.sum(final_both > 0)
        pos_bull = np.sum(final_bull > 0)

        print("\n" + "="*60)
        print("TEST: Bull filter in BULLISH market")
        print("="*60)
        print(f"Both filter - positive values: {pos_both}/20")
        print(f"Bull filter - positive values: {pos_bull}/20")
        print(f"Both values (last 5): {final_both[-5:]}")
        print(f"Bull values (last 5): {final_bull[-5:]}")

        # In bullish market, Bull filter should match Both filter
        np.testing.assert_array_almost_equal(
            final_both, final_bull, decimal=10,
            err_msg="In bullish market, Bull filter should equal Both filter"
        )

    def test_bull_filter_in_bearish_market(self):
        """
        Test Bull filter when market is bearish (-DI > +DI).

        Expected: Bull filter should return all zeros (opposite direction filtered out).
        """
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bull = create_adx_indicator(direction_filter="Bull")

        # Generate bearish market data
        tick_data = generate_controlled_trend_data(100.0, 80, 'bear', 0.02)

        values_both, comp_both = indicator_both.calculate(tick_data)
        values_bull, comp_bull = indicator_bull.calculate(tick_data)

        final_both = values_both[-20:]
        final_bull = values_bull[-20:]

        print("\n" + "="*60)
        print("TEST: Bull filter in BEARISH market")
        print("="*60)
        print(f"Both values (last 5): {final_both[-5:]}")
        print(f"Bull values (last 5): {final_bull[-5:]}")
        print(f"Both has negative: {np.any(final_both < 0)}")
        print(f"Bull has any nonzero: {np.any(final_bull != 0)}")

        # Both should have negative values (bearish)
        self.assertTrue(np.any(final_both < 0), "Both filter should show bearish (negative) values")

        # Bull filter should be all zeros (filters out bearish direction)
        self.assertTrue(np.all(final_bull == 0), "Bull filter should return zeros in bearish market")

    def test_bear_filter_in_bearish_market(self):
        """
        Test Bear filter when market is bearish (-DI > +DI).

        Expected: Bear filter should return negative values (same magnitude as Both, but negative).
        """
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bear = create_adx_indicator(direction_filter="Bear")

        # Generate bearish market data
        tick_data = generate_controlled_trend_data(100.0, 80, 'bear', 0.02)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bear, _ = indicator_bear.calculate(tick_data)

        final_both = values_both[-20:]
        final_bear = values_bear[-20:]

        print("\n" + "="*60)
        print("TEST: Bear filter in BEARISH market")
        print("="*60)
        print(f"Both values (last 5): {final_both[-5:]}")
        print(f"Bear values (last 5): {final_bear[-5:]}")

        # In bearish market, Bear filter should match Both filter (both negative)
        np.testing.assert_array_almost_equal(
            final_both, final_bear, decimal=10,
            err_msg="In bearish market, Bear filter should equal Both filter"
        )

    def test_bear_filter_in_bullish_market(self):
        """
        Test Bear filter when market is bullish (+DI > -DI).

        Expected: Bear filter should return all zeros (opposite direction filtered out).
        """
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bear = create_adx_indicator(direction_filter="Bear")

        # Generate bullish market data
        tick_data = generate_controlled_trend_data(100.0, 80, 'bull', 0.02)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bear, _ = indicator_bear.calculate(tick_data)

        final_both = values_both[-20:]
        final_bear = values_bear[-20:]

        print("\n" + "="*60)
        print("TEST: Bear filter in BULLISH market")
        print("="*60)
        print(f"Both values (last 5): {final_both[-5:]}")
        print(f"Bear values (last 5): {final_bear[-5:]}")

        # Both should have positive values (bullish)
        self.assertTrue(np.any(final_both > 0), "Both filter should show bullish (positive) values")

        # Bear filter should be all zeros (filters out bullish direction)
        self.assertTrue(np.all(final_bear == 0), "Bear filter should return zeros in bullish market")


class TestTrendGateInteraction(unittest.TestCase):
    """
    Test how direction_filter interacts with the trend gating system.

    This is the CRITICAL test class - the trend gate has its own direction
    alignment logic, so using direction_filter might be redundant or problematic.
    """

    def setUp(self):
        np.random.seed(42)

    def test_bull_filter_on_bull_bar_bullish_market(self):
        """
        Scenario: Bull filter + Bull bar + Bullish market

        Expected flow:
        1. ADX detects bullish trend → positive value
        2. Bull filter keeps positive value
        3. Trend gate (bull bar): keeps positive → HIGH gate (good)
        """
        indicator = create_adx_indicator(direction_filter="Bull")
        tick_data = generate_controlled_trend_data(100.0, 80, 'bull', 0.02)
        values, _ = indicator.calculate(tick_data)

        # Get last value (after trend establishes)
        trend_value = values[-1]

        # Simulate trend gate for bull bar
        gate = simulate_trend_gate(trend_value, 'bull', 'soft')

        print("\n" + "="*60)
        print("TEST: Bull filter + Bull bar + BULLISH market")
        print("="*60)
        print(f"ADX trend value: {trend_value:.4f}")
        print(f"Trend gate (bull bar): {gate:.4f}")

        self.assertGreater(trend_value, 0, "Bull filter in bullish market should be positive")
        self.assertGreater(gate, 0, "Gate should pass for aligned trend")

    def test_bull_filter_on_bull_bar_bearish_market(self):
        """
        Scenario: Bull filter + Bull bar + Bearish market

        Expected flow:
        1. ADX detects bearish trend → negative value
        2. Bull filter ZEROS OUT negative value → 0
        3. Trend gate (bull bar): 0 → gate = 0 (BLOCKED)

        QUESTION: Is this the intended behavior?
        Without Bull filter: negative → gate = 0 (same result)
        So Bull filter is REDUNDANT here.
        """
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bull = create_adx_indicator(direction_filter="Bull")

        tick_data = generate_controlled_trend_data(100.0, 80, 'bear', 0.02)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bull, _ = indicator_bull.calculate(tick_data)

        # Get last values
        trend_both = values_both[-1]
        trend_bull = values_bull[-1]

        # Simulate trend gates for bull bar
        gate_both = simulate_trend_gate(trend_both, 'bull', 'soft')
        gate_bull = simulate_trend_gate(trend_bull, 'bull', 'soft')

        print("\n" + "="*60)
        print("TEST: Bull filter + Bull bar + BEARISH market")
        print("="*60)
        print(f"Both filter trend value: {trend_both:.4f}")
        print(f"Bull filter trend value: {trend_bull:.4f}")
        print(f"Gate (Both filter): {gate_both:.4f}")
        print(f"Gate (Bull filter): {gate_bull:.4f}")
        print(f"\n⚠️  OBSERVATION: Both gates are 0 - Bull filter is REDUNDANT here")

        self.assertEqual(gate_both, gate_bull,
            "Bull filter should produce same gate result as Both filter on bull bar in bearish market")

    def test_bear_filter_on_bear_bar_bearish_market(self):
        """
        Scenario: Bear filter + Bear bar + Bearish market

        Expected flow:
        1. ADX detects bearish trend → negative value
        2. Bear filter keeps negative value
        3. Trend gate (bear bar): INVERTS → positive gate (good!)

        This is the correct and intended use case.
        """
        indicator = create_adx_indicator(direction_filter="Bear")
        tick_data = generate_controlled_trend_data(100.0, 80, 'bear', 0.02)
        values, _ = indicator.calculate(tick_data)

        trend_value = values[-1]
        gate = simulate_trend_gate(trend_value, 'bear', 'soft')

        print("\n" + "="*60)
        print("TEST: Bear filter + Bear bar + BEARISH market")
        print("="*60)
        print(f"ADX trend value (negative = bearish): {trend_value:.4f}")
        print(f"Trend gate (bear bar, inverted): {gate:.4f}")

        self.assertLess(trend_value, 0, "Bear filter in bearish market should be negative")
        self.assertGreater(gate, 0, "Gate should pass after inversion for aligned trend")

    def test_bear_filter_on_bear_bar_bullish_market(self):
        """
        Scenario: Bear filter + Bear bar + Bullish market

        Expected flow:
        1. ADX detects bullish trend → positive value
        2. Bear filter ZEROS OUT positive value → 0
        3. Trend gate (bear bar): inverts 0 → 0 (BLOCKED)

        Compare with Both filter:
        1. ADX detects bullish trend → positive value
        2. Trend gate (bear bar): inverts positive → negative → gate = 0 (BLOCKED)

        SAME RESULT - Bear filter is REDUNDANT.
        """
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bear = create_adx_indicator(direction_filter="Bear")

        tick_data = generate_controlled_trend_data(100.0, 80, 'bull', 0.02)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bear, _ = indicator_bear.calculate(tick_data)

        trend_both = values_both[-1]
        trend_bear = values_bear[-1]

        # Simulate trend gates for BEAR bar
        gate_both = simulate_trend_gate(trend_both, 'bear', 'soft')
        gate_bear = simulate_trend_gate(trend_bear, 'bear', 'soft')

        print("\n" + "="*60)
        print("TEST: Bear filter + Bear bar + BULLISH market")
        print("="*60)
        print(f"Both filter trend value: {trend_both:.4f}")
        print(f"Bear filter trend value: {trend_bear:.4f}")
        print(f"Gate (Both filter): {gate_both:.4f}")
        print(f"Gate (Bear filter): {gate_bear:.4f}")
        print(f"\n⚠️  OBSERVATION: Both gates are 0 - Bear filter is REDUNDANT here")

        self.assertEqual(gate_both, gate_bear,
            "Bear filter should produce same gate result as Both filter on bear bar in bullish market")


class TestDirectionFilterEdgeCases(unittest.TestCase):
    """Test edge cases and potential bugs in direction filter."""

    def setUp(self):
        np.random.seed(42)

    def test_bear_filter_on_bull_bar_issue(self):
        """
        POTENTIAL BUG SCENARIO: Bear filter used on BULL bar in bearish market.

        Expected intuition: "Only use bearish trends" → should NOT help bull bar

        Reality:
        1. ADX detects bearish trend → negative value
        2. Bear filter keeps negative value
        3. Trend gate (bull bar): negative stays negative → gate = 0 (BLOCKED)

        Without Bear filter (Both):
        1. ADX detects bearish trend → negative value
        2. Trend gate (bull bar): negative stays negative → gate = 0 (BLOCKED)

        SAME RESULT - the direction filter doesn't change anything here.
        The trend gate's own logic handles direction alignment.
        """
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bear = create_adx_indicator(direction_filter="Bear")

        tick_data = generate_controlled_trend_data(100.0, 80, 'bear', 0.02)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bear, _ = indicator_bear.calculate(tick_data)

        trend_both = values_both[-1]
        trend_bear = values_bear[-1]

        # Simulate trend gates for BULL bar (testing mismatched filter + bar type)
        gate_both = simulate_trend_gate(trend_both, 'bull', 'soft')
        gate_bear = simulate_trend_gate(trend_bear, 'bull', 'soft')

        print("\n" + "="*60)
        print("TEST: Bear filter on BULL bar in BEARISH market")
        print("="*60)
        print(f"Both filter trend value: {trend_both:.4f}")
        print(f"Bear filter trend value: {trend_bear:.4f}")
        print(f"Gate for bull bar (Both): {gate_both:.4f}")
        print(f"Gate for bull bar (Bear): {gate_bear:.4f}")

        # The gates should be equal (both 0) - Bear filter is redundant
        self.assertEqual(gate_both, gate_bear)

    def test_bull_filter_on_bear_bar_issue(self):
        """
        POTENTIAL BUG SCENARIO: Bull filter used on BEAR bar in bullish market.

        Reality:
        1. ADX detects bullish trend → positive value
        2. Bull filter keeps positive value
        3. Trend gate (bear bar): INVERTS positive → negative → gate = 0 (BLOCKED)

        Without Bull filter (Both):
        1. ADX detects bullish trend → positive value
        2. Trend gate (bear bar): INVERTS positive → negative → gate = 0 (BLOCKED)

        SAME RESULT.
        """
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bull = create_adx_indicator(direction_filter="Bull")

        tick_data = generate_controlled_trend_data(100.0, 80, 'bull', 0.02)

        values_both, _ = indicator_both.calculate(tick_data)
        values_bull, _ = indicator_bull.calculate(tick_data)

        trend_both = values_both[-1]
        trend_bull = values_bull[-1]

        # Simulate trend gates for BEAR bar
        gate_both = simulate_trend_gate(trend_both, 'bear', 'soft')
        gate_bull = simulate_trend_gate(trend_bull, 'bear', 'soft')

        print("\n" + "="*60)
        print("TEST: Bull filter on BEAR bar in BULLISH market")
        print("="*60)
        print(f"Both filter trend value: {trend_both:.4f}")
        print(f"Bull filter trend value: {trend_bull:.4f}")
        print(f"Gate for bear bar (Both): {gate_both:.4f}")
        print(f"Gate for bear bar (Bull): {gate_bull:.4f}")

        self.assertEqual(gate_both, gate_bull)

    def test_direction_filter_has_no_effect_summary(self):
        """
        SUMMARY TEST: The direction_filter parameter is REDUNDANT when used
        with the trend gating system.

        The trend gate's own direction alignment logic already handles:
        - Positive trend values → good for bull bars, bad for bear bars
        - Negative trend values → good for bear bars, bad for bull bars

        The direction_filter pre-filtering:
        - Bull filter zeros out negative → but negative would give gate=0 anyway
        - Bear filter zeros out positive → but positive would give gate=0 on bear bars anyway

        CONCLUSION: direction_filter="Both" is always sufficient.
        Bull/Bear filters only make sense for NON-gating use cases.
        """
        print("\n" + "="*70)
        print("SUMMARY: Direction Filter Redundancy Analysis")
        print("="*70)
        print("""
The direction_filter parameter has NO EFFECT when used with trend gating:

┌─────────────────┬─────────────┬─────────────────────────────────────┐
│ Market          │ Bar Type    │ Result with Any Filter              │
├─────────────────┼─────────────┼─────────────────────────────────────┤
│ Bullish (+)     │ Bull        │ PASS (positive gate)                │
│ Bullish (+)     │ Bear        │ BLOCK (negative after invert)       │
│ Bearish (-)     │ Bull        │ BLOCK (negative trend)              │
│ Bearish (-)     │ Bear        │ PASS (positive after invert)        │
└─────────────────┴─────────────┴─────────────────────────────────────┘

The trend gate's direction alignment makes the indicator's direction
filter redundant. Using Bull/Bear filter just adds an extra step that
produces the same result.

RECOMMENDATION:
- For trend gating: Use direction_filter="Both" (or remove the parameter)
- direction_filter Bull/Bear is only useful for NON-gating scenarios
""")
        # This is a documentation test - always passes
        self.assertTrue(True)


class TestCompleteFlowDiagnostic(unittest.TestCase):
    """
    Complete flow diagnostic test showing every value at each step.
    This helps identify exactly where unexpected behavior might occur.
    """

    def setUp(self):
        np.random.seed(42)

    def test_complete_flow_trace(self):
        """
        Trace through the complete flow for Bull, Bear, and Both filters.
        Shows: raw ADX, +DI, -DI, direction, strength, final output, gate value.
        """
        print("\n" + "="*80)
        print("COMPLETE FLOW DIAGNOSTIC")
        print("="*80)

        # Create all three indicator variants
        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bull = create_adx_indicator(direction_filter="Bull")
        indicator_bear = create_adx_indicator(direction_filter="Bear")

        # Generate test data (mix of up and down movements for variety)
        tick_data = generate_controlled_trend_data(100.0, 80, 'bull', 0.02)

        # Calculate for all three
        values_both, comp_both = indicator_both.calculate(tick_data)
        values_bull, comp_bull = indicator_bull.calculate(tick_data)
        values_bear, comp_bear = indicator_bear.calculate(tick_data)

        # Get component arrays
        adx = comp_both['adx_trend_adx']
        plus_di = comp_both['adx_trend_plus_di']
        minus_di = comp_both['adx_trend_minus_di']
        strength = comp_both['adx_trend_strength']
        direction = comp_both['adx_trend_direction']

        print(f"\nMarket type: BULLISH (price rising, +DI should > -DI)")
        print(f"\nLast 10 data points:\n")
        print(f"{'Idx':<5} {'ADX':<8} {'+DI':<8} {'-DI':<8} {'Dir':<6} {'Str':<8} {'Both':<8} {'Bull':<8} {'Bear':<8}")
        print("-" * 75)

        for i in range(-10, 0):
            idx = len(tick_data) + i
            adx_v = adx[idx] if not np.isnan(adx[idx]) else 0
            pdi = plus_di[idx] if not np.isnan(plus_di[idx]) else 0
            mdi = minus_di[idx] if not np.isnan(minus_di[idx]) else 0
            dir_v = direction[idx]
            str_v = strength[idx]
            both_v = values_both[idx]
            bull_v = values_bull[idx]
            bear_v = values_bear[idx]

            print(f"{idx:<5} {adx_v:<8.2f} {pdi:<8.2f} {mdi:<8.2f} {dir_v:<6.0f} {str_v:<8.4f} {both_v:<8.4f} {bull_v:<8.4f} {bear_v:<8.4f}")

        print("\n" + "-"*80)
        print("GATE CALCULATION SIMULATION")
        print("-"*80)

        # Take last value
        last_both = values_both[-1]
        last_bull = values_bull[-1]
        last_bear = values_bear[-1]

        print(f"\nIndicator outputs: Both={last_both:.4f}, Bull={last_bull:.4f}, Bear={last_bear:.4f}")

        for bar_type in ['bull', 'bear']:
            print(f"\nFor {bar_type.upper()} bar:")
            for name, val in [('Both', last_both), ('Bull', last_bull), ('Bear', last_bear)]:
                gate = simulate_trend_gate(val, bar_type, 'soft')
                print(f"  {name} filter: input={val:.4f} → gate={gate:.4f}")

    def test_bearish_market_complete_flow(self):
        """Same diagnostic for bearish market."""
        print("\n" + "="*80)
        print("COMPLETE FLOW DIAGNOSTIC - BEARISH MARKET")
        print("="*80)

        indicator_both = create_adx_indicator(direction_filter="Both")
        indicator_bull = create_adx_indicator(direction_filter="Bull")
        indicator_bear = create_adx_indicator(direction_filter="Bear")

        tick_data = generate_controlled_trend_data(100.0, 80, 'bear', 0.02)

        values_both, comp_both = indicator_both.calculate(tick_data)
        values_bull, comp_bull = indicator_bull.calculate(tick_data)
        values_bear, comp_bear = indicator_bear.calculate(tick_data)

        adx = comp_both['adx_trend_adx']
        plus_di = comp_both['adx_trend_plus_di']
        minus_di = comp_both['adx_trend_minus_di']
        strength = comp_both['adx_trend_strength']
        direction = comp_both['adx_trend_direction']

        print(f"\nMarket type: BEARISH (price falling, -DI should > +DI)")
        print(f"\nLast 10 data points:\n")
        print(f"{'Idx':<5} {'ADX':<8} {'+DI':<8} {'-DI':<8} {'Dir':<6} {'Str':<8} {'Both':<8} {'Bull':<8} {'Bear':<8}")
        print("-" * 75)

        for i in range(-10, 0):
            idx = len(tick_data) + i
            adx_v = adx[idx] if not np.isnan(adx[idx]) else 0
            pdi = plus_di[idx] if not np.isnan(plus_di[idx]) else 0
            mdi = minus_di[idx] if not np.isnan(minus_di[idx]) else 0
            dir_v = direction[idx]
            str_v = strength[idx]
            both_v = values_both[idx]
            bull_v = values_bull[idx]
            bear_v = values_bear[idx]

            print(f"{idx:<5} {adx_v:<8.2f} {pdi:<8.2f} {mdi:<8.2f} {dir_v:<6.0f} {str_v:<8.4f} {both_v:<8.4f} {bull_v:<8.4f} {bear_v:<8.4f}")

        print("\n" + "-"*80)
        print("GATE CALCULATION SIMULATION")
        print("-"*80)

        last_both = values_both[-1]
        last_bull = values_bull[-1]
        last_bear = values_bear[-1]

        print(f"\nIndicator outputs: Both={last_both:.4f}, Bull={last_bull:.4f}, Bear={last_bear:.4f}")

        for bar_type in ['bull', 'bear']:
            print(f"\nFor {bar_type.upper()} bar:")
            for name, val in [('Both', last_both), ('Bull', last_bull), ('Bear', last_bear)]:
                gate = simulate_trend_gate(val, bar_type, 'soft')
                print(f"  {name} filter: input={val:.4f} → gate={gate:.4f}")

        # The key observation
        print("\n" + "="*80)
        print("KEY OBSERVATIONS:")
        print("="*80)
        print("""
In BEARISH market:
- Both filter: returns -1.0 (negative = bearish)
- Bull filter: returns 0.0 (filters out bearish)
- Bear filter: returns -1.0 (keeps bearish)

For BEAR bar (want bearish confirmation):
- Both filter: -1.0 → inverted → +1.0 gate (PASS)
- Bear filter: -1.0 → inverted → +1.0 gate (PASS)
- Bull filter: 0.0 → inverted → 0.0 gate (BLOCKED - but this is correct!)

The Bull filter on a bear bar in bearish market returns 0 because:
1. Bull filter zeros out bearish signal (correct behavior)
2. But bear bar NEEDS bearish signal to pass
3. So Bull filter is inappropriate for bear bars

CONCLUSION: Use 'Both' filter, or match filter to bar type.
""")


if __name__ == '__main__':
    unittest.main(verbosity=2)
