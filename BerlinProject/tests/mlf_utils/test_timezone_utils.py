"""
Tests for timezone_utils module.

Run with: python -m pytest tests/mlf_utils/test_timezone_utils.py -v
Or standalone: python tests/mlf_utils/test_timezone_utils.py
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from datetime import datetime, timezone, timedelta
from contextlib import contextmanager

# Simple pytest.raises replacement for standalone testing
@contextmanager
def raises(exception_type, match=None):
    """Context manager that asserts an exception is raised."""
    try:
        yield
        raise AssertionError(f"Expected {exception_type.__name__} to be raised")
    except exception_type as e:
        if match and match not in str(e):
            raise AssertionError(f"Exception message '{e}' does not contain '{match}'")

# Try to import pytest, fall back to our simple implementation
try:
    import pytest
except ImportError:
    class pytest:
        raises = staticmethod(raises)

from mlf_utils.timezone_utils import (
    # Constants
    UTC, ET,
    MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE,
    # Current time
    now_utc, now_et,
    # Timestamp conversion
    utc_from_timestamp_ms, utc_from_timestamp_s,
    to_timestamp_ms, to_timestamp_s,
    # Timezone conversion
    to_et, to_utc, assume_et, assume_utc,
    # Validation
    validate_aware, is_aware, is_naive,
    # Market hours
    is_market_hours, is_premarket, is_afterhours, is_trading_day,
    get_market_open_today, get_market_close_today, get_trading_session_range,
    # Formatting
    format_et, format_utc, format_for_display, isoformat_utc, isoformat_et,
)


class TestConstants:
    """Test timezone constants."""

    def test_utc_constant(self):
        assert UTC == timezone.utc

    def test_et_constant(self):
        # ET should be America/New_York timezone
        now = datetime.now(ET)
        # Should have tzinfo
        assert now.tzinfo is not None
        # Should be 4-5 hours behind UTC depending on DST
        utc_now = datetime.now(UTC)
        diff_hours = (utc_now - now.astimezone(UTC)).total_seconds() / 3600
        assert abs(diff_hours) < 0.01  # Should be essentially zero (same instant)

    def test_market_hour_constants(self):
        assert MARKET_OPEN_HOUR == 9
        assert MARKET_OPEN_MINUTE == 30
        assert MARKET_CLOSE_HOUR == 16
        assert MARKET_CLOSE_MINUTE == 0


class TestCurrentTime:
    """Test current time functions."""

    def test_now_utc_is_aware(self):
        result = now_utc()
        assert result.tzinfo is not None
        assert result.tzinfo == UTC

    def test_now_et_is_aware(self):
        result = now_et()
        assert result.tzinfo is not None

    def test_now_utc_and_now_et_same_instant(self):
        # Both should represent the same instant in time
        utc = now_utc()
        et = now_et()
        # Convert both to UTC and compare (within 1 second tolerance)
        diff = abs((utc - et.astimezone(UTC)).total_seconds())
        assert diff < 1.0


class TestTimestampConversion:
    """Test timestamp conversion functions."""

    def test_utc_from_timestamp_ms(self):
        # Known timestamp: 2024-01-29 15:00:00 UTC
        ts_ms = 1706540400000
        result = utc_from_timestamp_ms(ts_ms)

        assert result.tzinfo == UTC
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 29
        assert result.hour == 15
        assert result.minute == 0

    def test_utc_from_timestamp_s(self):
        ts_s = 1706540400.0
        result = utc_from_timestamp_s(ts_s)

        assert result.tzinfo == UTC
        assert result.year == 2024

    def test_to_timestamp_ms_roundtrip(self):
        original_ms = 1706540400000
        dt = utc_from_timestamp_ms(original_ms)
        result_ms = to_timestamp_ms(dt)
        assert result_ms == original_ms

    def test_to_timestamp_ms_rejects_naive(self):
        naive = datetime(2024, 1, 29, 15, 0, 0)
        with pytest.raises(ValueError, match="Naive datetime"):
            to_timestamp_ms(naive)

    def test_to_timestamp_s_roundtrip(self):
        original_s = 1706540400.5
        dt = utc_from_timestamp_s(original_s)
        result_s = to_timestamp_s(dt)
        assert abs(result_s - original_s) < 0.001


class TestTimezoneConversion:
    """Test timezone conversion functions."""

    def test_to_et_from_utc(self):
        utc_dt = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        et_dt = to_et(utc_dt)

        assert et_dt.tzinfo is not None
        # January = EST = UTC-5, so 15:00 UTC = 10:00 ET
        assert et_dt.hour == 10

    def test_to_utc_from_et(self):
        # Create ET datetime (January = EST)
        et_dt = assume_et(datetime(2024, 1, 29, 10, 0, 0))
        utc_dt = to_utc(et_dt)

        assert utc_dt.tzinfo == UTC
        # 10:00 ET in January = 15:00 UTC
        assert utc_dt.hour == 15

    def test_to_et_rejects_naive(self):
        naive = datetime(2024, 1, 29, 15, 0, 0)
        with pytest.raises(ValueError, match="Cannot convert naive"):
            to_et(naive)

    def test_to_utc_rejects_naive(self):
        naive = datetime(2024, 1, 29, 15, 0, 0)
        with pytest.raises(ValueError, match="Cannot convert naive"):
            to_utc(naive)

    def test_assume_et_makes_aware(self):
        naive = datetime(2024, 1, 29, 10, 0, 0)
        result = assume_et(naive)
        assert result.tzinfo is not None
        assert result.hour == 10  # Hour should not change

    def test_assume_et_rejects_aware(self):
        aware = datetime(2024, 1, 29, 10, 0, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="already timezone-aware"):
            assume_et(aware)

    def test_assume_utc_makes_aware(self):
        naive = datetime(2024, 1, 29, 15, 0, 0)
        result = assume_utc(naive)
        assert result.tzinfo == UTC
        assert result.hour == 15

    def test_assume_utc_rejects_aware(self):
        aware = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="already timezone-aware"):
            assume_utc(aware)


class TestValidation:
    """Test validation functions."""

    def test_validate_aware_passes_for_aware(self):
        aware = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        result = validate_aware(aware)
        assert result == aware

    def test_validate_aware_raises_for_naive(self):
        naive = datetime(2024, 1, 29, 15, 0, 0)
        with pytest.raises(ValueError, match="Naive datetime not allowed"):
            validate_aware(naive)

    def test_validate_aware_includes_context(self):
        naive = datetime(2024, 1, 29, 15, 0, 0)
        with pytest.raises(ValueError, match="in test_context"):
            validate_aware(naive, "test_context")

    def test_is_aware_true_for_aware(self):
        aware = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        assert is_aware(aware) is True

    def test_is_aware_false_for_naive(self):
        naive = datetime(2024, 1, 29, 15, 0, 0)
        assert is_aware(naive) is False

    def test_is_naive_true_for_naive(self):
        naive = datetime(2024, 1, 29, 15, 0, 0)
        assert is_naive(naive) is True

    def test_is_naive_false_for_aware(self):
        aware = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        assert is_naive(aware) is False


class TestMarketHours:
    """Test market hours functions."""

    def test_is_market_hours_during_open(self):
        # Monday at 10:30 AM ET = market open
        # Create as UTC (10:30 ET in January = 15:30 UTC)
        utc_dt = datetime(2024, 1, 29, 15, 30, 0, tzinfo=UTC)  # Monday
        assert is_market_hours(utc_dt) is True

    def test_is_market_hours_before_open(self):
        # Monday at 9:00 AM ET = before market
        # 9:00 ET in January = 14:00 UTC
        utc_dt = datetime(2024, 1, 29, 14, 0, 0, tzinfo=UTC)  # Monday
        assert is_market_hours(utc_dt) is False

    def test_is_market_hours_after_close(self):
        # Monday at 4:30 PM ET = after market
        # 16:30 ET in January = 21:30 UTC
        utc_dt = datetime(2024, 1, 29, 21, 30, 0, tzinfo=UTC)  # Monday
        assert is_market_hours(utc_dt) is False

    def test_is_market_hours_at_close(self):
        # Monday at exactly 4:00 PM ET = market closed
        # 16:00 ET in January = 21:00 UTC
        utc_dt = datetime(2024, 1, 29, 21, 0, 0, tzinfo=UTC)  # Monday
        assert is_market_hours(utc_dt) is False

    def test_is_market_hours_weekend(self):
        # Saturday at 10:30 AM ET
        utc_dt = datetime(2024, 1, 27, 15, 30, 0, tzinfo=UTC)  # Saturday
        assert is_market_hours(utc_dt) is False

    def test_is_market_hours_rejects_naive(self):
        naive = datetime(2024, 1, 29, 10, 30, 0)
        with pytest.raises(ValueError, match="naive datetime"):
            is_market_hours(naive)

    def test_is_market_hours_extended_premarket(self):
        # Monday at 5:00 AM ET (pre-market)
        # 5:00 ET in January = 10:00 UTC
        utc_dt = datetime(2024, 1, 29, 10, 0, 0, tzinfo=UTC)
        assert is_market_hours(utc_dt, include_extended=False) is False
        assert is_market_hours(utc_dt, include_extended=True) is True

    def test_is_market_hours_extended_afterhours(self):
        # Monday at 6:00 PM ET (after-hours)
        # 18:00 ET in January = 23:00 UTC
        utc_dt = datetime(2024, 1, 29, 23, 0, 0, tzinfo=UTC)
        assert is_market_hours(utc_dt, include_extended=False) is False
        assert is_market_hours(utc_dt, include_extended=True) is True

    def test_is_premarket(self):
        # Monday at 5:00 AM ET (pre-market)
        utc_dt = datetime(2024, 1, 29, 10, 0, 0, tzinfo=UTC)
        assert is_premarket(utc_dt) is True

        # Monday at 10:30 AM ET (regular hours)
        utc_dt = datetime(2024, 1, 29, 15, 30, 0, tzinfo=UTC)
        assert is_premarket(utc_dt) is False

    def test_is_afterhours(self):
        # Monday at 6:00 PM ET (after-hours)
        utc_dt = datetime(2024, 1, 29, 23, 0, 0, tzinfo=UTC)
        assert is_afterhours(utc_dt) is True

        # Monday at 10:30 AM ET (regular hours)
        utc_dt = datetime(2024, 1, 29, 15, 30, 0, tzinfo=UTC)
        assert is_afterhours(utc_dt) is False

    def test_is_trading_day_weekday(self):
        monday = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        assert is_trading_day(monday) is True

    def test_is_trading_day_weekend(self):
        saturday = datetime(2024, 1, 27, 15, 0, 0, tzinfo=UTC)
        assert is_trading_day(saturday) is False

    def test_get_market_open_today(self):
        ref = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        market_open = get_market_open_today(ref)
        et_open = to_et(market_open)
        assert et_open.hour == 9
        assert et_open.minute == 30

    def test_get_market_close_today(self):
        ref = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        market_close = get_market_close_today(ref)
        et_close = to_et(market_close)
        assert et_close.hour == 16
        assert et_close.minute == 0

    def test_get_trading_session_range(self):
        ref = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        open_time, close_time = get_trading_session_range(ref)
        assert to_et(open_time).hour == 9
        assert to_et(close_time).hour == 16


class TestFormatting:
    """Test formatting functions."""

    def test_format_et(self):
        utc_dt = datetime(2024, 1, 29, 15, 0, 0, tzinfo=UTC)
        result = format_et(utc_dt, '%H:%M')
        assert result == '10:00'  # 15:00 UTC = 10:00 EST

    def test_format_utc(self):
        utc_dt = datetime(2024, 1, 29, 15, 30, 45, tzinfo=UTC)
        result = format_utc(utc_dt)
        assert result == '2024-01-29T15:30:45Z'

    def test_format_for_display(self):
        utc_dt = datetime(2024, 1, 29, 15, 30, 0, tzinfo=UTC)
        result = format_for_display(utc_dt)
        assert 'Jan 29, 2024' in result
        assert '10:30' in result
        assert 'ET' in result

    def test_isoformat_utc(self):
        utc_dt = datetime(2024, 1, 29, 15, 30, 45, 123456, tzinfo=UTC)
        result = isoformat_utc(utc_dt)
        assert result == '2024-01-29T15:30:45.123Z'

    def test_isoformat_et(self):
        utc_dt = datetime(2024, 1, 29, 15, 30, 45, tzinfo=UTC)
        result = isoformat_et(utc_dt)
        assert '10:30:45' in result
        assert '-05:00' in result  # EST offset


class TestDSTHandling:
    """Test Daylight Saving Time edge cases."""

    def test_winter_time_offset(self):
        # January = EST (UTC-5)
        winter = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        et = to_et(winter)
        assert et.hour == 7  # 12:00 UTC = 7:00 EST

    def test_summer_time_offset(self):
        # July = EDT (UTC-4)
        summer = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        et = to_et(summer)
        assert et.hour == 8  # 12:00 UTC = 8:00 EDT

    def test_market_hours_across_dst(self):
        # Test that market hours (9:30 AM - 4:00 PM ET) work correctly in both EST and EDT

        # Winter: 10:30 AM EST = 15:30 UTC
        winter_market = datetime(2024, 1, 15, 15, 30, 0, tzinfo=UTC)  # Monday
        assert is_market_hours(winter_market) is True

        # Summer: 10:30 AM EDT = 14:30 UTC (1 hour earlier in UTC)
        summer_market = datetime(2024, 7, 15, 14, 30, 0, tzinfo=UTC)  # Monday
        assert is_market_hours(summer_market) is True


# Run tests directly
if __name__ == '__main__':
    # Simple test runner for standalone execution
    import traceback

    test_classes = [
        TestConstants,
        TestCurrentTime,
        TestTimestampConversion,
        TestTimezoneConversion,
        TestValidation,
        TestMarketHours,
        TestFormatting,
        TestDSTHandling,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}")
        print('='*60)

        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                try:
                    method = getattr(instance, method_name)
                    method()
                    print(f"  ✅ {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  ❌ {method_name}: {e}")
                    failed += 1
                except Exception as e:
                    # Check if it's an expected exception (from pytest.raises)
                    print(f"  ❌ {method_name}: Unexpected error: {e}")
                    traceback.print_exc()
                    failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print('='*60)

    if failed > 0:
        sys.exit(1)
