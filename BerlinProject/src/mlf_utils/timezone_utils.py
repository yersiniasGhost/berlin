"""
Centralized timezone handling for BerlinProject.

TIMEZONE POLICY:
================
1. All internal timestamps should be UTC-aware datetimes
2. ET (Eastern Time) conversion happens ONLY at boundaries:
   - Data ingestion (converting from broker API timestamps)
   - Display to user (showing times in market timezone)
   - Market hours calculations
3. Naive datetimes should be rejected at validation points
4. MongoDB storage: UTC milliseconds since epoch (or UTC-aware datetime)

USAGE:
======
    from mlf_utils.timezone_utils import (
        UTC, ET,
        now_utc, now_et,
        utc_from_timestamp_ms, utc_from_timestamp_s,
        to_et, to_utc,
        is_market_hours,
        validate_aware,
        get_market_open_today, get_market_close_today
    )

    # Get current time
    current = now_utc()  # For internal use
    current_et = now_et()  # For display or market logic

    # Convert from broker API (milliseconds since epoch)
    timestamp = utc_from_timestamp_ms(1706540400000)

    # Check market hours (handles any timezone-aware datetime)
    if is_market_hours(timestamp):
        process_tick(...)

    # Display to user
    display_time = to_et(timestamp).strftime('%Y-%m-%d %H:%M:%S %Z')

WHY zoneinfo OVER pytz:
=======================
- Built-in to Python 3.9+ (no external dependency)
- Handles DST transitions correctly without localize() gotchas
- Simpler API: datetime(..., tzinfo=ZoneInfo('America/New_York'))
- Future-proof: pytz is in maintenance mode
"""

from datetime import datetime, timezone, timedelta, time
from typing import Optional, Tuple
import sys

# Use zoneinfo (Python 3.9+) with pytz fallback for older versions
if sys.version_info >= (3, 9):
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/New_York')
else:
    # Fallback for Python 3.8
    import pytz
    ET = pytz.timezone('America/New_York')

# UTC timezone constant
UTC = timezone.utc

# Market hours constants (Eastern Time)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0

# Seconds from midnight (useful for stored data format)
MARKET_OPEN_SECONDS = MARKET_OPEN_HOUR * 3600 + MARKET_OPEN_MINUTE * 60  # 34200 (9:30 AM)
MARKET_CLOSE_SECONDS = MARKET_CLOSE_HOUR * 3600 + MARKET_CLOSE_MINUTE * 60  # 57600 (4:00 PM)

# Pre-market and after-hours boundaries
PREMARKET_START_HOUR = 4
PREMARKET_START_MINUTE = 0
AFTERHOURS_END_HOUR = 20
AFTERHOURS_END_MINUTE = 0


# =============================================================================
# Current Time Functions
# =============================================================================

def now_utc() -> datetime:
    """
    Get current time as UTC-aware datetime.

    Use this for:
    - Internal timestamps
    - Logging
    - Any timestamp that will be stored

    Returns:
        UTC-aware datetime of current time
    """
    return datetime.now(UTC)


def now_et() -> datetime:
    """
    Get current time as ET-aware datetime.

    Use this for:
    - Market hours calculations
    - Display to user
    - Comparing with market open/close times

    Returns:
        ET-aware datetime of current time
    """
    return datetime.now(ET)


# =============================================================================
# Timestamp Conversion Functions
# =============================================================================

def utc_from_timestamp_ms(timestamp_ms: int) -> datetime:
    """
    Convert milliseconds since Unix epoch to UTC-aware datetime.

    Use this for:
    - Schwab API timestamps (returns milliseconds)
    - Any broker API that returns epoch milliseconds

    Args:
        timestamp_ms: Milliseconds since Unix epoch (Jan 1, 1970 UTC)

    Returns:
        UTC-aware datetime

    Example:
        >>> ts = utc_from_timestamp_ms(1706540400000)
        >>> print(ts)
        2024-01-29 15:00:00+00:00
    """
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)


