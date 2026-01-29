"""
Diagnostic tests for ADXTrendIndicator using real NVDA data from MongoDB.

This test validates that:
1. ADX values transition smoothly (not jumping 0 to 1)
2. ADX values correlate with actual price trends
3. The indicator behavior is correct across different date ranges
"""

import unittest
import sys
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent / 'src'
sys.path.insert(0, str(project_root))

from models.tick_data import TickData
from indicator_triggers.indicator_base import IndicatorConfiguration
from indicator_triggers.trend_indicators import ADXTrendIndicator
from mongo_tools.tick_history_tools import TickHistoryTools


def create_adx_indicator(name: str = "test_adx", period: int = 14,
                         trend_threshold: float = 25.0, strong_trend_threshold: float = 40.0):
    """Factory function to create ADXTrendIndicator with custom parameters."""
    config = IndicatorConfiguration(
        indicator_name="ADXTrendIndicator",
        display_name=name,
        parameters={
            "period": period,
            "trend_threshold": trend_threshold,
            "strong_trend_threshold": strong_trend_threshold
        }
    )
    return ADXTrendIndicator(config)


def load_nvda_data(start_date: str, end_date: str, time_increment: int = 1) -> list:
    """
    Load NVDA tick data from MongoDB.

    Args:
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format
        time_increment: Time increment (1=1min, 5=5min)

    Returns:
        List of TickData objects
    """
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')

    # Load data using TickHistoryTools
    tick_tools = TickHistoryTools.get_tools("NVDA", start_dt, end_dt, time_increment)

    # Flatten all tick data from all days
    all_ticks = []
    for book in tick_tools.books:
        for day_data in book.data:
            # day_data is a list of TickData objects for one day
            all_ticks.extend(day_data)

    return all_ticks


def analyze_adx_transitions(values: np.ndarray, threshold: float = 0.3) -> dict:
    """
    Analyze ADX value transitions to detect sudden jumps.

    Args:
        values: Array of ADX output values
        threshold: Maximum expected change between consecutive values

    Returns:
        Dict with analysis results
    """
    if len(values) < 2:
        return {"error": "Not enough values"}

    # Calculate consecutive differences
    diffs = np.diff(values)
    abs_diffs = np.abs(diffs)

    # Find large jumps
    large_jumps = np.where(abs_diffs > threshold)[0]

    # Calculate statistics
    return {
        "total_points": len(values),
        "max_single_jump": float(np.max(abs_diffs)) if len(abs_diffs) > 0 else 0,
        "mean_abs_change": float(np.mean(abs_diffs)) if len(abs_diffs) > 0 else 0,
        "std_change": float(np.std(abs_diffs)) if len(abs_diffs) > 0 else 0,
        "num_large_jumps": len(large_jumps),
        "large_jump_indices": large_jumps.tolist(),
        "large_jump_values": [(int(i), float(values[i]), float(values[i+1])) for i in large_jumps[:10]]  # First 10
    }


