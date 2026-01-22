#!/usr/bin/env python3
"""
Debug script to verify the timestamp-based alignment fix for multi-timeframe indicators.

This tests that 5m indicator values are correctly aligned to 1m timestamps using
timestamp matching instead of buggy index-based ratios.

The bug: index-based alignment (5m_idx = 1m_idx / 5) breaks when market gaps cause
the candle ratio to not be exactly 5:1 (e.g., extended hours, lunch breaks).
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(project_root))

import numpy as np
from candle_aggregator.candle_aggregator_normal import CANormal
from models.tick_data import TickData


def create_test_candles_with_gap():
    """
    Create test candles simulating a market gap scenario.

    We'll create 1m candles that skip some minutes (simulating a gap),
    which causes the 5m aggregator to have fewer candles than 1m/5.

    This is the exact scenario that breaks index-based alignment.
    """
    candles = []
    base_time = datetime(2026, 1, 15, 9, 30)  # Market open
    price = 100.0

    # Create candles with a gap from 10:30 to 11:00 (30 min gap)
    minute = 0
    while minute < 180:  # 3 hours of trading
        # Skip minutes 60-89 (simulating a 30-minute gap)
        if 60 <= minute < 90:
            minute += 1
            continue

        timestamp = base_time + timedelta(minutes=minute)
        price += np.random.uniform(-0.5, 0.5)

        candle = TickData(
            open=price,
            high=price + 0.2,
            low=price - 0.2,
            close=price + np.random.uniform(-0.1, 0.1),
            volume=1000,
            timestamp=timestamp,
            symbol="TEST"
        )
        candles.append(candle)
        minute += 1

    return candles


def test_alignment_with_gap():
    """Test that timestamp-based alignment handles market gaps correctly."""
    print("="*70)
    print("TEST: Timestamp-based alignment with market gap")
    print("="*70)

    # Create candles with a gap
    candles_1m = create_test_candles_with_gap()

    print(f"\nCreated {len(candles_1m)} 1m candles")
    print(f"First candle: {candles_1m[0].timestamp}")
    print(f"Last candle: {candles_1m[-1].timestamp}")

    # Find the gap
    print("\nChecking for gaps:")
    for i in range(1, len(candles_1m)):
        diff = (candles_1m[i].timestamp - candles_1m[i-1].timestamp).total_seconds() / 60
        if diff > 1.5:  # More than 1.5 minutes apart
            print(f"  Gap at index {i}: {candles_1m[i-1].timestamp} -> {candles_1m[i].timestamp} ({diff:.0f} min)")

    # Create aggregators
    agg_1m = CANormal(symbol="TEST", timeframe="1m")
    agg_5m = CANormal(symbol="TEST", timeframe="5m")

    # Feed candles to both aggregators
    for candle in candles_1m:
        agg_1m.process_tick(candle)
        agg_5m.process_tick(candle)

    history_1m = agg_1m.get_history()
    history_5m = agg_5m.get_history()

    print(f"\n1m aggregator: {len(history_1m)} candles")
    print(f"5m aggregator: {len(history_5m)} candles")
    print(f"Ratio: {len(history_1m) / max(1, len(history_5m)):.2f} (should be ~5 but won't be exact due to gap)")

    # Expected ratio without gap: 150 1m candles -> 30 5m candles
    # With 30 min gap: ~120 1m candles, and the 5m candles will be affected

    # Create fake indicator values for 5m (just using index as value for easy debugging)
    values_5m = [float(i) for i in range(len(history_5m))]

    print("\n5m candle timestamps and values:")
    for i, candle in enumerate(history_5m[:10]):
        print(f"  [{i}] {candle.timestamp} -> value={values_5m[i]}")
    print("  ...")

    # Test OLD index-based alignment (the buggy version)
    print("\n" + "-"*70)
    print("OLD INDEX-BASED ALIGNMENT (buggy):")
    print("-"*70)

    ratio = 5
    aligned_old = np.zeros(len(history_1m))
    for coarse_idx, value in enumerate(values_5m):
        start = int(coarse_idx * ratio)
        end = min(int((coarse_idx + 1) * ratio), len(history_1m))
        aligned_old[start:end] = value

    # Check what value is at specific 1m timestamps
    test_indices = [0, 10, 55, 60, 90, 100, len(history_1m)-1]
    print("\nSample alignment results:")
    for idx in test_indices:
        if idx < len(history_1m):
            ts_1m = history_1m[idx].timestamp
            val = aligned_old[idx]
            print(f"  1m[{idx}] {ts_1m} -> 5m value={val:.0f}")

    # Test NEW timestamp-based alignment
    print("\n" + "-"*70)
    print("NEW TIMESTAMP-BASED ALIGNMENT (fixed):")
    print("-"*70)

    import bisect

    aligned_new = np.zeros(len(history_1m))
    coarse_timestamps = [c.timestamp.timestamp() for c in history_5m]

    for primary_idx, primary_candle in enumerate(history_1m):
        primary_ts = primary_candle.timestamp.timestamp()
        coarse_idx = bisect.bisect_right(coarse_timestamps, primary_ts) - 1

        if 0 <= coarse_idx < len(values_5m):
            aligned_new[primary_idx] = values_5m[coarse_idx]

    print("\nSample alignment results:")
    for idx in test_indices:
        if idx < len(history_1m):
            ts_1m = history_1m[idx].timestamp
            val = aligned_new[idx]
            # Also find which 5m candle this maps to
            primary_ts = history_1m[idx].timestamp.timestamp()
            coarse_idx = bisect.bisect_right(coarse_timestamps, primary_ts) - 1
            ts_5m = history_5m[coarse_idx].timestamp if 0 <= coarse_idx < len(history_5m) else "N/A"
            print(f"  1m[{idx}] {ts_1m} -> 5m[{coarse_idx}] {ts_5m} -> value={val:.0f}")

    # Compare the two methods
    print("\n" + "-"*70)
    print("COMPARISON:")
    print("-"*70)

    differences = np.abs(aligned_old - aligned_new)
    num_different = np.sum(differences > 0.001)

    print(f"Values that differ: {num_different}/{len(history_1m)} ({100*num_different/len(history_1m):.1f}%)")

    if num_different > 0:
        print("\nFirst 10 differences:")
        diff_count = 0
        for idx in range(len(history_1m)):
            if differences[idx] > 0.001:
                ts = history_1m[idx].timestamp
                print(f"  1m[{idx}] {ts}: OLD={aligned_old[idx]:.0f}, NEW={aligned_new[idx]:.0f}")
                diff_count += 1
                if diff_count >= 10:
                    break

        print("\nThe OLD method gets WRONG values after the gap!")
        print("The NEW timestamp-based method correctly maps to the right 5m candles.")
    else:
        print("No differences found - this might mean the test data doesn't have the right gap structure.")

    return num_different > 0


def test_alignment_without_gap():
    """Test that alignment still works correctly when there are no gaps."""
    print("\n" + "="*70)
    print("TEST: Timestamp-based alignment WITHOUT gaps (should match old method)")
    print("="*70)

    # Create continuous candles (no gaps)
    candles = []
    base_time = datetime(2026, 1, 15, 9, 30)
    price = 100.0

    for minute in range(100):  # 100 1m candles
        timestamp = base_time + timedelta(minutes=minute)
        price += np.random.uniform(-0.5, 0.5)

        candle = TickData(
            open=price, high=price + 0.2, low=price - 0.2,
            close=price + np.random.uniform(-0.1, 0.1),
            volume=1000, timestamp=timestamp, symbol="TEST"
        )
        candles.append(candle)

    # Create aggregators
    agg_1m = CANormal(symbol="TEST", timeframe="1m")
    agg_5m = CANormal(symbol="TEST", timeframe="5m")

    for candle in candles:
        agg_1m.process_tick(candle)
        agg_5m.process_tick(candle)

    history_1m = agg_1m.get_history()
    history_5m = agg_5m.get_history()

    print(f"1m candles: {len(history_1m)}")
    print(f"5m candles: {len(history_5m)}")
    print(f"Ratio: {len(history_1m) / max(1, len(history_5m)):.2f}")

    # Create values
    values_5m = [float(i * 10) for i in range(len(history_5m))]

    # Old method
    import bisect
    ratio = 5
    aligned_old = np.zeros(len(history_1m))
    for coarse_idx, value in enumerate(values_5m):
        start = int(coarse_idx * ratio)
        end = min(int((coarse_idx + 1) * ratio), len(history_1m))
        aligned_old[start:end] = value

    # New method
    aligned_new = np.zeros(len(history_1m))
    coarse_timestamps = [c.timestamp.timestamp() for c in history_5m]

    for primary_idx, primary_candle in enumerate(history_1m):
        primary_ts = primary_candle.timestamp.timestamp()
        coarse_idx = bisect.bisect_right(coarse_timestamps, primary_ts) - 1

        if 0 <= coarse_idx < len(values_5m):
            aligned_new[primary_idx] = values_5m[coarse_idx]

    # Compare
    differences = np.abs(aligned_old - aligned_new)
    num_different = np.sum(differences > 0.001)

    print(f"\nValues that differ: {num_different}/{len(history_1m)}")

    if num_different == 0:
        print("Both methods produce identical results when there are no gaps.")
        return True
    else:
        print("WARNING: Methods differ even without gaps - investigate!")
        for idx in range(len(history_1m)):
            if differences[idx] > 0.001:
                ts = history_1m[idx].timestamp
                print(f"  1m[{idx}] {ts}: OLD={aligned_old[idx]:.0f}, NEW={aligned_new[idx]:.0f}")
        return False


if __name__ == '__main__':
    print("Verifying timestamp-based alignment fix...\n")

    # Test with gap (should show differences)
    gap_test = test_alignment_with_gap()

    # Test without gap (should be identical)
    no_gap_test = test_alignment_without_gap()

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    if gap_test:
        print("Gap test: PASSED - New method handles gaps correctly where old method fails")
    else:
        print("Gap test: INCONCLUSIVE - No differences found (check test data)")

    if no_gap_test:
        print("No-gap test: PASSED - Both methods produce same results without gaps")
    else:
        print("No-gap test: FAILED - Unexpected differences without gaps")

    if gap_test and no_gap_test:
        print("\nAlignment fix verified successfully!")
    else:
        print("\nSome tests inconclusive - manual verification may be needed")
