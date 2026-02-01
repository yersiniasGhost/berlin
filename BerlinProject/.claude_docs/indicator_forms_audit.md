# Indicator Forms Audit - Cross-UI Analysis

> Generated: 2026-01-30 | Brainstorming Session

## Executive Summary

| UI | Form Type | Indicator Source | Duplication Level |
|----|-----------|------------------|-------------------|
| visualization_apps/monitor-config | API-driven dynamic | IndicatorRegistry API | 40-50% with siblings |
| visualization_apps/replay-config | API-driven dynamic | IndicatorRegistry API | 40-50% with siblings |
| visualization_apps/optimizer-config | API-driven dynamic | IndicatorRegistry API | 40-50% with siblings |
| stock_analysis_ui | Hardcoded | 3 indicators only | N/A (standalone) |

## 1. VISUALIZATION_APPS (Modern Pattern)

### Files Involved:
- `static/js/monitor-config.js` - Monitor configuration editor
- `static/js/replay-config.js` - Replay configuration editor
- `static/js/optimizer-config.js` - Optimization page editor
- `static/js/config-utils.js` - Shared utilities (22KB)

### Pattern:
```javascript
// Fetch indicator classes from API
const response = await fetch('/monitor_config/api/get_indicator_classes');
const indicatorClasses = await response.json();

// Generate dropdown options dynamically
function generateIndicatorClassOptions(indicatorClasses) {
    return Object.keys(indicatorClasses)
        .map(cls => `<option value="${cls}">${cls}</option>`)
        .join('');
}
```

### Duplicated Functions (across 3 files):
- `loadIndicatorClasses()` - Fetches from API
- `addIndicator()` - Adds indicator row to UI
- `generateIndicatorClassOptions()` - Generates dropdown HTML
- `updateIndicatorParams()` - Renders parameter inputs
- `generateBarHtml()` - Bar card generation
- `collectIndicatorData()` - Collects form data

## 2. STOCK_ANALYSIS_UI (Legacy Pattern)

### Files Involved:
- `templates/monitor_creation.html` - ~1100 lines inline JS
- Hardcoded `indicatorFunctions` object

### Pattern:
```javascript
// Hardcoded indicators (ONLY 3 available)
const indicatorFunctions = {
    sma_crossover: {
        name: "SMA Crossover",
        params: { short_period: 10, long_period: 20 }
    },
    macd_histogram_crossover: { ... },
    bol_bands_lower_band_bounce: { ... }
};
```

### Limitations:
- Cannot add new indicators without code changes
- No TrendIndicator support at all
- No API integration
- Completely separate from visualization_apps

## 3. SHARED UTILITIES

### Currently Shared (`config-utils.js`):
- `generateTrendIndicatorsSectionHtml()` - Trend gate UI
- `generateTrendIndicatorRowHtml()` - Trend row template
- `collectTrendIndicatorData()` - Collects trend config
- `buildBarConfigFromUI()` - Builds bar config

### Not Shared (Duplicated):
- All indicator class loading/rendering
- All "Add Indicator" button handlers
- All parameter form generation
- All dropdown population logic

## 4. API ENDPOINTS

| Endpoint | Used By | Returns |
|----------|---------|---------|
| `/monitor_config/api/get_indicator_classes` | visualization_apps | All indicator schemas |
| `/api/indicators/schemas` | features module | Same data, different path |
| (none) | stock_analysis_ui | Hardcoded only |

### Current Response Structure:
```json
{
  "SMA": {
    "indicator_type": "signal",
    "parameter_groups": [...],
    "layout_type": "overlay"
  },
  "ADXTrendIndicator": {
    "indicator_type": "trend",
    "parameter_groups": [...],
    "layout_type": "stacked"
  }
}
```

**Note**: `indicator_type` field already exists in API response!

## 5. CONSOLIDATION OPPORTUNITIES

### Priority 1: Extract Shared Form Handler
Create `static/js/indicator-form-handler.js`:
- `loadIndicatorClasses(filterType)` - With optional type filter
- `renderIndicatorForm(container, indicatorClass)` - Unified form rendering
- `generateIndicatorDropdown(classes, selectedValue)` - Dropdown generation
- `collectIndicatorFormData(container)` - Data collection

### Priority 2: Add Type Filtering to API
Modify `/monitor_config/api/get_indicator_classes`:
- Accept `?type=signal` or `?type=trend` parameter
- Return filtered results

### Priority 3: Migrate stock_analysis_ui
Replace hardcoded indicators with API-driven approach using shared handler.

## 6. SIGNAL/TREND SEPARATION REQUIREMENTS

Based on user requirements:
1. **Two buttons**: "Add Signal Indicator" + "Add Trend Indicator"
2. **Filtered dropdowns**: Show only appropriate type in each context
3. **Bar sections**: Signal indicators in signal section, Trend in gate section
4. **Prevention**: Filtering eliminates wrong-type additions

## 7. IMPLEMENTATION CHECKLIST

### Backend:
- [ ] Add `?type=signal|trend` filter to API endpoint
- [ ] (Optional) Create `/api/indicators/signal` and `/api/indicators/trend`

### Shared JavaScript:
- [ ] Create `indicator-form-handler.js` with type-aware loading
- [ ] Export `loadSignalIndicators()` and `loadTrendIndicators()`
- [ ] Create separate button handlers for each type

### visualization_apps:
- [ ] Update monitor-config.js to use shared handler
- [ ] Update replay-config.js to use shared handler
- [ ] Update optimizer-config.js to use shared handler
- [ ] Add "Add Signal Indicator" button
- [ ] Add "Add Trend Indicator" button
- [ ] Filter bar signal dropdown to signal type
- [ ] Filter bar trend dropdown to trend type

### stock_analysis_ui:
- [ ] Migrate from hardcoded to API-driven
- [ ] Use shared indicator-form-handler.js
- [ ] Add both indicator type buttons