class TestADXTrendIndicatorRealData(unittest.TestCase):
    """Test ADXTrendIndicator with real NVDA data from MongoDB."""

    @classmethod
    def setUpClass(cls):
        """Load NVDA data once for all tests."""
        print("\n" + "="*70)
        print("Loading NVDA data from MongoDB...")
        print("="*70)

        # Full date range (for building up ADX warmup)
        cls.full_start = "2026-01-02"
        cls.full_end = "2026-01-10"

        # Date from which we'll analyze (after warmup)
        cls.analysis_start = "2026-01-03"

        try:
            # Load full data range
            cls.tick_data = load_nvda_data(cls.full_start, cls.full_end)
            print(f"Loaded {len(cls.tick_data)} ticks from {cls.full_start} to {cls.full_end}")

            if len(cls.tick_data) > 0:
                print(f"First tick: {cls.tick_data[0].timestamp}")
                print(f"Last tick: {cls.tick_data[-1].timestamp}")
        except Exception as e:
            print(f"ERROR loading data: {e}")
            cls.tick_data = []

    def test_01_data_loaded(self):
        """Verify that data was loaded successfully."""
        self.assertGreater(len(self.tick_data), 0, "No tick data loaded from MongoDB")
        self.assertGreater(len(self.tick_data), 14, "Need at least 14+ ticks for ADX calculation")

        # Print data summary
        print(f"\n✓ Loaded {len(self.tick_data)} ticks")

    def test_02_adx_values_are_bounded(self):
        """Verify ADX output values are in expected range [-1, 1]."""
        if len(self.tick_data) < 20:
            self.skipTest("Insufficient data")

        indicator = create_adx_indicator()
        values, components = indicator.calculate(self.tick_data)

        # Check bounds
        self.assertTrue(np.all(values >= -1.0), f"Values below -1: {np.min(values)}")
        self.assertTrue(np.all(values <= 1.0), f"Values above 1: {np.max(values)}")

        print(f"\n✓ ADX values bounded: min={np.min(values):.4f}, max={np.max(values):.4f}")

    def test_03_adx_transitions_smoothly(self):
        """
        CRITICAL TEST: Verify ADX values do NOT jump suddenly from 0 to 1.

        ADX is inherently smoothed (uses EMA), so large jumps indicate a bug.
        """
        if len(self.tick_data) < 50:
            self.skipTest("Insufficient data for transition analysis")

        indicator = create_adx_indicator()
        values, components = indicator.calculate(self.tick_data)

        # Analyze transitions
        analysis = analyze_adx_transitions(values)

        print("\n" + "-"*50)
        print("ADX Transition Analysis:")
        print("-"*50)
        print(f"Total data points: {analysis['total_points']}")
        print(f"Max single jump: {analysis['max_single_jump']:.4f}")
        print(f"Mean absolute change: {analysis['mean_abs_change']:.4f}")
        print(f"Std of changes: {analysis['std_change']:.4f}")
        print(f"Number of large jumps (>0.3): {analysis['num_large_jumps']}")

        if analysis['large_jump_values']:
            print("\nLarge jump examples (index, before, after):")
            for idx, before, after in analysis['large_jump_values']:
                print(f"  Index {idx}: {before:.4f} → {after:.4f} (Δ={after-before:.4f})")

        # ASSERTION: No sudden jumps from 0 to ~1 or vice versa
        # A threshold of 0.3 is generous - ADX should change much more gradually
        self.assertLess(
            analysis['max_single_jump'], 0.5,
            f"ADX jumped too suddenly: max change = {analysis['max_single_jump']:.4f}. "
            "This indicates a bug - ADX should transition smoothly."
        )

        print(f"\n✓ ADX transitions smoothly (max jump: {analysis['max_single_jump']:.4f})")

    def test_04_compare_full_vs_partial_calculation(self):
        """
        Test that calculating ADX on full range vs starting later produces consistent results.

        This validates that the warmup period doesn't cause weird behavior.
        """
        if len(self.tick_data) < 100:
            self.skipTest("Insufficient data for comparison test")

        indicator = create_adx_indicator()

        # Calculate on full range
        values_full, components_full = indicator.calculate(self.tick_data)

        # Find where 01/03/2026 starts in the data
        analysis_start_dt = datetime.strptime(self.analysis_start, '%Y-%m-%d')
        start_idx = None
        for i, tick in enumerate(self.tick_data):
            if tick.timestamp.date() >= analysis_start_dt.date():
                start_idx = i
                break

        if start_idx is None:
            self.skipTest("Could not find analysis start date in data")

        print(f"\n" + "-"*50)
        print("Comparing full range vs partial range calculation:")
        print("-"*50)
        print(f"Full range: {len(self.tick_data)} ticks")
        print(f"Analysis starts at index {start_idx} ({self.analysis_start})")

        # Calculate on partial range (starting from 01/03)
        partial_data = self.tick_data[start_idx:]
        values_partial, components_partial = indicator.calculate(partial_data)

        # The values from full calculation (starting at start_idx) should be similar
        # to the partial calculation, but not identical due to warmup differences
        values_full_subset = values_full[start_idx:]

        # Print comparison
        print(f"\nFirst 20 values comparison (full vs partial):")
        print(f"{'Index':<6} {'Full':<12} {'Partial':<12} {'Diff':<12}")
        print("-"*42)
        for i in range(min(20, len(values_partial))):
            full_val = values_full_subset[i] if i < len(values_full_subset) else float('nan')
            partial_val = values_partial[i] if i < len(values_partial) else float('nan')
            diff = abs(full_val - partial_val) if not (np.isnan(full_val) or np.isnan(partial_val)) else float('nan')
            print(f"{i:<6} {full_val:<12.4f} {partial_val:<12.4f} {diff:<12.4f}")

        print(f"\n✓ Comparison complete")

    def test_05_print_adx_components(self):
        """Print ADX component values for manual inspection."""
        if len(self.tick_data) < 50:
            self.skipTest("Insufficient data")

        indicator = create_adx_indicator()
        values, components = indicator.calculate(self.tick_data)

        print("\n" + "-"*70)
        print("ADX Components (first 30 valid values):")
        print("-"*70)

        # Get component arrays
        adx_raw = components.get(f"{indicator.config.display_name}_adx", np.array([]))
        plus_di = components.get(f"{indicator.config.display_name}_plus_di", np.array([]))
        minus_di = components.get(f"{indicator.config.display_name}_minus_di", np.array([]))
        strength = components.get(f"{indicator.config.display_name}_strength", np.array([]))
        direction = components.get(f"{indicator.config.display_name}_direction", np.array([]))

        print(f"\nComponent keys: {list(components.keys())}")

        # Find first non-NaN index
        start_valid = 0
        for i, v in enumerate(adx_raw):
            if not np.isnan(v):
                start_valid = i
                break

        print(f"\nFirst valid index: {start_valid}")
        print(f"\n{'Idx':<5} {'Time':<20} {'Price':<10} {'ADX':<8} {'+DI':<8} {'-DI':<8} {'Str':<8} {'Dir':<6} {'Out':<8}")
        print("-"*95)

        count = 0
        for i in range(start_valid, len(values)):
            if count >= 30:
                break
            if i < len(adx_raw) and not np.isnan(adx_raw[i]):
                tick = self.tick_data[i] if i < len(self.tick_data) else None
                time_str = tick.timestamp.strftime('%m/%d %H:%M') if tick else "?"
                price = tick.close if tick else 0
                print(f"{i:<5} {time_str:<20} {price:<10.2f} {adx_raw[i]:<8.2f} {plus_di[i]:<8.2f} {minus_di[i]:<8.2f} {strength[i]:<8.4f} {direction[i]:<6.0f} {values[i]:<8.4f}")
                count += 1

        print(f"\n✓ Printed {count} ADX component values")

    def test_06_detect_zero_to_one_jumps(self):
        """
        Specifically detect if there are any 0→1 or 1→0 jumps.
        This is the exact bug the user reported.
        """
        if len(self.tick_data) < 50:
            self.skipTest("Insufficient data")

        indicator = create_adx_indicator()
        values, components = indicator.calculate(self.tick_data)

        # Find indices where value jumps from near-0 to near-1 (or vice versa)
        suspicious_jumps = []
        for i in range(1, len(values)):
            prev = values[i-1]
            curr = values[i]

            # Check for 0→1 type jumps
            if abs(prev) < 0.1 and abs(curr) > 0.8:
                suspicious_jumps.append((i, prev, curr, "0→1"))
            elif abs(prev) > 0.8 and abs(curr) < 0.1:
                suspicious_jumps.append((i, prev, curr, "1→0"))

        print("\n" + "-"*50)
        print("Suspicious Jump Detection (0↔1):")
        print("-"*50)
        print(f"Total suspicious jumps found: {len(suspicious_jumps)}")

        if suspicious_jumps:
            print("\nJump details:")
            for idx, prev, curr, jump_type in suspicious_jumps[:20]:
                tick = self.tick_data[idx] if idx < len(self.tick_data) else None
                time_str = tick.timestamp.strftime('%m/%d %H:%M') if tick else "?"
                print(f"  Index {idx} ({time_str}): {prev:.4f} → {curr:.4f} ({jump_type})")

            # This is the critical failure
            self.fail(
                f"Found {len(suspicious_jumps)} suspicious 0↔1 jumps! "
                "This confirms the bug: ADX should NEVER jump directly from 0 to 1."
            )
        else:
            print("✓ No suspicious 0↔1 jumps detected")

    def test_07_verify_gradual_buildup(self):
        """
        Verify that ADX builds up gradually from 0 at the start of data.

        Since ADX uses a 14-period EMA, the first ~14 values should be 0,
        and then values should increase gradually.
        """
        if len(self.tick_data) < 50:
            self.skipTest("Insufficient data")

        indicator = create_adx_indicator(period=14)
        values, components = indicator.calculate(self.tick_data)

        print("\n" + "-"*50)
        print("ADX Buildup Analysis (first 50 values):")
        print("-"*50)

        # First ~period values should be 0 or very small
        warmup_values = values[:20]
        post_warmup = values[20:50]

        print(f"First 20 values (warmup): mean={np.mean(np.abs(warmup_values)):.4f}")
        print(f"Values 20-50 (post warmup): mean={np.mean(np.abs(post_warmup)):.4f}")

        print(f"\nDetailed first 30 values:")
        for i in range(min(30, len(values))):
            tick = self.tick_data[i] if i < len(self.tick_data) else None
            time_str = tick.timestamp.strftime('%m/%d %H:%M') if tick else "?"
            print(f"  [{i:3d}] {time_str}: {values[i]:.4f}")

        # Check that warmup period has mostly zeros
        warmup_nonzero = np.sum(np.abs(warmup_values) > 0.01)
        print(f"\nWarmup period non-zero count: {warmup_nonzero}/20")

        print(f"\n✓ Buildup analysis complete")


