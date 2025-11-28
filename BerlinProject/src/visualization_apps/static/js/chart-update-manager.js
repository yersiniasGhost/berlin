/**
 * Chart Update Manager
 * Handles efficient, debounced chart updates with batching
 */

class ChartUpdateManager {
    constructor() {
        this.pendingUpdates = new Map();
        this.updateScheduled = false;
        this.updateInProgress = false;
        this.charts = {};
        this.lastUpdateTime = 0;
        this.minUpdateInterval = 100; // Minimum 100ms between updates
        this.existingPlotBands = new Map();
        this.dataCache = new Map();
        this.animationsEnabled = false; // Disable animations for performance
    }

    /**
     * Register a chart with the manager
     */
    registerChart(name, chart) {
        this.charts[name] = chart;
        console.log(`📊 Registered chart: ${name}`);
    }

    /**
     * Schedule a chart update (debounced)
     */
    scheduleUpdate(chartName, data) {
        // Store pending update
        this.pendingUpdates.set(chartName, data);

        // Debounce with requestAnimationFrame
        if (!this.updateScheduled) {
            this.updateScheduled = true;

            // Check if enough time has passed since last update
            const now = performance.now();
            const timeSinceLastUpdate = now - this.lastUpdateTime;

            if (timeSinceLastUpdate < this.minUpdateInterval) {
                // Wait before scheduling
                setTimeout(() => {
                    requestAnimationFrame(() => this.flushUpdates());
                }, this.minUpdateInterval - timeSinceLastUpdate);
            } else {
                // Schedule immediately
                requestAnimationFrame(() => this.flushUpdates());
            }
        }
    }

    /**
     * Flush all pending updates in a batch
     */
    flushUpdates() {
        // Prevent concurrent updates
        if (this.updateInProgress) {
            this.updateScheduled = false;
            // Re-schedule after current update completes
            setTimeout(() => this.scheduleUpdate(null, null), 50);
            return;
        }

        this.updateInProgress = true;
        this.updateScheduled = false;

        const updates = new Map(this.pendingUpdates);
        this.pendingUpdates.clear();

        try {
            // Process all updates without redraw (fast)
            window.perfMonitor?.measure('batch_chart_update_data', () => {
                updates.forEach((data, chartName) => {
                    this.updateChartInternal(chartName, data, false);
                });
            });

            // Stagger redraws across multiple frames to avoid UI freeze
            this.staggeredRedraw();

            this.lastUpdateTime = performance.now();
        } catch (error) {
            console.error('❌ Error in batch update:', error);
            this.updateInProgress = false;
        }
    }

    /**
     * Stagger chart redraws across multiple animation frames
     * This prevents the 1.4s UI freeze from synchronous redraws
     */
    staggeredRedraw() {
        const charts = Object.values(this.charts).filter(c => c && typeof c.redraw === 'function');
        let index = 0;

        const redrawNext = () => {
            if (index >= charts.length) {
                this.updateInProgress = false;
                return;
            }

            window.perfMonitor?.measure(`redraw_${index}`, () => {
                // Redraw without animation for speed
                charts[index].redraw(false);
            });

            index++;

            // Schedule next redraw in next frame
            if (index < charts.length) {
                requestAnimationFrame(redrawNext);
            } else {
                this.updateInProgress = false;
            }
        };

        // Start the staggered redraw
        requestAnimationFrame(redrawNext);
    }

    /**
     * Update a chart without redrawing
     */
    updateChartInternal(chartName, data, redraw = false) {
        const chart = this.charts[chartName];
        if (!chart) {
            console.warn(`⚠️ Chart not registered: ${chartName}`);
            return;
        }

        try {
            switch (chartName) {
                case 'objective':
                    this.updateObjectiveChart(chart, data, redraw);
                    break;
                case 'parallelCoords':
                    this.updateParallelCoordsChart(chart, data, redraw);
                    break;
                case 'winningTrades':
                    this.updateDistributionChart(chart, data, redraw);
                    break;
                case 'losingTrades':
                    this.updateDistributionChart(chart, data, redraw);
                    break;
                case 'bestStrategy':
                    this.updateBestStrategyChart(chart, data, redraw);
                    break;
                case 'parameterHistogram':
                    this.updateParameterHistogram(chart, data, redraw);
                    break;
                case 'parameterEvolution':
                    this.updateParameterEvolution(chart, data, redraw);
                    break;
            }
        } catch (error) {
            console.error(`❌ Error updating ${chartName}:`, error);
        }
    }

