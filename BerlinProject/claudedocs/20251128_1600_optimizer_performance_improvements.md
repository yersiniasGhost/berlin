# Optimizer Visualization Performance Improvements

**Date**: 2025-11-28
**Issue**: Page becomes unresponsive during optimization due to excessive data processing and DOM manipulation

## Performance Bottlenecks Identified

### 1. **Massive WebSocket Payloads** (CRITICAL)
**Location**: `src/visualization_apps/routes/optimizer_routes.py:1074-1090`

**Problem**:
- Every `generation_complete` event sends the ENTIRE `best_individuals_log` (grows with each generation)
- Full chart data regenerated and sent every generation
- Payload size grows linearly: Gen 100 sends 100x more data than Gen 1

**Impact**:
- Network bandwidth saturation
- JSON parsing overhead increases exponentially
- Memory pressure on client

**Solution**: Send only incremental/delta data
```python
# BEFORE (sends everything)
'best_individuals_log': opt_state.get('best_individuals_log', [])

# AFTER (send only new data)
'new_best_individual': best_individual,
'generation': current_gen
```

### 2. **Chart Destruction on Every Update** (CRITICAL)
**Location**: `src/visualization_apps/templates/optimizer/main.html:728-731`

**Problem**:
```javascript
if (charts.parallelCoords) {
    charts.parallelCoords.destroy();  // Destroys entire chart
}
// Then recreates from scratch
```

**Impact**:
- DOM thrashing (destroy → garbage collect → recreate → reflow)
- 100+ ms per update on complex charts

**Solution**: Update chart data in-place
```javascript
// Use chart.update() or series.setData() instead of destroy/recreate
charts.parallelCoords.series.forEach((series, index) => {
    series.setData(normalizedData[index], false);
});
charts.parallelCoords.redraw();
```

### 3. **Plot Band Recreation** (HIGH)
**Location**: `src/visualization_apps/templates/optimizer/main.html:868-946`

**Problem**:
- Removes ALL plot bands on every update
- Recreates ALL plot bands from scratch
- O(n²) complexity with many trades

**Impact**:
- Expensive DOM operations
- Layout thrashing
- Cumulative slowdown

**Solution**: Track existing plot bands and update only changed ones

### 4. **Synchronous Blocking Updates** (HIGH)
**Location**: `src/visualization_apps/templates/optimizer/main.html:661-966`

**Problem**:
- All chart updates happen synchronously in main thread
- No debouncing or throttling
- Blocks UI during processing

**Impact**:
- Browser "Page Unresponsive" warnings
- Janky animations
- Frozen UI during updates

**Solution**: Debounce updates + Web Workers for data processing

### 5. **Redundant Data Processing** (MEDIUM)
**Location**: `src/visualization_apps/templates/optimizer/main.html:739-757`

**Problem**:
- Data normalization recalculated every update
- No memoization or caching
- Recalculates ranges even when data unchanged

**Impact**:
- Wasted CPU cycles
- Increased update latency

**Solution**: Cache computed ranges and normalize only new data

### 6. **No Update Batching** (MEDIUM)
**Location**: `src/visualization_apps/static/js/optimizer-ui-integration.js:178-221`

**Problem**:
- WebSocket events trigger immediate chart updates
- Multiple updates can queue up
- No coalescence of rapid updates

**Impact**:
- Redundant rendering
- Frame drops
- Memory pressure

**Solution**: Batch updates with requestAnimationFrame

## Recommended Optimizations

### Priority 1: Incremental Data Transmission

**Backend Changes** (`optimizer_routes.py`):
```python
# Only send incremental updates
socketio.emit('generation_complete', {
    'generation': current_gen,
    'total_generations': genetic_algorithm.number_of_generations,

    # Send only new data points
    'new_objective_values': dict(zip(objectives, metrics)),
    'new_elite': {
        'objectives': elite_objectives,
        'parameters': best_individual
    },

    # Send deltas for charts
    'chart_updates': {
        'objective_evolution': {
            obj: [[current_gen, value]]
            for obj, value in zip(objectives, metrics)
        }
    },

    # Full data only on request or major milestones
    'full_refresh': current_gen % 10 == 0  # Every 10 generations
})
```

### Priority 2: Debounced Chart Updates

