/**
 * Monitor Configuration Editor
 * Handles dynamic loading, editing, and saving of monitor configurations
 */

let currentConfig = null;

// Note: toggleTakeProfitInputs() is now in trade-executor-common.js

let currentFilename = null;
let indicatorClasses = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadIndicatorClasses();
    setupEventListeners();
});

function setupEventListeners() {
    // File input
    document.getElementById('fileInput').addEventListener('change', function() {
        const loadBtn = document.getElementById('loadBtn');
        loadBtn.disabled = !this.files.length;
    });

    // Load button
    document.getElementById('loadBtn').addEventListener('click', loadConfiguration);

    // Save button
    document.getElementById('saveBtn').addEventListener('click', saveConfiguration);

    // Cancel button
    document.getElementById('cancelBtn').addEventListener('click', function() {
        if (confirm('Are you sure you want to cancel? Unsaved changes will be lost.')) {
            document.getElementById('configEditor').style.display = 'none';
            currentConfig = null;
            currentFilename = null;
        }
    });

    // Add indicator button
    document.getElementById('addIndicatorBtn').addEventListener('click', addIndicator);

    // Add bar button
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

async function loadConfiguration() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) return;

    const file = fileInput.files[0];
    currentFilename = file.name;

    try {
        const text = await file.text();
        currentConfig = JSON.parse(text);

        renderConfiguration();
        document.getElementById('configEditor').style.display = 'block';
        showAlert('Configuration loaded successfully', 'success');
    } catch (error) {
        showAlert('Error loading configuration: ' + error.message, 'danger');
    }
}

function renderConfiguration() {
    if (!currentConfig) return;

    const monitor = currentConfig.monitor || {};
    const tradeExecutor = monitor.trade_executor || {};
    const indicators = currentConfig.indicators || [];
    const bars = monitor.bars || {};

    // Monitor tab
    document.getElementById('monitorName').value = monitor.name || '';
    document.getElementById('monitorDescription').value = monitor.description || '';

    // Trade Executor tab
    document.getElementById('positionSize').value = tradeExecutor.default_position_size || 100;
    document.getElementById('stopLoss').value = tradeExecutor.stop_loss_pct || 0.02;
    document.getElementById('takeProfit').value = tradeExecutor.take_profit_pct || 0.04;

    // Take profit type and dollar amount
    const takeProfitType = tradeExecutor.take_profit_type || 'percent';
    document.getElementById('takeProfitType').value = takeProfitType;
    document.getElementById('takeProfitDollars').value = tradeExecutor.take_profit_dollars || 0;
    toggleTakeProfitInputs(); // Update visibility based on type

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

    // Get bar names from current config
    if (currentConfig && currentConfig.monitor && currentConfig.monitor.bars) {
        const bars = currentConfig.monitor.bars;
        for (const barName of Object.keys(bars)) {
            const isSelected = barName === selectedName ? 'selected' : '';
            options += `<option value="${barName}" ${isSelected}>${barName}</option>`;
        }
    }

    return options;
}

function generateIndicatorNameOptions(selectedName) {
    let options = '<option value="">-- Select Indicator --</option>';

    // Get indicator names from current config
    if (currentConfig && currentConfig.indicators) {
        for (const indicator of currentConfig.indicators) {
            const indName = indicator.name;
            const isSelected = indName === selectedName ? 'selected' : '';
            options += `<option value="${indName}" ${isSelected}>${indName}</option>`;
        }
    }

    return options;
}

function addCondition(containerId) {
    const container = document.getElementById(containerId);
    const conditions = container.querySelectorAll('[data-condition-index]');
    const newIndex = conditions.length / 2; // Divide by 2 because each condition has 2 inputs

    const conditionHtml = `
        <div class="row g-2 mb-2">
            <div class="col-md-5">
                <select class="form-select" data-condition-index="${newIndex}" data-field="name">
                    ${generateBarNameOptions('')}
                </select>
            </div>
            <div class="col-md-5">
                <input type="number" class="form-control" placeholder="Threshold"
                       value="0.5" step="0.01"
                       data-condition-index="${newIndex}" data-field="threshold">
            </div>
            <div class="col-md-2">
                <button class="btn btn-danger w-100" onclick="removeCondition('${containerId}', ${newIndex})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `;

    // Insert before the add button
    const addButton = container.querySelector('.btn-primary');
    addButton.insertAdjacentHTML('beforebegin', conditionHtml);
}

