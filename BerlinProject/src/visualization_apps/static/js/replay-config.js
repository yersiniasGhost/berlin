/**
 * Replay Configuration Editor
 * Handles dynamic loading, editing, and saving of replay configurations
 */

let monitorConfig = null;
let dataConfig = null;
let currentMonitorFilename = null;
let currentDataFilename = null;
let indicatorClasses = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadIndicatorClasses();
    setupEventListeners();
});

function setupEventListeners() {
    // Monitor file input
    document.getElementById('monitorFileInput').addEventListener('change', function() {
        const loadBtn = document.getElementById('loadMonitorBtn');
        loadBtn.disabled = !this.files.length;
    });

    // Data file input
    document.getElementById('dataFileInput').addEventListener('change', function() {
        const loadBtn = document.getElementById('loadDataBtn');
        loadBtn.disabled = !this.files.length;
    });

    // Load buttons
    document.getElementById('loadMonitorBtn').addEventListener('click', loadMonitorConfiguration);
    document.getElementById('loadDataBtn').addEventListener('click', loadDataConfiguration);

    // Save button
    document.getElementById('saveBtn').addEventListener('click', saveConfiguration);

    // Cancel button
    document.getElementById('cancelBtn').addEventListener('click', function() {
        if (confirm('Are you sure you want to cancel? Unsaved changes will be lost.')) {
            document.getElementById('configEditor').style.display = 'none';
            monitorConfig = null;
            dataConfig = null;
        }
    });

    // Run replay button
    document.getElementById('runReplayBtn').addEventListener('click', runReplay);

    // Add indicator/bar buttons
    document.getElementById('addIndicatorBtn').addEventListener('click', addIndicator);
    document.getElementById('addBarBtn').addEventListener('click', addBar);
}

async function loadIndicatorClasses() {
    try {
        const response = await fetch('/monitor_config/api/get_indicator_classes');
        const result = await response.json();

        if (result.success) {
            indicatorClasses = result.indicators;
            console.log('Loaded indicator classes:', indicatorClasses);
        } else {
            showAlert('Failed to load indicator classes: ' + result.error, 'warning');
        }
    } catch (error) {
        console.error('Error loading indicator classes:', error);
    }
}

async function loadMonitorConfiguration() {
    const fileInput = document.getElementById('monitorFileInput');
    if (!fileInput.files.length) return;

    const file = fileInput.files[0];
    currentMonitorFilename = file.name;

    try {
        const text = await file.text();
        monitorConfig = JSON.parse(text);

        renderMonitorConfiguration();
        checkBothConfigsLoaded();
        showAlert('Monitor configuration loaded successfully', 'success');
    } catch (error) {
        showAlert('Error loading monitor configuration: ' + error.message, 'danger');
    }
}

async function loadDataConfiguration() {
    const fileInput = document.getElementById('dataFileInput');
    if (!fileInput.files.length) return;

    const file = fileInput.files[0];
    currentDataFilename = file.name;

    try {
        const text = await file.text();
        dataConfig = JSON.parse(text);

        renderDataConfiguration();
        checkBothConfigsLoaded();
        showAlert('Data configuration loaded successfully', 'success');
    } catch (error) {
        showAlert('Error loading data configuration: ' + error.message, 'danger');
    }
}

function checkBothConfigsLoaded() {
    if (monitorConfig && dataConfig) {
        document.getElementById('configEditor').style.display = 'block';
    }
}

