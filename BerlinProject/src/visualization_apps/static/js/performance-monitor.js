/**
 * Performance Monitor
 * Tracks and reports UI performance metrics
 */

class PerformanceMonitor {
    constructor() {
        this.metrics = {
            updateLatency: [],
            chartUpdates: new Map(),
            frameDrops: 0,
            memorySnapshots: []
        };
        this.lastFrameTime = performance.now();
        this.enabled = true;
        this.maxMetricsHistory = 100; // Keep last 100 measurements
    }

    /**
     * Measure execution time of a function
     */
    measure(name, fn) {
        if (!this.enabled) return fn();

        const start = performance.now();
        try {
            const result = fn();

            // Handle promises
            if (result && typeof result.then === 'function') {
                return result.finally(() => {
                    this.recordMetric(name, performance.now() - start);
                });
            }

            this.recordMetric(name, performance.now() - start);
            return result;
        } catch (error) {
            this.recordMetric(name, performance.now() - start, error);
            throw error;
        }
    }

    /**
     * Record a metric
     */
    recordMetric(name, duration, error = null) {
        const metric = {
            name,
            duration,
            timestamp: Date.now(),
            error: error ? error.message : null
        };

        this.metrics.updateLatency.push(metric);

        // Track per-operation metrics
        if (!this.metrics.chartUpdates.has(name)) {
            this.metrics.chartUpdates.set(name, []);
        }
        this.metrics.chartUpdates.get(name).push(duration);

        // Trim history
        if (this.metrics.updateLatency.length > this.maxMetricsHistory) {
            this.metrics.updateLatency.shift();
        }

        const operationHistory = this.metrics.chartUpdates.get(name);
        if (operationHistory.length > this.maxMetricsHistory) {
            operationHistory.shift();
        }

        // Warn if slow (>16ms = below 60fps)
        if (duration > 16) {
            console.warn(`⚠️ Slow operation: ${name} took ${duration.toFixed(2)}ms`);
        }

        // Critical warning for very slow operations
        if (duration > 100) {
            console.error(`🔴 CRITICAL: ${name} took ${duration.toFixed(2)}ms - potential UI freeze!`);
        }
    }

    /**
     * Check frame rate
     */
    checkFrameRate() {
        if (!this.enabled) return;

        const now = performance.now();
        const frameDelta = now - this.lastFrameTime;

        // Frame drop if > 33ms (< 30fps)
        if (frameDelta > 33) {
            this.metrics.frameDrops++;
            if (frameDelta > 100) {
                console.warn(`⚠️ Major frame drop: ${frameDelta.toFixed(2)}ms`);
            }
        }

        this.lastFrameTime = now;
    }

    /**
     * Record memory snapshot
     */
    recordMemory() {
        if (!this.enabled || !performance.memory) return;

        this.metrics.memorySnapshots.push({
            timestamp: Date.now(),
            usedJSHeapSize: performance.memory.usedJSHeapSize,
            totalJSHeapSize: performance.memory.totalJSHeapSize,
            jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
        });

        // Keep last 100 snapshots
        if (this.metrics.memorySnapshots.length > 100) {
            this.metrics.memorySnapshots.shift();
        }
    }

    /**
     * Get performance report
     */
    getReport() {
        const latencies = this.metrics.updateLatency.map(m => m.duration);
        const avgLatency = latencies.length > 0
            ? latencies.reduce((a, b) => a + b, 0) / latencies.length
            : 0;

        const slowUpdates = this.metrics.updateLatency
            .filter(m => m.duration > 16)
            .sort((a, b) => b.duration - a.duration)
            .slice(0, 10); // Top 10 slowest

        const operationStats = {};
        this.metrics.chartUpdates.forEach((durations, name) => {
            const avg = durations.reduce((a, b) => a + b, 0) / durations.length;
            const max = Math.max(...durations);
            const min = Math.min(...durations);
            operationStats[name] = { avg, max, min, count: durations.length };
        });

        let memoryTrend = 'N/A';
        if (this.metrics.memorySnapshots.length >= 2) {
            const first = this.metrics.memorySnapshots[0].usedJSHeapSize;
            const last = this.metrics.memorySnapshots[this.metrics.memorySnapshots.length - 1].usedJSHeapSize;
            const growth = ((last - first) / first * 100).toFixed(1);
            memoryTrend = `${growth}%`;
        }

        return {
            averageLatency: avgLatency.toFixed(2),
            frameDrops: this.metrics.frameDrops,
            slowUpdates,
            operationStats,
            memoryTrend,
            currentMemory: performance.memory
                ? (performance.memory.usedJSHeapSize / 1048576).toFixed(0)
                : 'N/A'
        };
    }

    /**
     * Display performance HUD
     */
    showHUD() {
        // Create HUD if doesn't exist
        let hud = document.getElementById('performance-hud');
        if (!hud) {
            hud = document.createElement('div');
            hud.id = 'performance-hud';
            hud.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: rgba(0, 0, 0, 0.85);
                color: #00ff00;
                padding: 15px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                z-index: 10000;
                min-width: 250px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            `;
            document.body.appendChild(hud);
        }

        // Update HUD content every second
        const updateHUD = () => {
            const report = this.getReport();

            hud.innerHTML = `
                <div style="font-weight: bold; margin-bottom: 10px; color: #fff;">📊 Performance Monitor</div>
                <div>Avg Update: <span style="color: ${parseFloat(report.averageLatency) > 16 ? '#ff6b6b' : '#51cf66'}">${report.averageLatency}ms</span></div>
                <div>Frame Drops: <span style="color: ${report.frameDrops > 10 ? '#ff6b6b' : '#51cf66'}">${report.frameDrops}</span></div>
                <div>Memory: ${report.currentMemory}MB (${report.memoryTrend})</div>
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #444;">
                    <div style="font-size: 10px; color: #888;">
                        ${Object.entries(report.operationStats).slice(0, 3).map(([name, stats]) =>
                            `${name}: ${stats.avg.toFixed(1)}ms`
                        ).join('<br>')}
                    </div>
                </div>
            `;
        };

        // Update HUD
        updateHUD();
        setInterval(updateHUD, 1000);

        // Record memory periodically
        setInterval(() => this.recordMemory(), 5000);
    }

    /**
     * Hide HUD
     */
    hideHUD() {
        const hud = document.getElementById('performance-hud');
        if (hud) {
            hud.remove();
        }
    }

    /**
     * Reset metrics
     */
    reset() {
        this.metrics = {
            updateLatency: [],
            chartUpdates: new Map(),
            frameDrops: 0,
            memorySnapshots: []
        };
        this.lastFrameTime = performance.now();
    }

    /**
     * Enable/disable monitoring
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    }
}

// Create global instance
window.perfMonitor = new PerformanceMonitor();

// Auto-start HUD in development mode (can be disabled via console)
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    console.log('💡 Performance monitoring enabled. Use perfMonitor.showHUD() to display metrics.');
}
