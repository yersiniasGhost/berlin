/**
 * Indicator Charts Module - Shared chart visualization functions
 *
 * Reusable chart components for indicator visualization including:
 * - MACD stacked charts (histogram + lines)
 * - SMA/EMA overlay charts (price + indicator line)
 * - Trigger value charts (time-decayed values)
 * - P&L evolution charts
 * - Chart synchronization (zoom, pan)
 * - Trade background bands with P&L labels
 *
 * Compatible with both replay visualization and live card details.
 */

// Global charts registry for synchronization
window.indicatorCharts = window.indicatorCharts || {};

/**
 * Configuration defaults for charts
 */
const CHART_DEFAULTS = {
    height: {
        candlestick: 500,
        indicator: 300,
        trigger: 200,
        pnl: 300
    },
    colors: {
        upCandle: '#28a745',
        downCandle: '#dc3545',
        macdLine: '#2962FF',
        signalLine: '#FF6D00',
        histogram: '#00897B',
        triggerLine: '#9C27B0',
        pnlLine: '#007bff',
        profitBand: 'rgba(40, 167, 69, 0.1)',
        lossBand: 'rgba(220, 53, 69, 0.1)',
        extendedHoursBand: 'rgba(100, 100, 140, 0.12)'  // Subtle blue-gray for extended hours
    },
    // Market hours are ALWAYS in Eastern Time (US markets)
    // These are used to calculate UTC timestamps for any given date
    marketHoursET: {
        openHour: 9,
        openMinute: 30,
        closeHour: 16,
        closeMinute: 0,
        premarketStartHour: 4,
        premarketStartMinute: 0,
        afterhoursEndHour: 20,
        afterhoursEndMinute: 0
    }
};

/**
 * Helper function to find component keys by pattern matching
 */
function findComponentKeys(indicatorName, componentHistory, componentNames) {
    const foundKeys = {};

    for (const componentName of componentNames) {
        // Look for keys that end with the component name
        // Pattern: {indicatorName}_{componentName}
        const matchingKey = Object.keys(componentHistory).find(key => {
            return key.startsWith(indicatorName + '_') && key.endsWith('_' + componentName);
        });

        if (matchingKey) {
            foundKeys[componentName] = matchingKey;
        }
    }

    return foundKeys;
}

/**
 * Create MACD-style stacked chart (histogram + signal lines)
 */
function createMACDChart(indicatorName, componentHistory, chartId, chartsRegistry) {
    chartsRegistry = chartsRegistry || window.indicatorCharts;

    console.log(`📊 [MACD CHART] Creating chart for '${indicatorName}'`);
    console.log(`   Available components:`, Object.keys(componentHistory));

    const componentKeys = findComponentKeys(indicatorName, componentHistory, ['macd', 'signal', 'histogram']);

    const series = [];
    if (componentKeys.macd && componentHistory[componentKeys.macd]) {
        series.push({
            name: 'MACD Line',
            data: componentHistory[componentKeys.macd],
            color: CHART_DEFAULTS.colors.macdLine,
            lineWidth: 2,
            marker: { enabled: false }
        });
    }
    if (componentKeys.signal && componentHistory[componentKeys.signal]) {
        series.push({
            name: 'Signal Line',
            data: componentHistory[componentKeys.signal],
            color: CHART_DEFAULTS.colors.signalLine,
            lineWidth: 2,
            marker: { enabled: false }
        });
    }
    if (componentKeys.histogram && componentHistory[componentKeys.histogram]) {
        series.push({
            name: 'Histogram',
            data: componentHistory[componentKeys.histogram],
            type: 'column',
            color: CHART_DEFAULTS.colors.histogram
        });
    }

    if (series.length === 0) {
        console.warn(`⚠️ No MACD components found for '${indicatorName}'.`);
    }

    const chartConfig = {
        chart: {
            height: CHART_DEFAULTS.height.indicator,
            zoomType: 'x',
            panKey: 'shift',
            panning: { enabled: true, type: 'x' }
        },
        title: { text: `${indicatorName} - Raw Values`, style: { fontSize: '14px' } },
        xAxis: {
            type: 'datetime',
            ordinal: true,
            labels: { enabled: false },
            lineWidth: 0,
            tickWidth: 0,
            crosshair: true
        },
        yAxis: { title: { text: 'Value' }, crosshair: true },
        series: series,
        credits: { enabled: false },
        legend: { enabled: series.length > 1 }
    };

    const chart = Highcharts.chart(chartId, chartConfig);
    chartsRegistry[`raw_${indicatorName}`] = chart;

    enableChartSynchronization(chart, chartsRegistry);

    return chart;
}

