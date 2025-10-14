/**
 * Optimizer Configuration Editor
 * Handles dynamic loading, editing, and saving of optimizer configurations with ranges
 */

let monitorConfig = null;
let dataConfig = null;
let gaConfig = null;
let indicatorClasses = {};

const AVAILABLE_OBJECTIVES = [
    'MaximizeProfit',
    'MinimizeLosingTrades',
    'MinimizeLoss',
    'MinimizeTrades',
    'MaximizeNetPnL',
    'MaximizeScaledNetPnL'
];

// Default ranges for bar weights and thresholds
const DEFAULT_WEIGHT_RANGE = [0.0, 10.0];
const DEFAULT_THRESHOLD_RANGE = [0.0, 1.0];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadIndicatorClasses();
    setupEventListeners();
});

function setupEventListeners() {
    // File input change listeners
    document.getElementById('monitorFileInput').addEventListener('change', checkFilesSelected);
    document.getElementById('dataFileInput').addEventListener('change', checkFilesSelected);
    document.getElementById('gaFileInput').addEventListener('change', checkFilesSelected);

    // Load configs button
    document.getElementById('loadConfigsBtn').addEventListener('click', loadConfigurations);

    // Add indicator/bar buttons
    document.getElementById('addIndicatorBtn').addEventListener('click', addIndicator);
    document.getElementById('addBarBtn').addEventListener('click', addBar);

    // Add objective button
    document.getElementById('addObjectiveBtn').addEventListener('click', addObjective);
}

function checkFilesSelected() {
    const monitorFile = document.getElementById('monitorFileInput').files.length > 0;
    const dataFile = document.getElementById('dataFileInput').files.length > 0;
    const gaFile = document.getElementById('gaFileInput').files.length > 0;
    document.getElementById('loadConfigsBtn').disabled = !(monitorFile && dataFile && gaFile);
}

async function loadIndicatorClasses() {
    try {
        const response = await fetch('/monitor_config/api/get_indicator_classes');
        const result = await response.json();

        if (result.success) {
            indicatorClasses = result.indicators;
            console.log('Loaded indicator classes:', indicatorClasses);
        }
    } catch (error) {
        console.error('Error loading indicator classes:', error);
    }
}