**Create**: `src/visualization_apps/static/js/optimizer-chart-manager.js`
```javascript
class ChartUpdateManager {
    constructor() {
        this.pendingUpdates = {};
        this.updateScheduled = false;
        this.charts = {};
    }

    scheduleUpdate(chartName, data) {
        // Collect updates
        this.pendingUpdates[chartName] = data;

        // Debounce with requestAnimationFrame
        if (!this.updateScheduled) {
            this.updateScheduled = true;
            requestAnimationFrame(() => this.flushUpdates());
        }
    }

    flushUpdates() {
        const updates = this.pendingUpdates;
        this.pendingUpdates = {};
        this.updateScheduled = false;

        // Batch all chart updates
        Object.entries(updates).forEach(([chartName, data]) => {
            this.updateChartIncremental(chartName, data);
        });
    }

    updateChartIncremental(chartName, data) {
        const chart = this.charts[chartName];
        if (!chart) return;

        // Update without redraw
        chart.series[0].addPoint(data, false, data.length > 1000);

        // Single redraw at end
        if (Object.keys(this.pendingUpdates).length === 0) {
            chart.redraw();
        }
    }
}
```

### Priority 3: Efficient Chart Updates

**Update**: `src/visualization_apps/templates/optimizer/main.html`
```javascript
function updateCharts(chartData) {
    // Prevent concurrent updates
    if (this.updateInProgress) {
        this.pendingUpdate = chartData;
        return;
    }

    this.updateInProgress = true;

    try {
        // Batch updates without redraw
        updateObjectiveChart(chartData, false);
        updateParallelCoords(chartData, false);
        updateTradeDistributions(chartData, false);
        updateBestStrategy(chartData, false);

        // Single redraw for all charts
        Object.values(charts).forEach(chart => {
            if (chart && chart.redraw) {
                chart.redraw();
            }
        });
    } finally {
        this.updateInProgress = false;

        // Process pending update if any
        if (this.pendingUpdate) {
            const pending = this.pendingUpdate;
            this.pendingUpdate = null;
            setTimeout(() => updateCharts(pending), 16); // Next frame
        }
    }
}

function updateParallelCoordsEfficient(chartData, redraw = true) {
    if (!chartData.elite_population_data) return;

    const chart = charts.parallelCoords;

    // Update series data in-place instead of destroy/recreate
    const normalizedData = normalizeEliteData(chartData);

    // Update existing series or add new ones
    normalizedData.forEach((data, index) => {
        if (chart.series[index]) {
            chart.series[index].setData(data, false);
        } else {
            chart.addSeries({
                data: data,
                lineWidth: 2.5,
                opacity: 0.75
            }, false);
        }
    });

    // Remove excess series
    while (chart.series.length > normalizedData.length) {
        chart.series[chart.series.length - 1].remove(false);
    }

    if (redraw) chart.redraw();
}
```

### Priority 4: Web Worker for Data Processing

**Create**: `src/visualization_apps/static/js/workers/data-processor.js`
```javascript
// Web Worker for heavy data processing
self.addEventListener('message', function(e) {
    const { type, data } = e.data;

    switch(type) {
        case 'normalize_elite_data':
            const normalized = normalizeEliteData(data);
            self.postMessage({ type: 'normalized_data', data: normalized });
            break;

        case 'calculate_histograms':
            const histograms = calculateHistograms(data);
            self.postMessage({ type: 'histogram_data', data: histograms });
            break;
    }
});

function normalizeEliteData(eliteData) {
    // Heavy computation off main thread
    // ... normalization logic ...
    return normalizedData;
}
```

**Usage in main thread**:
```javascript
const dataWorker = new Worker('/static/js/workers/data-processor.js');

dataWorker.addEventListener('message', function(e) {
    const { type, data } = e.data;
    if (type === 'normalized_data') {
        updateParallelCoordsWithNormalizedData(data);
    }
});

// Send heavy work to worker
function updateParallelCoords(chartData) {
    dataWorker.postMessage({
        type: 'normalize_elite_data',
        data: chartData.elite_population_data
    });
}
```

### Priority 5: Smart Plot Band Management