function renderMonitorConfiguration() {
    if (!monitorConfig) return;

    const monitor = monitorConfig.monitor || {};
    const tradeExecutor = monitor.trade_executor || {};
    const indicators = monitorConfig.indicators || [];
    const bars = monitor.bars || {};

    // Monitor tab
    document.getElementById('monitorName').value = monitor.name || '';
    document.getElementById('monitorDescription').value = monitor.description || '';

    // Trade Executor tab
    document.getElementById('positionSize').value = tradeExecutor.default_position_size || 100;
    document.getElementById('stopLoss').value = tradeExecutor.stop_loss_pct || 0.02;
    document.getElementById('takeProfit').value = tradeExecutor.take_profit_pct || 0.04;
    document.getElementById('trailingStopEnabled').checked = tradeExecutor.trailing_stop_loss || false;
    document.getElementById('trailingDistance').value = tradeExecutor.trailing_stop_distance_pct || 0.01;
    document.getElementById('trailingActivation').value = tradeExecutor.trailing_stop_activation_pct || 0.005;
    document.getElementById('ignoreBearSignals').checked = tradeExecutor.ignore_bear_signals || false;

    // Enter/Exit conditions
    renderConditions('enterLongContainer', monitor.enter_long || []);
    renderConditions('exitLongContainer', monitor.exit_long || []);

    // Indicators tab
    renderIndicators(indicators);

    // Bars tab
    renderBars(bars);
}

function renderDataConfiguration() {
    if (!dataConfig) return;

    document.getElementById('dataTicker').value = dataConfig.ticker || '';
    document.getElementById('dataStartDate').value = dataConfig.start_date || '';
    document.getElementById('dataEndDate').value = dataConfig.end_date || '';
}

// Reuse the same functions from monitor-config.js for consistency
// (I'll copy the key functions here to keep it self-contained)