/**
 * Create SMA/EMA overlay chart (price candlestick + indicator line)
 */
function createSMAChart(indicatorName, componentHistory, candlestickData, chartId, chartsRegistry) {
    chartsRegistry = chartsRegistry || window.indicatorCharts;

    console.log(`📊 [SMA CHART] Creating chart for '${indicatorName}'`);

    const componentKeys = findComponentKeys(indicatorName, componentHistory, ['sma']);

    const series = [
        {
            name: 'Price',
            data: candlestickData,
            type: 'candlestick',
            color: CHART_DEFAULTS.colors.downCandle,
            upColor: CHART_DEFAULTS.colors.upCandle
        }
    ];

    if (componentKeys.sma && componentHistory[componentKeys.sma]) {
        series.push({
            name: indicatorName,
            data: componentHistory[componentKeys.sma],
            type: 'line',
            color: CHART_DEFAULTS.colors.macdLine,
            lineWidth: 2,
            marker: { enabled: false }
        });
    } else {
        console.warn(`⚠️ No SMA component found for '${indicatorName}'.`);
    }

    const chartConfig = {
        chart: {
            height: CHART_DEFAULTS.height.indicator,
            zoomType: 'x',
            panKey: 'shift',
            panning: { enabled: true, type: 'x' }
        },
        title: { text: `${indicatorName} - Raw Values (with Price)`, style: { fontSize: '14px' } },
        xAxis: {
            type: 'datetime',
            ordinal: true,
            labels: { enabled: false },
            lineWidth: 0,
            tickWidth: 0,
            crosshair: true
        },
        yAxis: { title: { text: 'Price' }, crosshair: true },
        series: series,
        credits: { enabled: false },
        legend: { enabled: true }
    };

    const chart = Highcharts.chart(chartId, chartConfig);
    chartsRegistry[`raw_${indicatorName}`] = chart;

    enableChartSynchronization(chart, chartsRegistry);

    return chart;
}

/**
 * Create generic indicator chart for unknown types
 */
function createGenericIndicatorChart(indicatorName, componentHistory, chartId, chartsRegistry) {
    chartsRegistry = chartsRegistry || window.indicatorCharts;

    // Find any matching components
    const matchingKeys = Object.keys(componentHistory).filter(k =>
        k.toLowerCase().includes(indicatorName.toLowerCase())
    );

    const series = matchingKeys.map((key, idx) => ({
        name: key,
        data: componentHistory[key],
        lineWidth: 2,
        marker: { enabled: false },
        color: ['#2962FF', '#FF6D00', '#00897B', '#9C27B0'][idx % 4]
    }));

    const chartConfig = {
        chart: {
            height: CHART_DEFAULTS.height.indicator,
            zoomType: 'x',
            panKey: 'shift',
            panning: { enabled: true, type: 'x' }
        },
        title: { text: `${indicatorName} - Raw Values`, style: { fontSize: '14px' } },
        xAxis: {
            type: 'datetime',
            ordinal: true,
            labels: { enabled: false },
            lineWidth: 0,
            tickWidth: 0,
            crosshair: true
        },
        yAxis: { title: { text: 'Value' }, crosshair: true },
        series: series,
        credits: { enabled: false },
        legend: { enabled: series.length > 1 }
    };

    const chart = Highcharts.chart(chartId, chartConfig);
    chartsRegistry[`raw_${indicatorName}`] = chart;

    enableChartSynchronization(chart, chartsRegistry);

    return chart;
}

/**
 * Create trigger value chart (time-decayed values 0-1.1)
 */
