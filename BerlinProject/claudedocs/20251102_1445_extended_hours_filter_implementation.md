# Extended Hours Filter Implementation

**Date**: 2025-11-02
**Feature**: Include Extended Hours Checkbox for Data Config
**Status**: ✅ Implemented and Tested

## Overview

Added a checkbox to both **Optimizer** and **Replay** visualization UIs that allows users to filter out extended trading hours (pre-market and after-hours) data when analyzing trading strategies.

## Trading Hours Definition

- **Regular Market Hours**: 9:30 AM - 4:00 PM ET (NYSE/NASDAQ)
- **Extended Hours (Filtered)**:
  - **Pre-market**: Before 9:30 AM ET
  - **After-hours**: 4:00 PM ET and later

## Implementation Details

### 1. User Interface Changes

#### Optimizer UI (`src/visualization_apps/templates/optimizer/main.html`)
- Added checkbox in Data Config tab (line 334-342)
- Field ID: `dataExtendedHours`
- Default: Checked (true) for backward compatibility
- Helper text explains filtering behavior

#### Replay UI (`src/visualization_apps/templates/replay/main.html`)
- Added identical checkbox in Data Config section (line 309-317)
- Same field ID and behavior as Optimizer

### 2. JavaScript Configuration

#### Optimizer Config (`src/visualization_apps/static/js/optimizer-config.js`)
- Updated `collectDataConfigData()` to collect checkbox state (line 1320)
- Updated `renderDataConfiguration()` to set checkbox from loaded config (line 201)
- Updated `DEFAULT_DATA_CONFIG` to include field with default `true` (line 39)

#### Replay Config (`src/visualization_apps/static/js/replay-config.js`)
- Updated `collectDataConfigData()` to collect checkbox state (line 871)
- Updated `renderDataConfiguration()` to set checkbox from loaded config (line 152)
- Updated `DEFAULT_DATA_CONFIG` to include field with default `true` (line 17)

### 3. Core Data Processing

#### CandleAggregator Base Class (`src/candle_aggregator/candle_aggregator.py`)

**Constructor Update** (line 14):
```python
def __init__(self, symbol: str, timeframe: str, include_extended_hours: bool = True):
    # ... existing code ...
    self.include_extended_hours = include_extended_hours
```

**Trading Hours Check Method** (line 60-88):
```python
def _is_trading_hours(self, timestamp: datetime) -> bool:
    """Check if timestamp is during regular trading hours (9:30 AM - 4:00 PM ET)"""
    hour = timestamp.hour
    minute = timestamp.minute

    # Before 9:30 AM = pre-market
    if hour < 9 or (hour == 9 and minute < 30):
        return False

    # After 4:00 PM = after-hours
    if hour >= 16:
        return False

    return True
```

**Tick Processing Filter** (line 90-103):
```python
def process_tick(self, tick_data: TickData) -> Optional[TickData]:
    """Process tick and return completed candle if timeframe ended"""
    # Filter extended hours if configured
    if not self.include_extended_hours and not self._is_trading_hours(tick_data.timestamp):
        return None  # Skip this tick - outside regular trading hours

    # ... existing candle processing logic ...
```

#### CSAContainer (`src/candle_aggregator/csa_container.py`)

**Extract Config** (line 18):
```python
self.include_extended_hours = data_config.get('include_extended_hours', True)
```

**Pass to Aggregators** (line 39-41):
```python
if agg_type == "heiken":
    aggregator = CAHeiken(self.ticker, timeframe, self.include_extended_hours)
else:
    aggregator = CANormal(self.ticker, timeframe, self.include_extended_hours)
```

#### DataStreamer (`src/data_streamer/data_streamer.py`)

**Constructor Parameter** (line 28):
```python
def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration,
             include_extended_hours: bool = True):
    # ... existing code ...
    self.include_extended_hours = include_extended_hours
```

**Aggregator Creation** (line 103-105):
```python
if agg_type == "heiken":
    return CAHeiken(symbol, timeframe, self.include_extended_hours)
else:
    return CANormal(symbol, timeframe, self.include_extended_hours)
```

### 4. Configuration Schema

#### Data Config JSON Format
```json
{
  "ticker": "PLTR",
  "start_date": "2025-01-30",
  "end_date": "2025-08-11",
  "include_extended_hours": true
}
```

**Updated Example Files**:
- `src/optimization/genetic_optimizer/apps/inputs/data_config.json`
- `src/optimization/genetic_optimizer/apps/inputs/data_config_nvda.json`

## Test Results

### Test Script: `scripts/test_extended_hours_filter.py`

**Test Data**: PLTR, 2025-01-30 to 2025-02-01