async function loadConfigurations() {
    const monitorFileInput = document.getElementById('monitorFileInput');
    const dataFileInput = document.getElementById('dataFileInput');
    const gaFileInput = document.getElementById('gaFileInput');

    if (!monitorFileInput.files.length || !dataFileInput.files.length || !gaFileInput.files.length) return;

    try {
        // Load monitor config
        const monitorFile = monitorFileInput.files[0];
        const monitorText = await monitorFile.text();
        monitorConfig = JSON.parse(monitorText);

        // Load data config
        const dataFile = dataFileInput.files[0];
        const dataText = await dataFile.text();
        dataConfig = JSON.parse(dataText);

        // Load GA config
        const gaFile = gaFileInput.files[0];
        const gaText = await gaFile.text();
        gaConfig = JSON.parse(gaText);

        // Render configurations
        renderMonitorConfiguration();
        renderDataConfiguration();
        renderGAConfiguration();

        // Show editor
        document.getElementById('configEditor').style.display = 'block';

        // Wait for pattern listboxes to be initialized before collecting config
        // (CDL pattern listboxes are populated in a setTimeout, so we need to wait)
        setTimeout(() => {
            // Store configs globally for start button
            window.currentConfigs = {
                ga_config: collectAllConfigs(),
                data_config: dataConfig
            };

            // Dispatch event to enable start button
            document.dispatchEvent(new CustomEvent('configurationsLoaded', {
                detail: {
                    monitor: monitorConfig,
                    data: dataConfig,
                    ga: gaConfig
                }
            }));
        }, 100); // Wait longer than the 50ms timeout for initializePatternListbox
    } catch (error) {
        alert('Error loading configurations: ' + error.message);
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

    // Entry/Exit conditions with ranges
    renderConditionsWithRanges('enterLongContainer', monitor.enter_long || []);
    renderConditionsWithRanges('exitLongContainer', monitor.exit_long || []);

    // Indicators tab with ranges
    renderIndicators(indicators);

    // Bars tab with ranges
    renderBars(bars);
}

function renderDataConfiguration() {
    if (!dataConfig) return;

    document.getElementById('dataTicker').value = dataConfig.ticker || '';
    document.getElementById('dataStartDate').value = dataConfig.start_date || '';
    document.getElementById('dataEndDate').value = dataConfig.end_date || '';
}

function renderGAConfiguration() {
    if (!gaConfig) return;

    // Render objectives
    renderObjectives(gaConfig.objectives || []);

    // Render GA hyperparameters
    const hp = gaConfig.ga_hyperparameters || {};
    document.getElementById('numIterations').value = hp.number_of_iterations || 500;
    document.getElementById('populationSize').value = hp.population_size || 200;
    document.getElementById('propagationFraction').value = hp.propagation_fraction || 0.4;
    document.getElementById('elitesToSave').value = hp.elites_to_save || 2;
    document.getElementById('eliteSize').value = hp.elite_size || 12;
    document.getElementById('chanceMutation').value = hp.chance_of_mutation || 0.05;
    document.getElementById('chanceCrossover').value = hp.chance_of_crossover || 0.03;
    document.getElementById('numSplits').value = hp.num_splits || 1;
}

function renderConditionsWithRanges(containerId, conditions) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';

    conditions.forEach((condition, index) => {
        const startThreshold = condition.threshold || 0.5;
        const thresholdRange = condition.threshold_range || DEFAULT_THRESHOLD_RANGE;

        const conditionHtml = `
            <div class="row g-2 mb-2">
                <div class="col-md-3">
                    <label class="form-label">Bar Name</label>
                    <select class="form-select form-select-sm" data-condition-index="${index}" data-field="name">
                        ${generateBarNameOptions(condition.name || '')}
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Start</label>
                    <input type="number" class="form-control form-control-sm" value="${startThreshold}" step="0.01"
                           data-condition-index="${index}" data-field="threshold_start">
                </div>
                <div class="col-md-2">
                    <label class="form-label">Min</label>
                    <input type="number" class="form-control form-control-sm" value="${thresholdRange[0]}" step="0.01"
                           data-condition-index="${index}" data-field="threshold_min">
                </div>
                <div class="col-md-2">
                    <label class="form-label">Max</label>
                    <input type="number" class="form-control form-control-sm" value="${thresholdRange[1]}" step="0.01"
                           data-condition-index="${index}" data-field="threshold_max">
                </div>
                <div class="col-md-3">
                    <label class="form-label">&nbsp;</label>
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

function renderIndicators(indicators) {
    const container = document.getElementById('indicatorsContainer');
    container.innerHTML = '';

    indicators.forEach((indicator, index) => {
        container.insertAdjacentHTML('beforeend', createIndicatorCardWithRanges(indicator, index));

        // Special handling for CDLPatternIndicator - initialize dual listbox
        if (indicator.indicator_class === 'CDLPatternIndicator') {
            const params = indicator.parameters || {};
            const patterns = params.patterns || [];
            const trend = params.trend || 'bullish';

            // First ensure the dual listbox UI exists (since renderIndicatorParamsWithRanges doesn't handle it)
            // This needs to happen before we can initialize the patterns
            const paramsContainer = document.getElementById(`indicator-params-${index}`);
            if (paramsContainer && !paramsContainer.querySelector('[data-listbox-type="selected"]')) {
                // Dual listbox doesn't exist yet, create it
                updateIndicatorParamsWithRanges(index, indicator.indicator_class);
            }

            // Initialize pattern listbox with loaded patterns
            setTimeout(() => {
                initializePatternListbox(index, trend, patterns);
            }, 50);
        }
    });
}

function createIndicatorCardWithRanges(indicator, index) {
    const params = indicator.parameters || {};
    const ranges = indicator.ranges || {};
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
                <div class="row g-2 mb-2">
                    <div class="col-md-4">
                        <label class="form-label">Name</label>
                        <input type="text" class="form-control" value="${indicator.name || ''}"
                               data-indicator-field="name" onchange="refreshBarIndicatorDropdowns()">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Indicator Class</label>
                        <select class="form-select" data-indicator-field="indicator_class"
                                onchange="updateIndicatorParamsWithRanges(${index}, this.value)">
                            ${generateIndicatorClassOptions(indicatorClass)}
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Aggregation Config</label>
                        <input type="text" class="form-control" value="${indicator.agg_config || '1m-normal'}"
                               data-indicator-field="agg_config" placeholder="e.g. 1m-normal, 5m-heiken">
                    </div>
                </div>
                <div id="indicator-params-${index}">
                    ${renderIndicatorParamsWithRanges(params, ranges, index)}
                </div>
            </div>
        </div>
    `;
}

function renderIndicatorParamsWithRanges(params, ranges, index) {
    let html = '<div class="row g-2 mt-2">';

    for (const [key, value] of Object.entries(params)) {
        const range = ranges[key] || {};
        const rangeValues = range.r || [value * 0.5, value * 1.5]; // Default range if not specified
        const rangeType = range.t || (typeof value === 'number' ? (Number.isInteger(value) ? 'int' : 'float') : 'skip');

        if (rangeType === 'skip') {
            // Skip parameters that shouldn't be optimized (like 'trend')
            continue;
        }

        const step = rangeType === 'float' ? '0.001' : '1';

        html += `
            <div class="col-md-6">
                <label class="form-label">${key}</label>
                <div class="row g-1">
                    <div class="col-4">
                        <input type="number" class="form-control form-control-sm"
                               value="${value}" step="${step}" placeholder="Start"
                               data-indicator-param="${key}" data-range-type="start">
                    </div>
                    <div class="col-4">
                        <input type="number" class="form-control form-control-sm"
                               value="${rangeValues[0]}" step="${step}" placeholder="Min"
                               data-indicator-param="${key}" data-range-type="min">
                    </div>
                    <div class="col-4">
                        <input type="number" class="form-control form-control-sm"
                               value="${rangeValues[1]}" step="${step}" placeholder="Max"
                               data-indicator-param="${key}" data-range-type="max">
                    </div>
                </div>
            </div>
        `;
    }

    html += '</div>';
    return html;
}

function renderBars(bars) {
    const container = document.getElementById('barsContainer');
    container.innerHTML = '';

    for (const [barName, barConfig] of Object.entries(bars)) {
        const barHtml = createBarCardWithRanges(barName, barConfig);
        container.insertAdjacentHTML('beforeend', barHtml);
    }
}

function createBarCardWithRanges(barName, barConfig) {
    const indicators = barConfig.indicators || {};

    let indicatorsHtml = '';
    for (const [indName, weight] of Object.entries(indicators)) {
        // Check if weight is an object with start/range, array, or single value
        let startValue, weightRange;
        if (weight && typeof weight === 'object' && 'start' in weight && 'range' in weight) {
            // New format: {start: x, range: [min, max]}
            startValue = weight.start;
            weightRange = weight.range;
        } else if (Array.isArray(weight)) {
            // Array format: [min, max]
            startValue = weight[0]; // Use min as start
            weightRange = weight;
        } else {
            // Single value, create default range
            startValue = weight;
            weightRange = DEFAULT_WEIGHT_RANGE;
        }

        indicatorsHtml += `
            <div class="row g-2 mb-2">
                <div class="col-md-3">
                    <select class="form-select form-select-sm" data-bar-indicator-name>
                        ${generateIndicatorNameOptions(indName)}
                    </select>
                </div>
                <div class="col-md-2">
                    <input type="number" class="form-control form-control-sm" value="${startValue}"
                           data-bar-indicator-weight-start step="0.1" placeholder="Start">
                </div>
                <div class="col-md-2">
                    <input type="number" class="form-control form-control-sm" value="${weightRange[0]}"
                           data-bar-indicator-weight-min step="0.1" placeholder="Min">
                </div>
                <div class="col-md-2">
                    <input type="number" class="form-control form-control-sm" value="${weightRange[1]}"
                           data-bar-indicator-weight-max step="0.1" placeholder="Max">
                </div>
                <div class="col-md-3">
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
                    <label class="form-label"><strong>Indicators & Weight Ranges:</strong></label>
                    <div class="bar-indicators-container">
                        ${indicatorsHtml}
                    </div>
                    <button class="btn btn-sm btn-primary mt-2" onclick="addBarIndicatorWithRange(this)">
                        <i class="fas fa-plus me-2"></i>Add Indicator
                    </button>
                </div>
            </div>
        </div>
    `;
}

function renderObjectives(objectives) {
    const container = document.getElementById('objectivesContainer');
    container.innerHTML = '';

    objectives.forEach((objective, index) => {
        const objectiveHtml = createObjectiveCard(objective, index);
        container.insertAdjacentHTML('beforeend', objectiveHtml);
    });
}

function createObjectiveCard(objective, index) {
    return `
        <div class="objective-card" data-objective-index="${index}">
            <div class="row g-2 align-items-end">
                <div class="col-md-5">
                    <label class="form-label">Objective</label>
                    <select class="form-select" data-objective-field="objective">
                        ${generateObjectiveOptions(objective.objective || '')}
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Weight</label>
                    <input type="number" class="form-control" value="${objective.weight || 1.0}"
                           step="0.1" data-objective-field="weight">
                </div>
                <div class="col-md-2">
                    <button class="btn btn-danger w-100" onclick="removeObjective(${index})">
                        <i class="fas fa-trash"></i> Remove
                    </button>
                </div>
            </div>
        </div>
    `;
}

function generateObjectiveOptions(selected) {
    let options = '<option value="">-- Select Objective --</option>';
    AVAILABLE_OBJECTIVES.forEach(obj => {
        const isSelected = obj === selected ? 'selected' : '';
        options += `<option value="${obj}" ${isSelected}>${obj}</option>`;
    });
    return options;
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

function generateIndicatorClassOptions(selectedClass) {
    let options = '<option value="">-- Select Class --</option>';

    for (const className of Object.keys(indicatorClasses)) {
        const isSelected = className === selectedClass ? 'selected' : '';
        options += `<option value="${className}" ${isSelected}>${className}</option>`;
    }

    return options;
}

function toggleIndicatorCard(index) {
    const body = document.getElementById(`indicator-body-${index}`);
    const icon = document.getElementById(`collapse-icon-${index}`);

    if (body && icon) {
        body.classList.toggle('show');
        icon.classList.toggle('expanded');
    }
}

function updateIndicatorParamsWithRanges(index, className) {
    if (!className || !indicatorClasses[className]) return;

    const schema = indicatorClasses[className];
    const paramsContainer = document.getElementById(`indicator-params-${index}`);

    const paramGroups = schema.parameter_groups || {};
    const allParams = Object.values(paramGroups).flat();

    let html = '<div class="row g-2 mt-2">';
    allParams.forEach(param => {
        if (param.type === 'list' && param.name === 'patterns') {
            // Handle patterns parameter with dual listbox (no ranges for lists)
            html += `
                <div class="col-md-12">
                    <label class="form-label">${param.display_name}</label>
                    <div class="row">
                        <div class="col-md-5">
                            <label class="form-label small">Selected Patterns</label>
                            <select multiple class="form-select" size="10"
                                    data-indicator-param="patterns"
                                    data-param-type="list"
                                    data-listbox-type="selected"
                                    style="max-width: 100%;">
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
        } else if (param.type === 'choice') {
            // Handle choice parameters (fixed values, no ranges)
            const choices = param.choices || [];
            let optionsHtml = choices.map(choice =>
                `<option value="${choice}" ${choice === param.default ? 'selected' : ''}>${choice}</option>`
            ).join('');

            // Add onchange handler for trend parameter to update pattern listboxes
            const onchangeAttr = param.name === 'trend' ? `onchange="updatePatternListboxes(${index}, this.value)"` : '';

            html += `
                <div class="col-md-6">
                    <label class="form-label">${param.display_name}</label>
                    <select class="form-select form-control-sm" data-indicator-param="${param.name}" ${onchangeAttr}>
                        ${optionsHtml}
                    </select>
                </div>
            `;
        } else if (param.type === 'string' || param.type === 'list') {
            // Skip other non-numeric parameters
            return;
        } else {
            // Handle numeric parameters with ranges
            const startVal = param.default;
            const minVal = param.min !== undefined ? param.min : (param.default * 0.5);
            const maxVal = param.max !== undefined ? param.max : (param.default * 1.5);
            const step = param.type === 'float' ? '0.001' : '1';

            html += `
                <div class="col-md-6">
                    <label class="form-label">${param.display_name}</label>
                    <div class="row g-1">
                        <div class="col-4">
                            <input type="number" class="form-control form-control-sm"
                                   value="${startVal}" step="${step}" placeholder="Start"
                                   data-indicator-param="${param.name}" data-range-type="start">
                        </div>
                        <div class="col-4">
                            <input type="number" class="form-control form-control-sm"
                                   value="${minVal}" step="${step}" placeholder="Min"
                                   data-indicator-param="${param.name}" data-range-type="min">
                        </div>
                        <div class="col-4">
                            <input type="number" class="form-control form-control-sm"
                                   value="${maxVal}" step="${step}" placeholder="Max"
                                   data-indicator-param="${param.name}" data-range-type="max">
                        </div>
                    </div>
                </div>
            `;
        }
    });
    html += '</div>';

    paramsContainer.innerHTML = html;
}

function addIndicator() {
    const container = document.getElementById('indicatorsContainer');
    const index = container.querySelectorAll('.indicator-card').length;

    const newIndicator = {
        name: 'new_indicator',
        indicator_class: '',
        type: 'Indicator',
        agg_config: '1m-normal',
        calc_on_pip: false,
        parameters: {},
        ranges: {}
    };

    const indicatorHtml = createIndicatorCardWithRanges(newIndicator, index);
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

function addBar() {
    const container = document.getElementById('barsContainer');
    const barName = `new_bar_${Date.now()}`;

    const newBar = {
        type: 'bull',
        description: 'New bar configuration',
        indicators: {}
    };

    const barHtml = createBarCardWithRanges(barName, newBar);
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

function addBarIndicatorWithRange(button) {
    const barCard = button.closest('.bar-card');
    const container = barCard.querySelector('.bar-indicators-container');

    const newIndicatorHtml = `
        <div class="row g-2 mb-2">
            <div class="col-md-3">
                <select class="form-select form-select-sm" data-bar-indicator-name>
                    ${generateIndicatorNameOptions('')}
                </select>
            </div>
            <div class="col-md-2">
                <input type="number" class="form-control form-control-sm" value="1.0"
                       data-bar-indicator-weight-start step="0.1" placeholder="Start">
            </div>
            <div class="col-md-2">
                <input type="number" class="form-control form-control-sm" value="${DEFAULT_WEIGHT_RANGE[0]}"
                       data-bar-indicator-weight-min step="0.1" placeholder="Min">
            </div>
            <div class="col-md-2">
                <input type="number" class="form-control form-control-sm" value="${DEFAULT_WEIGHT_RANGE[1]}"
                       data-bar-indicator-weight-max step="0.1" placeholder="Max">
            </div>
            <div class="col-md-3">
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

function addObjective() {
    const container = document.getElementById('objectivesContainer');
    const index = container.querySelectorAll('.objective-card').length;

    const newObjective = {
        objective: '',
        weight: 1.0,
        parameters: {}
    };

    const objectiveHtml = createObjectiveCard(newObjective, index);
    container.insertAdjacentHTML('beforeend', objectiveHtml);
}

function removeObjective(index) {
    const card = document.querySelector(`[data-objective-index="${index}"]`);
    if (card && confirm('Remove this objective?')) {
        card.remove();
    }
}

function addCondition(containerId) {
    const container = document.getElementById(containerId);
    const conditions = container.querySelectorAll('[data-condition-index]');
    const newIndex = conditions.length / 4; // 4 inputs per condition (name, start, min, max)

    const conditionHtml = `
        <div class="row g-2 mb-2">
            <div class="col-md-3">
                <label class="form-label">Bar Name</label>
                <select class="form-select form-select-sm" data-condition-index="${newIndex}" data-field="name">
                    ${generateBarNameOptions('')}
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label">Start</label>
                <input type="number" class="form-control form-control-sm" value="0.5" step="0.01"
                       data-condition-index="${newIndex}" data-field="threshold_start">
            </div>
            <div class="col-md-2">
                <label class="form-label">Min</label>
                <input type="number" class="form-control form-control-sm" value="${DEFAULT_THRESHOLD_RANGE[0]}" step="0.01"
                       data-condition-index="${newIndex}" data-field="threshold_min">
            </div>
            <div class="col-md-2">
                <label class="form-label">Max</label>
                <input type="number" class="form-control form-control-sm" value="${DEFAULT_THRESHOLD_RANGE[1]}" step="0.01"
                       data-condition-index="${newIndex}" data-field="threshold_max">
            </div>
            <div class="col-md-3">
                <label class="form-label">&nbsp;</label>
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
    // Find all inputs with this index and remove their parent row
    const container = document.getElementById(containerId);
    const inputs = container.querySelectorAll(`[data-condition-index="${index}"]`);

    if (inputs.length > 0 && confirm('Remove this condition?')) {
        inputs[0].closest('.row.g-2').remove();
    }
}

function refreshConditionDropdowns() {
    updateCurrentConfigBars();

    if (monitorConfig && monitorConfig.monitor) {
        const enterLongConditions = monitorConfig.monitor.enter_long || [];
        const exitLongConditions = monitorConfig.monitor.exit_long || [];

        renderConditionsWithRanges('enterLongContainer', enterLongConditions);
        renderConditionsWithRanges('exitLongContainer', exitLongConditions);
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
        const ranges = {};

        const paramInputs = card.querySelectorAll('[data-indicator-param]');
        const paramNames = new Set();

        // First pass: collect all values and determine types
        const paramData = {};
        paramInputs.forEach(input => {
            const paramName = input.dataset.indicatorParam;
            const paramType = input.dataset.paramType;
            const listboxType = input.dataset.listboxType;
            const rangeType = input.dataset.rangeType; // 'start', 'min' or 'max'

            paramNames.add(paramName);

            // Handle list parameters (like patterns)
            if (paramType === 'list') {
                if (listboxType === 'selected') {
                    // For dual listbox, get all options from selected listbox
                    const patterns = Array.from(input.options).map(opt => opt.value);
                    parameters[paramName] = patterns;
                    // No ranges for list parameters
                }
                return;
            }

            // Handle choice parameters (like trend)
            if (input.tagName === 'SELECT' && !rangeType) {
                parameters[paramName] = input.value;
                // No ranges for choice parameters
                return;
            }

            // Handle numeric parameters with ranges
            const paramValue = input.type === 'number' ? parseFloat(input.value) : input.value;

            if (!paramData[paramName]) {
                paramData[paramName] = { start: null, min: null, max: null, type: 'float' };
            }

            if (rangeType === 'start') {
                // Determine type based on start value
                const isInteger = Number.isInteger(paramValue);
                paramData[paramName].start = isInteger ? Math.round(paramValue) : paramValue;
                paramData[paramName].type = isInteger ? 'int' : 'float';
            } else if (rangeType === 'min') {
                paramData[paramName].min = paramValue;
            } else if (rangeType === 'max') {
                paramData[paramName].max = paramValue;
            }
        });

        // Second pass: build parameters and ranges with correct types (only for numeric params)
        for (const [paramName, data] of Object.entries(paramData)) {
            parameters[paramName] = data.start;

            // Convert min/max to correct type
            const minValue = data.type === 'int' ? Math.round(data.min) : data.min;
            const maxValue = data.type === 'int' ? Math.round(data.max) : data.max;

            ranges[paramName] = {
                t: data.type,
                r: [minValue, maxValue]
            };
        }

        if (name) {
            indicators.push({
                name: name,
                indicator_class: indicatorClass,
                type: 'Indicator',
                agg_config: aggConfig,
                calc_on_pip: false,
                parameters: parameters,
                ranges: ranges
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
        const indicatorSelects = card.querySelectorAll('[data-bar-indicator-name]');

        indicatorSelects.forEach(select => {
            const indName = select.value;
            const row = select.closest('.row.g-2');
            const startInput = row.querySelector('[data-bar-indicator-weight-start]');
            const minInput = row.querySelector('[data-bar-indicator-weight-min]');
            const maxInput = row.querySelector('[data-bar-indicator-weight-max]');

            if (indName && startInput && minInput && maxInput) {
                const weightStart = parseFloat(startInput.value);
                // For the monitor config, use the start value as the actual weight
                // The ranges are stored separately in the GA config
                indicators[indName] = weightStart;
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

    // Collect entry/exit conditions
    collectConditions();
}

function collectConditions() {
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
        } else if (field === 'threshold_start') {
            enterLongByIndex[index].threshold = parseFloat(input.value);
        } else if (field === 'threshold_min') {
            if (!enterLongByIndex[index].threshold_range) {
                enterLongByIndex[index].threshold_range = [null, null];
            }
            enterLongByIndex[index].threshold_range[0] = parseFloat(input.value);
        } else if (field === 'threshold_max') {
            if (!enterLongByIndex[index].threshold_range) {
                enterLongByIndex[index].threshold_range = [null, null];
            }
            enterLongByIndex[index].threshold_range[1] = parseFloat(input.value);
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
        } else if (field === 'threshold_start') {
            exitLongByIndex[index].threshold = parseFloat(input.value);
        } else if (field === 'threshold_min') {
            if (!exitLongByIndex[index].threshold_range) {
                exitLongByIndex[index].threshold_range = [null, null];
            }
            exitLongByIndex[index].threshold_range[0] = parseFloat(input.value);
        } else if (field === 'threshold_max') {
            if (!exitLongByIndex[index].threshold_range) {
                exitLongByIndex[index].threshold_range = [null, null];
            }
            exitLongByIndex[index].threshold_range[1] = parseFloat(input.value);
        }
    });

    // Convert to array
    Object.values(exitLongByIndex).forEach(condition => {
        if (condition.name) {
            exitLongConditions.push(condition);
        }
    });

    monitorConfig.monitor.enter_long = enterLongConditions;
    monitorConfig.monitor.exit_long = exitLongConditions;
}

function collectDataConfigData() {
    dataConfig.ticker = document.getElementById('dataTicker').value;
    dataConfig.start_date = document.getElementById('dataStartDate').value;
    dataConfig.end_date = document.getElementById('dataEndDate').value;
}

function collectGAConfigData() {
    // Collect objectives
    const objectives = [];
    const objectiveCards = document.querySelectorAll('.objective-card');

    objectiveCards.forEach(card => {
        const objectiveSelect = card.querySelector('[data-objective-field="objective"]');
        const weightInput = card.querySelector('[data-objective-field="weight"]');

        if (objectiveSelect && objectiveSelect.value) {
            objectives.push({
                objective: objectiveSelect.value,
                weight: parseFloat(weightInput.value),
                parameters: {} // Empty for now, can be extended
            });
        }
    });

    gaConfig.objectives = objectives;

    // Collect GA hyperparameters
    gaConfig.ga_hyperparameters = {
        number_of_iterations: parseInt(document.getElementById('numIterations').value),
        population_size: parseInt(document.getElementById('populationSize').value),
        propagation_fraction: parseFloat(document.getElementById('propagationFraction').value),
        elites_to_save: parseInt(document.getElementById('elitesToSave').value),
        elite_size: parseInt(document.getElementById('eliteSize').value),
        chance_of_mutation: parseFloat(document.getElementById('chanceMutation').value),
        chance_of_crossover: parseFloat(document.getElementById('chanceCrossover').value),
        num_splits: parseInt(document.getElementById('numSplits').value)
    };
}

// Merge all configs into a single GA config JSON
function collectAllConfigs() {
    collectMonitorConfigData();
    collectDataConfigData();
    collectGAConfigData();

    // Combine into single GA config structure
    const combinedConfig = {
        test_name: monitorConfig.monitor.name,
        monitor: monitorConfig.monitor,
        indicators: monitorConfig.indicators,
        objectives: gaConfig.objectives,
        ga_hyperparameters: gaConfig.ga_hyperparameters
    };

    console.log('🔍 Collected GA Config:', JSON.stringify(combinedConfig, null, 2));
    console.log('🔍 Monitor bars:', combinedConfig.monitor.bars);
    console.log('🔍 Enter long conditions:', combinedConfig.monitor.enter_long);
    console.log('🔍 Exit long conditions:', combinedConfig.monitor.exit_long);
    console.log('🔍 Indicators:', combinedConfig.indicators);

    return combinedConfig;
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
