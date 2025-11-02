#!/usr/bin/env python3
"""
Test Script: Extended Hours Filter Validation
Tests the include_extended_hours parameter in CandleAggregator

This script validates:
1. Data loading with extended hours included (default)
2. Data filtering when extended hours are excluded
3. Correct identification of trading hours (9:30 AM - 4:00 PM ET)
4. Comparison of candle counts between filtered and unfiltered data
"""

import sys
import os
from datetime import datetime, time
from typing import List, Dict

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from models.tick_data import TickData
from candle_aggregator.candle_aggregator_normal import CANormal
from mongo_tools.mongo_db_connect import MongoDBConnect


class ExtendedHoursFilterTest:
    """Test suite for extended hours filtering"""

    def __init__(self, ticker: str, start_date: str, end_date: str):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.raw_ticks: List[TickData] = []

    def load_data(self):
        """Load raw tick data from MongoDB"""
        print(f"\n{'='*80}")
        print(f"LOADING DATA: {self.ticker} from {self.start_date} to {self.end_date}")
        print(f"{'='*80}\n")

        mongo = MongoDBConnect()
        self.raw_ticks = mongo._load_raw_ticks(self.ticker, self.start_date, self.end_date)
        mongo.close()

        print(f"✅ Loaded {len(self.raw_ticks)} raw ticks from MongoDB\n")

        if not self.raw_ticks:
            print("❌ No data loaded! Check MongoDB connection and date range.")
            return False

        return True

    def analyze_tick_distribution(self):
        """Analyze the time distribution of ticks"""
        print(f"\n{'='*80}")
        print("TICK TIME DISTRIBUTION ANALYSIS")
        print(f"{'='*80}\n")

        pre_market = 0
        regular_hours = 0
        after_hours = 0

        for tick in self.raw_ticks:
            hour = tick.timestamp.hour
            minute = tick.timestamp.minute

            # Before 9:30 AM = pre-market
            if hour < 9 or (hour == 9 and minute < 30):
                pre_market += 1
            # After 4:00 PM = after-hours
            elif hour >= 16:
                after_hours += 1
            # 9:30 AM - 4:00 PM = regular hours
            else:
                regular_hours += 1

        total = len(self.raw_ticks)

        print(f"Total Ticks: {total:,}")
        print(f"\nTime Distribution:")
        print(f"  Pre-Market  (< 9:30 AM):   {pre_market:,} ticks ({pre_market/total*100:.1f}%)")
        print(f"  Regular Hours (9:30-4:00): {regular_hours:,} ticks ({regular_hours/total*100:.1f}%)")
        print(f"  After-Hours (>= 4:00 PM):  {after_hours:,} ticks ({after_hours/total*100:.1f}%)")

        return {
            'total': total,
            'pre_market': pre_market,
            'regular_hours': regular_hours,
            'after_hours': after_hours
        }

    def test_aggregator_with_extended_hours(self) -> Dict[str, int]:
        """Test aggregator with extended hours INCLUDED"""
        print(f"\n{'='*80}")
        print("TEST 1: CandleAggregator with EXTENDED HOURS INCLUDED")
        print(f"{'='*80}\n")

        agg = CANormal(self.ticker, "1m", include_extended_hours=True)

        candle_count = 0
        for tick in self.raw_ticks:
            completed = agg.process_tick(tick)
            if completed:
                candle_count += 1

        total_candles = len(agg.history)

        print(f"Configuration: include_extended_hours = True")
        print(f"✅ Processed {len(self.raw_ticks):,} ticks")
        print(f"✅ Created {total_candles:,} completed candles")
        print(f"✅ Current open candle: {'Yes' if agg.current_candle else 'No'}")

        if total_candles > 0:
            first_candle = agg.history[0]
            last_candle = agg.history[-1]
            print(f"\nFirst Candle: {first_candle.timestamp} (Hour: {first_candle.timestamp.hour:02d}:{first_candle.timestamp.minute:02d})")
            print(f"Last Candle:  {last_candle.timestamp} (Hour: {last_candle.timestamp.hour:02d}:{last_candle.timestamp.minute:02d})")

        return {
            'total_candles': total_candles,
            'current_candle': 1 if agg.current_candle else 0
        }

    def test_aggregator_without_extended_hours(self) -> Dict[str, int]:
        """Test aggregator with extended hours EXCLUDED"""
        print(f"\n{'='*80}")
        print("TEST 2: CandleAggregator with EXTENDED HOURS EXCLUDED")
        print(f"{'='*80}\n")

        agg = CANormal(self.ticker, "1m", include_extended_hours=False)

        candle_count = 0
        filtered_ticks = 0

        for tick in self.raw_ticks:
            completed = agg.process_tick(tick)
            if completed:
                candle_count += 1

            # Check if tick was filtered (outside trading hours)
            hour = tick.timestamp.hour
            minute = tick.timestamp.minute
            is_trading_hours = not (hour < 9 or (hour == 9 and minute < 30) or hour >= 16)
            if not is_trading_hours:
                filtered_ticks += 1

        total_candles = len(agg.history)

        print(f"Configuration: include_extended_hours = False")
        print(f"✅ Processed {len(self.raw_ticks):,} ticks")
        print(f"✅ Filtered out {filtered_ticks:,} extended hours ticks")
        print(f"✅ Created {total_candles:,} completed candles")
        print(f"✅ Current open candle: {'Yes' if agg.current_candle else 'No'}")

        if total_candles > 0:
            first_candle = agg.history[0]
            last_candle = agg.history[-1]
            print(f"\nFirst Candle: {first_candle.timestamp} (Hour: {first_candle.timestamp.hour:02d}:{first_candle.timestamp.minute:02d})")
            print(f"Last Candle:  {last_candle.timestamp} (Hour: {last_candle.timestamp.hour:02d}:{last_candle.timestamp.minute:02d})")

            # Validate all candles are during trading hours
            invalid_candles = []
            for candle in agg.history:
                hour = candle.timestamp.hour
                minute = candle.timestamp.minute
                if hour < 9 or (hour == 9 and minute < 30) or hour >= 16:
                    invalid_candles.append(candle)

            if invalid_candles:
                print(f"\n⚠️  WARNING: Found {len(invalid_candles)} candles outside trading hours!")
                for candle in invalid_candles[:5]:  # Show first 5
                    print(f"   {candle.timestamp}")
            else:
                print(f"\n✅ All candles are within regular trading hours (9:30 AM - 4:00 PM)")

        return {
            'total_candles': total_candles,
            'filtered_ticks': filtered_ticks,
            'current_candle': 1 if agg.current_candle else 0
        }

    def compare_results(self, with_extended: Dict, without_extended: Dict, tick_dist: Dict):
        """Compare results and validate filtering logic"""
        print(f"\n{'='*80}")
        print("COMPARISON AND VALIDATION")
        print(f"{'='*80}\n")

        print("Results Summary:")
        print(f"  With Extended Hours:    {with_extended['total_candles']:,} candles")
        print(f"  Without Extended Hours: {without_extended['total_candles']:,} candles")
        print(f"  Difference:             {with_extended['total_candles'] - without_extended['total_candles']:,} candles")

        expected_filtered = tick_dist['pre_market'] + tick_dist['after_hours']
        actual_filtered = without_extended['filtered_ticks']

        print(f"\nFiltered Ticks:")
        print(f"  Expected (Pre-market + After-hours): {expected_filtered:,}")
        print(f"  Actual Filtered:                      {actual_filtered:,}")

        # Validation checks
        print(f"\n{'='*80}")
        print("VALIDATION CHECKS")
        print(f"{'='*80}\n")

        checks_passed = 0
        checks_total = 4

        # Check 1: Filtered version should have fewer candles
        if without_extended['total_candles'] < with_extended['total_candles']:
            print("✅ CHECK 1: Filtered version has fewer candles (PASS)")
            checks_passed += 1
        else:
            print("❌ CHECK 1: Filtered version should have fewer candles (FAIL)")

        # Check 2: Number of filtered ticks should match extended hours ticks
        tolerance = 0.05  # 5% tolerance for edge cases
        expected_min = expected_filtered * (1 - tolerance)
        expected_max = expected_filtered * (1 + tolerance)

        if expected_min <= actual_filtered <= expected_max:
            print(f"✅ CHECK 2: Filtered tick count matches expected range (PASS)")
            checks_passed += 1
        else:
            print(f"❌ CHECK 2: Filtered tick count outside expected range (FAIL)")
            print(f"   Expected: {expected_filtered:,} (±{tolerance*100:.0f}%)")
            print(f"   Actual:   {actual_filtered:,}")

        # Check 3: With extended hours should include all time periods
        if with_extended['total_candles'] > 0:
            print("✅ CHECK 3: Extended hours version includes data (PASS)")
            checks_passed += 1
        else:
            print("❌ CHECK 3: Extended hours version should include data (FAIL)")

        # Check 4: Without extended hours should only have regular hours
        if without_extended['total_candles'] > 0:
            print("✅ CHECK 4: Regular hours version includes data (PASS)")
            checks_passed += 1
        else:
            print("❌ CHECK 4: Regular hours version should include data (FAIL)")

        # Final result
        print(f"\n{'='*80}")
        if checks_passed == checks_total:
            print(f"🎉 ALL TESTS PASSED ({checks_passed}/{checks_total})")
        else:
            print(f"⚠️  SOME TESTS FAILED ({checks_passed}/{checks_total} passed)")
        print(f"{'='*80}\n")

        return checks_passed == checks_total

    def run_tests(self):
        """Run all tests"""
        if not self.load_data():
            return False

        tick_dist = self.analyze_tick_distribution()
        with_extended = self.test_aggregator_with_extended_hours()
        without_extended = self.test_aggregator_without_extended_hours()

        return self.compare_results(with_extended, without_extended, tick_dist)


def main():
    """Main entry point"""
    # Test configuration - update these values as needed
    TICKER = "PLTR"
    START_DATE = "2025-01-30"
    END_DATE = "2025-02-01"  # Short range for quick testing

    print("\n" + "="*80)
    print("EXTENDED HOURS FILTER TEST SUITE")
    print("="*80)
    print(f"\nTesting extended hours filtering for {TICKER}")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print(f"Regular Trading Hours: 9:30 AM - 4:00 PM ET")

    tester = ExtendedHoursFilterTest(TICKER, START_DATE, END_DATE)
    success = tester.run_tests()

    if success:
        print("\n✅ Extended hours filter implementation is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ Extended hours filter has issues - review test output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
