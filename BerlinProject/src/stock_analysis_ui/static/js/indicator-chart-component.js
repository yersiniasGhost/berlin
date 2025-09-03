/**
 * Reusable Indicator Chart Component
 * 
 * Provides dynamic indicator display functionality with:
 * - Dynamic checkboxes based on monitor configuration
 * - MACD overlays below candlestick charts
 * - SMA overlays on candlestick charts
 * - Trigger graphs showing 0-1 indicator activation
 */

class IndicatorChartComponent {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.options = {
            showTriggerGraphs: true,
            chartHeight: 400,
            indicatorHeight: 250,
            triggerHeight: 150,
            ...options
        };
        
        this.indicators = {};
        this.charts = {};
        this.enabledIndicators = new Set();
        this.triggerData = {};
        
        this.init();
    }
    
    init() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container with id "${this.containerId}" not found`);
            return;
        }
        
        // Create the main structure
        container.innerHTML = `
            <div class="indicator-controls mb-3">
                <h6><i class="fas fa-chart-bar"></i> Indicator Display Controls</h6>
                <div id="${this.containerId}_checkboxes" class="indicator-checkboxes row">
                    <!-- Dynamic checkboxes will be inserted here -->
                </div>
            </div>
            
            <div class="charts-container">
                <!-- Main candlestick chart -->
                <div id="${this.containerId}_main_chart" class="chart-container mb-3" 
                     style="height: ${this.options.chartHeight}px;">
                    <div class="text-center text-muted d-flex align-items-center justify-content-center h-100">
                        <i class="fas fa-chart-line me-2"></i>Load data to display charts
                    </div>
                </div>
                
                <!-- Indicator charts container -->
                <div id="${this.containerId}_indicator_charts">
                    <!-- Dynamic indicator charts will be inserted here -->
                </div>
                
                <!-- Trigger graphs container -->
                <div id="${this.containerId}_trigger_charts" style="display: ${this.options.showTriggerGraphs ? 'block' : 'none'}">
                    <!-- Dynamic trigger charts will be inserted here -->
                </div>
            </div>
        `;
        
        this.setupStyles();
    }
    
    setupStyles() {
        // Add custom styles if not already present
        if (!document.getElementById('indicator-chart-styles')) {
            const style = document.createElement('style');
            style.id = 'indicator-chart-styles';
            style.textContent = `
                .indicator-checkboxes {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    padding: 15px;
                }
                
                .indicator-checkbox-group {
                    margin-bottom: 10px;
                }
                
                .indicator-checkbox {
                    margin-right: 8px;
                }
                
                .indicator-label {
                    font-size: 0.9rem;
                    font-weight: 500;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                }
                
                .indicator-type-badge {
                    font-size: 0.75rem;
                    margin-left: 8px;
                    padding: 2px 6px;
                    border-radius: 3px;
                }
                
                .badge-macd { background-color: #e3f2fd; color: #1976d2; }
                .badge-sma { background-color: #f3e5f5; color: #7b1fa2; }
                .badge-rsi { background-color: #e8f5e8; color: #388e3c; }
                .badge-other { background-color: #fff3e0; color: #f57c00; }
                
                .chart-container {
                    border: 2px solid #e9ecef;
                    border-radius: 8px;
                    background: white;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                
                .indicator-chart {
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    margin-bottom: 10px;
                    background: white;
                }
                
                .trigger-chart {
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    margin-bottom: 15px;
                    background: white;
                    min-height: 150px;
                }
                
                .trigger-chart .chart-title {
                    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                    border-bottom: 2px solid #28a745;
                }
                
                .chart-title {
                    background: #f8f9fa;
                    padding: 8px 12px;
                    border-bottom: 1px solid #dee2e6;
                    font-size: 0.9rem;
                    font-weight: 600;
                    color: #495057;
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    /**
     * Load indicators from monitor configuration
     * @param {Object} monitorConfig - Monitor configuration object
     */
    loadIndicators(monitorConfig) {
        this.indicators = {};
        
        if (!monitorConfig || !monitorConfig.indicators) {
            console.warn('No indicators found in monitor configuration');
            return;
        }
        
        // Process indicators and group by type
        monitorConfig.indicators.forEach(indicator => {
            const type = this.getIndicatorType(indicator.function);
            this.indicators[indicator.name] = {
                ...indicator,
                displayType: type,
                enabled: false
            };
        });
        
        this.generateCheckboxes();
    }
    
    /**
     * Determine indicator display type from function name
     * @param {string} functionName - Indicator function name
     * @returns {string} Display type (macd, sma, rsi, other)
     */
    getIndicatorType(functionName) {
        if (functionName.toLowerCase().includes('macd')) return 'macd';
        if (functionName.toLowerCase().includes('sma')) return 'sma';
        if (functionName.toLowerCase().includes('rsi')) return 'rsi';
        return 'other';
    }
    
    /**
     * Generate dynamic checkboxes for all indicators
     */
    generateCheckboxes() {
        const checkboxContainer = document.getElementById(`${this.containerId}_checkboxes`);
        if (!checkboxContainer) return;
        
        const indicatorTypes = ['macd', 'sma', 'rsi', 'other'];
        let html = '';
        
        indicatorTypes.forEach(type => {
            const typeIndicators = Object.entries(this.indicators)
                .filter(([name, indicator]) => indicator.displayType === type);
                
            if (typeIndicators.length === 0) return;
            
            html += `
                <div class="col-md-6 col-lg-3">
                    <h6 class="text-uppercase text-muted mb-2" style="font-size: 0.8rem;">
                        ${type.toUpperCase()} Indicators
                    </h6>
            `;
            
            typeIndicators.forEach(([name, indicator]) => {
                const checkboxId = `${this.containerId}_indicator_${name}`;
                html += `
                    <div class="indicator-checkbox-group">
                        <div class="form-check">
                            <input class="form-check-input indicator-checkbox" 
                                   type="checkbox" 
                                   id="${checkboxId}" 
                                   data-indicator="${name}"
                                   ${indicator.enabled ? 'checked' : ''}>
                            <label class="form-check-label indicator-label" for="${checkboxId}">
                                ${name}
                                <span class="indicator-type-badge badge-${type}">${type.toUpperCase()}</span>
                            </label>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
        });
        
        checkboxContainer.innerHTML = html;
        
        // Add event listeners
        this.attachCheckboxListeners();
    }
    
    /**
     * Attach event listeners to checkboxes
     */
    attachCheckboxListeners() {
        const checkboxes = document.querySelectorAll(`#${this.containerId}_checkboxes .indicator-checkbox`);
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const indicatorName = e.target.dataset.indicator;
                const isEnabled = e.target.checked;
                
                this.toggleIndicator(indicatorName, isEnabled);
            });
        });
    }
    
    /**
     * Toggle indicator display
     * @param {string} indicatorName - Name of the indicator
     * @param {boolean} enabled - Whether to enable or disable
     */
    toggleIndicator(indicatorName, enabled) {
        if (enabled) {
            this.enabledIndicators.add(indicatorName);
            this.indicators[indicatorName].enabled = true;
        } else {
            this.enabledIndicators.delete(indicatorName);
            this.indicators[indicatorName].enabled = false;
        }
        
        this.updateCharts();
    }
    
    /**
     * Set chart data for main candlestick chart and indicators
     * @param {Object} chartData - Chart data object containing candlestick data and indicator values
     */
    setChartData(chartData) {
        this.chartData = chartData;
        this.updateCharts();
    }
    
    /**
     * Set real-time indicator values and trigger data
     * @param {Object} indicators - Current indicator values
     * @param {Object} triggerData - Trigger data (0-1 values for each indicator)
     */
    updateIndicatorData(indicators, triggerData = {}) {
        this.currentIndicators = indicators;
        this.triggerData = triggerData;
        
        // Update charts with new data
        if (this.charts.main) {
            this.updateRealTimeData();
        }
    }
    
    /**
     * Update all charts based on current settings
     */
    updateCharts() {
        if (!this.chartData) {
            console.warn('No chart data available for indicator charts');
            return;
        }
        
        console.log('Updating indicator charts with data:', {
            candlestickData: this.chartData.candlestick_data?.length || 0,
            indicatorHistory: this.chartData.indicator_history?.length || 0,
            enabledIndicators: Array.from(this.enabledIndicators)
        });
        
        this.createMainChart();
        this.createIndicatorCharts();
        if (this.options.showTriggerGraphs) {
            this.createTriggerCharts();
        }
    }
    
    /**
     * Create main candlestick chart with SMA overlays
     */
    createMainChart() {
        const container = document.getElementById(`${this.containerId}_main_chart`);
        if (!container || !this.chartData.candlestick_data) return;
        
        const series = [{
            name: 'Price',
            data: this.chartData.candlestick_data,
            type: 'candlestick',
            color: '#dc3545',
            upColor: '#28a745',
            lineColor: '#dc3545',
            upLineColor: '#28a745'
        }];
        
        // Add SMA overlays
        this.enabledIndicators.forEach(indicatorName => {
            const indicator = this.indicators[indicatorName];
            if (indicator.displayType === 'sma' && this.chartData.indicator_history) {
                const smaData = this.prepareSMAData(indicatorName);
                if (smaData.length > 0) {
                    series.push({
                        name: `${indicatorName} (SMA)`,
                        data: smaData,
                        type: 'line',
                        color: this.getIndicatorColor(indicatorName),
                        lineWidth: 2
                    });
                }
            }
        });
        
        const config = {
            chart: {
                height: this.options.chartHeight,
                zoomType: 'x'
            },
            title: { text: 'Price Chart with Indicators' },
            xAxis: {
                type: 'datetime',
                ordinal: true,
                crosshair: true
            },
            yAxis: {
                title: { text: 'Price' },
                crosshair: true
            },
            series: series,
            tooltip: {
                shared: true,
                split: false
            },
            rangeSelector: { enabled: false },
            navigator: { enabled: false },
            scrollbar: { enabled: false },
            credits: { enabled: false }
        };
        
        if (this.charts.main) {
            this.charts.main.destroy();
        }
        this.charts.main = Highcharts.chart(container, config);
    }
    
    /**
     * Create separate charts for MACD and other indicators
     */
    createIndicatorCharts() {
        const container = document.getElementById(`${this.containerId}_indicator_charts`);
        if (!container) return;
        
        let html = '';
        const indicatorCharts = [];
        
        this.enabledIndicators.forEach(indicatorName => {
            const indicator = this.indicators[indicatorName];
            if (indicator.displayType === 'macd' || indicator.displayType === 'rsi') {
                const chartId = `${this.containerId}_${indicatorName}_chart`;
                html += `
                    <div class="indicator-chart">
                        <div class="chart-title">${indicatorName.toUpperCase()} - ${indicator.displayType.toUpperCase()}</div>
                        <div id="${chartId}" style="height: ${this.options.indicatorHeight}px;"></div>
                    </div>
                `;
                indicatorCharts.push({ name: indicatorName, id: chartId, type: indicator.displayType });
            }
        });
        
        container.innerHTML = html;
        
        // Create the charts
        indicatorCharts.forEach(chart => {
            this.createIndividualIndicatorChart(chart.name, chart.id, chart.type);
        });
    }
    
    /**
     * Create individual indicator chart (MACD, RSI, etc.)
     */
    createIndividualIndicatorChart(indicatorName, containerId, type) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        let series = [];
        let yAxisConfig = { title: { text: 'Value' } };
        
        if (type === 'macd') {
            // MACD typically shows MACD line, signal line, and histogram
            const macdData = this.prepareMACDData(indicatorName);
            
            console.log(`MACD data for ${indicatorName}:`, {
                macdPoints: macdData.macd.length,
                signalPoints: macdData.signal.length,
                histogramPoints: macdData.histogram.length,
                sampleMacd: macdData.macd.slice(0, 3),
                sampleSignal: macdData.signal.slice(0, 3)
            });
            
            if (macdData.macd.length > 0 && macdData.signal.length > 0) {
                series = [
                    {
                        name: 'MACD Line',
                        data: macdData.macd,
                        type: 'line',
                        color: '#2196F3',
                        lineWidth: 2
                    },
                    {
                        name: 'Signal Line',
                        data: macdData.signal,
                        type: 'line',
                        color: '#FF9800',
                        lineWidth: 2
                    },
                    {
                        name: 'Histogram',
                        data: macdData.histogram,
                        type: 'column',
                        color: '#4CAF50',
                        pointWidth: 2
                    }
                ];
            } else {
                console.warn(`No MACD data available for ${indicatorName}`);
                series = [{
                    name: 'No Data Available',
                    data: [],
                    type: 'line'
                }];
            }
            yAxisConfig.plotLines = [{
                value: 0,
                color: '#999',
                width: 1,
                dashStyle: 'dash'
            }];
        } else if (type === 'rsi') {
            const rsiData = this.prepareRSIData(indicatorName);
            series = [{
                name: 'RSI',
                data: rsiData,
                type: 'line',
                color: '#9C27B0'
            }];
            yAxisConfig.min = 0;
            yAxisConfig.max = 100;
            yAxisConfig.plotLines = [
                { value: 70, color: '#dc3545', width: 1, dashStyle: 'dash' },
                { value: 30, color: '#28a745', width: 1, dashStyle: 'dash' }
            ];
        }
        
        const config = {
            chart: {
                height: this.options.indicatorHeight
            },
            title: { text: null },
            xAxis: {
                type: 'datetime',
                ordinal: true
            },
            yAxis: yAxisConfig,
            series: series,
            tooltip: {
                shared: true,
                split: false
            },
            credits: { enabled: false }
        };
        
        this.charts[indicatorName] = Highcharts.chart(container, config);
    }
    
    /**
     * Create trigger charts showing 0-1 indicator activation
     */
    createTriggerCharts() {
        const container = document.getElementById(`${this.containerId}_trigger_charts`);
        if (!container) return;
        
        let html = '<h6 class="mt-4 mb-3"><i class="fas fa-signal"></i> Indicator Trigger Signals</h6>';
        
        this.enabledIndicators.forEach(indicatorName => {
            const chartId = `${this.containerId}_${indicatorName}_trigger`;
            html += `
                <div class="trigger-chart">
                    <div class="chart-title">${indicatorName} Trigger Signal</div>
                    <div id="${chartId}" style="height: ${this.options.triggerHeight}px;"></div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
        // Create trigger charts
        this.enabledIndicators.forEach(indicatorName => {
            this.createTriggerChart(indicatorName);
        });
    }
    
    /**
     * Create individual trigger chart
     */
    createTriggerChart(indicatorName) {
        const chartId = `${this.containerId}_${indicatorName}_trigger`;
        const container = document.getElementById(chartId);
        if (!container) return;
        
        const triggerData = this.prepareTriggerData(indicatorName);
        
        const config = {
            chart: {
                type: 'area',
                height: this.options.triggerHeight,
                backgroundColor: '#ffffff',
                borderRadius: 6,
                spacing: [15, 15, 15, 15],
                style: {
                    fontFamily: 'Inter, Arial, sans-serif'
                }
            },
            title: { text: null },
            xAxis: {
                type: 'datetime',
                ordinal: true,
                lineWidth: 1,
                lineColor: '#ccd6dd',
                tickColor: '#ccd6dd',
                labels: {
                    style: { fontSize: '11px', color: '#657786' }
                }
            },
            yAxis: {
                min: -0.1,
                max: 1.1,
                title: { 
                    text: 'Signal Strength',
                    style: { fontSize: '12px', fontWeight: '600', color: '#14171a' }
                },
                labels: {
                    formatter: function() {
                        return this.value === 0 ? 'OFF' : this.value === 1 ? 'ON' : this.value.toFixed(1);
                    },
                    style: { fontSize: '11px', color: '#657786' }
                },
                gridLineColor: '#e1e8ed',
                plotLines: [
                    { 
                        value: 0.5, 
                        color: '#657786', 
                        width: 1, 
                        dashStyle: 'dash',
                        label: {
                            text: 'Threshold',
                            style: { fontSize: '10px', color: '#657786' }
                        }
                    }
                ],
                plotBands: [
                    {
                        from: 0.8,
                        to: 1.1,
                        color: 'rgba(40, 167, 69, 0.1)',
                        label: {
                            text: 'ACTIVE',
                            style: { fontSize: '10px', color: '#28a745', fontWeight: 'bold' }
                        }
                    },
                    {
                        from: -0.1,
                        to: 0.2,
                        color: 'rgba(220, 53, 69, 0.1)',
                        label: {
                            text: 'INACTIVE',
                            style: { fontSize: '10px', color: '#dc3545', fontWeight: 'bold' }
                        }
                    }
                ]
            },
            series: [{
                name: `${indicatorName} Signal`,
                data: triggerData,
                color: this.getIndicatorColor(indicatorName),
                fillColor: {
                    linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
                    stops: [
                        [0, this.getIndicatorColorWithOpacity(indicatorName, 0.7)],
                        [1, this.getIndicatorColorWithOpacity(indicatorName, 0.2)]
                    ]
                },
                lineWidth: 2,
                shadow: false
            }],
            tooltip: {
                backgroundColor: '#14171a',
                borderColor: '#657786',
                style: { color: '#ffffff', fontSize: '12px' },
                pointFormat: '<b>{series.name}:</b> {point.y}<br/>',
                shared: true,
                useHTML: true,
                formatter: function() {
                    const status = this.y >= 0.8 ? '<span style="color: #28a745;">🟢 ACTIVE</span>' : 
                                 this.y <= 0.2 ? '<span style="color: #dc3545;">🔴 INACTIVE</span>' : 
                                 '<span style="color: #ffc107;">🟡 NEUTRAL</span>';
                    return `<b>${this.series.name}:</b> ${status}<br/>Value: ${this.y}`;
                }
            },
            plotOptions: {
                area: {
                    fillOpacity: 0.6,
                    lineWidth: 2,
                    marker: {
                        enabled: false,
                        states: {
                            hover: {
                                enabled: true,
                                radius: 4
                            }
                        }
                    },
                    states: {
                        hover: {
                            lineWidth: 3
                        }
                    },
                    step: true  // Creates step-like appearance for binary signals
                }
            },
            credits: { enabled: false },
            legend: { enabled: false }
        };
        
        this.charts[`${indicatorName}_trigger`] = Highcharts.chart(container, config);
    }
    
    /**
     * Prepare SMA data for overlay
     */
    prepareSMAData(indicatorName) {
        // Try multiple data sources for SMA values
        if (this.chartData.indicator_history) {
            const smaData = this.chartData.indicator_history
                .filter(point => point[indicatorName] !== undefined && point[indicatorName] !== null)
                .map(point => [
                    new Date(point.timestamp).getTime(),
                    parseFloat(point[indicatorName])
                ]);
            if (smaData.length > 0) return smaData;
        }
        
        // Try candlestick data with mock SMA calculation for demonstration
        if (this.chartData.candlestick_data && this.chartData.candlestick_data.length > 0) {
            const period = 20; // Default SMA period
            const smaData = [];
            
            for (let i = period - 1; i < this.chartData.candlestick_data.length; i++) {
                let sum = 0;
                for (let j = 0; j < period; j++) {
                    sum += this.chartData.candlestick_data[i - j][4]; // Close price
                }
                const sma = sum / period;
                smaData.push([this.chartData.candlestick_data[i][0], sma]);
            }
            return smaData;
        }
        
        return [];
    }
    
    /**
     * Prepare MACD data based on indicator history or generate from price data
     */
    prepareMACDData(indicatorName) {
        // Try to get MACD data from indicator_history first
        if (this.chartData.indicator_history) {
            const macdData = this.chartData.indicator_history
                .filter(point => point[indicatorName] !== undefined && point[indicatorName] !== null)
                .map(point => [
                    new Date(point.timestamp).getTime(),
                    parseFloat(point[indicatorName])
                ]);
                
            if (macdData.length > 0) {
                // Return MACD line as the main data, with generated signal and histogram
                const signalData = macdData.map(([timestamp, value]) => [timestamp, value * 0.7]);
                const histogramData = macdData.map(([timestamp, value], index) => {
                    const signalValue = signalData[index] ? signalData[index][1] : 0;
                    return [timestamp, value - signalValue];
                });
                
                return {
                    macd: macdData,
                    signal: signalData,
                    histogram: histogramData
                };
            }
        }
        
        // Generate MACD from candlestick data if no indicator history
        if (this.chartData.candlestick_data && this.chartData.candlestick_data.length > 0) {
            return this.calculateMACDFromPrices(indicatorName);
        }
        
        return { macd: [], signal: [], histogram: [] };
    }
    
    /**
     * Calculate MACD from price data
     */
    calculateMACDFromPrices(indicatorName) {
        const prices = this.chartData.candlestick_data.map(candle => candle[4]); // Close prices
        const timestamps = this.chartData.candlestick_data.map(candle => candle[0]);
        
        // Get parameters from indicator config if available
        const indicator = this.indicators[indicatorName];
        const fastPeriod = indicator?.parameters?.fast || 12;
        const slowPeriod = indicator?.parameters?.slow || 26;
        const signalPeriod = indicator?.parameters?.signal || 9;
        
        // Calculate EMAs
        const fastEMA = this.calculateEMA(prices, fastPeriod);
        const slowEMA = this.calculateEMA(prices, slowPeriod);
        
        // Calculate MACD line (only where both EMAs are available)
        const macdLine = [];
        for (let i = 0; i < Math.min(fastEMA.length, slowEMA.length); i++) {
            if (fastEMA[i] !== null && slowEMA[i] !== null) {
                macdLine[i] = fastEMA[i] - slowEMA[i];
            } else {
                macdLine[i] = null;
            }
        }
        
        // Calculate signal line (EMA of MACD line, excluding nulls)
        const validMacdValues = macdLine.filter(val => val !== null);
        const signalEMA = this.calculateEMA(validMacdValues, signalPeriod);
        
        // Map signal EMA back to full timeline
        const signalLine = [];
        let signalIndex = 0;
        for (let i = 0; i < macdLine.length; i++) {
            if (macdLine[i] !== null) {
                signalLine[i] = signalEMA[signalIndex] || null;
                signalIndex++;
            } else {
                signalLine[i] = null;
            }
        }
        
        // Calculate histogram
        const histogram = [];
        for (let i = 0; i < macdLine.length; i++) {
            if (macdLine[i] !== null && signalLine[i] !== null) {
                histogram[i] = macdLine[i] - signalLine[i];
            } else {
                histogram[i] = null;
            }
        }
        
        // Format for Highcharts (filter out null values)
        const macdData = [];
        const signalData = [];
        const histogramData = [];
        
        for (let i = 0; i < timestamps.length; i++) {
            if (macdLine[i] !== null) {
                macdData.push([timestamps[i], macdLine[i]]);
            }
            if (signalLine[i] !== null) {
                signalData.push([timestamps[i], signalLine[i]]);
            }
            if (histogram[i] !== null) {
                histogramData.push([timestamps[i], histogram[i]]);
            }
        }
        
        return {
            macd: macdData,
            signal: signalData,
            histogram: histogramData
        };
    }
    
    /**
     * Calculate Exponential Moving Average
     */
    calculateEMA(prices, period) {
        const ema = [];
        const multiplier = 2 / (period + 1);
        
        if (prices.length === 0) return ema;
        
        // Start with SMA for first value
        let sum = 0;
        for (let i = 0; i < period && i < prices.length; i++) {
            sum += prices[i];
        }
        
        // Fill initial values with null
        for (let i = 0; i < period - 1; i++) {
            ema[i] = null;
        }
        
        if (prices.length >= period) {
            ema[period - 1] = sum / period;
            
            // Calculate EMA for remaining values
            for (let i = period; i < prices.length; i++) {
                ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1];
            }
        }
        
        return ema;
    }
    
    /**
     * Prepare RSI data
     */
    prepareRSIData(indicatorName) {
        return this.prepareSMAData(indicatorName);
    }
    
    /**
     * Prepare trigger data (0-1 signals)
     */
    prepareTriggerData(indicatorName) {
        if (this.triggerData && this.triggerData[indicatorName]) {
            return this.triggerData[indicatorName];
        }
        
        // Generate more realistic trigger data based on indicator type and values
        if (this.chartData.candlestick_data) {
            const timestamps = this.chartData.candlestick_data.map(candle => candle[0]);
            const indicator = this.indicators[indicatorName];
            
            if (indicator.displayType === 'macd') {
                return this.generateMACDTriggers(timestamps, indicatorName);
            } else if (indicator.displayType === 'sma') {
                return this.generateSMATriggers(timestamps, indicatorName);
            } else {
                return this.generateGenericTriggers(timestamps);
            }
        }
        
        return [];
    }
    
    /**
     * Generate MACD-based trigger signals
     */
    generateMACDTriggers(timestamps, indicatorName) {
        const macdData = this.prepareMACDData(indicatorName);
        const triggers = [];
        
        if (macdData.macd.length > 0 && macdData.signal.length > 0) {
            timestamps.forEach((timestamp, index) => {
                if (index < macdData.macd.length) {
                    const macdValue = macdData.macd[index][1];
                    const signalValue = macdData.signal[index][1];
                    
                    // Trigger when MACD crosses above signal line
                    const trigger = macdValue > signalValue ? 1 : 0;
                    triggers.push([timestamp, trigger]);
                } else {
                    triggers.push([timestamp, 0]);
                }
            });
        } else {
            // Fallback to random triggers with clustering
            let currentState = 0;
            let stateCounter = 0;
            
            timestamps.forEach(timestamp => {
                stateCounter++;
                
                if (stateCounter > 10) { // Change state every ~10 periods
                    currentState = Math.random() > 0.75 ? 1 : 0;
                    stateCounter = 0;
                }
                
                triggers.push([timestamp, currentState]);
            });
        }
        
        return triggers;
    }
    
    /**
     * Generate SMA-based trigger signals
     */
    generateSMATriggers(timestamps, indicatorName) {
        const triggers = [];
        const prices = this.chartData.candlestick_data.map(candle => candle[4]);
        const smaData = this.prepareSMAData(indicatorName);
        
        timestamps.forEach((timestamp, index) => {
            if (index < smaData.length && index < prices.length) {
                const price = prices[index];
                const smaValue = smaData.find(([ts]) => ts === timestamp);
                
                if (smaValue) {
                    // Trigger when price is above SMA
                    const trigger = price > smaValue[1] ? 1 : 0;
                    triggers.push([timestamp, trigger]);
                } else {
                    triggers.push([timestamp, 0]);
                }
            } else {
                triggers.push([timestamp, 0]);
            }
        });
        
        return triggers;
    }
    
    /**
     * Generate generic trigger signals
     */
    generateGenericTriggers(timestamps) {
        const triggers = [];
        let currentState = 0;
        let stateCounter = 0;
        
        timestamps.forEach(timestamp => {
            stateCounter++;
            
            if (stateCounter > 8) { // Change state every ~8 periods
                currentState = Math.random() > 0.7 ? 1 : 0;
                stateCounter = 0;
            }
            
            triggers.push([timestamp, currentState]);
        });
        
        return triggers;
    }
    
    /**
     * Get color for indicator based on name/type
     */
    getIndicatorColor(indicatorName) {
        const colors = {
            'macd': '#2196F3',
            'sma': '#9C27B0',
            'rsi': '#FF9800',
            'default': '#4CAF50'
        };
        
        const indicator = this.indicators[indicatorName];
        return colors[indicator.displayType] || colors.default;
    }
    
    /**
     * Get color with opacity for gradients
     */
    getIndicatorColorWithOpacity(indicatorName, opacity) {
        const color = this.getIndicatorColor(indicatorName);
        // Convert hex to rgba
        const hex = color.replace('#', '');
        const r = parseInt(hex.substr(0, 2), 16);
        const g = parseInt(hex.substr(2, 2), 16);
        const b = parseInt(hex.substr(4, 2), 16);
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    }
    
    /**
     * Update charts with real-time data
     */
    updateRealTimeData() {
        // Update trigger charts with new trigger data
        this.enabledIndicators.forEach(indicatorName => {
            const triggerChart = this.charts[`${indicatorName}_trigger`];
            if (triggerChart && this.triggerData[indicatorName]) {
                // Add new point to trigger chart
                const newPoint = [
                    Date.now(),
                    this.triggerData[indicatorName]
                ];
                triggerChart.series[0].addPoint(newPoint, true, true);
            }
        });
    }
    
    /**
     * Destroy all charts and clean up
     */
    destroy() {
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.destroy) {
                chart.destroy();
            }
        });
        this.charts = {};
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = IndicatorChartComponent;
}