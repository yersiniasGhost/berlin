/**
 * Chart Dashboard Orchestrator
 *
 * Coordinates all chart components for the Card Details page:
 * - Candlestick chart with trade markers
 * - Bar scores chart
 * - Indicator analysis tabs
 * - Trade history table
 *
 * Manages:
 * - Data fetching from unified API
 * - Chart synchronization
 * - Theme coordination
 * - Component lifecycle
 *
 * Used by stock_analysis_ui Card Details page.
 */

/**
 * ChartDashboard - Orchestrates all chart components
 */
class ChartDashboard {
    /**
     * Create a ChartDashboard instance
     * @param {Object} options - Configuration options
     * @param {string} options.theme - 'dark' or 'light' (default: 'dark')
     * @param {Object} options.containers - Container IDs for each component
     * @param {string} options.apiBaseUrl - Base URL for API calls (default: '/api')
     */
    constructor(options = {}) {
        this.theme = options.theme || 'dark';
        this.apiBaseUrl = options.apiBaseUrl || '/api';

        // Container IDs
        this.containers = {
            candlestick: options.containers?.candlestick || 'candlestickChart',
            barScores: options.containers?.barScores || 'barScoresChart',
            indicatorTabs: options.containers?.indicatorTabs || 'indicatorTabs',
            indicatorContents: options.containers?.indicatorContents || 'indicatorTabContents',
            tradeTable: options.containers?.tradeTable || 'tradeHistoryTable',
            ...options.containers
        };

        // Charts registry for synchronization
        this.charts = {};

        // Component instances
        this.components = {
            barScoresChart: null,
            tradeHistoryTable: null
        };

        // Data storage
        this.data = null;
        this.cardId = null;

        // Initialize global charts registry
        window.indicatorCharts = window.indicatorCharts || {};
        this.charts = window.indicatorCharts;
    }

    /**
     * Initialize the dashboard
     * @param {string} cardId - The card ID to load data for
     */
    async initialize(cardId) {
        console.log(`📊 ChartDashboard: Initializing for card ${cardId}`);
        this.cardId = cardId;

        try {
            // Fetch data from unified API
            await this.loadData(cardId);

            // Render all components
            this.renderAll();

            console.log('✅ ChartDashboard: Initialized successfully');
        } catch (error) {
            console.error('❌ ChartDashboard: Initialization failed', error);
            throw error;
        }
    }

    /**
     * Load data from the unified chart data API
     * @param {string} cardId - The card ID
     */
    async loadData(cardId) {
        console.log(`📡 ChartDashboard: Fetching data for card ${cardId}`);

        const response = await fetch(`${this.apiBaseUrl}/combinations/${cardId}/chart-data`);
        if (!response.ok) {
            throw new Error(`Failed to fetch chart data: ${response.statusText}`);
        }

        this.data = await response.json();

        if (!this.data.success) {
            throw new Error(this.data.error || 'Unknown error fetching chart data');
        }

        console.log(`📊 ChartDashboard: Loaded data summary:`, {
            candles: this.data.total_candles,
            trades: this.data.total_trades,
            barScoresFormatted: (this.data.bar_scores_formatted || []).length,
            rawIndicatorHistory: Object.keys(this.data.raw_indicator_history || {}),
            indicatorHistory: Object.keys(this.data.indicator_history || {}),
            componentHistory: Object.keys(this.data.component_history || {}),
            thresholdConfig: this.data.threshold_config
        });
        return this.data;
    }

    /**
     * Render all dashboard components
     */
    renderAll() {
        if (!this.data) {
            console.warn('ChartDashboard: No data to render');
            return;
        }

        // Render candlestick chart
        this.renderCandlestickChart();

        // Render bar scores chart
        this.renderBarScoresChart();

        // Render indicator charts
        this.renderIndicatorCharts();

        // Render trade history table
        this.renderTradeHistoryTable();

        // Set up chart synchronization
        this.setupSynchronization();
    }