function removeCondition(containerId, index) {
    const container = document.getElementById(containerId);
    const rows = container.querySelectorAll('.row.g-2');
    if (rows[index]) {
        rows[index].remove();
    }
}

function renderIndicators(indicators) {
    const container = document.getElementById('indicatorsContainer');
    container.innerHTML = '';

    indicators.forEach((indicator, index) => {
        const indicatorHtml = createIndicatorCard(indicator, index);
        container.insertAdjacentHTML('beforeend', indicatorHtml);

        // If it's a CDLPatternIndicator, initialize the pattern listbox with loaded data
        if (indicator.indicator_class === 'CDLPatternIndicator') {
            const params = indicator.parameters || {};
            const patterns = params.patterns || [];
            const trend = params.trend || 'bullish';

            // Re-render params with proper UI
            updateIndicatorParams(index, indicator.indicator_class);

            // Initialize listbox with loaded patterns
            setTimeout(() => {
                initializePatternListbox(index, trend, patterns);
            }, 50);
        }
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

function toggleIndicatorCard(index) {
    const body = document.getElementById(`indicator-body-${index}`);
    const icon = document.getElementById(`collapse-icon-${index}`);

    if (body && icon) {
        body.classList.toggle('show');
        icon.classList.toggle('expanded');
    }
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

function updateIndicatorParams(index, className) {
    if (!className || !indicatorClasses[className]) return;

    const schema = indicatorClasses[className];
    const paramsContainer = document.getElementById(`indicator-params-${index}`);

    // Get parameter specs from schema
    const paramGroups = schema.parameter_groups || {};
    const allParams = Object.values(paramGroups).flat();

    let html = '';
    allParams.forEach(param => {
        if (param.type === 'list' && param.name === 'patterns') {
            // Handle patterns LIST parameter with dual listbox
            const defaultList = Array.isArray(param.default) ? param.default : [];
            html += `
                <div class="col-md-12">
                    <label class="form-label">${param.display_name}</label>
                    <div class="row">
                        <div class="col-md-5">
                            <label class="form-label text-muted small">Selected Patterns</label>
                            <select multiple class="form-select" size="10"
                                    data-indicator-param="${param.name}"
                                    data-param-type="list"
                                    data-listbox-type="selected"
                                    style="height: 250px;">
                            </select>
                        </div>
                        <div class="col-md-2 d-flex flex-column justify-content-center align-items-center">
                            <button type="button" class="btn btn-sm btn-outline-primary mb-2"
                                    onclick="movePatterns(${index}, 'add')" title="Add selected">
                                <i class="fas fa-angle-double-left"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-primary mb-2"
                                    onclick="movePatterns(${index}, 'remove')" title="Remove selected">
                                <i class="fas fa-angle-double-right"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary mb-2"
                                    onclick="movePatterns(${index}, 'add-all')" title="Add all">
                                <i class="fas fa-angle-double-left"></i><i class="fas fa-angle-double-left"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary"
                                    onclick="movePatterns(${index}, 'remove-all')" title="Remove all">
                                <i class="fas fa-angle-double-right"></i><i class="fas fa-angle-double-right"></i>
                            </button>
                        </div>
                        <div class="col-md-5">
                            <label class="form-label text-muted small">Available Patterns</label>
                            <select multiple class="form-select" size="10"
                                    data-listbox-type="available"
                                    style="height: 250px;">
                            </select>
                        </div>
                    </div>
                    <small class="form-text text-muted">Patterns filtered by trend selection</small>
                </div>
            `;
        } else if (param.type === 'list') {
            // Handle other LIST parameters (e.g., for candlestick patterns)
            const defaultList = Array.isArray(param.default) ? param.default.join(', ') : '';
            html += `
                <div class="col-md-6">
                    <label class="form-label">${param.display_name}</label>
                    <input type="text" class="form-control" value="${defaultList}"
                           data-indicator-param="${param.name}" data-param-type="list"
                           placeholder="${param.description || 'Comma-separated list'}">
                    <small class="form-text text-muted">Comma-separated values</small>
                </div>
            `;
        } else if (param.type === 'choice') {
            // Handle CHOICE parameters
            const choices = param.choices || [];
            let optionsHtml = choices.map(choice =>
                `<option value="${choice}" ${choice === param.default ? 'selected' : ''}>${choice}</option>`
            ).join('');

            // Add onchange handler for trend parameter to update pattern lists
            const onchangeAttr = param.name === 'trend' ? `onchange="updatePatternListboxes(${index}, this.value)"` : '';

            html += `
                <div class="col-md-3">
                    <label class="form-label">${param.display_name}</label>
                    <select class="form-select" data-indicator-param="${param.name}" ${onchangeAttr}>
                        ${optionsHtml}
                    </select>
                </div>
            `;
        } else {
            // Handle numeric and text parameters
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
        }
    });

    paramsContainer.innerHTML = html;

    // Initialize pattern listbox if this is a CDLPatternIndicator
    if (className === 'CDLPatternIndicator') {
        // Find trend parameter value
        const trendSelect = paramsContainer.closest('.indicator-card-body').querySelector('[data-indicator-param="trend"]');
        const trend = trendSelect ? trendSelect.value : 'bullish';

        // Initialize with empty selection
        initializePatternListbox(index, trend, []);
    }
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

    // Refresh bar indicator dropdowns
    refreshBarIndicatorDropdowns();
}

function removeIndicator(index) {
    const card = document.querySelector(`[data-indicator-index="${index}"]`);
    if (card && confirm('Remove this indicator?')) {
        card.remove();

        // Refresh bar indicator dropdowns
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

    // Refresh entry/exit condition dropdowns
    refreshConditionDropdowns();
}

function removeBar(barName) {
    const card = document.querySelector(`[data-bar-name="${barName}"]`);
    if (card && confirm('Remove this bar?')) {
        card.remove();

        // Refresh entry/exit condition dropdowns
        refreshConditionDropdowns();
    }
}

function refreshConditionDropdowns() {
    // Update currentConfig with current bar names from DOM
    updateCurrentConfigBars();

    // Re-render the entry/exit conditions with updated bar list
    if (currentConfig && currentConfig.monitor) {
        const enterLongConditions = currentConfig.monitor.enter_long || [];
        const exitLongConditions = currentConfig.monitor.exit_long || [];

        renderConditions('enterLongContainer', enterLongConditions);
        renderConditions('exitLongContainer', exitLongConditions);
    }
}

function refreshBarIndicatorDropdowns() {
    // Update currentConfig with current indicator names from DOM
    updateCurrentConfigIndicators();

    // Update all bar indicator dropdowns
    const barIndicatorSelects = document.querySelectorAll('[data-bar-indicator-name]');
    barIndicatorSelects.forEach(select => {
        const currentValue = select.value;
        select.innerHTML = generateIndicatorNameOptions(currentValue);
    });
}

function updateCurrentConfigIndicators() {
    if (!currentConfig) return;

    // Rebuild indicators array from DOM
    const indicators = [];
    const indicatorCards = document.querySelectorAll('[data-indicator-index]');

    indicatorCards.forEach(card => {
        const nameInput = card.querySelector('[data-indicator-field="name"]');
        const classSelect = card.querySelector('[data-indicator-field="indicator_class"]');
        const aggInput = card.querySelector('[data-indicator-field="agg_config"]');

        const name = nameInput ? nameInput.value : '';
        const indicatorClass = classSelect ? classSelect.value : '';
        const aggConfig = aggInput ? aggInput.value : '1m-normal';

        // Get parameters
        const parameters = {};
        const paramInputs = card.querySelectorAll('[data-indicator-param]');
        paramInputs.forEach(input => {
            const paramName = input.dataset.indicatorParam;
            const paramType = input.dataset.paramType;

            if (paramType === 'list') {
                // Check if it's a dual listbox (for patterns)
                const listboxType = input.dataset.listboxType;
                if (listboxType === 'selected') {
                    // Get all selected patterns from the listbox
                    parameters[paramName] = Array.from(input.options).map(opt => opt.value);
                } else {
                    // Convert comma-separated string to array (fallback for other lists)
                    const listValue = input.value.trim();
                    parameters[paramName] = listValue ? listValue.split(',').map(v => v.trim()) : [];
                }
            } else if (input.tagName === 'SELECT') {
                // Handle select dropdowns
                parameters[paramName] = input.value;
            } else {
                // Handle numeric and text inputs
                const paramValue = input.type === 'number' ? parseFloat(input.value) : input.value;
                parameters[paramName] = paramValue;
            }
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

    currentConfig.indicators = indicators;
}

function updateCurrentConfigBars() {
    if (!currentConfig || !currentConfig.monitor) return;

    // Rebuild bars object from DOM
    const bars = {};
    const barCards = document.querySelectorAll('[data-bar-name]');

    barCards.forEach(card => {
        const nameInput = card.querySelector('[data-bar-field="name"]');
        const typeSelect = card.querySelector('[data-bar-field="type"]');
        const descInput = card.querySelector('[data-bar-field="description"]');

        const barName = nameInput ? nameInput.value : card.dataset.barName;

        // Get indicators and weights
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

    currentConfig.monitor.bars = bars;
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

async function saveConfiguration() {
    if (!currentFilename) {
        showAlert('No file loaded', 'warning');
        return;
    }

    try {
        // Collect all data from the form
        const config = collectConfigurationData();

        // Create a blob and download it
        const jsonStr = JSON.stringify(config, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        // Create download link and trigger it
        const a = document.createElement('a');
        a.href = url;
        a.download = currentFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showAlert('Configuration downloaded successfully', 'success');
        currentConfig = config;
    } catch (error) {
        showAlert('Error saving configuration: ' + error.message, 'danger');
    }
}

function collectConfigurationData() {
    // Monitor data
    const monitor = {
        name: document.getElementById('monitorName').value,
        description: document.getElementById('monitorDescription').value,
        trade_executor: {
            default_position_size: parseFloat(document.getElementById('positionSize').value),
            stop_loss_pct: parseFloat(document.getElementById('stopLoss').value),
            take_profit_pct: parseFloat(document.getElementById('takeProfit').value),
            take_profit_type: document.getElementById('takeProfitType').value,
            take_profit_dollars: parseFloat(document.getElementById('takeProfitDollars').value) || 0,
            ignore_bear_signals: document.getElementById('ignoreBearSignals').checked,
            trailing_stop_loss: document.getElementById('trailingStopEnabled').checked,
            trailing_stop_distance_pct: parseFloat(document.getElementById('trailingDistance').value),
            trailing_stop_activation_pct: parseFloat(document.getElementById('trailingActivation').value)
        },
        enter_long: collectConditions('enterLongContainer'),
        exit_long: collectConditions('exitLongContainer'),
        bars: collectBars()
    };

    // Add IDs if they exist
    if (currentConfig.monitor._id) monitor._id = currentConfig.monitor._id;
    if (currentConfig.monitor.user_id) monitor.user_id = currentConfig.monitor.user_id;

    // Indicators
    const indicators = collectIndicators();

    return {
        test_name: currentConfig.test_name || 'custom-config',
        monitor: monitor,
        indicators: indicators
    };
}

function collectConditions(containerId) {
    const container = document.getElementById(containerId);
    const rows = container.querySelectorAll('.row.g-2:not(:last-child)');
    const conditions = [];

    rows.forEach(row => {
        const nameInput = row.querySelector('[data-field="name"]');
        const thresholdInput = row.querySelector('[data-field="threshold"]');

        if (nameInput && thresholdInput && nameInput.value) {
            conditions.push({
                name: nameInput.value,
                threshold: parseFloat(thresholdInput.value)
            });
        }
    });

    return conditions;
}

function collectIndicators() {
    const cards = document.querySelectorAll('.indicator-card');
    const indicators = [];

    cards.forEach(card => {
        const name = card.querySelector('[data-indicator-field="name"]').value;
        const indicatorClass = card.querySelector('[data-indicator-field="indicator_class"]').value;
        const aggConfig = card.querySelector('[data-indicator-field="agg_config"]').value;

        const parameters = {};
        card.querySelectorAll('[data-indicator-param]').forEach(input => {
            const paramName = input.getAttribute('data-indicator-param');
            const value = input.type === 'number' ? parseFloat(input.value) : input.value;
            parameters[paramName] = value;
        });

        indicators.push({
            name: name,
            indicator_class: indicatorClass,
            type: 'Indicator',
            function: parameters.function || '',
            agg_config: aggConfig,
            calc_on_pip: false,
            parameters: parameters
        });
    });

    return indicators;
}

function collectBars() {
    const barCards = document.querySelectorAll('.bar-card');
    const bars = {};

    barCards.forEach(card => {
        const nameInput = card.querySelector('[data-bar-field="name"]');
        const typeSelect = card.querySelector('[data-bar-field="type"]');
        const descInput = card.querySelector('[data-bar-field="description"]');

        const barName = nameInput.value;
        const indicators = {};

        card.querySelectorAll('[data-bar-indicator-name]').forEach(input => {
            const indName = input.value;
            const weightInput = input.closest('.row').querySelector('[data-bar-indicator-weight]');
            if (indName && weightInput) {
                indicators[indName] = parseFloat(weightInput.value);
            }
        });

        bars[barName] = {
            type: typeSelect.value,
            description: descInput.value,
            indicators: indicators
        };
    });

    return bars;
}

// ========== Pattern Listbox Functions ==========

function movePatterns(indicatorIndex, action) {
    const card = document.querySelector(`[data-indicator-index="${indicatorIndex}"]`);
    if (!card) return;

    const selectedListbox = card.querySelector('[data-listbox-type="selected"]');
    const availableListbox = card.querySelector('[data-listbox-type="available"]');

    if (!selectedListbox || !availableListbox) return;

    if (action === 'add') {
        // Move selected items from available to selected
        const selected = Array.from(availableListbox.selectedOptions);
        selected.forEach(option => {
            selectedListbox.appendChild(option.cloneNode(true));
            option.remove();
        });
    } else if (action === 'remove') {
        // Move selected items from selected to available
        const selected = Array.from(selectedListbox.selectedOptions);
        selected.forEach(option => {
            availableListbox.appendChild(option.cloneNode(true));
            option.remove();
        });
        sortListbox(availableListbox);
    } else if (action === 'add-all') {
        // Move all from available to selected
        Array.from(availableListbox.options).forEach(option => {
            selectedListbox.appendChild(option.cloneNode(true));
        });
        availableListbox.innerHTML = '';
    } else if (action === 'remove-all') {
        // Move all from selected to available
        Array.from(selectedListbox.options).forEach(option => {
            availableListbox.appendChild(option.cloneNode(true));
        });
        selectedListbox.innerHTML = '';
        sortListbox(availableListbox);
    }
}

function sortListbox(listbox) {
    const options = Array.from(listbox.options);
    options.sort((a, b) => a.value.localeCompare(b.value));
    listbox.innerHTML = '';
    options.forEach(option => listbox.appendChild(option));
}

function updatePatternListboxes(indicatorIndex, trend) {
    const card = document.querySelector(`[data-indicator-index="${indicatorIndex}"]`);
    if (!card) return;

    const selectedListbox = card.querySelector('[data-listbox-type="selected"]');
    const availableListbox = card.querySelector('[data-listbox-type="available"]');

    if (!selectedListbox || !availableListbox) return;

    // Get current selected patterns
    const currentSelected = Array.from(selectedListbox.options).map(opt => opt.value);

    // Get patterns for this trend type
    const allPatterns = getPatternsByTrend(trend);

    // Populate available patterns (excluding already selected)
    availableListbox.innerHTML = '';
    allPatterns.forEach(pattern => {
        if (!currentSelected.includes(pattern)) {
            const option = document.createElement('option');
            option.value = pattern;
            option.textContent = pattern;
            availableListbox.appendChild(option);
        }
    });
}

function initializePatternListbox(indicatorIndex, trend, selectedPatterns) {
    const card = document.querySelector(`[data-indicator-index="${indicatorIndex}"]`);
    if (!card) return;

    const selectedListbox = card.querySelector('[data-listbox-type="selected"]');
    const availableListbox = card.querySelector('[data-listbox-type="available"]');

    if (!selectedListbox || !availableListbox) return;

    // Get patterns for this trend type
    const allPatterns = getPatternsByTrend(trend);

    // Populate selected patterns
    selectedListbox.innerHTML = '';
    selectedPatterns.forEach(pattern => {
        const option = document.createElement('option');
        option.value = pattern;
        option.textContent = pattern;
        selectedListbox.appendChild(option);
    });

    // Populate available patterns (excluding selected)
    availableListbox.innerHTML = '';
    allPatterns.forEach(pattern => {
        if (!selectedPatterns.includes(pattern)) {
            const option = document.createElement('option');
            option.value = pattern;
            option.textContent = pattern;
            availableListbox.appendChild(option);
        }
    });

    // Add double-click handlers
    selectedListbox.addEventListener('dblclick', function(e) {
        if (e.target.tagName === 'OPTION') {
            // Move from selected to available
            availableListbox.appendChild(e.target.cloneNode(true));
            e.target.remove();
            sortListbox(availableListbox);
        }
    });

    availableListbox.addEventListener('dblclick', function(e) {
        if (e.target.tagName === 'OPTION') {
            // Move from available to selected
            selectedListbox.appendChild(e.target.cloneNode(true));
            e.target.remove();
        }
    });
}