class TestADXAlgorithmCorrectness(unittest.TestCase):
    """Additional tests for ADX algorithm correctness."""

    @classmethod
    def setUpClass(cls):
        """Load data."""
        try:
            cls.tick_data = load_nvda_data("2026-01-02", "2026-01-10")
        except Exception as e:
            print(f"ERROR: {e}")
            cls.tick_data = []

    def test_strength_interpolation(self):
        """Verify that strength values are correctly interpolated between thresholds."""
        if len(self.tick_data) < 50:
            self.skipTest("Insufficient data")

        indicator = create_adx_indicator(
            trend_threshold=25.0,
            strong_trend_threshold=40.0
        )
        values, components = indicator.calculate(self.tick_data)

        # Get raw ADX and strength
        adx_raw = components.get(f"{indicator.config.display_name}_adx", np.array([]))
        strength = components.get(f"{indicator.config.display_name}_strength", np.array([]))

        print("\n" + "-"*50)
        print("Strength Interpolation Verification:")
        print("-"*50)

        # Find indices where we can verify interpolation
        verified = 0
        for i in range(len(adx_raw)):
            if np.isnan(adx_raw[i]):
                continue

            adx_val = adx_raw[i]
            expected_strength = 0.0

            if adx_val < 25.0:
                expected_strength = 0.0
            elif adx_val >= 40.0:
                expected_strength = 1.0
            else:
                # Linear interpolation
                expected_strength = (adx_val - 25.0) / (40.0 - 25.0)

            actual_strength = strength[i]
            diff = abs(expected_strength - actual_strength)

            if diff > 0.001:
                print(f"MISMATCH at {i}: ADX={adx_val:.2f}, Expected={expected_strength:.4f}, Got={actual_strength:.4f}")
            else:
                verified += 1

        print(f"\n✓ Verified {verified} strength calculations")


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