def utc_from_timestamp_s(timestamp_s: float) -> datetime:
    """
    Convert seconds since Unix epoch to UTC-aware datetime.

    Use this for:
    - Standard Unix timestamps
    - Polygon.io timestamps

    Args:
        timestamp_s: Seconds since Unix epoch (can be float for sub-second precision)

    Returns:
        UTC-aware datetime
    """
    return datetime.fromtimestamp(timestamp_s, tz=UTC)


def to_timestamp_ms(dt: datetime) -> int:
    """
    Convert datetime to milliseconds since Unix epoch.

    Args:
        dt: Timezone-aware datetime

    Returns:
        Milliseconds since Unix epoch

    Raises:
        ValueError: If datetime is naive (no timezone)
    """
    validate_aware(dt, "to_timestamp_ms")
    return int(dt.timestamp() * 1000)


def to_timestamp_s(dt: datetime) -> float:
    """
    Convert datetime to seconds since Unix epoch.

    Args:
        dt: Timezone-aware datetime

    Returns:
        Seconds since Unix epoch (float for sub-second precision)

    Raises:
        ValueError: If datetime is naive (no timezone)
    """
    validate_aware(dt, "to_timestamp_s")
    return dt.timestamp()


# =============================================================================
# Timezone Conversion Functions
# =============================================================================

def to_et(dt: datetime) -> datetime:
    """
    Convert any timezone-aware datetime to Eastern Time.

    Use this for:
    - Display to user
    - Market hours calculations
    - Comparing with market schedule

    Args:
        dt: Timezone-aware datetime (any timezone)

    Returns:
        ET-aware datetime

    Raises:
        ValueError: If datetime is naive (no timezone)
    """
    if dt.tzinfo is None:
        raise ValueError(f"Cannot convert naive datetime to ET: {dt}. "
                        f"Use utc_from_timestamp_ms() or ensure datetime has timezone.")
    return dt.astimezone(ET)


def to_utc(dt: datetime) -> datetime:
    """
    Convert any timezone-aware datetime to UTC.

    Use this for:
    - Internal storage
    - API calls that expect UTC
    - Consistent timestamp comparison

    Args:
        dt: Timezone-aware datetime (any timezone)

    Returns:
        UTC-aware datetime

    Raises:
        ValueError: If datetime is naive (no timezone)
    """
    if dt.tzinfo is None:
        raise ValueError(f"Cannot convert naive datetime to UTC: {dt}. "
                        f"Use utc_from_timestamp_ms() or ensure datetime has timezone.")
    return dt.astimezone(UTC)


def assume_et(dt: datetime) -> datetime:
    """
    Treat a naive datetime as if it were in ET timezone.

    WARNING: Use this ONLY for legacy data migration or when you are CERTAIN
    the naive datetime represents ET time. Prefer using timezone-aware
    datetimes from the start.

    Args:
        dt: Naive datetime assumed to be in ET

    Returns:
        ET-aware datetime

    Raises:
        ValueError: If datetime is already timezone-aware
    """
    if dt.tzinfo is not None:
        raise ValueError(f"datetime is already timezone-aware: {dt}. "
                        f"Use to_et() for timezone conversion instead.")

    if sys.version_info >= (3, 9):
        return dt.replace(tzinfo=ET)
    else:
        # pytz requires localize() for correct DST handling
        return ET.localize(dt)


def assume_utc(dt: datetime) -> datetime:
    """
    Treat a naive datetime as if it were in UTC timezone.

    WARNING: Use this ONLY for legacy data migration or when you are CERTAIN
    the naive datetime represents UTC time.

    Args:
        dt: Naive datetime assumed to be in UTC

    Returns:
        UTC-aware datetime

    Raises:
        ValueError: If datetime is already timezone-aware
    """
    if dt.tzinfo is not None:
        raise ValueError(f"datetime is already timezone-aware: {dt}. "
                        f"Use to_utc() for timezone conversion instead.")
    return dt.replace(tzinfo=UTC)


# =============================================================================
# Validation Functions
# =============================================================================

