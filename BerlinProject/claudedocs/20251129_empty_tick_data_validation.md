# Empty TICK Data Validation Fix

## Problem
When selecting random data streamers for new EPOCHs during genetic algorithm optimization with data splits, streamers with empty TICK data could be selected, causing downstream failures.

## Root Cause
In `src/optimization/genetic_optimizer/apps/utils/mlf_optimizer_config.py`, BacktestDataStreamer objects were unconditionally added to the `backtest_streamers` list after initialization, regardless of whether they contained any tick data.

## Solution Applied
Instead of filtering streamers during selection, we now **prevent creation** of invalid streamers at the source.

### File: `src/optimization/genetic_optimizer/apps/utils/mlf_optimizer_config.py` (lines 53-77)

**Before:**
```python
for split_config in dc.split_configs:
    csa = CSAContainer(split_config, aggregator_list)
    streamer = BacktestDataStreamer()
    streamer.initialize(csa.get_aggregators(), split_config, self.monitor_config)
    backtest_streamers.append(streamer)  # Always added, even if empty!
```

**After:**
```python
for split_config in dc.split_configs:
    csa = CSAContainer(split_config, aggregator_list)
    streamer = BacktestDataStreamer()
    streamer.initialize(csa.get_aggregators(), split_config, self.monitor_config)

    # Only add streamer if it has non-empty TICK data
    if streamer.tick_history and len(streamer.tick_history) > 0:
        backtest_streamers.append(streamer)
    else:
        error_msg = (
            f"ERROR: Skipping data streamer for {split_config.ticker} "
            f"({split_config.start_date} to {split_config.end_date}) - "
            f"TICK data is empty. This split will not be used for training."
        )
        logger.error(error_msg)
        print(f"⚠️  {error_msg}")

# Validate we have at least one valid streamer
if not backtest_streamers:
    raise ValueError(
        f"ERROR: No valid data streamers created. All {len(dc.split_configs)} splits had empty TICK data. "
        f"Cannot proceed with optimization without training data."
    )

logger.info(f"Created {len(backtest_streamers)} valid data streamers out of {len(dc.split_configs)} splits")
```

## Benefits

1. **Prevention over Detection**: Invalid streamers are never created, eliminating the need for downstream validation
2. **Clear Error Messages**: Users immediately see which data splits have empty tick data with ticker and date range information
3. **Fail-Fast**: If ALL splits have empty data, the system raises a ValueError immediately rather than failing later during optimization
4. **Logging**: Both logger and console output provide visibility into data quality issues
5. **No Selection Logic Changes**: The `_select_random_streamer()` method remains simple since it only works with valid streamers

## Behavior

When a data split has empty tick_history:
- ⚠️ An ERROR message is logged and printed to console
- The streamer is **not added** to the available pool
- Processing continues with remaining splits

When ALL splits have empty tick_history:
- A ValueError is raised immediately
- Clear message indicates no valid training data exists
- Optimization cannot proceed (fail-fast)

## Impact

- Genetic algorithm optimizer will only use data splits with valid tick data
- Users get immediate feedback about data quality issues
- No silent failures or mysterious errors during EPOCH selection
