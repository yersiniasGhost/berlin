# Stock Analysis UI - Indicator Usage Analysis

> Generated: 2026-01-30 | Brainstorming Session

## Executive Summary

**stock_analysis_ui is a FULL-FEATURED live trading interface** that:
- Loads ANY monitor configuration (via JSON upload)
- Calculates ALL indicators from IndicatorRegistry
- Displays them in real-time via WebSocket
- Has NO backend restrictions on which indicators are allowed

**The only limitation is artificial**: The `monitor_creation.html` wizard hardcodes only 3 indicators, but users can bypass this by uploading configs created elsewhere.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    stock_analysis_ui                         │
├─────────────────────────────────────────────────────────────┤
│  monitor_creation.html (WIZARD)                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Hardcoded: sma_crossover, macd_histogram, bol_bands │    │
│  │ ⚠️ LIMITATION: Only 3 indicators available          │    │
│  └─────────────────────────────────────────────────────┘    │
│                          ↓                                   │
│                   JSON Configuration                         │
│                          ↓                                   │
├─────────────────────────────────────────────────────────────┤
│  Backend (app_service.py, api_routes.py)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Uses IndicatorRegistry - ALL indicators supported   │    │
│  │ ✅ NO hardcoded limits                              │    │
│  └─────────────────────────────────────────────────────┘    │
│                          ↓                                   │
├─────────────────────────────────────────────────────────────┤
│  card_details.html (DASHBOARD)                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Displays ANY indicators from loaded config          │    │
│  │ ✅ Full charting: MACD, Trigger, Overlay types      │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Indicator Data Flow

```
MonitorConfiguration (JSON)
       ↓
AppService.add_combination()
       ↓
DataStreamer(monitor_config=config)
       ↓
IndicatorProcessor.calculate_indicators()  ← Uses IndicatorRegistry
       ↓
API: /api/combinations/<card_id>/details
       ↓
card_details.html renders charts
```

## Key Files

| File | Purpose | Indicator Handling |
|------|---------|-------------------|
| `templates/monitor_creation.html` | Creation wizard | ⚠️ 3 hardcoded indicators |
| `templates/card_details.html` | Live dashboard | ✅ Any indicator from config |
| `routes/api_routes.py` | API endpoints | ✅ Uses IndicatorRegistry |
| `static/js/indicator-charts.js` | Chart rendering | ✅ All chart types |
| `app_service.py` | Core logic | ✅ Loads any MonitorConfiguration |

## Comparison: What Users See

| Scenario | Available Indicators |
|----------|---------------------|
| Create via wizard | Only 3 (hardcoded) |
| Upload JSON config | ALL from IndicatorRegistry |
| View in dashboard | ALL from loaded config |

## Recommendation

**Option A: Full migration to API-driven forms is REQUIRED** because:

1. **Trading interface needs all tools** - Limiting traders to 3 indicators is arbitrary
2. **Backend already supports it** - No code changes needed in calculation layer
3. **User workaround exists** - They can create configs in visualization_apps and upload
4. **Consistency** - Same indicator experience across all UIs
5. **TrendIndicators** - Currently impossible to add via wizard, but backend supports them

## Implementation Impact

### What Changes:
- `monitor_creation.html` JavaScript (~1100 lines to refactor)
- Replace `indicatorFunctions` object with API fetch
- Use shared `indicator-form-handler.js`

### What Stays Same:
- `card_details.html` - No changes needed
- `api_routes.py` - No changes needed
- `indicator-charts.js` - No changes needed
- All backend calculation logic - No changes needed