def validate_aware(dt: datetime, context: str = "") -> datetime:
    """
    Validate that datetime is timezone-aware, raise error if not.

    Use this at function boundaries to catch naive datetimes early.

    Args:
        dt: Datetime to validate
        context: Optional context string for error message (e.g., "TickData.timestamp")

    Returns:
        The same datetime if valid

    Raises:
        ValueError: If datetime is naive (no timezone)

    Example:
        def process_tick(timestamp: datetime):
            validate_aware(timestamp, "process_tick.timestamp")
            # ... rest of function
    """
    if dt.tzinfo is None:
        ctx = f" in {context}" if context else ""
        raise ValueError(
            f"Naive datetime not allowed{ctx}: {dt}. "
            f"Use utc_from_timestamp_ms() or now_utc() to create timezone-aware datetimes."
        )
    return dt


def is_aware(dt: datetime) -> bool:
    """
    Check if datetime is timezone-aware.

    Args:
        dt: Datetime to check

    Returns:
        True if timezone-aware, False if naive
    """
    return dt.tzinfo is not None


def is_naive(dt: datetime) -> bool:
    """
    Check if datetime is naive (no timezone).

    Args:
        dt: Datetime to check

    Returns:
        True if naive, False if timezone-aware
    """
    return dt.tzinfo is None


# =============================================================================
# Market Hours Functions
# =============================================================================

def is_market_hours(dt: datetime, include_extended: bool = False) -> bool:
    """
    Check if datetime is during market hours.

    Regular market hours: 9:30 AM - 4:00 PM ET
    Extended hours: 4:00 AM - 8:00 PM ET (pre-market + after-hours)

    Args:
        dt: Timezone-aware datetime to check
        include_extended: If True, includes pre-market (4:00 AM) and
                         after-hours (until 8:00 PM)

    Returns:
        True if during market hours, False otherwise

    Raises:
        ValueError: If datetime is naive (no timezone)

    Example:
        >>> from mlf_utils.timezone_utils import is_market_hours, now_utc
        >>> if is_market_hours(now_utc()):
        ...     print("Market is open!")
    """
    if dt.tzinfo is None:
        raise ValueError(
            f"Cannot check market hours for naive datetime: {dt}. "
            f"Use utc_from_timestamp_ms() or now_utc() to create timezone-aware datetimes."
        )

    # Convert to ET for market hours check
    et_time = dt.astimezone(ET)

    # Check weekday (Monday=0, Sunday=6)
    if et_time.weekday() >= 5:
        return False

    hour = et_time.hour
    minute = et_time.minute

    if include_extended:
        # Extended hours: 4:00 AM - 8:00 PM ET
        if hour < PREMARKET_START_HOUR:
            return False
        if hour >= AFTERHOURS_END_HOUR:
            return False
    else:
        # Regular hours: 9:30 AM - 4:00 PM ET
        # Before 9:30 AM ET
        if hour < MARKET_OPEN_HOUR or (hour == MARKET_OPEN_HOUR and minute < MARKET_OPEN_MINUTE):
            return False
        # At or after 4:00 PM ET
        if hour >= MARKET_CLOSE_HOUR:
            return False

    return True


def is_premarket(dt: datetime) -> bool:
    """
    Check if datetime is during pre-market hours (4:00 AM - 9:30 AM ET).

    Args:
        dt: Timezone-aware datetime to check

    Returns:
        True if during pre-market hours, False otherwise

    Raises:
        ValueError: If datetime is naive
    """
    validate_aware(dt, "is_premarket")
    et_time = dt.astimezone(ET)

    if et_time.weekday() >= 5:
        return False

    hour = et_time.hour
    minute = et_time.minute

    # Pre-market: 4:00 AM - 9:30 AM ET
    if hour < PREMARKET_START_HOUR:
        return False
    if hour > MARKET_OPEN_HOUR or (hour == MARKET_OPEN_HOUR and minute >= MARKET_OPEN_MINUTE):
        return False

    return True


