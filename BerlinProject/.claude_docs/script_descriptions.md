# Script Descriptions

Documentation for debug and utility scripts in the `scripts/` directory.

## test_alignment_fix_debug.py

**Purpose**: Verifies the timestamp-based alignment fix for multi-timeframe indicators in `indicator_processor_historical_new.py`.

**What it tests**:
- Creates test candle data with simulated market gaps
- Compares old index-based alignment vs new timestamp-based alignment
- Demonstrates that index-based alignment fails when candle ratios aren't constant (due to market gaps)
- Shows that timestamp-based alignment correctly maps 1m candles to their containing 5m candles

**Usage**:
```bash
conda run -n mlf python scripts/test_alignment_fix_debug.py
```

**Background**: The original alignment code used `5m_idx = 1m_idx / 5` which breaks when market gaps cause the candle ratio to deviate from exactly 5:1. For example, a 30-minute lunch gap means fewer 1m candles than expected, causing indices to drift and return stale indicator values.

## migrate_polygon_timezone_fix.py

**Purpose**: Fixes timezone data corruption in the `tick_history_polygon` MongoDB collection where timestamps were incorrectly stored in Pacific Time instead of Eastern Time.

**Problem**: The original Polygon data fetch code used `datetime.fromtimestamp()` which converts UTC timestamps to the server's local timezone (Pacific). This caused all `seconds_from_midnight` keys to be 3 hours behind (PT vs ET).

**What it does**:
- Shifts all time keys by +10800 seconds (3 hours) to convert from PT to ET
- Handles day boundary crossings (times >= 86400 roll to next day)
- Handles month boundary crossings (day 31 -> day 1 of next month)
- Merges cross-month data into existing or new documents

**Usage**:
```bash
# Preview changes without modifying database
python scripts/migrate_polygon_timezone_fix.py --dry-run

# Execute migration
python scripts/migrate_polygon_timezone_fix.py

# Verbose mode (shows each change)
python scripts/migrate_polygon_timezone_fix.py --verbose

# Verify results after migration
python scripts/migrate_polygon_timezone_fix.py --verify

# Test with limited documents
python scripts/migrate_polygon_timezone_fix.py --dry-run --limit 5
```

**Safety**: Always run with `--dry-run` first to preview changes.
