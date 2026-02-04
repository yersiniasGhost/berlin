/**
 * Bar Scores Chart Component
 *
 * Reusable bar scores visualization showing weighted indicator trigger combinations.
 * Each bar is displayed as a line series with threshold markers.
 *
 * Features:
 * - Bull bars in green tones, bear bars in red tones
 * - Entry/exit threshold plot lines
 * - Chart synchronization support
 * - Dark/light theme support
 *
 * Used by both stock_analysis_ui (Card Details) and visualization_apps (Replay).
 */

/**
 * BarScoresChart - Renders and manages a bar scores chart
 */
class BarScoresChart {
    /**
     * Create a BarScoresChart instance
     * @param {Object} options - Configuration options
     * @param {string} options.containerId - ID of the chart container element
     * @param {string} options.theme - 'dark' or 'light' (default: 'light')
     * @param {number} options.height - Chart height in pixels (default: 280)
     * @param {Object} options.chartsRegistry - Registry of charts for synchronization
     */
    constructor(options = {}) {
        this.containerId = options.containerId || 'barScoresChart';
        this.theme = options.theme || 'light';
        this.height = options.height || 280;
        this.chartsRegistry = options.chartsRegistry || window.indicatorCharts || {};
        this.registryKey = options.registryKey || 'barScores';

        this.chart = null;

        // Color palettes
        this.colors = {
            light: {
                bull: ['#4CAF50', '#8BC34A', '#CDDC39', '#00BCD4'],
                bear: ['#f44336', '#E91E63', '#FF5722', '#FF9800'],
                default: ['#2196F3', '#9C27B0', '#607D8B', '#795548'],
                entryThreshold: '#28a745',
                exitThreshold: '#dc3545',
                gridLine: '#e6e6e6',
                background: '#ffffff',
                textColor: '#333333'
            },
            dark: {
                bull: ['#4CAF50', '#8BC34A', '#CDDC39', '#00BCD4'],
                bear: ['#ef5350', '#E91E63', '#FF5722', '#FF9800'],
                default: ['#42A5F5', '#AB47BC', '#78909C', '#8D6E63'],
                entryThreshold: '#3fb950',
                exitThreshold: '#f85149',
                gridLine: '#30363d',
                background: '#0d1117',
                textColor: '#e6edf3'
            }
        };
    }

    /**
     * Get the current color palette based on theme
     * @returns {Object} Color palette
     */
    getColors() {
        return this.colors[this.theme] || this.colors.light;
    }