**Results**:
```
Total Ticks: 1,776

Time Distribution:
  Pre-Market  (< 9:30 AM):   909 ticks (51.2%)
  Regular Hours (9:30-4:00): 755 ticks (42.5%)
  After-Hours (>= 4:00 PM):  112 ticks (6.3%)

With Extended Hours:    1,775 candles
Without Extended Hours:   754 candles
Difference:             1,021 candles (matches pre-market + after-hours)

✅ All 4 validation checks PASSED
```

**Validation Checks**:
1. ✅ Filtered version has fewer candles
2. ✅ Filtered tick count matches expected range
3. ✅ Extended hours version includes all data
4. ✅ Regular hours version only includes 9:30 AM - 4:00 PM data

## Usage

### Optimizer Workflow

1. Navigate to Optimizer visualization
2. Click on **Data Config** tab
3. Enter ticker, start date, end date
4. **Check/Uncheck** "Include Extended Hours" checkbox:
   - **Checked** (default): Includes all hours (pre-market, regular, after-hours)
   - **Unchecked**: Only uses regular market hours (9:30 AM - 4:00 PM ET)
5. Click "Save Configurations"
6. Run genetic algorithm optimization

### Replay Workflow

1. Navigate to Replay visualization
2. Load monitor configuration
3. In Data Config section:
   - Enter ticker, start date, end date
   - **Check/Uncheck** "Include Extended Hours" checkbox
4. Click "Save and Download Configurations"
5. Run replay visualization

### Programmatic Usage

```python
from candle_aggregator.candle_aggregator_normal import CANormal

# Include extended hours (default)
agg_with_extended = CANormal("PLTR", "1m", include_extended_hours=True)

# Regular hours only
agg_regular_only = CANormal("PLTR", "1m", include_extended_hours=False)

# Process ticks
for tick in ticks:
    completed_candle = agg_regular_only.process_tick(tick)
    # Ticks outside 9:30 AM - 4:00 PM will be filtered
```

## Backward Compatibility

✅ **Fully Backward Compatible**

- Default value: `include_extended_hours = True`
- Existing configs without the field will default to `True`
- No changes required to existing workflows
- Existing data files continue to work without modification

## File Changes Summary

| File | Type | Lines Changed |
|------|------|---------------|
| `templates/optimizer/main.html` | UI | +8 |
| `templates/replay/main.html` | UI | +8 |
| `static/js/optimizer-config.js` | Config | +3 |
| `static/js/replay-config.js` | Config | +3 |
| `candle_aggregator/candle_aggregator.py` | Core | +35 |
| `candle_aggregator/csa_container.py` | Integration | +4 |
| `data_streamer/data_streamer.py` | Integration | +4 |
| `data_config.json` (examples) | Config | +2 each |
| `scripts/test_extended_hours_filter.py` | Test | +370 (new) |

**Total**: ~450 lines added/modified across 9 files

## Performance Impact

- **Negligible**: Filtering happens at tick processing level with O(1) time check
- **Memory**: Reduced memory usage when filtering is enabled (fewer candles stored)
- **Processing**: Minimal overhead - single timestamp comparison per tick

## Known Limitations

1. **Timezone Assumption**: Currently assumes timestamps are in ET (Eastern Time)
   - Future enhancement: Add timezone conversion support
2. **Holiday Calendar**: Does not account for market holidays
   - Regular hours filter still applies on holidays
3. **Partial Trading Days**: Early close days (e.g., day before Thanksgiving) still use standard 4:00 PM cutoff

## Future Enhancements

1. **Timezone Detection**: Automatic timezone conversion from data source
2. **Holiday Calendar Integration**: NYSE/NASDAQ holiday calendar support
3. **Custom Hours**: Allow user-defined trading hour ranges
4. **Visual Indicator**: Show filtered tick count in UI
5. **Per-Aggregator Settings**: Different extended hours settings per timeframe

## Testing Checklist

- [x] UI checkbox renders correctly in Optimizer
- [x] UI checkbox renders correctly in Replay
- [x] Checkbox state persists when loading configurations
- [x] Data config JSON includes field when saved
- [x] CandleAggregator correctly filters pre-market ticks
- [x] CandleAggregator correctly filters after-hours ticks
- [x] Regular hours candles remain unaffected
- [x] Backward compatibility maintained
- [x] Test script validates all filtering logic
- [x] Example config files updated

## Related Files

- Implementation: `src/candle_aggregator/candle_aggregator.py`
- Test Script: `scripts/test_extended_hours_filter.py`
- UI Templates: `src/visualization_apps/templates/{optimizer,replay}/main.html`
- Config Scripts: `src/visualization_apps/static/js/{optimizer,replay}-config.js`
- Documentation: This file

## Support

For issues or questions about this feature:
1. Check test script output: `conda activate mlf && python scripts/test_extended_hours_filter.py`
2. Verify data config JSON includes `"include_extended_hours"` field
3. Review implementation in `candle_aggregator.py` for filtering logic