function createTriggerChart(indicatorName, rawIndicatorHistory, indicatorHistory, chartId, chartsRegistry) {
    chartsRegistry = chartsRegistry || window.indicatorCharts;

    console.log(`📊 [TRIGGER CHART] Creating chart for '${indicatorName}'`);

    const series = [];

    // Add time-decayed trigger values
    if (indicatorHistory && indicatorHistory[indicatorName]) {
        series.push({
            name: 'Trigger with Decay',
            data: indicatorHistory[indicatorName],
            color: CHART_DEFAULTS.colors.triggerLine,
            lineWidth: 2,
            marker: { enabled: false }
        });
    }

    const chartConfig = {
        chart: {
            height: CHART_DEFAULTS.height.trigger,
            zoomType: 'x',
            panKey: 'shift',
            panning: { enabled: true, type: 'x' }
        },
        title: { text: `${indicatorName} - Trigger Values`, style: { fontSize: '14px' } },
        xAxis: {
            type: 'datetime',
            ordinal: true,
            labels: { enabled: true },
            crosshair: true
        },
        yAxis: {
            title: { text: 'Trigger Value' },
            min: 0,
            max: 1.1,
            plotLines: [{
                value: 1,
                color: '#999',
                width: 1,
                dashStyle: 'dash'
            }],
            crosshair: true
        },
        series: series,
        credits: { enabled: false }
    };

    const chart = Highcharts.chart(chartId, chartConfig);
    chartsRegistry[`trigger_${indicatorName}`] = chart;

    enableChartSynchronization(chart, chartsRegistry);

    return chart;
}

/**
 * Create candlestick chart with trade background bands
 */
function createCandlestickChart(candlestickData, trades, chartId, chartsRegistry) {
    chartsRegistry = chartsRegistry || window.indicatorCharts;

    const chartConfig = {
        chart: {
            height: CHART_DEFAULTS.height.candlestick,
            zoomType: 'x',
            panKey: 'shift',
            panning: { enabled: true, type: 'x' },
            marginBottom: 10
        },
        title: { text: 'Price Chart with Trade Background Shading' },
        xAxis: {
            type: 'datetime',
            ordinal: true,
            crosshair: true,
            labels: { enabled: false },
            lineWidth: 0,
            tickWidth: 0,
            plotBands: []
        },
        yAxis: {
            title: { text: 'Price' },
            crosshair: true
        },
        series: [
            {
                name: 'Price',
                data: candlestickData,
                type: 'candlestick',
                color: CHART_DEFAULTS.colors.downCandle,
                upColor: CHART_DEFAULTS.colors.upCandle
            }
        ],
        credits: { enabled: false }
    };

    // Destroy existing chart if present
    if (chartsRegistry.candlestick) {
        chartsRegistry.candlestick.destroy();
    }

    const chart = Highcharts.chart(chartId, chartConfig);
    chartsRegistry.candlestick = chart;

    // Add trade bands
    if (trades && trades.length > 0) {
        addTradeBandsToChart(chart, trades);
    }

    enableChartSynchronization(chart, chartsRegistry);

    return chart;
}

/**
 * Create P&L evolution chart
 */
