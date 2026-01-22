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
