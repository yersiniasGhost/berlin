"""
Tests for CandleAggregator extended hours filtering functionality.

Tests verify that when include_extended_hours=False, ticks outside
regular market hours (9:30 AM - 4:00 PM ET) are filtered out.

Run with: python -m pytest tests/data_streamer/test_candle_aggregator_extended_hours.py -v
Or standalone: python tests/data_streamer/test_candle_aggregator_extended_hours.py
"""
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from datetime import datetime

# Try to import pytest, fall back to simple runner
try:
    import pytest
except ImportError:
    pytest = None

from candle_aggregator.candle_aggregator_normal import CANormal
from models.tick_data import TickData
from mlf_utils.timezone_utils import ET, assume_et


def create_tick(symbol: str, dt: datetime, price: float = 100.0) -> TickData:
    """Helper to create a TickData object with ET-aware timestamp."""
    if dt.tzinfo is None:
        dt = assume_et(dt)
    return TickData(
        symbol=symbol,
        timestamp=dt,
        open=price,
        high=price + 0.1,
        low=price - 0.1,
        close=price,
        volume=100,
        time_increment="RAW"
    )


class TestExtendedHoursFiltering:
    """Test suite for extended hours filtering in CandleAggregator."""

    def test_regular_hours_tick_included_when_extended_false(self):
        """Ticks during regular hours (9:30 AM - 4:00 PM ET) should be processed."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=False)

        # 10:30 AM ET - regular trading hours
        dt = datetime(2026, 1, 27, 10, 30, 0)
        tick = create_tick("TEST", dt, 100.0)

        result = aggregator.process_tick(tick)

        # Should have started a candle (not filtered)
        assert aggregator.current_candle is not None
        assert aggregator.current_candle.close == 100.0

    def test_premarket_tick_filtered_when_extended_false(self):
        """Ticks during pre-market (before 9:30 AM ET) should be filtered."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=False)

        # 7:00 AM ET - pre-market
        dt = datetime(2026, 1, 27, 7, 0, 0)
        tick = create_tick("TEST", dt, 100.0)

        result = aggregator.process_tick(tick)

        # Should be filtered - no candle started
        assert result is None
        assert aggregator.current_candle is None

    def test_afterhours_tick_filtered_when_extended_false(self):
        """Ticks during after-hours (after 4:00 PM ET) should be filtered."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=False)

        # 5:30 PM ET - after hours
        dt = datetime(2026, 1, 27, 17, 30, 0)
        tick = create_tick("TEST", dt, 100.0)

        result = aggregator.process_tick(tick)

        # Should be filtered - no candle started
        assert result is None
        assert aggregator.current_candle is None

    def test_premarket_tick_included_when_extended_true(self):
        """Ticks during pre-market should be processed when extended hours enabled."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=True)

        # 7:00 AM ET - pre-market
        dt = datetime(2026, 1, 27, 7, 0, 0)
        tick = create_tick("TEST", dt, 100.0)

        result = aggregator.process_tick(tick)

        # Should have started a candle (not filtered)
        assert aggregator.current_candle is not None
        assert aggregator.current_candle.close == 100.0

    def test_afterhours_tick_included_when_extended_true(self):
        """Ticks during after-hours should be processed when extended hours enabled."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=True)

        # 5:30 PM ET - after hours
        dt = datetime(2026, 1, 27, 17, 30, 0)
        tick = create_tick("TEST", dt, 100.0)

        result = aggregator.process_tick(tick)

        # Should have started a candle (not filtered)
        assert aggregator.current_candle is not None
        assert aggregator.current_candle.close == 100.0

    def test_market_open_boundary(self):
        """Test exact market open time (9:30 AM ET) is included."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=False)

        # Exactly 9:30 AM ET - market open
        dt = datetime(2026, 1, 27, 9, 30, 0)
        tick = create_tick("TEST", dt, 100.0)

        result = aggregator.process_tick(tick)

        # Should be included
        assert aggregator.current_candle is not None

    def test_just_before_market_open(self):
        """Test 9:29 AM ET is filtered when extended hours disabled."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=False)

        # 9:29 AM ET - one minute before open
        dt = datetime(2026, 1, 27, 9, 29, 0)
        tick = create_tick("TEST", dt, 100.0)

        result = aggregator.process_tick(tick)

        # Should be filtered
        assert aggregator.current_candle is None

    def test_market_close_boundary(self):
        """Test 3:59 PM ET is included, 4:00 PM ET is filtered."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=False)

        # 3:59 PM ET - just before close
        dt_before = datetime(2026, 1, 27, 15, 59, 0)
        tick_before = create_tick("TEST", dt_before, 100.0)

        aggregator.process_tick(tick_before)
        assert aggregator.current_candle is not None

        # Reset aggregator
        aggregator2 = CANormal("TEST", "1m", include_extended_hours=False)

        # 4:00 PM ET - market close (after hours)
        dt_at = datetime(2026, 1, 27, 16, 0, 0)
        tick_at = create_tick("TEST", dt_at, 100.0)

        aggregator2.process_tick(tick_at)
        # 4:00 PM should be filtered (market is closed)
        assert aggregator2.current_candle is None

    def test_multiple_ticks_mixed_hours(self):
        """Test processing multiple ticks with some in and some out of regular hours."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=False)

        ticks = [
            # Pre-market - should be filtered
            create_tick("TEST", datetime(2026, 1, 27, 8, 0, 0), 99.0),
            # Regular hours - should be included
            create_tick("TEST", datetime(2026, 1, 27, 10, 0, 0), 100.0),
            create_tick("TEST", datetime(2026, 1, 27, 10, 0, 30), 101.0),
            # After hours - should be filtered
            create_tick("TEST", datetime(2026, 1, 27, 18, 0, 0), 102.0),
        ]

        for tick in ticks:
            aggregator.process_tick(tick)

        # Should only have processed the regular hours ticks
        # Current candle should be from 10:00 AM with close=101.0
        assert aggregator.current_candle is not None
        assert aggregator.current_candle.close == 101.0

    def test_default_includes_extended_hours(self):
        """Test that default behavior includes extended hours."""
        aggregator = CANormal("TEST", "1m")  # No include_extended_hours specified

        # 7:00 AM ET - pre-market
        dt = datetime(2026, 1, 27, 7, 0, 0)
        tick = create_tick("TEST", dt, 100.0)

        result = aggregator.process_tick(tick)

        # Default should include extended hours
        assert aggregator.current_candle is not None


class TestExtendedHoursBoundaries:
    """Test extended hours boundary conditions.

    Note: When include_extended_hours=True, ALL ticks are allowed through
    (no filtering at all). The filtering only applies when
    include_extended_hours=False (regular hours 9:30 AM - 4:00 PM ET).
    """

    def test_extended_hours_early_premarket(self):
        """Test 4:00 AM ET is included with extended hours enabled."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=True)

        # 4:00 AM ET - early pre-market
        dt = datetime(2026, 1, 27, 4, 0, 0)
        tick = create_tick("TEST", dt, 100.0)

        aggregator.process_tick(tick)
        assert aggregator.current_candle is not None

    def test_very_early_morning_included_when_extended_true(self):
        """Test that even very early times (3:00 AM) are included with extended hours."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=True)

        # 3:00 AM ET - before typical extended hours
        dt = datetime(2026, 1, 27, 3, 0, 0)
        tick = create_tick("TEST", dt, 100.0)

        aggregator.process_tick(tick)
        # With extended hours enabled, ALL ticks pass through (no filtering)
        assert aggregator.current_candle is not None

    def test_extended_hours_late_afterhours(self):
        """Test 7:59 PM ET is included with extended hours enabled."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=True)

        # 7:59 PM ET - late after-hours
        dt = datetime(2026, 1, 27, 19, 59, 0)
        tick = create_tick("TEST", dt, 100.0)

        aggregator.process_tick(tick)
        assert aggregator.current_candle is not None

    def test_late_night_included_when_extended_true(self):
        """Test that late night times (10:00 PM) are included with extended hours."""
        aggregator = CANormal("TEST", "1m", include_extended_hours=True)

        # 10:00 PM ET - late night
        dt = datetime(2026, 1, 27, 22, 0, 0)
        tick = create_tick("TEST", dt, 100.0)

        aggregator.process_tick(tick)
        # With extended hours enabled, ALL ticks pass through (no filtering)
        assert aggregator.current_candle is not None


def run_tests():
    """Run all tests without pytest."""
    import traceback

    test_classes = [TestExtendedHoursFiltering, TestExtendedHoursBoundaries]
    passed = 0
    failed = 0

    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                try:
                    print(f"Running {test_class.__name__}.{method_name}...", end=" ")
                    getattr(instance, method_name)()
                    print("PASSED")
                    passed += 1
                except AssertionError as e:
                    print(f"FAILED: {e}")
                    failed += 1
                except Exception as e:
                    print(f"ERROR: {e}")
                    traceback.print_exc()
                    failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__, "-v"])
    else:
        success = run_tests()
        sys.exit(0 if success else 1)