**Update**: `src/visualization_apps/templates/optimizer/main.html`
```javascript
// Track existing plot bands
const existingPlotBands = new Map();

function updatePlotBandsEfficient(trades) {
    if (!trades) return;

    const chart = charts.bestStrategy;
    const currentBandIds = new Set();

    // Update or create plot bands
    trades.forEach((trade, index) => {
        const bandId = `trade-band-${index}`;
        currentBandIds.add(bandId);

        const existingBand = existingPlotBands.get(bandId);

        // Only update if changed
        if (!existingBand ||
            existingBand.entry !== trade.entry_time ||
            existingBand.exit !== trade.exit_time) {

            // Remove old band if exists
            const oldBand = chart.xAxis[0].plotLinesAndBands
                .find(b => b.id === bandId);
            if (oldBand) oldBand.destroy();

            // Add new band
            chart.xAxis[0].addPlotBand({
                id: bandId,
                from: new Date(trade.entry_time).getTime(),
                to: new Date(trade.exit_time).getTime(),
                color: trade.pnl > 0 ? 'rgba(40, 167, 69, 0.1)' : 'rgba(220, 53, 69, 0.1)'
            });

            existingPlotBands.set(bandId, {
                entry: trade.entry_time,
                exit: trade.exit_time
            });
        }
    });

    // Remove bands that no longer exist
    existingPlotBands.forEach((band, bandId) => {
        if (!currentBandIds.has(bandId)) {
            const oldBand = chart.xAxis[0].plotLinesAndBands
                .find(b => b.id === bandId);
            if (oldBand) oldBand.destroy();
            existingPlotBands.delete(bandId);
        }
    });
}
```

### Priority 6: Performance Monitoring

**Create**: `src/visualization_apps/static/js/performance-monitor.js`
```javascript
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            updateLatency: [],
            frameDrops: 0,
            memoryUsage: []
        };
        this.lastFrameTime = performance.now();
    }

    measureUpdate(name, fn) {
        const start = performance.now();
        const result = fn();
        const duration = performance.now() - start;

        this.metrics.updateLatency.push({ name, duration });

        // Warn if slow
        if (duration > 16) {  // 60fps = 16ms per frame
            console.warn(`⚠️ Slow update: ${name} took ${duration.toFixed(2)}ms`);
        }

        return result;
    }

    checkFrameRate() {
        const now = performance.now();
        const frameDelta = now - this.lastFrameTime;

        // Frame drop if > 33ms (< 30fps)
        if (frameDelta > 33) {
            this.metrics.frameDrops++;
            console.warn(`⚠️ Frame drop: ${frameDelta.toFixed(2)}ms`);
        }

        this.lastFrameTime = now;
    }

    getReport() {
        const avgLatency = this.metrics.updateLatency
            .reduce((sum, m) => sum + m.duration, 0) / this.metrics.updateLatency.length;

        return {
            averageUpdateLatency: avgLatency.toFixed(2),
            frameDrops: this.metrics.frameDrops,
            slowUpdates: this.metrics.updateLatency.filter(m => m.duration > 16)
        };
    }
}

window.perfMonitor = new PerformanceMonitor();
```

## Implementation Plan

### Phase 1: Quick Wins (1-2 hours)
1. Add debouncing to chart updates (requestAnimationFrame)
2. Batch chart redraws (single redraw at end)
3. Add performance monitoring
4. Implement update queue to prevent concurrent updates

### Phase 2: Data Optimization (2-3 hours)
1. Modify backend to send incremental data
2. Update frontend to handle delta updates
3. Implement data caching and memoization
4. Add "full refresh" mechanism for every N generations

### Phase 3: Chart Optimization (2-3 hours)
1. Replace chart destruction with in-place updates
2. Implement smart plot band management
3. Add chart update throttling
4. Optimize parallel coordinates rendering

### Phase 4: Advanced (4-6 hours)
1. Implement Web Worker for data processing
2. Add virtual scrolling for large tables
3. Implement chart data windowing (show last N generations)
4. Add memory cleanup and garbage collection hints

## Expected Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Update Latency | 200-500ms | 16-50ms | 75-90% |
| Memory Growth | Linear | Bounded | Sustainable |
| Frame Drops | Frequent | Rare | 90%+ |
| Network Payload | Growing | Constant | 90%+ |
| UI Responsiveness | Poor | Smooth | Excellent |

## Monitoring Success

Add performance dashboard to UI:
```javascript
// Show performance metrics in UI
setInterval(() => {
    const report = window.perfMonitor.getReport();
    document.getElementById('perfMetrics').innerHTML = `
        Avg Update: ${report.averageUpdateLatency}ms |
        Frame Drops: ${report.frameDrops} |
        Memory: ${(performance.memory.usedJSHeapSize / 1048576).toFixed(0)}MB
    `;
}, 1000);
```

## Testing Checklist

- [ ] Run optimization with 100+ generations
- [ ] Monitor Chrome DevTools Performance tab
- [ ] Check memory usage doesn't grow unbounded
- [ ] Verify no "Page Unresponsive" warnings
- [ ] Test with multiple concurrent optimizations
- [ ] Validate chart data accuracy after optimizations
- [ ] Test reconnection with in-progress optimization
- [ ] Verify all charts update correctly with delta data