function createPnLChart(pnlData, trades, candlestickData, chartId, chartsRegistry) {
    chartsRegistry = chartsRegistry || window.indicatorCharts;

    let adjustedPnlData = [];

    // Get time range from candlestick data
    const candlestickStart = candlestickData[0] ? candlestickData[0][0] : Date.now();
    const candlestickEnd = candlestickData.length > 0 ?
        candlestickData[candlestickData.length - 1][0] : Date.now();

    if (!trades || trades.length === 0) {
        // No trades - flat line at 0
        adjustedPnlData.push([candlestickStart, 0]);
        adjustedPnlData.push([candlestickEnd, 0]);
    } else {
        // Sort trades by timestamp
        const sortedTrades = [...trades].sort((a, b) =>
            new Date(a.timestamp) - new Date(b.timestamp)
        );
        const buyTrades = sortedTrades.filter(t => t.type === 'buy');
        const sellTrades = sortedTrades.filter(t => t.type === 'sell');

        // Create candlestick map for quick lookup
        const candlestickMap = new Map();
        candlestickData.forEach(candle => {
            candlestickMap.set(candle[0], candle[4]); // timestamp -> close price
        });

        let cumulativeRealizedPnL = 0;
        let currentPosition = null;
        let buyIndex = 0;
        let sellIndex = 0;

        // Process each candlestick chronologically
        candlestickData.forEach((candle) => {
            const timestamp = candle[0];
            const closePrice = candle[4];

            // Check for buy trades
            while (buyIndex < buyTrades.length &&
                   new Date(buyTrades[buyIndex].timestamp).getTime() <= timestamp) {
                if (!currentPosition) {
                    currentPosition = {
                        entryPrice: buyTrades[buyIndex].price,
                        entryTime: new Date(buyTrades[buyIndex].timestamp).getTime()
                    };
                }
                buyIndex++;
            }

            // Check for sell trades
            while (sellIndex < sellTrades.length &&
                   new Date(sellTrades[sellIndex].timestamp).getTime() <= timestamp) {
                if (currentPosition) {
                    cumulativeRealizedPnL += (sellTrades[sellIndex].pnl || 0);
                    currentPosition = null;
                }
                sellIndex++;
            }

            // Add data points
            if (currentPosition) {
                const unrealizedPnL = ((closePrice - currentPosition.entryPrice) /
                                       currentPosition.entryPrice) * 100;
                const currentPnL = cumulativeRealizedPnL + unrealizedPnL;
                adjustedPnlData.push([timestamp, currentPnL]);
            } else if (adjustedPnlData.length > 0) {
                const lastDataPoint = adjustedPnlData[adjustedPnlData.length - 1];
                if (lastDataPoint[0] < timestamp) {
                    adjustedPnlData.push([timestamp, cumulativeRealizedPnL]);
                }
            } else {
                adjustedPnlData.push([timestamp, 0]);
            }
        });
    }

    const chartConfig = {
        chart: {
            type: 'line',
            height: CHART_DEFAULTS.height.pnl,
            zoomType: 'x',
            panKey: 'shift',
            panning: { enabled: true, type: 'x' },
            marginBottom: 60
        },
        title: { text: 'Cumulative P&L Evolution' },
        xAxis: {
            type: 'datetime',
            ordinal: true,
            crosshair: true,
            labels: { enabled: true },
            lineWidth: 1,
            tickWidth: 1
        },
        yAxis: {
            title: { text: 'Cumulative P&L (%)' },
            plotLines: [{
                value: 0,
                color: '#999',
                width: 1,
                dashStyle: 'dash'
            }],
            crosshair: true
        },
        series: [{
            name: 'Cumulative P&L',
            data: adjustedPnlData,
            color: CHART_DEFAULTS.colors.pnlLine,
            lineWidth: 2
        }],
        credits: { enabled: false }
    };

    if (chartsRegistry.pnl) {
        chartsRegistry.pnl.destroy();
    }

    const chart = Highcharts.chart(chartId, chartConfig);
    chartsRegistry.pnl = chart;

    enableChartSynchronization(chart, chartsRegistry);

    return chart;
}

/**
 * Add trade background shading bands to a chart
 */
function addTradeBandsToChart(chart, trades) {
    if (!chart || !trades || trades.length === 0) return;

    // Clear existing trade bands
    if (chart.xAxis[0].plotLinesAndBands) {
        chart.xAxis[0].plotLinesAndBands.slice().forEach(band => {
            if (band.options.className && band.options.className.includes('trade-band')) {
                band.destroy();
            }
        });
    }

    // Group trades by pairs (buy followed by sell)
    const buyTrades = trades.filter(t => t.type === 'buy')
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const sellTrades = trades.filter(t => t.type === 'sell')
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    // Create trade pairs and add background bands
    let buyIndex = 0, sellIndex = 0;
    let tradeCount = 0;

    while (buyIndex < buyTrades.length && sellIndex < sellTrades.length) {
        const buyTrade = buyTrades[buyIndex];
        const sellTrade = sellTrades[sellIndex];

        if (new Date(buyTrade.timestamp) < new Date(sellTrade.timestamp)) {
            // Calculate P&L for this trade pair
            const entryPrice = buyTrade.price;
            const exitPrice = sellTrade.price;
            const pnl = ((exitPrice - entryPrice) / entryPrice) * 100;

            // Use actual P&L from trade data if available
            const actualPnl = sellTrade.pnl || pnl;
            const isProfit = actualPnl > 0;

            const bandColor = isProfit ?
                CHART_DEFAULTS.colors.profitBand :
                CHART_DEFAULTS.colors.lossBand;

            chart.xAxis[0].addPlotBand({
                from: new Date(buyTrade.timestamp).getTime(),
                to: new Date(sellTrade.timestamp).getTime(),
                color: bandColor,
                className: `trade-band trade-${tradeCount}`,
                id: `trade-band-${tradeCount}`,
                zIndex: 0,
                label: {
                    text: `${isProfit ? '+' : ''}${actualPnl.toFixed(2)}%`,
                    align: 'center',
                    verticalAlign: 'middle',
                    style: {
                        color: isProfit ? '#28a745' : '#dc3545',
                        fontWeight: 'bold',
                        fontSize: '10px',
                        backgroundColor: 'rgba(255, 255, 255, 0.8)',
                        padding: '2px 4px',
                        borderRadius: '3px'
                    }
                }
            });

            buyIndex++;
            sellIndex++;
            tradeCount++;
        } else {
            sellIndex++;
        }
    }

    console.log(`📊 Added ${tradeCount} trade bands to chart`);
}