function renderConditions(containerId, conditions) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';

    conditions.forEach((condition, index) => {
        const conditionHtml = `
            <div class="row g-2 mb-2">
                <div class="col-md-5">
                    <select class="form-select" data-condition-index="${index}" data-field="name">
                        ${generateBarNameOptions(condition.name || '')}
                    </select>
                </div>
                <div class="col-md-5">
                    <input type="number" class="form-control" placeholder="Threshold"
                           value="${condition.threshold || 0.5}" step="0.01"
                           data-condition-index="${index}" data-field="threshold">
                </div>
                <div class="col-md-2">
                    <button class="btn btn-danger w-100" onclick="removeCondition('${containerId}', ${index})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', conditionHtml);
    });

    // Add button
    const addButtonHtml = `
        <button class="btn btn-sm btn-primary mt-2" onclick="addCondition('${containerId}')">
            <i class="fas fa-plus me-2"></i>Add Condition
        </button>
    `;
    container.insertAdjacentHTML('beforeend', addButtonHtml);
}

function generateBarNameOptions(selectedName) {
    let options = '<option value="">-- Select Bar --</option>';

    if (monitorConfig && monitorConfig.monitor && monitorConfig.monitor.bars) {
        const bars = monitorConfig.monitor.bars;
        for (const barName of Object.keys(bars)) {
            const isSelected = barName === selectedName ? 'selected' : '';
            options += `<option value="${barName}" ${isSelected}>${barName}</option>`;
        }
    }

    return options;
}

function generateIndicatorNameOptions(selectedName) {
    let options = '<option value="">-- Select Indicator --</option>';

    if (monitorConfig && monitorConfig.indicators) {
        for (const indicator of monitorConfig.indicators) {
            const indName = indicator.name;
            const isSelected = indName === selectedName ? 'selected' : '';
            options += `<option value="${indName}" ${isSelected}>${indName}</option>`;
        }
    }

    return options;
}

function renderIndicators(indicators) {
    const container = document.getElementById('indicatorsContainer');
    container.innerHTML = '';

    indicators.forEach((indicator, index) => {
        const indicatorHtml = createIndicatorCard(indicator, index);
        container.insertAdjacentHTML('beforeend', indicatorHtml);
    });
}

function createIndicatorCard(indicator, index) {
    const params = indicator.parameters || {};
    const indicatorClass = indicator.indicator_class || '';

    return `
        <div class="indicator-card" data-indicator-index="${index}">
            <div class="indicator-card-header" onclick="toggleIndicatorCard(${index})">
                <span class="indicator-card-title">
                    <i class="fas fa-chevron-right collapse-icon" id="collapse-icon-${index}"></i>
                    ${indicator.name || 'New Indicator'}
                </span>
                <button class="btn-remove" onclick="event.stopPropagation(); removeIndicator(${index})">
                    <i class="fas fa-trash me-1"></i>Remove
                </button>
            </div>
            <div class="indicator-card-body" id="indicator-body-${index}">
                <div class="row g-2">
                    <div class="col-md-4">
                        <label class="form-label">Name</label>
                        <input type="text" class="form-control" value="${indicator.name || ''}"
                               data-indicator-field="name" onchange="refreshBarIndicatorDropdowns()">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Indicator Class</label>
                        <select class="form-select" data-indicator-field="indicator_class"
                                onchange="updateIndicatorParams(${index}, this.value)">
                            ${generateIndicatorClassOptions(indicatorClass)}
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Aggregation Config</label>
                        <input type="text" class="form-control" value="${indicator.agg_config || '1m-normal'}"
                               data-indicator-field="agg_config" placeholder="e.g. 1m-normal, 5m-heiken">
                    </div>
                </div>
                <div class="row g-2 mt-2" id="indicator-params-${index}">
                    ${renderIndicatorParams(params, index)}
                </div>
            </div>
        </div>
    `;
}

function generateIndicatorClassOptions(selectedClass) {
    let options = '<option value="">-- Select Class --</option>';

    for (const className of Object.keys(indicatorClasses)) {
        const isSelected = className === selectedClass ? 'selected' : '';
        options += `<option value="${className}" ${isSelected}>${className}</option>`;
    }

    return options;
}

function renderIndicatorParams(params, index) {
    let html = '';
    for (const [key, value] of Object.entries(params)) {
        const inputType = typeof value === 'number' ? 'number' : 'text';
        const step = typeof value === 'number' && value < 1 ? '0.001' : '1';

        html += `
            <div class="col-md-3">
                <label class="form-label">${key}</label>
                <input type="${inputType}" class="form-control" value="${value}"
                       data-indicator-param="${key}" step="${step}">
            </div>
        `;
    }
    return html;
}

function toggleIndicatorCard(index) {
    const body = document.getElementById(`indicator-body-${index}`);
    const icon = document.getElementById(`collapse-icon-${index}`);

    if (body && icon) {
        body.classList.toggle('show');
        icon.classList.toggle('expanded');
    }
}

function updateIndicatorParams(index, className) {
    if (!className || !indicatorClasses[className]) return;

    const schema = indicatorClasses[className];
    const paramsContainer = document.getElementById(`indicator-params-${index}`);

    const paramGroups = schema.parameter_groups || {};
    const allParams = Object.values(paramGroups).flat();

    let html = '';
    allParams.forEach(param => {
        const inputType = param.type === 'integer' || param.type === 'float' ? 'number' : 'text';
        const step = param.type === 'float' ? '0.001' : param.step || '1';

        html += `
            <div class="col-md-3">
                <label class="form-label">${param.display_name}</label>
                <input type="${inputType}" class="form-control" value="${param.default}"
                       data-indicator-param="${param.name}" step="${step}"
                       placeholder="${param.description || ''}">
            </div>
        `;
    });

    paramsContainer.innerHTML = html;
}

function addIndicator() {
    const container = document.getElementById('indicatorsContainer');
    const index = container.querySelectorAll('.indicator-card').length;

    const newIndicator = {
        name: 'new_indicator',
        indicator_class: '',
        type: 'Indicator',
        function: '',
        agg_config: '1m-normal',
        calc_on_pip: false,
        parameters: {}
    };

    const indicatorHtml = createIndicatorCard(newIndicator, index);
    container.insertAdjacentHTML('beforeend', indicatorHtml);

    refreshBarIndicatorDropdowns();
}

function removeIndicator(index) {
    const card = document.querySelector(`[data-indicator-index="${index}"]`);
    if (card && confirm('Remove this indicator?')) {
        card.remove();
        refreshBarIndicatorDropdowns();
    }
}

function renderBars(bars) {
    const container = document.getElementById('barsContainer');
    container.innerHTML = '';

    for (const [barName, barConfig] of Object.entries(bars)) {
        const barHtml = createBarCard(barName, barConfig);
        container.insertAdjacentHTML('beforeend', barHtml);
    }
}

function createBarCard(barName, barConfig) {
    const indicators = barConfig.indicators || {};

    let indicatorsHtml = '';
    for (const [indName, weight] of Object.entries(indicators)) {
        indicatorsHtml += `
            <div class="row g-2 mb-2">
                <div class="col-md-6">
                    <select class="form-select" data-bar-indicator-name>
                        ${generateIndicatorNameOptions(indName)}
                    </select>
                </div>
                <div class="col-md-4">
                    <input type="number" class="form-control" value="${weight}"
                           data-bar-indicator-weight step="0.1" placeholder="Weight">
                </div>
                <div class="col-md-2">
                    <button class="btn btn-sm btn-danger w-100" onclick="removeBarIndicator(this)">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }

    return `
        <div class="bar-card" data-bar-name="${barName}">
            <div class="bar-card-header">
                <span class="indicator-card-title">${barName}</span>
                <button class="btn-remove" onclick="removeBar('${barName}')">
                    <i class="fas fa-trash me-1"></i>Remove
                </button>
            </div>
            <div class="bar-card-body show">
                <div class="row g-2 mb-2">
                    <div class="col-md-4">
                        <label class="form-label">Bar Name</label>
                        <input type="text" class="form-control" value="${barName}"
                               data-bar-field="name" onchange="refreshConditionDropdowns()">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Type</label>
                        <select class="form-select" data-bar-field="type">
                            <option value="bull" ${barConfig.type === 'bull' ? 'selected' : ''}>Bull</option>
                            <option value="bear" ${barConfig.type === 'bear' ? 'selected' : ''}>Bear</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Description</label>
                        <input type="text" class="form-control" value="${barConfig.description || ''}"
                               data-bar-field="description">
                    </div>
                </div>
                <div class="mt-2">
                    <label class="form-label"><strong>Indicators & Weights:</strong></label>
                    <div class="bar-indicators-container">
                        ${indicatorsHtml}
                    </div>
                    <button class="btn btn-sm btn-primary mt-2" onclick="addBarIndicator(this)">
                        <i class="fas fa-plus me-2"></i>Add Indicator
                    </button>
                </div>
            </div>
        </div>
    `;
}

