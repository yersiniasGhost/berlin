/**
 * Replay Configuration Editor
 * Handles dynamic loading, editing, and saving of replay configurations
 */

let monitorConfig = null;
let dataConfig = null;
let currentMonitorFilename = null;
let currentDataFilename = null;
let indicatorClasses = {};

// Default data configuration
const DEFAULT_DATA_CONFIG = {
    ticker: "NVDA",
    start_date: "2024-01-01",
    end_date: "2024-02-28",
    include_extended_hours: true
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadIndicatorClasses();
    setupEventListeners();
});

function setupEventListeners() {
    // Add indicator/bar buttons
    const addIndicatorBtn = document.getElementById('addIndicatorBtn');
    const addBarBtn = document.getElementById('addBarBtn');

    if (addIndicatorBtn) {
        addIndicatorBtn.addEventListener('click', addIndicator);
    }
    if (addBarBtn) {
        addBarBtn.addEventListener('click', addBar);
    }
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

    // If no file selected, use default data config
    if (!fileInput.files.length) {
        dataConfig = JSON.parse(JSON.stringify(DEFAULT_DATA_CONFIG)); // Deep clone
        currentDataFilename = 'default_data_config.json';

        renderDataConfiguration();
        checkBothConfigsLoaded();
        showAlert('Using default data configuration: NVDA, 2024-01-01 to 2024-02-28', 'info');
        return;
    }

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
    if (monitorConfig) {
        // If monitor config is loaded but no data config, use defaults
        if (!dataConfig) {
            loadDataConfiguration(); // This will use defaults if no file selected
        }
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
    // Default to checked (true) if not specified for backward compatibility
    document.getElementById('dataExtendedHours').checked = dataConfig.include_extended_hours !== undefined ? dataConfig.include_extended_hours : true;
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
        container.insertAdjacentHTML('beforeend', createIndicatorCard(indicator, index));

        // Special handling for CDLPatternIndicator - initialize dual listbox
        if (indicator.indicator_class === 'CDLPatternIndicator') {
            const params = indicator.parameters || {};
            const patterns = params.patterns || [];
            const trend = params.trend || 'bullish';

            // Update params to show dual listbox with current parameters
            updateIndicatorParams(index, indicator.indicator_class, params);

            // Initialize pattern listbox with loaded patterns
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
                        <label class="form-label">Aggregation Config
                            ${!indicator.agg_config ? '<span class="badge bg-danger ms-1" title="Required field missing"><i class="fas fa-exclamation-circle"></i></span>' : ''}
                        </label>
                        <select class="form-select" data-indicator-field="agg_config">
                            ${generateAggregatorOptions(indicator.agg_config || '')}
                        </select>
                    </div>
                </div>
                <div class="row g-2 mt-2" id="indicator-params-${index}">
                    ${renderIndicatorParams(params, index, indicatorClass)}
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

function generateAggregatorOptions(selectedValue) {
    const aggregators = [
        '1m-normal',
        '1m-heiken',
        '5m-normal',
        '5m-heiken',
        '15m-normal',
        '15m-heiken',
        '30m-normal',
        '30m-heiken',
        '1h-normal',
        '1h-heiken'
    ];

    let options = '<option value="">-- Select --</option>';

    for (const agg of aggregators) {
        const isSelected = agg === selectedValue ? 'selected' : '';
        options += `<option value="${agg}" ${isSelected}>${agg}</option>`;
    }

    return options;
}

function renderIndicatorParams(params, index, indicatorClass) {
    // If we have a schema, use it to render ALL required parameters
    // Otherwise fall back to rendering only the params we have
    if (indicatorClass && indicatorClasses[indicatorClass]) {
        return updateIndicatorParams(index, indicatorClass, params);
    }

    // Fallback: render only existing parameters
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

function updateIndicatorParams(index, className, currentParams = {}) {
    if (!className || !indicatorClasses[className]) {
        console.warn(`No schema found for indicator class: ${className}`);
        return '';
    }

    const schema = indicatorClasses[className];
    const paramsContainer = document.getElementById(`indicator-params-${index}`);

    // Try to get parameter specs from schema
    let paramSpecs = schema.parameter_specs || [];

    // Fallback to parameter_groups if parameter_specs not available
    if (paramSpecs.length === 0 && schema.parameter_groups) {
        const paramGroups = schema.parameter_groups;
        paramSpecs = Object.values(paramGroups).flat();
    }

    console.log(`Rendering parameters for ${className}:`, paramSpecs.length, 'parameters');

    // Detect if this is a new indicator (empty parameters)
    const isNewIndicator = Object.keys(currentParams).length === 0;

    let html = '';
    paramSpecs.forEach(param => {
        // Get the current value or use default if this is a new indicator
        let currentValue;
        let isMissing;

        if (isNewIndicator) {
            // New indicator: use default value from schema
            currentValue = param.default !== undefined ? param.default : '';
            isMissing = false;
        } else {
            // Loaded from JSON: show empty with error badge if missing
            currentValue = currentParams[param.name] !== undefined ? currentParams[param.name] : '';
            isMissing = currentParams[param.name] === undefined;
        }

        const errorBadge = isMissing ? '<span class="badge bg-danger ms-1" title="Required field missing"><i class="fas fa-exclamation-circle"></i></span>' : '';

        // Map parameter_type to type for compatibility
        const paramType = param.type || param.parameter_type || 'text';

        if (paramType === 'list' && param.name === 'patterns') {
            // Handle patterns parameter with dual listbox
            html += `
                <div class="col-md-12">
                    <label class="form-label">${param.display_name}${errorBadge}</label>
                    <div class="row">
                        <div class="col-md-5">
                            <label class="form-label small">Selected Patterns</label>
                            <select multiple class="form-select" size="10"
                                    data-indicator-param="patterns"
                                    data-param-type="list"
                                    data-listbox-type="selected"
                                    style="max-width: 100%; ${isMissing ? 'border: 2px solid #dc3545;' : ''}">
                            </select>
                        </div>
                        <div class="col-md-2 d-flex flex-column justify-content-center align-items-center">
                            <button type="button" class="btn btn-sm btn-primary mb-2"
                                    onclick="movePatterns(${index}, 'add')"
                                    title="Add selected patterns">
                                <i class="fas fa-angle-double-left"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-secondary"
                                    onclick="movePatterns(${index}, 'remove')"
                                    title="Remove selected patterns">
                                <i class="fas fa-angle-double-right"></i>
                            </button>
                        </div>
                        <div class="col-md-5">
                            <label class="form-label small">Available Patterns</label>
                            <select multiple class="form-select" size="10"
                                    data-listbox-type="available"
                                    style="max-width: 100%;">
                            </select>
                        </div>
                    </div>
                </div>
            `;
        } else if (paramType === 'LIST') {
            // Handle other LIST parameters with comma-separated input
            const valueStr = Array.isArray(currentValue) ? currentValue.join(', ') : currentValue;
            html += `
                <div class="col-md-6">
                    <label class="form-label">${param.display_name}${errorBadge}</label>
                    <input type="text" class="form-control ${isMissing ? 'border-danger' : ''}" value="${valueStr}"
                           data-indicator-param="${param.name}" data-param-type="list"
                           placeholder="${param.description || 'Comma-separated list'}">
                    <small class="form-text text-muted">Comma-separated values</small>
                </div>
            `;
        } else if (paramType === 'list') {
            // Handle other LIST parameters with comma-separated input
            const defaultList = Array.isArray(param.default) ? param.default.join(', ') : '';
            const valueStr = Array.isArray(currentValue) ? currentValue.join(', ') : (currentValue || defaultList);
            html += `
                <div class="col-md-6">
                    <label class="form-label">${param.display_name}${errorBadge}</label>
                    <input type="text" class="form-control ${isMissing ? 'border-danger' : ''}" value="${valueStr}"
                           data-indicator-param="${param.name}" data-param-type="list"
                           placeholder="${param.description || 'Comma-separated list'}">
                    <small class="form-text text-muted">Comma-separated values</small>
                </div>
            `;
        } else if (paramType === 'CHOICE' || paramType === 'choice') {
            // Handle CHOICE parameters
            const choices = param.choices || [];
            let optionsHtml = '<option value="">-- Select --</option>';
            optionsHtml += choices.map(choice =>
                `<option value="${choice}" ${choice === currentValue ? 'selected' : ''}>${choice}</option>`
            ).join('');

            // Add onchange handler for trend parameter to update pattern listboxes
            const onchangeAttr = param.name === 'trend' ? `onchange="updatePatternListboxes(${index}, this.value)"` : '';

            html += `
                <div class="col-md-3">
                    <label class="form-label">${param.display_name}${errorBadge}</label>
                    <select class="form-select ${isMissing ? 'border-danger' : ''}" data-indicator-param="${param.name}" ${onchangeAttr}>
                        <option value="">-- Select --</option>
                        ${optionsHtml}
                    </select>
                </div>
            `;
        } else {
            // Handle numeric and text parameters
            const inputType = (paramType === 'INTEGER' || paramType === 'FLOAT' || paramType === 'integer' || paramType === 'float') ? 'number' : 'text';
            const step = (paramType === 'FLOAT' || paramType === 'float') ? '0.001' : (param.step || '1');
            // Don't fill in defaults - only use the current value, leave empty if missing
            const displayValue = currentValue !== undefined ? currentValue : '';

            html += `
                <div class="col-md-3">
                    <label class="form-label">${param.display_name}${errorBadge}</label>
                    <input type="${inputType}" class="form-control ${isMissing ? 'border-danger' : ''}" value="${displayValue}"
                           data-indicator-param="${param.name}" step="${step}"
                           ${param.min_value !== undefined ? `min="${param.min_value}"` : ''}
                           ${param.max_value !== undefined ? `max="${param.max_value}"` : ''}
                           placeholder="${param.description || ''}">
                </div>
            `;
        }
    });

    if (paramsContainer) {
        paramsContainer.innerHTML = html;
    }

    return html;
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

function addCondition(containerId) {
    const container = document.getElementById(containerId);
    const conditions = container.querySelectorAll('[data-condition-index]');
    const newIndex = conditions.length / 2; // 2 inputs per condition (name, threshold)

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

    const addButton = container.querySelector('.btn-primary');
    addButton.insertAdjacentHTML('beforebegin', conditionHtml);
}

function removeCondition(containerId, index) {
    const container = document.getElementById(containerId);
    const inputs = container.querySelectorAll(`[data-condition-index="${index}"]`);

    if (inputs.length > 0 && confirm('Remove this condition?')) {
        inputs[0].closest('.row.g-2').remove();
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
        console.log('[REPLAY COLLECT]', name, 'Found', paramInputs.length, 'param inputs');
        paramInputs.forEach(input => {
            const paramName = input.dataset.indicatorParam;
            const paramType = input.dataset.paramType;
            const listboxType = input.dataset.listboxType;

            if (paramType === 'list') {
                console.log('[REPLAY COLLECT]', name, 'List param:', paramName, 'listboxType:', listboxType, 'options:', input.options.length);
                if (listboxType === 'selected') {
                    // For dual listbox, get all options from selected listbox
                    const patterns = Array.from(input.options).map(opt => opt.value);
                    console.log('[REPLAY COLLECT]', name, 'Collected patterns:', patterns);
                    parameters[paramName] = patterns;
                } else if (!listboxType) {
                    // For comma-separated text input
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

    // Update entry/exit conditions from UI
    updateCurrentConfigConditions();
}

function updateCurrentConfigConditions() {
    if (!monitorConfig || !monitorConfig.monitor) return;

    // Collect enter_long conditions
    const enterLongContainer = document.getElementById('enterLongContainer');
    const enterLongInputs = enterLongContainer.querySelectorAll('[data-condition-index]');
    const enterLongConditions = [];

    // Group inputs by condition index
    const enterLongByIndex = {};
    enterLongInputs.forEach(input => {
        const index = input.dataset.conditionIndex;
        const field = input.dataset.field;

        if (!enterLongByIndex[index]) {
            enterLongByIndex[index] = {};
        }

        if (field === 'name') {
            enterLongByIndex[index].name = input.value;
        } else if (field === 'threshold') {
            enterLongByIndex[index].threshold = parseFloat(input.value);
        }
    });

    // Convert to array
    Object.values(enterLongByIndex).forEach(condition => {
        if (condition.name) {
            enterLongConditions.push(condition);
        }
    });

    // Collect exit_long conditions
    const exitLongContainer = document.getElementById('exitLongContainer');
    const exitLongInputs = exitLongContainer.querySelectorAll('[data-condition-index]');
    const exitLongConditions = [];

    // Group inputs by condition index
    const exitLongByIndex = {};
    exitLongInputs.forEach(input => {
        const index = input.dataset.conditionIndex;
        const field = input.dataset.field;

        if (!exitLongByIndex[index]) {
            exitLongByIndex[index] = {};
        }

        if (field === 'name') {
            exitLongByIndex[index].name = input.value;
        } else if (field === 'threshold') {
            exitLongByIndex[index].threshold = parseFloat(input.value);
        }
    });

    // Convert to array
    Object.values(exitLongByIndex).forEach(condition => {
        if (condition.name) {
            exitLongConditions.push(condition);
        }
    });

    // Update the monitor config with collected conditions
    monitorConfig.monitor.enter_long = enterLongConditions;
    monitorConfig.monitor.exit_long = exitLongConditions;

    console.log('[REPLAY] Updated enter_long conditions:', enterLongConditions);
    console.log('[REPLAY] Updated exit_long conditions:', exitLongConditions);
}

function collectDataConfigData() {
    dataConfig.ticker = document.getElementById('dataTicker').value.toUpperCase();
    dataConfig.start_date = document.getElementById('dataStartDate').value;
    dataConfig.end_date = document.getElementById('dataEndDate').value;
    dataConfig.include_extended_hours = document.getElementById('dataExtendedHours').checked;
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
            // Check if there are validation errors to display
            if (result.has_validation_errors && result.validation_errors) {
                showValidationErrors(result.validation_errors);
            } else {
                showAlert('Failed to run replay: ' + result.error, 'danger');
            }
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

function showValidationErrors(validationErrors) {
    /**
     * Display validation errors in a user-friendly format
     * Each error contains indicator name and specific parameter issues
     */
    if (!validationErrors || validationErrors.length === 0) {
        showAlert('Configuration validation failed', 'danger');
        return;
    }

    // Format errors for display
    let errorMessage = '❌ Configuration Validation Failed:\n\n';

    validationErrors.forEach((error, index) => {
        // Parse error message to extract indicator name and issues
        // Error format: "Indicator 'sma_1m': Parameter validation failed for SMACrossoverIndicator:\n  • Missing required parameter: 'trend'"

        const lines = error.split('\n');
        const firstLine = lines[0];

        // Extract indicator name
        const indicatorMatch = firstLine.match(/Indicator '([^']+)'/);
        const indicatorName = indicatorMatch ? indicatorMatch[1] : 'Unknown';

        errorMessage += `\n${index + 1}. Indicator: ${indicatorName}\n`;

        // Add all parameter issues
        lines.forEach(line => {
            if (line.includes('Missing required parameter')) {
                const paramMatch = line.match(/'([^']+)'/);
                const paramName = paramMatch ? paramMatch[1] : 'unknown';
                errorMessage += `   ⚠️  Missing required parameter: "${paramName}"\n`;
            } else if (line.includes('must be')) {
                errorMessage += `   ⚠️  ${line.trim()}\n`;
            } else if (line.includes('not in allowed choices')) {
                errorMessage += `   ⚠️  ${line.trim()}\n`;
            } else if (line.includes('is below') || line.includes('is above')) {
                errorMessage += `   ⚠️  ${line.trim()}\n`;
            }
        });
    });

    console.error('Validation Errors:', validationErrors);
    showAlert(errorMessage, 'danger');
}

// Pattern management functions for dual listbox
function movePatterns(indicatorIndex, action) {
    const card = document.querySelector(`[data-indicator-index="${indicatorIndex}"]`);
    if (!card) return;

    const selectedListbox = card.querySelector('[data-listbox-type="selected"]');
    const availableListbox = card.querySelector('[data-listbox-type="available"]');

    if (!selectedListbox || !availableListbox) return;

    if (action === 'add') {
        // Move from available to selected
        Array.from(availableListbox.selectedOptions).forEach(option => {
            selectedListbox.appendChild(option.cloneNode(true));
            option.remove();
        });
    } else if (action === 'remove') {
        // Move from selected to available
        Array.from(selectedListbox.selectedOptions).forEach(option => {
            availableListbox.appendChild(option.cloneNode(true));
            option.remove();
        });
        sortListbox(availableListbox);
    }
}

function sortListbox(selectElement) {
    const options = Array.from(selectElement.options);
    options.sort((a, b) => a.value.localeCompare(b.value));
    selectElement.innerHTML = '';
    options.forEach(option => selectElement.appendChild(option));
}

function updatePatternListboxes(indicatorIndex, newTrend) {
    const card = document.querySelector(`[data-indicator-index="${indicatorIndex}"]`);
    if (!card) return;

    const selectedListbox = card.querySelector('[data-listbox-type="selected"]');
    const availableListbox = card.querySelector('[data-listbox-type="available"]');

    if (!selectedListbox || !availableListbox) return;

    // Get current selected patterns
    const currentSelected = Array.from(selectedListbox.options).map(opt => opt.value);

    // Get patterns for new trend
    const newPatterns = getPatternsByTrend(newTrend);

    // Update available listbox with new patterns, excluding already selected
    availableListbox.innerHTML = '';
    newPatterns.forEach(pattern => {
        if (!currentSelected.includes(pattern)) {
            const option = document.createElement('option');
            option.value = pattern;
            option.textContent = pattern;
            availableListbox.appendChild(option);
        }
    });

    // Remove selected patterns that are not in new trend's pattern list
    Array.from(selectedListbox.options).forEach(option => {
        if (!newPatterns.includes(option.value)) {
            option.remove();
        }
    });
}

function initializePatternListbox(indicatorIndex, trend, selectedPatterns) {
    const card = document.querySelector(`[data-indicator-index="${indicatorIndex}"]`);
    if (!card) return;

    const selectedListbox = card.querySelector('[data-listbox-type="selected"]');
    const availableListbox = card.querySelector('[data-listbox-type="available"]');

    if (!selectedListbox || !availableListbox) return;

    // Get all patterns for this trend
    const allPatterns = getPatternsByTrend(trend);

    // Clear both listboxes
    selectedListbox.innerHTML = '';
    availableListbox.innerHTML = '';

    // Add selected patterns to selected listbox
    selectedPatterns.forEach(pattern => {
        if (allPatterns.includes(pattern)) {
            const option = document.createElement('option');
            option.value = pattern;
            option.textContent = pattern;
            selectedListbox.appendChild(option);
        }
    });

    // Add remaining patterns to available listbox
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