/**
 * Get market hours boundaries for a specific date in UTC milliseconds
 * Market hours are always in Eastern Time (America/New_York)
 *
 * @param {Date} date - Any date to get market hours for (uses the calendar date)
 * @returns {object} Object with premarketStart, marketOpen, marketClose, afterhoursEnd in UTC ms
 */
function getMarketHoursForDate(date) {
    const mh = CHART_DEFAULTS.marketHoursET;

    // Create dates in ET timezone for the given calendar date
    // We need to construct the time in ET then convert to UTC timestamp
    const year = date.getFullYear();
    const month = date.getMonth();
    const day = date.getDate();

    // Helper to create a date at specific ET time and get UTC timestamp
    function etTimeToUtcMs(hour, minute) {
        // Create a date string that we can parse with ET timezone
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const timeStr = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`;

        // Use Intl to format in ET and calculate offset
        const etDate = new Date(`${dateStr}T${timeStr}`);

        // Get the ET offset for this date (handles DST automatically)
        const etFormatter = new Intl.DateTimeFormat('en-US', {
            timeZone: 'America/New_York',
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: false
        });

        // Calculate offset by comparing UTC vs ET formatted times
        const utcDate = new Date(Date.UTC(year, month, day, hour, minute, 0));
        const etParts = etFormatter.formatToParts(utcDate);
        const etHour = parseInt(etParts.find(p => p.type === 'hour').value);

        // The difference tells us the offset
        let offsetHours = hour - etHour;
        if (offsetHours > 12) offsetHours -= 24;
        if (offsetHours < -12) offsetHours += 24;

        // Adjust UTC time by the offset to get actual ET time in UTC
        return Date.UTC(year, month, day, hour + offsetHours, minute, 0);
    }

    // Alternative simpler approach: use the browser's timezone conversion
    function etTimeToUtcMsSimple(hour, minute) {
        // Create an ISO string with the target ET time, then let JS parse it
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const timeStr = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`;

        // Create date in local time first
        const localDate = new Date(`${dateStr}T${timeStr}`);

        // We need to find what UTC time corresponds to this ET time
        // Try a different approach: create formatter that shows us the offset
        try {
            const testDate = new Date(Date.UTC(year, month, day, 12, 0, 0)); // noon UTC
            const etString = testDate.toLocaleString('en-US', {
                timeZone: 'America/New_York',
                hour: 'numeric',
                hour12: false
            });
            const etHourAtNoonUtc = parseInt(etString);
            const etOffsetHours = etHourAtNoonUtc - 12; // negative means behind UTC

            // ET time we want, adjusted to UTC
            return Date.UTC(year, month, day, hour - etOffsetHours, minute, 0);
        } catch (e) {
            // Fallback: assume EST (UTC-5)
            return Date.UTC(year, month, day, hour + 5, minute, 0);
        }
    }

    return {
        premarketStart: etTimeToUtcMsSimple(mh.premarketStartHour, mh.premarketStartMinute),
        marketOpen: etTimeToUtcMsSimple(mh.openHour, mh.openMinute),
        marketClose: etTimeToUtcMsSimple(mh.closeHour, mh.closeMinute),
        afterhoursEnd: etTimeToUtcMsSimple(mh.afterhoursEndHour, mh.afterhoursEndMinute)
    };
}