    /**
     * Render the bar scores chart
     * @param {Array} barScoresHistory - Array of {timestamp, scores: {bar_name: score}}
     * @param {Object} barsConfig - Bar definitions with types (bull/bear)
     * @param {Array} entryConditions - Entry conditions with thresholds [{name, threshold}]
     * @param {Array} exitConditions - Exit conditions with thresholds [{name, threshold}]
     */
    render(barScoresHistory, barsConfig = {}, entryConditions = [], exitConditions = []) {
        console.log('📊 BarScoresChart: Creating chart');
        console.log('   History entries:', barScoresHistory?.length || 0);
        console.log('   Bars config:', Object.keys(barsConfig));

        if (!barScoresHistory || barScoresHistory.length === 0) {
            console.warn('⚠️ BarScoresChart: No bar scores history data');
            this._showEmptyState();
            return;
        }

        // Get all unique bar names from the first entry
        const barNames = Object.keys(barScoresHistory[0]?.scores || {});
        if (barNames.length === 0) {
            console.warn('⚠️ BarScoresChart: No bar names found in scores history');
            this._showEmptyState();
            return;
        }

        const colors = this.getColors();

        // Build threshold lookup from entry/exit conditions
        const thresholds = {};
        entryConditions.forEach(cond => {
            if (cond.name) thresholds[cond.name] = { value: cond.threshold || 0.5, type: 'entry' };
        });
        exitConditions.forEach(cond => {
            if (cond.name) thresholds[cond.name] = { value: cond.threshold || 0.5, type: 'exit' };
        });

        // Create series for each bar
        const series = [];
        let bullIdx = 0, bearIdx = 0, defaultIdx = 0;

        barNames.forEach(barName => {
            // Extract data for this bar
            const barData = barScoresHistory.map(entry => [
                entry.timestamp,
                entry.scores[barName] || 0
            ]);

            // Determine bar type and color
            const barConfig = barsConfig[barName] || {};
            const barType = barConfig.type || 'unknown';
            let color;

            if (barType === 'bull') {
                color = colors.bull[bullIdx % colors.bull.length];
                bullIdx++;
            } else if (barType === 'bear') {
                color = colors.bear[bearIdx % colors.bear.length];
                bearIdx++;
            } else {
                color = colors.default[defaultIdx % colors.default.length];
                defaultIdx++;
            }

            series.push({
                name: barName,
                data: barData,
                color: color,
                lineWidth: 2,
                marker: { enabled: false },
                tooltip: { valueDecimals: 3 }
            });
        });

        // Create threshold plot lines
        const plotLines = [];
        Object.entries(thresholds).forEach(([barName, thresh]) => {
            plotLines.push({
                value: thresh.value,
                color: thresh.type === 'entry' ? colors.entryThreshold : colors.exitThreshold,
                width: 1,
                dashStyle: 'Dash',
                label: {
                    text: `${barName}: ${thresh.value}`,
                    align: 'right',
                    style: {
                        fontSize: '9px',
                        color: thresh.type === 'entry' ? colors.entryThreshold : colors.exitThreshold
                    }
                },
                zIndex: 3
            });
        });

        // Build chart configuration
        const chartConfig = this._buildChartConfig(series, plotLines, thresholds, colors);

        // Destroy existing chart if present
        this.destroy();

        // Create the chart
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`BarScoresChart: Container #${this.containerId} not found`);
            return;
        }

        this.chart = Highcharts.chart(this.containerId, chartConfig);

        // Register for synchronization
        if (this.chartsRegistry) {
            this.chartsRegistry[this.registryKey] = this.chart;
        }

        // Enable synchronization
        if (typeof window.IndicatorCharts?.enableChartSynchronization === 'function') {
            window.IndicatorCharts.enableChartSynchronization(this.chart, this.chartsRegistry);
        } else if (typeof enableChartSynchronization === 'function') {
            enableChartSynchronization(this.chart, this.chartsRegistry);
        }

        console.log(`✅ BarScoresChart: Created with ${barNames.length} bars`);
    }

    /**
     * Build the Highcharts configuration object
     * @private
     */
    _buildChartConfig(series, plotLines, thresholds, colors) {
        return {
            chart: {
                type: 'line',
                height: this.height,
                zoomType: 'x',
                panKey: 'shift',
                panning: { enabled: true, type: 'x' },
                marginBottom: 10,
                backgroundColor: colors.background
            },
            title: {
                text: 'Bar Scores (Weighted Indicator Triggers)',
                style: { color: colors.textColor }
            },
            xAxis: {
                type: 'datetime',
                ordinal: true,
                crosshair: true,
                labels: {
                    enabled: false,
                    style: { color: colors.textColor }
                },
                lineWidth: 0,
                tickWidth: 0,
                gridLineColor: colors.gridLine
            },
            yAxis: {
                title: {
                    text: 'Score',
                    style: { color: colors.textColor }
                },
                min: 0,
                max: 1.1,
                crosshair: true,
                plotLines: plotLines,
                gridLineWidth: 1,
                gridLineColor: colors.gridLine,
                labels: { style: { color: colors.textColor } }
            },
            legend: {
                enabled: true,
                align: 'right',
                verticalAlign: 'top',
                layout: 'horizontal',
                itemStyle: {
                    fontSize: '10px',
                    color: colors.textColor
                }
            },
            plotOptions: {
                line: {
                    lineWidth: 2,
                    marker: { enabled: false },
                    states: { hover: { lineWidth: 3 } }
                }
            },
            series: series,
            tooltip: {
                shared: true,
                crosshairs: true,
                backgroundColor: this.theme === 'dark' ? '#21262d' : '#ffffff',
                style: { color: colors.textColor },
                formatter: function() {
                    let s = '<b>' + Highcharts.dateFormat('%Y-%m-%d %H:%M', this.x) + '</b><br/>';
                    this.points.forEach(point => {
                        const thresh = thresholds[point.series.name];
                        const threshStr = thresh ? ` (thresh: ${thresh.value})` : '';
                        const triggered = thresh && point.y >= thresh.value ? ' ✓' : '';
                        s += `<span style="color:${point.color}">●</span> ${point.series.name}: <b>${point.y.toFixed(3)}</b>${threshStr}${triggered}<br/>`;
                    });
                    return s;
                }
            },
            credits: { enabled: false }
        };
    }

    /**
     * Show empty state when no data is available
     * @private
     */
    _showEmptyState() {
        const container = document.getElementById(this.containerId);
        if (container) {
            const colors = this.getColors();
            container.innerHTML = `
                <div style="height: ${this.height}px; display: flex; align-items: center; justify-content: center;
                            background: ${colors.background}; color: ${colors.textColor}; border-radius: 8px;">
                    <p class="text-muted">No bar scores data available</p>
                </div>
            `;
        }
    }

    /**
     * Set the theme and re-render if data exists
     * @param {string} theme - 'dark' or 'light'
     */
    setTheme(theme) {
        this.theme = theme;
        // Note: To re-render, the caller should call render() again with the data
    }

    /**
     * Set the charts registry
     * @param {Object} registry - Charts registry object
     */
    setChartsRegistry(registry) {
        this.chartsRegistry = registry;

        // Re-register current chart if it exists
        if (this.chart && this.registryKey) {
            this.chartsRegistry[this.registryKey] = this.chart;
        }
    }

    /**
     * Destroy the chart and clean up
     */
    destroy() {
        if (this.chart) {
            // Remove from registry
            if (this.chartsRegistry && this.chartsRegistry[this.registryKey]) {
                delete this.chartsRegistry[this.registryKey];
            }

            this.chart.destroy();
            this.chart = null;
        }
    }

    /**
     * Get the underlying Highcharts instance
     * @returns {Object|null} Highcharts chart instance
     */
    getChart() {
        return this.chart;
    }
}

// Export for use in other scripts
window.BarScoresChart = BarScoresChart;
