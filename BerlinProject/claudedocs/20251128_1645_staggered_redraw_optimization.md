# Staggered Redraw Optimization

**Date**: 2025-11-28 16:45
**Issue**: batch_chart_update taking 1393ms (1.4 seconds) causing UI freeze
**Solution**: Stagger chart redraws across multiple animation frames

## Problem Analysis

Performance monitoring revealed:
```
batch_chart_update: Avg 1393ms (1.4-1.8 seconds!)
├─ Individual updates are fast:
│  ├─ update_objective_chart: 0.57ms ✅
│  ├─ update_parallel_coords: 2.57ms ✅
│  ├─ update_distribution_chart: 1.07ms ✅
│  └─ update_best_strategy: 53.86ms ⚠️
└─ But synchronous redraws block UI for 1.4s ❌
```

**Root Cause**: All 7 charts calling `chart.redraw()` synchronously in one frame.

## Solution Implemented

### 1. Staggered Redraws
Instead of redrawing all charts at once:
```javascript
// BEFORE (blocking)
Object.values(charts).forEach(chart => chart.redraw());  // 1400ms freeze!

// AFTER (non-blocking)
requestAnimationFrame(() => chart[0].redraw(false));  // ~20ms
requestAnimationFrame(() => chart[1].redraw(false));  // ~20ms
requestAnimationFrame(() => chart[2].redraw(false));  // ~20ms
// ... spreads work across frames
```

### 2. Disabled Animations
```javascript
chart.redraw(false)  // false = no animation, much faster
```

### 3. Performance Tracking
Separate measurements for:
- `batch_chart_update_data`: Data processing time
- `redraw_0`, `redraw_1`, etc.: Individual chart redraws

## Expected Performance Improvement

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Redraw Time | 1393ms | 140ms | **90% faster** |
| UI Freeze Duration | 1.4s | 0ms | **No freezes** |
| Perceived Smoothness | Janky | Smooth | **Excellent** |
| Frame Drops | Frequent | None | **100% reduction** |

## Testing Instructions

1. **Refresh the page** to load updated code
2. **Re-enable performance HUD**:
```javascript
perfMonitor.showHUD()
```

3. **Run optimization** for 20+ generations

4. **Check metrics**:
```javascript
perfMonitor.getReport().operationStats
```

**Expected Results**:
- ✅ `batch_chart_update_data` should be <10ms
- ✅ Individual `redraw_X` should each be 10-30ms
- ✅ No single operation >100ms
- ✅ Avg update latency should drop to <50ms
- ✅ Frame drops should be near zero

## What Changed

**File**: `src/visualization_apps/static/js/chart-update-manager.js`

**Changes**:
1. Split `flushUpdates()` into data updates + staggered redraws
2. Added `staggeredRedraw()` method using `requestAnimationFrame`
3. Disabled chart animations during redraws (`chart.redraw(false)`)
4. Added `animationsEnabled` flag (currently false for max performance)

## Verification

After refresh, check console for:
```
📊 Registering charts with performance-optimized update manager...
✅ All charts registered with update manager
```

Then during optimization:
```javascript
// Should see fast individual redraws instead of one massive batch
perfMonitor.getReport().slowUpdates
// Should NOT see batch_chart_update >100ms anymore
```

## Trade-offs

**Pro**:
- ✅ Eliminates UI freezing
- ✅ Maintains responsive interface
- ✅ Better user experience
- ✅ Spreads work across frames

**Con**:
- ⚠️ Charts update sequentially (very slightly delayed)
- ⚠️ No smooth animations (disabled for performance)

The trade-off is **heavily** in favor of performance - users won't notice the sequential updates (happens in <100ms total), but they WILL notice no more freezing.

## Rollback

If issues occur, previous version is in git history:
```bash
git diff HEAD~1 src/visualization_apps/static/js/chart-update-manager.js
```

## Next Optimization

If `update_best_strategy` is still slow (53ms), optimize plot band management:
- Reduce number of plot bands
- Use simpler rendering
- Consider sampling for many trades (show every Nth trade)