/**
 * Check if a given date is a trading day (weekday)
 * @param {Date} date - Date to check
 * @returns {boolean} True if weekday
 */
function isTradingDay(date) {
    const day = date.getDay();
    return day !== 0 && day !== 6; // Not Sunday (0) or Saturday (6)
}

/**
 * Add market hours background shading to a chart
 * Extended hours (premarket and afterhours) are shaded with a subtle background
 * Regular market hours (9:30 AM - 4:00 PM ET) remain unshaded
 *
 * @param {Highcharts.Chart} chart - The Highcharts chart instance
 * @param {Array} candlestickData - Array of [timestamp, o, h, l, c] data
 */
function addMarketHoursBandsToChart(chart, candlestickData) {
    if (!chart || !candlestickData || candlestickData.length === 0) return;

    // Clear existing market hours bands
    if (chart.xAxis[0].plotLinesAndBands) {
        chart.xAxis[0].plotLinesAndBands.slice().forEach(band => {
            if (band.options.className && band.options.className.includes('market-hours-band')) {
                band.destroy();
            }
        });
    }

    // Get time range from candlestick data
    const startTime = candlestickData[0][0];
    const endTime = candlestickData[candlestickData.length - 1][0];

    // Find unique trading days in the data
    const startDate = new Date(startTime);
    const endDate = new Date(endTime);

    // Iterate through each day and add bands for extended hours
    const currentDate = new Date(startDate);
    currentDate.setUTCHours(0, 0, 0, 0);

    const endDateCheck = new Date(endDate);
    endDateCheck.setUTCHours(23, 59, 59, 999);

    let bandCount = 0;
    const bandColor = CHART_DEFAULTS.colors.extendedHoursBand;

    while (currentDate <= endDateCheck) {
        // Only add bands for weekdays
        if (isTradingDay(currentDate)) {
            const hours = getMarketHoursForDate(currentDate);

            // Add premarket band (4:00 AM - 9:30 AM ET)
            // Only add if it overlaps with our data range
            if (hours.premarketStart < endTime && hours.marketOpen > startTime) {
                const bandStart = Math.max(hours.premarketStart, startTime);
                const bandEnd = Math.min(hours.marketOpen, endTime);

                if (bandEnd > bandStart) {
                    chart.xAxis[0].addPlotBand({
                        from: bandStart,
                        to: bandEnd,
                        color: bandColor,
                        className: 'market-hours-band premarket-band',
                        id: `premarket-band-${bandCount}`,
                        zIndex: -1  // Behind trade bands (which use zIndex: 0)
                    });
                    bandCount++;
                }
            }

            // Add afterhours band (4:00 PM - 8:00 PM ET)
            if (hours.marketClose < endTime && hours.afterhoursEnd > startTime) {
                const bandStart = Math.max(hours.marketClose, startTime);
                const bandEnd = Math.min(hours.afterhoursEnd, endTime);

                if (bandEnd > bandStart) {
                    chart.xAxis[0].addPlotBand({
                        from: bandStart,
                        to: bandEnd,
                        color: bandColor,
                        className: 'market-hours-band afterhours-band',
                        id: `afterhours-band-${bandCount}`,
                        zIndex: -1
                    });
                    bandCount++;
                }
            }
        }

        // Move to next day
        currentDate.setUTCDate(currentDate.getUTCDate() + 1);
    }

    console.log(`🕐 Added ${bandCount} market hours bands to chart`);
}

/**
 * Enable chart synchronization (zoom, pan)
 */