function addBar() {
    const container = document.getElementById('barsContainer');
    const barName = `new_bar_${Date.now()}`;

    const newBar = {
        type: 'bull',
        description: 'New bar configuration',
        indicators: {}
    };

    const barHtml = createBarCard(barName, newBar);
    container.insertAdjacentHTML('beforeend', barHtml);

    refreshConditionDropdowns();
}

function removeBar(barName) {
    const card = document.querySelector(`[data-bar-name="${barName}"]`);
    if (card && confirm('Remove this bar?')) {
        card.remove();
        refreshConditionDropdowns();
    }
}

function addBarIndicator(button) {
    const barCard = button.closest('.bar-card');
    const container = barCard.querySelector('.bar-indicators-container');

    const newIndicatorHtml = `
        <div class="row g-2 mb-2">
            <div class="col-md-6">
                <select class="form-select" data-bar-indicator-name>
                    ${generateIndicatorNameOptions('')}
                </select>
            </div>
            <div class="col-md-4">
                <input type="number" class="form-control" value="1.0"
                       data-bar-indicator-weight step="0.1" placeholder="Weight">
            </div>
            <div class="col-md-2">
                <button class="btn btn-sm btn-danger w-100" onclick="removeBarIndicator(this)">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', newIndicatorHtml);
}

function removeBarIndicator(button) {
    const row = button.closest('.row.g-2');
    if (row && confirm('Remove this indicator from bar?')) {
        row.remove();
    }
}

function refreshConditionDropdowns() {
    updateCurrentConfigBars();

    if (monitorConfig && monitorConfig.monitor) {
        const enterLongConditions = monitorConfig.monitor.enter_long || [];
        const exitLongConditions = monitorConfig.monitor.exit_long || [];

        renderConditions('enterLongContainer', enterLongConditions);
        renderConditions('exitLongContainer', exitLongConditions);
    }
}

function refreshBarIndicatorDropdowns() {
    updateCurrentConfigIndicators();

    const barIndicatorSelects = document.querySelectorAll('[data-bar-indicator-name]');
    barIndicatorSelects.forEach(select => {
        const currentValue = select.value;
        select.innerHTML = generateIndicatorNameOptions(currentValue);
    });
}

function updateCurrentConfigIndicators() {
    if (!monitorConfig) return;

    const indicators = [];
    const indicatorCards = document.querySelectorAll('[data-indicator-index]');

    indicatorCards.forEach(card => {
        const nameInput = card.querySelector('[data-indicator-field="name"]');
        const classSelect = card.querySelector('[data-indicator-field="indicator_class"]');
        const aggInput = card.querySelector('[data-indicator-field="agg_config"]');

        const name = nameInput ? nameInput.value : '';
        const indicatorClass = classSelect ? classSelect.value : '';
        const aggConfig = aggInput ? aggInput.value : '1m-normal';

        const parameters = {};
        const paramInputs = card.querySelectorAll('[data-indicator-param]');
        paramInputs.forEach(input => {
            const paramName = input.dataset.indicatorParam;
            const paramValue = input.type === 'number' ? parseFloat(input.value) : input.value;
            parameters[paramName] = paramValue;
        });

        if (name) {
            indicators.push({
                name: name,
                indicator_class: indicatorClass,
                type: 'Indicator',
                agg_config: aggConfig,
                calc_on_pip: false,
                parameters: parameters
            });
        }
    });

    monitorConfig.indicators = indicators;
}

function updateCurrentConfigBars() {
    if (!monitorConfig || !monitorConfig.monitor) return;

    const bars = {};
    const barCards = document.querySelectorAll('[data-bar-name]');

    barCards.forEach(card => {
        const nameInput = card.querySelector('[data-bar-field="name"]');
        const typeSelect = card.querySelector('[data-bar-field="type"]');
        const descInput = card.querySelector('[data-bar-field="description"]');

        const barName = nameInput ? nameInput.value : card.dataset.barName;

        const indicators = {};
        const indicatorRows = card.querySelectorAll('[data-bar-indicator-name]');
        indicatorRows.forEach(row => {
            const indName = row.value;
            const weightInput = row.closest('.row').querySelector('[data-bar-indicator-weight]');
            const weight = weightInput ? parseFloat(weightInput.value) : 1.0;
            if (indName) {
                indicators[indName] = weight;
            }
        });

        bars[barName] = {
            type: typeSelect ? typeSelect.value : 'bull',
            description: descInput ? descInput.value : '',
            indicators: indicators
        };
    });

    monitorConfig.monitor.bars = bars;
}

function saveConfiguration() {
    if (!monitorConfig || !dataConfig) {
        showAlert('Both configurations must be loaded', 'warning');
        return;
    }

    // Update configs from form
    collectMonitorConfigData();
    collectDataConfigData();

    // Download both configs
    downloadConfig(monitorConfig, currentMonitorFilename || 'monitor_config.json');
    downloadConfig(dataConfig, currentDataFilename || 'data_config.json');

    showAlert('Configurations saved successfully', 'success');
}

function collectMonitorConfigData() {
    // Collect monitor info
    monitorConfig.monitor.name = document.getElementById('monitorName').value;
    monitorConfig.monitor.description = document.getElementById('monitorDescription').value;

    // Collect trade executor
    const te = monitorConfig.monitor.trade_executor;
    te.default_position_size = parseFloat(document.getElementById('positionSize').value);
    te.stop_loss_pct = parseFloat(document.getElementById('stopLoss').value);
    te.take_profit_pct = parseFloat(document.getElementById('takeProfit').value);
    te.trailing_stop_loss = document.getElementById('trailingStopEnabled').checked;
    te.trailing_stop_distance_pct = parseFloat(document.getElementById('trailingDistance').value);
    te.trailing_stop_activation_pct = parseFloat(document.getElementById('trailingActivation').value);
    te.ignore_bear_signals = document.getElementById('ignoreBearSignals').checked;

    // Update bars and indicators
    updateCurrentConfigBars();
    updateCurrentConfigIndicators();
}

function collectDataConfigData() {
    dataConfig.ticker = document.getElementById('dataTicker').value;
    dataConfig.start_date = document.getElementById('dataStartDate').value;
    dataConfig.end_date = document.getElementById('dataEndDate').value;
}

function downloadConfig(config, filename) {
    const jsonStr = JSON.stringify(config, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

async function runReplay() {
    if (!monitorConfig || !dataConfig) {
        showAlert('Both configurations must be loaded', 'warning');
        return;
    }

    collectMonitorConfigData();
    collectDataConfigData();

    const runButton = document.getElementById('runReplayBtn');
    runButton.disabled = true;
    runButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Running Replay...';

    try {
        const response = await fetch('/replay/api/run_replay', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                monitor_config: monitorConfig,
                data_config: dataConfig
            })
        });

        const result = await response.json();

        if (result.success) {
            displayResults(result.data);
            document.getElementById('resultsSection').style.display = 'block';
            showAlert('Replay completed successfully', 'success');
        } else {
            showAlert('Failed to run replay: ' + result.error, 'danger');
        }
    } catch (error) {
        showAlert('Error running replay: ' + error.message, 'danger');
    } finally {
        runButton.disabled = false;
        runButton.innerHTML = '<i class="fas fa-play me-2"></i>Run Replay';
    }
}

let charts = {};

function displayResults(data) {
    console.log('Displaying results:', data);

    // Update strategy overview
    document.getElementById('strategyName').textContent = data.monitor_config?.name || 'Unknown';
    document.getElementById('displayTicker').textContent = data.ticker || 'Unknown';
    document.getElementById('dateRange').textContent = `${data.date_range?.start || 'Unknown'} to ${data.date_range?.end || 'Unknown'}`;
    document.getElementById('totalTrades').textContent = data.trades?.length || 0;

    // Calculate and display metrics
    if (data.trades && data.trades.length > 0) {
        calculateMetrics(data.trades);
    }

    // Create charts
    if (data.candlestick_data) {
        createCandlestickChart(data.candlestick_data, data.trades);
    }

    if (data.pnl_data && data.trades && data.candlestick_data) {
        createPnLChart(data.pnl_data, data.trades, data.candlestick_data);
    }

    // Populate trade history
    populateTradeHistory(data.trades);
}

function calculateMetrics(trades) {
    let winningTrades = 0;
    let losingTrades = 0;
    let totalWinPnL = 0;
    let totalLossPnL = 0;
    let cumulativePnL = 0;

    trades.forEach(trade => {
        if (trade.pnl > 0) {
            winningTrades++;
            totalWinPnL += trade.pnl;
        } else if (trade.pnl < 0) {
            losingTrades++;
            totalLossPnL += Math.abs(trade.pnl);
        }
        cumulativePnL += trade.pnl;
    });

    const avgWin = winningTrades > 0 ? totalWinPnL / winningTrades : 0;
    const avgLoss = losingTrades > 0 ? totalLossPnL / losingTrades : 0;

    // Update UI
    document.getElementById('totalPnL').textContent = `${cumulativePnL.toFixed(2)}%`;
    document.getElementById('avgWin').textContent = `${avgWin.toFixed(2)}%`;
    document.getElementById('avgLoss').textContent = `${avgLoss.toFixed(2)}%`;

    // Color coding
    const totalPnLElement = document.getElementById('totalPnL');
    totalPnLElement.className = `h5 mb-0 ${cumulativePnL >= 0 ? 'text-success' : 'text-danger'}`;
}

function createCandlestickChart(candlestickData, trades) {
    const chartConfig = {
        chart: {
            height: 500,
            zoomType: 'x'
        },
        title: { text: 'Price Chart with Trades' },
        xAxis: {
            type: 'datetime',
            crosshair: true
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
                color: '#dc3545',
                upColor: '#28a745'
            }
        ],
        credits: { enabled: false }
    };

    if (charts.candlestick) {
        charts.candlestick.destroy();
    }
    charts.candlestick = Highcharts.chart('candlestickChart', chartConfig);

    // Add trade bands
    if (trades && trades.length > 0) {
        const buyTrades = trades.filter(t => t.type === 'buy').sort((a, b) => a.timestamp - b.timestamp);
        const sellTrades = trades.filter(t => t.type === 'sell').sort((a, b) => a.timestamp - b.timestamp);

        let buyIndex = 0, sellIndex = 0, tradeCount = 0;

        while (buyIndex < buyTrades.length && sellIndex < sellTrades.length) {
            const buyTrade = buyTrades[buyIndex];
            const sellTrade = sellTrades[sellIndex];

            if (buyTrade.timestamp < sellTrade.timestamp) {
                const pnl = sellTrade.pnl || 0;
                const isProfit = pnl > 0;
                const bandColor = isProfit ? 'rgba(40, 167, 69, 0.1)' : 'rgba(220, 53, 69, 0.1)';

                charts.candlestick.xAxis[0].addPlotBand({
                    from: buyTrade.timestamp,
                    to: sellTrade.timestamp,
                    color: bandColor,
                    label: {
                        text: `${isProfit ? '+' : ''}${pnl.toFixed(2)}%`,
                        style: {
                            color: isProfit ? '#28a745' : '#dc3545',
                            fontWeight: 'bold'
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
    }
}

function createPnLChart(pnlData, trades, candlestickData) {
    const chartConfig = {
        chart: {
            height: 300,
            zoomType: 'x'
        },
        title: { text: 'Cumulative P&L' },
        xAxis: {
            type: 'datetime',
            crosshair: true
        },
        yAxis: {
            title: { text: 'P&L %' },
            crosshair: true,
            plotLines: [{
                value: 0,
                color: '#999',
                width: 1,
                zIndex: 2
            }]
        },
        series: [{
            name: 'Cumulative P&L',
            data: pnlData,
            type: 'line',
            color: '#007bff',
            lineWidth: 2
        }],
        credits: { enabled: false }
    };

    if (charts.pnl) {
        charts.pnl.destroy();
    }
    charts.pnl = Highcharts.chart('pnlChart', chartConfig);
}

function populateTradeHistory(trades) {
    const tbody = document.getElementById('tradeHistoryTable');
    tbody.innerHTML = '';

    if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No trades to display</td></tr>';
        return;
    }

    let cumulativePnL = 0;

    trades.forEach(trade => {
        cumulativePnL += (trade.pnl || 0);

        const row = document.createElement('tr');
        const date = new Date(trade.timestamp);
        const typeClass = trade.type === 'buy' ? 'text-success' : 'text-danger';
        const pnlClass = trade.pnl > 0 ? 'text-success' : (trade.pnl < 0 ? 'text-danger' : '');

        row.innerHTML = `
            <td>${date.toLocaleString()}</td>
            <td class="${typeClass}">${trade.type.toUpperCase()}</td>
            <td>$${trade.price.toFixed(2)}</td>
            <td>${trade.quantity || '-'}</td>
            <td class="${pnlClass}">${trade.pnl ? trade.pnl.toFixed(2) + '%' : '-'}</td>
            <td>${cumulativePnL.toFixed(2)}%</td>
            <td><small>${trade.reason || '-'}</small></td>
        `;

        tbody.appendChild(row);
    });
}

function showAlert(message, type) {
    // Simple alert for now - could be enhanced with Bootstrap toast
    alert(message);
}