def is_afterhours(dt: datetime) -> bool:
    """
    Check if datetime is during after-hours (4:00 PM - 8:00 PM ET).

    Args:
        dt: Timezone-aware datetime to check

    Returns:
        True if during after-hours, False otherwise

    Raises:
        ValueError: If datetime is naive
    """
    validate_aware(dt, "is_afterhours")
    et_time = dt.astimezone(ET)

    if et_time.weekday() >= 5:
        return False

    hour = et_time.hour

    # After-hours: 4:00 PM - 8:00 PM ET
    return MARKET_CLOSE_HOUR <= hour < AFTERHOURS_END_HOUR


def get_market_open_today(reference: Optional[datetime] = None) -> datetime:
    """
    Get today's market open time (9:30 AM ET).

    Args:
        reference: Optional reference datetime (defaults to now)

    Returns:
        ET-aware datetime for today's market open
    """
    if reference is None:
        ref_et = now_et()
    else:
        ref_et = to_et(reference)

    return ref_et.replace(
        hour=MARKET_OPEN_HOUR,
        minute=MARKET_OPEN_MINUTE,
        second=0,
        microsecond=0
    )


def get_market_close_today(reference: Optional[datetime] = None) -> datetime:
    """
    Get today's market close time (4:00 PM ET).

    Args:
        reference: Optional reference datetime (defaults to now)

    Returns:
        ET-aware datetime for today's market close
    """
    if reference is None:
        ref_et = now_et()
    else:
        ref_et = to_et(reference)

    return ref_et.replace(
        hour=MARKET_CLOSE_HOUR,
        minute=MARKET_CLOSE_MINUTE,
        second=0,
        microsecond=0
    )


def get_trading_session_range(reference: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Get the market open and close times for the trading session.

    Args:
        reference: Optional reference datetime (defaults to now)

    Returns:
        Tuple of (market_open, market_close) as ET-aware datetimes
    """
    return get_market_open_today(reference), get_market_close_today(reference)


def is_trading_day(dt: datetime) -> bool:
    """
    Check if the date is a potential trading day (weekday).

    Note: This does not account for market holidays.

    Args:
        dt: Timezone-aware datetime to check

    Returns:
        True if Monday-Friday, False if Saturday-Sunday

    Raises:
        ValueError: If datetime is naive
    """
    validate_aware(dt, "is_trading_day")
    et_time = dt.astimezone(ET)
    return et_time.weekday() < 5


# =============================================================================
# Formatting Functions
# =============================================================================

def format_et(dt: datetime, fmt: str = '%Y-%m-%d %H:%M:%S %Z') -> str:
    """
    Format datetime in Eastern Time for display.

    Args:
        dt: Timezone-aware datetime
        fmt: strftime format string (default includes timezone)

    Returns:
        Formatted string in ET

    Raises:
        ValueError: If datetime is naive
    """
    return to_et(dt).strftime(fmt)


def format_utc(dt: datetime, fmt: str = '%Y-%m-%dT%H:%M:%SZ') -> str:
    """
    Format datetime in UTC (ISO format by default).

    Args:
        dt: Timezone-aware datetime
        fmt: strftime format string (default is ISO 8601)

    Returns:
        Formatted string in UTC

    Raises:
        ValueError: If datetime is naive
    """
    return to_utc(dt).strftime(fmt)


def format_for_display(dt: datetime) -> str:
    """
    Format datetime for user-facing display (ET, human-readable).

    Args:
        dt: Timezone-aware datetime

    Returns:
        Human-readable string like "Jan 29, 2024 10:30 AM ET"

    Raises:
        ValueError: If datetime is naive
    """
    return to_et(dt).strftime('%b %d, %Y %I:%M %p ET')


def isoformat_utc(dt: datetime) -> str:
    """
    Return ISO format string in UTC.

    Use this for API responses and JSON serialization.

    Args:
        dt: Timezone-aware datetime

    Returns:
        ISO 8601 formatted string with Z suffix

    Raises:
        ValueError: If datetime is naive
    """
    return to_utc(dt).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def isoformat_et(dt: datetime) -> str:
    """
    Return ISO format string in ET with offset.

    Args:
        dt: Timezone-aware datetime

    Returns:
        ISO 8601 formatted string with ET offset (e.g., -05:00 or -04:00)

    Raises:
        ValueError: If datetime is naive
    """
    return to_et(dt).isoformat()