    /**
     * Update objective evolution chart efficiently
     */
    updateObjectiveChart(chart, data, redraw) {
        if (!data || !data.objective_evolution) return;

        window.perfMonitor?.measure('update_objective_chart', () => {
            const objectiveColors = {
                'MaximizeProfit': '#28a745',
                'MinimizeLoss': '#dc3545',
                'MaximizeNetPnL': '#007bff',
                'MaximizeWinRate': '#ffc107',
                'MinimizeDrawdown': '#6f42c1'
            };

            // Update existing series or add new ones
            Object.entries(data.objective_evolution).forEach(([objectiveName, values], index) => {
                let series = chart.series.find(s => s.name === objectiveName);

                if (!series) {
                    // Add new series
                    const color = objectiveColors[objectiveName] || Highcharts.getOptions().colors[index];
                    chart.addSeries({
                        name: objectiveName,
                        data: values,
                        color: color,
                        lineWidth: 2
                    }, false);
                } else {
                    // Update existing series data
                    series.setData(values, false);
                }
            });

            if (redraw) chart.redraw();
        });
    }

    /**
     * Update parallel coordinates chart efficiently (NO DESTRUCTION)
     */
    updateParallelCoordsChart(chart, data, redraw) {
        if (!data || !data.elite_population_data || !data.objective_names) return;

        window.perfMonitor?.measure('update_parallel_coords', () => {
            const eliteData = data.elite_population_data;
            const objectiveNames = data.objective_names;

            if (eliteData.length === 0) return;

            // Normalize data
            const { normalizedData, originalData, objectiveRanges } = this.normalizeEliteData(
                eliteData,
                objectiveNames
            );

            const colors = Highcharts.getOptions().colors;
            const colorCount = colors.length;

            // Update series data in-place instead of destroying chart
            normalizedData.forEach((elite, index) => {
                if (chart.series[index]) {
                    // Update existing series
                    chart.series[index].setData(elite, false);
                } else {
                    // Add new series
                    chart.addSeries({
                        name: `Elite ${index + 1}`,
                        data: elite,
                        color: colors[index % colorCount],
                        lineWidth: index === 0 ? 3 : 2.5,
                        opacity: index === 0 ? 0.9 : 0.75
                    }, false);
                }
            });

            // Remove excess series
            while (chart.series.length > normalizedData.length) {
                chart.series[chart.series.length - 1].remove(false);
            }

            // Update title
            if (chart.setTitle) {
                chart.setTitle({
                    text: `Elite Population Analysis (${eliteData.length} Individuals)`
                }, null, false);
            }

            if (redraw) chart.redraw();
        });
    }

    /**
     * Normalize elite data with caching
     */
    normalizeEliteData(eliteData, objectiveNames) {
        // Create cache key
        const cacheKey = JSON.stringify([eliteData.length, objectiveNames]);

        // Check cache
        if (this.dataCache.has(cacheKey)) {
            const cached = this.dataCache.get(cacheKey);
            // Validate cache is still valid
            if (cached.eliteData.length === eliteData.length) {
                return cached;
            }
        }

        // Calculate ranges for each objective
        const objectiveRanges = objectiveNames.map((objName, objIndex) => {
            const values = eliteData.map(elite => elite[objIndex]);
            const min = Math.min(...values);
            const max = Math.max(...values);
            return { min, max, range: max - min || 1 };
        });

        // Normalize each elite's data to [0,1] range
        const normalizedData = [];
        const originalData = [];

        eliteData.forEach((elite) => {
            const normalizedElite = elite.map((value, objIndex) => {
                const { min, range } = objectiveRanges[objIndex];
                return range > 0 ? (value - min) / range : 0.5;
            });
            normalizedData.push(normalizedElite);
            originalData.push(elite);
        });

        const result = { normalizedData, originalData, objectiveRanges, eliteData };

        // Cache result
        this.dataCache.set(cacheKey, result);

        // Limit cache size
        if (this.dataCache.size > 10) {
            const firstKey = this.dataCache.keys().next().value;
            this.dataCache.delete(firstKey);
        }

        return result;
    }

