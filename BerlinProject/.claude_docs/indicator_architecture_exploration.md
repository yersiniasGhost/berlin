# Indicator Architecture Exploration - Complete Findings

> Generated: 2026-01-30 | Brainstorming Session

## 1. INDICATOR DEFINITIONS & CLASSIFICATION

**Location: `/src/indicator_triggers/indicator_base.py`**

The codebase implements a sophisticated indicator type system with two main categories:

```python
class IndicatorType(Enum):
    SIGNAL = "signal"    # Traditional trigger indicators (crossovers, patterns, etc.)
    TREND = "trend"      # Trend direction/strength indicators (ADX, EMA slope, etc.)
```

**Key Architecture Components:**

- **BaseIndicator**: Abstract base class for all indicators
  - Method: `get_indicator_type()` returns `IndicatorType.SIGNAL` by default
  - Method: `get_indicator_type()` can be overridden to return `IndicatorType.TREND`
  - All indicators return `(np.ndarray, Dict[str, np.ndarray])` from `calculate()` method

- **IndicatorRegistry**: Singleton that manages available indicators
  - Method: `get_available_indicators(indicator_type: Optional[IndicatorType])` - filters by type
  - Method: `get_signal_indicators()` - returns only SIGNAL type indicators
  - Method: `get_trend_indicators()` - returns only TREND type indicators

## 2. TREND INDICATORS IMPLEMENTATION

**Location: `/src/indicator_triggers/trend_indicators.py`**

Four concrete TrendIndicator implementations exist:

1. **ADXTrendIndicator** - ADX + DI-based trend strength and direction
2. **EMASlopeTrendIndicator** - EMA slope for trend direction
3. **SuperTrendIndicator** - ATR-based dynamic bands
4. **AROONTrendIndicator** - AROON oscillator for trend changes

**All TrendIndicators:**
- Override `get_indicator_type()` to return `IndicatorType.TREND`
- Use direction_filter parameter ("Both", "Bull", "Bear")
- Return (values, components_dict) where values are trend strength/direction
- All registered with IndicatorRegistry at module load time

## 3. INDICATOR CATEGORIZATION IN UI

**Current UI Architecture:**

The Monitor Configuration Editor has THREE distinct indicator sections:

1. **Indicators Tab** - Global indicator definitions (all types mixed)
2. **Bars Tab** - Signal Indicators + Trend Indicators (Gate) as separate sections
3. **Trade Executor Tab** - Trade execution settings

### Bar Structure:
- **Signal Indicators** (`.bar-indicators-container`) - Traditional signal triggers
- **Trend Indicators (Gate)** (`.trend-indicators-section`) - Gate/filter modulating signals

## 4. CURRENT STATE ASSESSMENT

| Aspect | Status |
|--------|--------|
| Type system design | ✅ Well-designed with clear distinction |
| TrendIndicator implementations | ✅ Fully implemented (4 types) |
| Backend models | ✅ Support trend gating perfectly |
| UI trend gate section | ✅ Dedicated section exists |
| Dropdown filtering by type | ⚠️ **Not implemented** - shows all indicators |
| Visual type distinction | ⚠️ **Not implemented** - no badges/icons |
| Add Indicator form | ⚠️ **Mixed types** - no separation |

## 5. KEY FILES

| File | Purpose |
|------|---------|
| `indicator_triggers/indicator_base.py` | IndicatorType enum, BaseIndicator, Registry |
| `indicator_triggers/trend_indicators.py` | 4 TrendIndicator implementations |
| `models/monitor_configuration.py` | MonitorConfiguration model |
| `visualization_apps/templates/monitor_config/main.html` | Monitor config UI |
| `visualization_apps/static/js/monitor-config.js` | Indicator/bar rendering |
| `visualization_apps/static/js/config-utils.js` | Trend indicator utilities |