function enableChartSynchronization(chart, chartsRegistry) {
    chartsRegistry = chartsRegistry || window.indicatorCharts;

    chart.update({
        chart: {
            events: {
                selection: function(event) {
                    if (event.xAxis) {
                        const min = event.xAxis[0].min;
                        const max = event.xAxis[0].max;
                        syncAllCharts(min, max, chart, chartsRegistry);
                    }
                },
                load: function() {
                    // Add mouse wheel zoom
                    const chartContainer = this.container;

                    chartContainer.addEventListener('wheel', function(e) {
                        if (e.target.closest('.highcharts-container')) {
                            e.preventDefault();
                            e.stopPropagation();

                            if (window.syncInProgress) return;

                            const xAxis = chart.xAxis[0];
                            const currentMin = xAxis.min;
                            const currentMax = xAxis.max;
                            const range = currentMax - currentMin;

                            const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
                            const newRange = range * zoomFactor;

                            // Get mouse position for zoom center
                            const rect = chartContainer.getBoundingClientRect();
                            const mouseX = e.clientX - rect.left;
                            const plotLeft = chart.plotLeft || 60;
                            const plotWidth = chart.plotWidth || (rect.width - 120);

                            let centerRatio = 0.5;
                            if (mouseX >= plotLeft && mouseX <= plotLeft + plotWidth) {
                                centerRatio = (mouseX - plotLeft) / plotWidth;
                            }

                            const center = currentMin + (range * centerRatio);
                            const newMin = center - (newRange * centerRatio);
                            const newMax = center + (newRange * (1 - centerRatio));

                            const dataMin = xAxis.getExtremes().dataMin || currentMin;
                            const dataMax = xAxis.getExtremes().dataMax || currentMax;
                            const minRange = (dataMax - dataMin) / 1000;

                            if (newMin >= dataMin && newMax <= dataMax && newRange > minRange) {
                                syncAllCharts(newMin, newMax, chart, chartsRegistry);
                            }
                        }
                    }, { passive: false });
                }
            }
        },
        xAxis: {
            events: {
                afterSetExtremes: function(e) {
                    if (e.trigger === 'zoom' || e.trigger === 'pan' ||
                        e.trigger === 'selection' || e.trigger === 'mousewheel') {
                        syncAllCharts(e.min, e.max, chart, chartsRegistry);
                    }
                }
            }
        }
    });
}

/**
 * Synchronize all charts to the same x-axis range
 */
function syncAllCharts(min, max, sourceChart, chartsRegistry) {
    chartsRegistry = chartsRegistry || window.indicatorCharts;

    if (window.syncInProgress) return;
    window.syncInProgress = true;

    try {
        Object.values(chartsRegistry).forEach(chart => {
            if (chart !== sourceChart && chart.xAxis && chart.xAxis[0]) {
                chart.xAxis[0].setExtremes(min, max, true, false);
            }
        });
    } finally {
        setTimeout(() => {
            window.syncInProgress = false;
        }, 50);
    }
}

/**
 * Create appropriate indicator chart based on layout type
 */
function createRawIndicatorChart(indicatorName, indicatorClass, componentHistory,
                                  candlestickData, chartId, classToLayout, chartsRegistry) {
    const layoutType = (classToLayout && classToLayout[indicatorClass]) || 'overlay';

    console.log(`📈 Creating chart for '${indicatorName}' (class: ${indicatorClass}) - layout: '${layoutType}'`);

    if (layoutType === 'stacked') {
        return createMACDChart(indicatorName, componentHistory, chartId, chartsRegistry);
    } else if (layoutType === 'overlay') {
        return createSMAChart(indicatorName, componentHistory, candlestickData, chartId, chartsRegistry);
    } else {
        return createGenericIndicatorChart(indicatorName, componentHistory, chartId, chartsRegistry);
    }
}

/**
 * Create all indicator charts with tabs
 */