    /**
     * Render the candlestick chart with trade markers
     */
    renderCandlestickChart() {
        const containerId = this.containers.candlestick;
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn(`ChartDashboard: Candlestick container #${containerId} not found`);
            return;
        }

        const candlestickData = this.data.candlestick_data || [];
        const trades = this.data.trades || [];

        // Use IndicatorCharts if available
        // Signature: createCandlestickChart(candlestickData, trades, chartId, chartsRegistry)
        if (typeof window.IndicatorCharts?.createCandlestickChart === 'function') {
            this.charts.candlestick = window.IndicatorCharts.createCandlestickChart(
                candlestickData,
                trades,           // trades array
                containerId,      // chart container ID
                this.charts       // charts registry
            );

            // Add market hours bands (trade bands are added inside createCandlestickChart)
            if (this.charts.candlestick && candlestickData.length > 0) {
                window.IndicatorCharts.addMarketHoursBandsToChart(this.charts.candlestick, candlestickData);
            }
        } else {
            console.warn('ChartDashboard: IndicatorCharts not available for candlestick');
        }

        console.log(`✅ ChartDashboard: Candlestick chart rendered with ${candlestickData.length} candles`);
    }

    /**
     * Render the bar scores chart
     */
    renderBarScoresChart() {
        const containerId = this.containers.barScores;
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn(`ChartDashboard: Bar scores container #${containerId} not found`);
            return;
        }

        const barScoresHistory = this.data.bar_scores_formatted || [];
        const thresholdConfig = this.data.threshold_config || {};

        console.log(`📊 Bar scores debug:`, {
            containerId,
            historyLength: barScoresHistory.length,
            thresholdConfig,
            sampleData: barScoresHistory.slice(0, 2)
        });

        if (barScoresHistory.length === 0) {
            console.warn('⚠️ ChartDashboard: No bar scores history data available');
            container.innerHTML = '<div class="chart-empty-state"><div class="chart-empty-state-text">No bar scores data available</div></div>';
            return;
        }

        // Create or update bar scores chart
        if (!this.components.barScoresChart) {
            this.components.barScoresChart = new BarScoresChart({
                containerId: containerId,
                theme: this.theme,
                chartsRegistry: this.charts,
                registryKey: 'barScores'
            });
        }

        // Get bars config from indicators or threshold config
        const barsConfig = this._buildBarsConfig();

        this.components.barScoresChart.render(
            barScoresHistory,
            barsConfig,
            thresholdConfig.enter_long || [],
            thresholdConfig.exit_long || []
        );

        console.log(`✅ ChartDashboard: Bar scores chart rendered`);
    }

    /**
     * Build bars configuration from threshold config
     * @private
     */
    _buildBarsConfig() {
        const barsConfig = {};
        const thresholdConfig = this.data.threshold_config || {};

        // Mark entry bars as bull
        (thresholdConfig.enter_long || []).forEach(cond => {
            if (cond.name) {
                barsConfig[cond.name] = { type: 'bull' };
            }
        });

        // Mark exit bars as bear
        (thresholdConfig.exit_long || []).forEach(cond => {
            if (cond.name) {
                barsConfig[cond.name] = { type: 'bear' };
            }
        });

        return barsConfig;
    }

    /**
     * Render indicator analysis charts in tabs
     */
    renderIndicatorCharts() {
        const tabsContainerId = this.containers.indicatorTabs;
        const contentsContainerId = this.containers.indicatorContents || 'indicatorTabContents';

        const tabsContainer = document.getElementById(tabsContainerId);
        const contentsContainer = document.getElementById(contentsContainerId);

        if (!tabsContainer) {
            console.warn(`ChartDashboard: Indicator tabs container #${tabsContainerId} not found`);
            return;
        }
        if (!contentsContainer) {
            console.warn(`ChartDashboard: Indicator contents container #${contentsContainerId} not found`);
            return;
        }

        console.log(`📊 Indicator charts debug:`, {
            tabsContainerId,
            contentsContainerId,
            rawIndicatorHistoryKeys: Object.keys(this.data.raw_indicator_history || {}),
            indicatorHistoryKeys: Object.keys(this.data.indicator_history || {}),
            componentHistoryKeys: Object.keys(this.data.component_history || {}),
            classToLayout: this.data.class_to_layout,
            renderIndicatorTabsAvailable: typeof window.renderIndicatorTabs === 'function',
            createIndicatorChartsAvailable: typeof window.IndicatorCharts?.createIndicatorCharts === 'function'
        });

        const rawIndicatorHistory = this.data.raw_indicator_history || {};
        if (Object.keys(rawIndicatorHistory).length === 0) {
            console.warn('⚠️ ChartDashboard: No raw indicator history data available');
            tabsContainer.innerHTML = '<div class="chart-empty-state"><div class="chart-empty-state-text">No indicator data available</div></div>';
            return;
        }

        // Prefer the template's renderIndicatorTabs function (uses custom CSS classes)
        // over IndicatorCharts.createIndicatorCharts (uses Bootstrap classes)
        if (typeof window.renderIndicatorTabs === 'function') {
            // Use the template's rendering function
            window.renderIndicatorTabs(
                this.data.raw_indicator_history || {},
                this.data.class_to_layout || {},
                this.data.component_history || {},
                this.data.raw_indicator_history || {}
            );
            console.log(`✅ ChartDashboard: Indicator charts rendered via template function`);
        } else if (typeof window.IndicatorCharts?.createIndicatorCharts === 'function') {
            // Fall back to IndicatorCharts module
            // Signature: (componentHistory, rawIndicatorHistory, indicatorHistory, candlestickData,
            //             indicatorConfigs, classToLayout, perAggregatorCandles, indicatorAggMapping,
            //             tabsContainerId, contentContainerId, chartsRegistry)
            window.IndicatorCharts.createIndicatorCharts(
                this.data.component_history || {},
                this.data.raw_indicator_history || {},
                this.data.indicator_history || {},
                this.data.candlestick_data || [],
                this.data.indicators || [],
                this.data.class_to_layout || {},
                this.data.per_aggregator_candles || {},
                this.data.indicator_agg_mapping || {},
                tabsContainerId,      // tabs container ID
                contentsContainerId,  // contents container ID
                this.charts           // charts registry
            );
            console.log(`✅ ChartDashboard: Indicator charts rendered via IndicatorCharts module`);
        } else {
            console.warn('ChartDashboard: No indicator chart rendering function available');
            tabsContainer.innerHTML = '<div class="chart-empty-state"><div class="chart-empty-state-text">Indicator charts not available</div></div>';
        }
    }

    /**
     * Render the trade history table
     */
    renderTradeHistoryTable() {
        const tableBodyId = this.containers.tradeTable;
        const tableBody = document.getElementById(tableBodyId);
        if (!tableBody) {
            console.warn(`ChartDashboard: Trade table #${tableBodyId} not found`);
            return;
        }

        // Create or update trade history table
        if (!this.components.tradeHistoryTable) {
            this.components.tradeHistoryTable = new TradeHistoryTable({
                tableBodyId: tableBodyId,
                theme: this.theme,
                chartsRegistry: this.charts,
                onDetailsClick: (timestamp, details) => {
                    this.handleTradeDetailsClick(timestamp, details);
                }
            });
        }

        this.components.tradeHistoryTable.render(
            this.data.trades || [],
            this.data.trade_details || {}
        );

        console.log(`✅ ChartDashboard: Trade history table rendered with ${(this.data.trades || []).length} trades`);
    }

    /**
     * Handle trade details button click
     * @param {number} timestamp - Trade timestamp
     * @param {Object} details - Trade details
     */
    handleTradeDetailsClick(timestamp, details) {
        // Zoom all charts to trade
        this.zoomToTimestamp(timestamp);

        // Show modal (using the table's built-in modal)
        if (this.components.tradeHistoryTable) {
            this.components.tradeHistoryTable._showDetailsModal(details || {});
        }
    }

    /**
     * Zoom all charts to center on a timestamp
     * @param {number} timestamp - Timestamp in milliseconds
     * @param {number} padding - Padding in milliseconds (default: 5 minutes)
     */
    zoomToTimestamp(timestamp, padding = 5 * 60 * 1000) {
        const min = timestamp - padding;
        const max = timestamp + padding;
        this.syncAllChartsFromDetails(min, max);
    }

    /**
     * Sync all charts to a specific time range
     * @param {number} min - Start of range in ms
     * @param {number} max - End of range in ms
     */
    syncAllChartsFromDetails(min, max) {
        if (window.syncInProgress) {
            console.log('Sync in progress, forcing zoom for details');
        }
        window.syncInProgress = true;

        try {
            let syncedCount = 0;
            Object.values(this.charts).forEach(chart => {
                if (chart && chart.xAxis && chart.xAxis[0]) {
                    chart.xAxis[0].setExtremes(min, max, true, false);
                    syncedCount++;
                }
            });
            console.log(`🔍 Zoomed ${syncedCount} charts to range`);
        } finally {
            setTimeout(() => {
                window.syncInProgress = false;
            }, 50);
        }
    }

    /**
     * Set up chart synchronization for zoom/pan
     */
    setupSynchronization() {
        // Make sync function globally available
        window.syncAllChartsFromDetails = (min, max) => {
            this.syncAllChartsFromDetails(min, max);
        };

        // Synchronization is handled by enableChartSynchronization in indicator-charts.js
        // Each chart calls this when created
        console.log(`✅ ChartDashboard: Synchronization set up for ${Object.keys(this.charts).length} charts`);
    }

    /**
     * Set the theme for all components
     * @param {string} theme - 'dark' or 'light'
     */
    setTheme(theme) {
        this.theme = theme;

        // Update component themes
        if (this.components.barScoresChart) {
            this.components.barScoresChart.setTheme(theme);
        }

        if (this.components.tradeHistoryTable) {
            this.components.tradeHistoryTable.setTheme(theme);
        }

        // Note: Candlestick and indicator charts would need to be re-rendered
        // with theme-aware configurations
    }

    /**
     * Refresh data and re-render all components
     */
    async refresh() {
        if (!this.cardId) {
            console.warn('ChartDashboard: No card ID set, cannot refresh');
            return;
        }

        await this.loadData(this.cardId);
        this.renderAll();
    }

    /**
     * Destroy all components and clean up
     */
    destroy() {
        // Destroy bar scores chart
        if (this.components.barScoresChart) {
            this.components.barScoresChart.destroy();
            this.components.barScoresChart = null;
        }

        // Clear trade history table
        if (this.components.tradeHistoryTable) {
            this.components.tradeHistoryTable.clear();
            this.components.tradeHistoryTable = null;
        }

        // Destroy all charts in registry
        Object.keys(this.charts).forEach(key => {
            const chart = this.charts[key];
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
            delete this.charts[key];
        });

        // Clear data
        this.data = null;
        this.cardId = null;

        console.log('✅ ChartDashboard: Destroyed and cleaned up');
    }

    /**
     * Get the current data
     * @returns {Object|null} Current chart data
     */
    getData() {
        return this.data;
    }

    /**
     * Get a specific chart from the registry
     * @param {string} key - Chart key (e.g., 'candlestick', 'barScores')
     * @returns {Object|null} Highcharts instance
     */
    getChart(key) {
        return this.charts[key] || null;
    }

    /**
     * Get all charts in the registry
     * @returns {Object} Charts registry
     */
    getCharts() {
        return this.charts;
    }
}

// Export for use in other scripts
window.ChartDashboard = ChartDashboard;