    /**
     * Update distribution chart efficiently
     */
    updateDistributionChart(chart, data, redraw) {
        if (!data || !Array.isArray(data)) return;

        window.perfMonitor?.measure('update_distribution_chart', () => {
            const categories = data.map(item => item[0]);
            const values = data.map(item => item[1]);

            chart.xAxis[0].setCategories(categories, false);
            chart.series[0].setData(values, false);

            if (redraw) chart.redraw();
        });
    }

    /**
     * Update best strategy chart with smart plot band management
     */
    updateBestStrategyChart(chart, data, redraw) {
        if (!data || !data.best_strategy) return;

        window.perfMonitor?.measure('update_best_strategy', () => {
            const candlestickData = data.best_strategy.candlestick_data || [];
            const trades = data.best_strategy.trades || [];

            // Update candlestick data
            chart.series[0].setData(candlestickData, false);

            // Update plot bands efficiently
            this.updatePlotBandsEfficient(chart, trades);

            if (redraw) chart.redraw();
        });
    }

    /**
     * Efficient plot band updates (only update changed bands)
     */
    updatePlotBandsEfficient(chart, trades) {
        if (!trades || trades.length === 0) return;

        const currentBandIds = new Set();
        const xAxis = chart.xAxis[0];

        trades.forEach((trade, index) => {
            if (!trade.entry_time || !trade.exit_time) return;

            const bandId = `trade-band-${index}`;
            currentBandIds.add(bandId);

            const existingBand = this.existingPlotBands.get(bandId);
            const tradeHash = `${trade.entry_time}-${trade.exit_time}-${trade.pnl}`;

            // Only update if changed
            if (!existingBand || existingBand.hash !== tradeHash) {
                // Remove old band
                const oldBand = xAxis.plotLinesAndBands?.find(b => b.id === bandId);
                if (oldBand) oldBand.destroy();

                // Add new band
                const isProfit = trade.pnl > 0;
                xAxis.addPlotBand({
                    id: bandId,
                    from: new Date(trade.entry_time).getTime(),
                    to: new Date(trade.exit_time).getTime(),
                    color: isProfit ? 'rgba(40, 167, 69, 0.1)' : 'rgba(220, 53, 69, 0.1)',
                    className: 'trade-band',
                    zIndex: 0
                });

                this.existingPlotBands.set(bandId, {
                    hash: tradeHash,
                    entry: trade.entry_time,
                    exit: trade.exit_time
                });
            }
        });

        // Remove bands that no longer exist
        this.existingPlotBands.forEach((band, bandId) => {
            if (!currentBandIds.has(bandId)) {
                const oldBand = xAxis.plotLinesAndBands?.find(b => b.id === bandId);
                if (oldBand) oldBand.destroy();
                this.existingPlotBands.delete(bandId);
            }
        });
    }

    /**
     * Update parameter histogram
     */
    updateParameterHistogram(chart, data, redraw) {
        if (!data) return;

        window.perfMonitor?.measure('update_parameter_histogram', () => {
            // Implementation depends on data structure
            if (data.categories && data.populationData && data.eliteData) {
                chart.xAxis[0].setCategories(data.categories, false);
                chart.series[0].setData(data.populationData, false);
                chart.series[1].setData(data.eliteData, false);
            }

            if (redraw) chart.redraw();
        });
    }

    /**
     * Update parameter evolution
     */
    updateParameterEvolution(chart, data, redraw) {
        if (!data || !Array.isArray(data.series)) return;

        window.perfMonitor?.measure('update_parameter_evolution', () => {
            data.series.forEach((seriesData, index) => {
                if (chart.series[index]) {
                    chart.series[index].setData(seriesData.data, false);
                }
            });

            if (redraw) chart.redraw();
        });
    }

    /**
     * Clear all caches
     */
    clearCache() {
        this.dataCache.clear();
        this.existingPlotBands.clear();
        console.log('🧹 Chart manager cache cleared');
    }

    /**
     * Reset manager state
     */
    reset() {
        this.pendingUpdates.clear();
        this.updateScheduled = false;
        this.updateInProgress = false;
        this.clearCache();
    }
}

// Create global instance
window.chartUpdateManager = new ChartUpdateManager();