function createIndicatorCharts(componentHistory, rawIndicatorHistory, indicatorHistory,
                               candlestickData, indicatorConfigs, classToLayout,
                               perAggregatorCandles, indicatorAggMapping,
                               tabsContainerId, contentContainerId, chartsRegistry) {
    chartsRegistry = chartsRegistry || window.indicatorCharts;

    console.log('📊 Creating indicator charts');
    console.log('  Component history keys:', Object.keys(componentHistory || {}));
    console.log('  Raw indicator history keys:', Object.keys(rawIndicatorHistory || {}));
    console.log('  Class to layout:', classToLayout);

    const indicatorNames = Object.keys(rawIndicatorHistory || {});
    if (indicatorNames.length === 0) {
        console.log('⚠️ No indicators found');
        return;
    }

    // Build maps from indicator configs
    const nameToClass = {};
    const nameToAggConfig = {};
    (indicatorConfigs || []).forEach(config => {
        nameToClass[config.name] = config.indicator_class;
        nameToAggConfig[config.name] = config.agg_config || '1m-normal';
    });

    const tabsContainer = document.getElementById(tabsContainerId);
    const contentContainer = document.getElementById(contentContainerId);

    if (!tabsContainer || !contentContainer) {
        console.error('Tabs or content container not found');
        return;
    }

    tabsContainer.innerHTML = '';
    contentContainer.innerHTML = '';

    // Create tabs for each indicator
    indicatorNames.forEach((indicatorName, index) => {
        const isActive = index === 0;
        const tabId = `indicator-tab-${index}`;
        const contentId = `indicator-content-${index}`;

        // Create tab button
        const tabButton = document.createElement('li');
        tabButton.className = 'nav-item';
        tabButton.innerHTML = `
            <button class="nav-link ${isActive ? 'active' : ''}"
                    id="${tabId}"
                    data-bs-toggle="tab"
                    data-bs-target="#${contentId}"
                    data-indicator-name="${indicatorName}"
                    type="button"
                    role="tab">
                ${indicatorName}
            </button>
        `;
        tabsContainer.appendChild(tabButton);

        // Create tab content
        const tabContent = document.createElement('div');
        tabContent.className = `tab-pane fade ${isActive ? 'show active' : ''}`;
        tabContent.id = contentId;
        tabContent.role = 'tabpanel';

        const rawChartId = `rawChart_${indicatorName.replace(/[^a-zA-Z0-9]/g, '_')}`;
        const triggerChartId = `triggerChart_${indicatorName.replace(/[^a-zA-Z0-9]/g, '_')}`;

        tabContent.innerHTML = `
            <div id="${rawChartId}" style="height: 300px; margin-bottom: 10px;"></div>
            <div id="${triggerChartId}" style="height: 200px;"></div>
        `;
        contentContainer.appendChild(tabContent);

        // Create charts after DOM is ready
        setTimeout(() => {
            const indicatorClass = nameToClass[indicatorName];
            const aggConfig = nameToAggConfig[indicatorName] ||
                              (indicatorAggMapping && indicatorAggMapping[indicatorName]) ||
                              '1m-normal';

            // Get correct candlestick data for this indicator's timeframe
            let indicatorCandles = perAggregatorCandles && perAggregatorCandles[aggConfig];
            if (!indicatorCandles) {
                console.warn(`⚠️ No candles for '${aggConfig}', using primary data`);
                indicatorCandles = candlestickData;
            }

            const rawChart = createRawIndicatorChart(
                indicatorName, indicatorClass, componentHistory,
                indicatorCandles, rawChartId, classToLayout, chartsRegistry
            );

            const triggerChart = createTriggerChart(
                indicatorName, rawIndicatorHistory, indicatorHistory,
                triggerChartId, chartsRegistry
            );
        }, 100);
    });
}

/**
 * Calculate trading metrics from trades
 */
function calculateMetrics(trades) {
    let winningTrades = 0;
    let losingTrades = 0;
    let totalWinPnL = 0;
    let totalLossPnL = 0;
    let cumulativePnL = 0;

    (trades || []).forEach(trade => {
        if (trade.pnl > 0) {
            winningTrades++;
            totalWinPnL += trade.pnl;
        } else if (trade.pnl < 0) {
            losingTrades++;
            totalLossPnL += Math.abs(trade.pnl);
        }
        cumulativePnL += (trade.pnl || 0);
    });

    return {
        totalTrades: trades ? trades.length : 0,
        winningTrades,
        losingTrades,
        cumulativePnL,
        avgWin: winningTrades > 0 ? totalWinPnL / winningTrades : 0,
        avgLoss: losingTrades > 0 ? totalLossPnL / losingTrades : 0,
        winRate: trades && trades.length > 0 ?
            (winningTrades / trades.length * 100) : 0
    };
}

// Export functions for use in other scripts
window.IndicatorCharts = {
    createMACDChart,
    createSMAChart,
    createGenericIndicatorChart,
    createTriggerChart,
    createCandlestickChart,
    createPnLChart,
    createRawIndicatorChart,
    createIndicatorCharts,
    addTradeBandsToChart,
    addMarketHoursBandsToChart,
    getMarketHoursForDate,
    enableChartSynchronization,
    syncAllCharts,
    calculateMetrics,
    findComponentKeys,
    CHART_DEFAULTS
};
