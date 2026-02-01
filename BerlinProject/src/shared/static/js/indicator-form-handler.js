/**
 * Shared Indicator Form Handler
 *
 * Provides unified indicator loading, form generation, and type-based filtering
 * for Signal and Trend indicators across all UIs:
 * - visualization_apps: monitor-config, replay-config, optimizer-config
 * - stock_analysis_ui: monitor_creation
 *
 * Key Features:
 * - Type-filtered API loading (signal vs trend indicators)
 * - Dynamic form generation based on indicator schemas
 * - Unified dropdown generation with type filtering
 * - Two-button UI support (Add Signal Indicator / Add Trend Indicator)
 */

// ============================================================================
// INDICATOR CLASS STORAGE
// ============================================================================

/**
 * Storage for loaded indicator classes, separated by type.
 * Populated by loadIndicatorClasses* functions.
 */
const IndicatorStore = {
    all: {},        // All indicators (signal + trend)
    signal: {},     // SIGNAL type indicators only
    trend: {},      // TREND type indicators only
    loaded: {
        all: false,
        signal: false,
        trend: false
    }
};

// ============================================================================
// API LOADING FUNCTIONS
// ============================================================================

/**
 * Load all indicator classes from the API.
 * Populates IndicatorStore.all
 *
 * @param {string} basePath - Base path for API (e.g., '/monitor_config')
 * @returns {Promise<Object>} The loaded indicator schemas
 */
async function loadAllIndicatorClasses(basePath = '/monitor_config') {
    try {
        const response = await fetch(`${basePath}/api/get_indicator_classes`);
        const result = await response.json();

        if (result.success) {
            IndicatorStore.all = result.indicators;
            IndicatorStore.loaded.all = true;
            console.log(`Loaded ${Object.keys(result.indicators).length} indicator classes (all types)`);
            return result.indicators;
        } else {
            console.error('Failed to load indicator classes:', result.error);
            return {};
        }
    } catch (error) {
        console.error('Error loading indicator classes:', error);
        return {};
    }
}

/**
 * Load SIGNAL type indicator classes from the API.
 * Populates IndicatorStore.signal
 *
 * @param {string} basePath - Base path for API (e.g., '/monitor_config')
 * @returns {Promise<Object>} The loaded signal indicator schemas
 */
async function loadSignalIndicatorClasses(basePath = '/monitor_config') {
    try {
        const response = await fetch(`${basePath}/api/indicators/signal`);
        const result = await response.json();

        if (result.success) {
            IndicatorStore.signal = result.indicators;
            IndicatorStore.loaded.signal = true;
            console.log(`Loaded ${Object.keys(result.indicators).length} SIGNAL indicator classes`);
            return result.indicators;
        } else {
            console.error('Failed to load signal indicator classes:', result.error);
            return {};
        }
    } catch (error) {
        console.error('Error loading signal indicator classes:', error);
        return {};
    }
}

/**
 * Load TREND type indicator classes from the API.
 * Populates IndicatorStore.trend
 *
 * @param {string} basePath - Base path for API (e.g., '/monitor_config')
 * @returns {Promise<Object>} The loaded trend indicator schemas
 */
async function loadTrendIndicatorClasses(basePath = '/monitor_config') {
    try {
        const response = await fetch(`${basePath}/api/indicators/trend`);
        const result = await response.json();

        if (result.success) {
            IndicatorStore.trend = result.indicators;
            IndicatorStore.loaded.trend = true;
            console.log(`Loaded ${Object.keys(result.indicators).length} TREND indicator classes`);
            return result.indicators;
        } else {
            console.error('Failed to load trend indicator classes:', result.error);
            return {};
        }
    } catch (error) {
        console.error('Error loading trend indicator classes:', error);
        return {};
    }
}

/**
 * Load all indicator types (signal and trend) in parallel.
 * Convenience function for pages that need both types.
 *
 * @param {string} basePath - Base path for API (e.g., '/monitor_config')
 * @returns {Promise<{signal: Object, trend: Object}>} Both indicator type schemas
 */
async function loadAllIndicatorTypes(basePath = '/monitor_config') {
    const [signal, trend] = await Promise.all([
        loadSignalIndicatorClasses(basePath),
        loadTrendIndicatorClasses(basePath)
    ]);

    // Also populate the 'all' store
    IndicatorStore.all = { ...signal, ...trend };
    IndicatorStore.loaded.all = true;

    return { signal, trend };
}

/**
 * Get indicator classes by type from the store.
 *
 * @param {string} indicatorType - 'signal', 'trend', or 'all'
 * @returns {Object} The indicator schemas for the specified type
 */
function getIndicatorClasses(indicatorType = 'all') {
    switch (indicatorType) {
        case 'signal':
            return IndicatorStore.signal;
        case 'trend':
            return IndicatorStore.trend;
        default:
            return IndicatorStore.all;
    }
}

// ============================================================================
// DROPDOWN GENERATION FUNCTIONS
// ============================================================================

/**
 * Generate <option> elements for indicator class dropdown.
 * Filters by indicator type.
 *
 * @param {string} selectedClass - Currently selected class name (for 'selected' attr)
 * @param {string} indicatorType - 'signal', 'trend', or 'all'
 * @returns {string} HTML string of <option> elements
 */
function generateIndicatorClassOptions(selectedClass, indicatorType = 'all') {
    const classes = getIndicatorClasses(indicatorType);
    let options = '<option value="">-- Select Class --</option>';

    for (const className of Object.keys(classes).sort()) {
        const isSelected = className === selectedClass ? 'selected' : '';
        const schema = classes[className];
        const displayName = schema.display_name || className;
        options += `<option value="${className}" ${isSelected}>${displayName}</option>`;
    }

    return options;
}

/**
 * Generate <option> elements for signal indicator class dropdown.
 *
 * @param {string} selectedClass - Currently selected class name
 * @returns {string} HTML string of <option> elements
 */
function generateSignalIndicatorClassOptions(selectedClass) {
    return generateIndicatorClassOptions(selectedClass, 'signal');
}

/**
 * Generate <option> elements for trend indicator class dropdown.
 *
 * @param {string} selectedClass - Currently selected class name
 * @returns {string} HTML string of <option> elements
 */
function generateTrendIndicatorClassOptions(selectedClass) {
    return generateIndicatorClassOptions(selectedClass, 'trend');
}

// ============================================================================
// PARAMETER FORM GENERATION
// ============================================================================

/**
 * Render parameter input fields for an indicator class.
 * Generates appropriate input types based on parameter specs.
 *
 * @param {Object} params - Current parameter values
 * @param {number} index - Indicator card index (for unique IDs)
 * @param {string} indicatorType - 'signal', 'trend', or 'all'
 * @returns {string} HTML string for parameter inputs
 */
function renderIndicatorParamsFromValues(params, index, indicatorType = 'all') {
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

/**
 * Generate parameter form HTML based on indicator class schema.
 * Handles all parameter types: integer, float, boolean, choice, list.
 *
 * @param {string} className - The indicator class name
 * @param {number} index - Indicator card index
 * @param {string} indicatorType - 'signal', 'trend', or 'all'
 * @param {Object} callbacks - Optional callbacks for special handling
 * @returns {string} HTML string for parameter form
 */
function generateIndicatorParamsFromSchema(className, index, indicatorType = 'all', callbacks = {}) {
    const classes = getIndicatorClasses(indicatorType);
    if (!className || !classes[className]) return '';

    const schema = classes[className];
    const paramGroups = schema.parameter_groups || {};
    const allParams = Object.values(paramGroups).flat();

    let html = '';
    allParams.forEach(param => {
        html += generateParamInputHtml(param, index, callbacks);
    });

    return html;
}

/**
 * Generate HTML for a single parameter input based on its type.
 *
 * @param {Object} param - Parameter specification
 * @param {number} index - Indicator card index
 * @param {Object} callbacks - Optional callbacks for special handling
 * @returns {string} HTML string for the parameter input
 */
function generateParamInputHtml(param, index, callbacks = {}) {
    if (param.type === 'list' && param.name === 'patterns') {
        // CDL Pattern listbox (special case)
        return generatePatternListboxHtml(param, index);
    } else if (param.type === 'list') {
        // Generic list parameter
        return generateListParamHtml(param);
    } else if (param.type === 'choice') {
        // Choice/select parameter
        return generateChoiceParamHtml(param, index, callbacks);
    } else {
        // Numeric or text parameter
        return generateSimpleParamHtml(param);
    }
}

/**
 * Generate HTML for pattern listbox (CDLPatternIndicator special case).
 */
function generatePatternListboxHtml(param, index) {
    return `
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
}

/**
 * Generate HTML for a generic list parameter (comma-separated input).
 */
function generateListParamHtml(param) {
    const defaultList = Array.isArray(param.default) ? param.default.join(', ') : '';
    return `
        <div class="col-md-6">
            <label class="form-label">${param.display_name}</label>
            <input type="text" class="form-control" value="${defaultList}"
                   data-indicator-param="${param.name}" data-param-type="list"
                   placeholder="${param.description || 'Comma-separated list'}">
            <small class="form-text text-muted">Comma-separated values</small>
        </div>
    `;
}

/**
 * Generate HTML for a choice/select parameter.
 */
function generateChoiceParamHtml(param, index, callbacks = {}) {
    const choices = param.choices || [];
    let optionsHtml = choices.map(choice =>
        `<option value="${choice}" ${choice === param.default ? 'selected' : ''}>${choice}</option>`
    ).join('');

    // Add onchange handler for trend parameter to update pattern lists
    let onchangeAttr = '';
    if (param.name === 'trend' && typeof updatePatternListboxes === 'function') {
        onchangeAttr = `onchange="updatePatternListboxes(${index}, this.value)"`;
    }

    return `
        <div class="col-md-3">
            <label class="form-label">${param.display_name}</label>
            <select class="form-select" data-indicator-param="${param.name}" ${onchangeAttr}>
                ${optionsHtml}
            </select>
        </div>
    `;
}

/**
 * Generate HTML for a simple numeric or text parameter.
 */
function generateSimpleParamHtml(param) {
    const inputType = param.type === 'integer' || param.type === 'float' ? 'number' : 'text';
    const step = param.type === 'float' ? '0.001' : param.step || '1';
    return `
        <div class="col-md-3">
            <label class="form-label">${param.display_name}</label>
            <input type="${inputType}" class="form-control" value="${param.default}"
                   data-indicator-param="${param.name}" step="${step}"
                   placeholder="${param.description || ''}">
        </div>
    `;
}

// ============================================================================
// INDICATOR CARD GENERATION
// ============================================================================

/**
 * Create an indicator card HTML with all fields and parameters.
 *
 * @param {Object} indicator - Indicator configuration object
 * @param {number} index - Card index
 * @param {string} indicatorType - 'signal', 'trend', or 'all'
 * @returns {string} HTML string for the indicator card
 */
function createIndicatorCardHtml(indicator, index, indicatorType = 'all') {
    const params = indicator.parameters || {};
    const indicatorClass = indicator.indicator_class || '';
    const typeLabel = indicatorType === 'trend' ? '🔀 Trend' :
                      indicatorType === 'signal' ? '📊 Signal' : '';
    const typeBadge = typeLabel ? `<span class="badge bg-secondary ms-2">${typeLabel}</span>` : '';

    return `
        <div class="indicator-card" data-indicator-index="${index}" data-indicator-type="${indicatorType}">
            <div class="indicator-card-header" onclick="toggleIndicatorCard(${index})">
                <span class="indicator-card-title">
                    <i class="fas fa-chevron-right collapse-icon" id="collapse-icon-${index}"></i>
                    <span id="indicator-title-${index}">${indicator.name || 'New Indicator'}</span>
                    ${typeBadge}
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
                               data-indicator-field="name"
                               oninput="updateIndicatorTitle(${index}, this.value)"
                               onchange="refreshBarIndicatorDropdowns()">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Indicator Class</label>
                        <select class="form-select" data-indicator-field="indicator_class"
                                onchange="updateIndicatorParams(${index}, this.value)">
                            ${generateIndicatorClassOptions(indicatorClass, indicatorType)}
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Aggregation Config</label>
                        <input type="text" class="form-control" value="${indicator.agg_config || '1m-normal'}"
                               data-indicator-field="agg_config" placeholder="e.g. 1m-normal, 5m-heiken">
                    </div>
                </div>
                <div class="row g-2 mt-2" id="indicator-params-${index}">
                    ${renderIndicatorParamsFromValues(params, index, indicatorType)}
                </div>
            </div>
        </div>
    `;
}

/**
 * Create a new indicator object with defaults.
 *
 * @param {string} indicatorType - 'signal' or 'trend'
 * @returns {Object} New indicator configuration object
 */
function createNewIndicator(indicatorType = 'signal') {
    return {
        name: `new_${indicatorType}_indicator`,
        indicator_class: '',
        type: 'Indicator',
        function: '',
        agg_config: '1m-normal',
        calc_on_pip: false,
        parameters: {},
        indicator_type: indicatorType  // Mark the intended type
    };
}

// ============================================================================
// INDICATOR TYPE UTILITIES
// ============================================================================

/**
 * Get the indicator type for a given class name.
 *
 * @param {string} className - The indicator class name
 * @returns {string} 'signal', 'trend', or 'unknown'
 */
function getIndicatorTypeForClass(className) {
    if (IndicatorStore.signal[className]) {
        return 'signal';
    }
    if (IndicatorStore.trend[className]) {
        return 'trend';
    }
    // Check in 'all' store as fallback
    const schema = IndicatorStore.all[className];
    if (schema && schema.indicator_type) {
        return schema.indicator_type;
    }
    return 'unknown';
}

/**
 * Check if an indicator class is of a specific type.
 *
 * @param {string} className - The indicator class name
 * @param {string} expectedType - 'signal' or 'trend'
 * @returns {boolean} True if the class matches the expected type
 */
function isIndicatorType(className, expectedType) {
    return getIndicatorTypeForClass(className) === expectedType;
}

/**
 * Filter a list of indicator definitions by type.
 *
 * @param {Array} indicators - Array of indicator definition objects
 * @param {string} indicatorType - 'signal', 'trend', or 'all'
 * @returns {Array} Filtered array of indicators
 */
function filterIndicatorsByType(indicators, indicatorType) {
    if (indicatorType === 'all') {
        return indicators;
    }
    return indicators.filter(ind => {
        const classType = getIndicatorTypeForClass(ind.indicator_class);
        return classType === indicatorType;
    });
}

// ============================================================================
// TWO-BUTTON UI SUPPORT
// ============================================================================

/**
 * Generate HTML for the two-button indicator addition UI.
 * Creates "Add Signal Indicator" and "Add Trend Indicator" buttons.
 *
 * @param {string} signalCallback - JavaScript function name for adding signal indicator
 * @param {string} trendCallback - JavaScript function name for adding trend indicator
 * @returns {string} HTML string for the button group
 */
function generateIndicatorButtonsHtml(signalCallback = 'addSignalIndicator', trendCallback = 'addTrendIndicator') {
    return `
        <div class="btn-group" role="group" aria-label="Add indicator buttons">
            <button type="button" class="btn btn-primary" onclick="${signalCallback}()">
                <i class="fas fa-plus me-1"></i>Add Signal Indicator
            </button>
            <button type="button" class="btn btn-outline-secondary" onclick="${trendCallback}()">
                <i class="fas fa-plus me-1"></i>Add Trend Indicator
            </button>
        </div>
    `;
}

/**
 * Replace the old single "Add Indicator" button with the two-button UI.
 * Call this after page load to upgrade existing UIs.
 *
 * @param {string} oldButtonId - ID of the old button to replace
 * @param {string} signalCallback - JavaScript function name for adding signal indicator
 * @param {string} trendCallback - JavaScript function name for adding trend indicator
 */
function upgradeToTwoButtonUI(oldButtonId, signalCallback, trendCallback) {
    const oldButton = document.getElementById(oldButtonId);
    if (oldButton) {
        const newButtonsHtml = generateIndicatorButtonsHtml(signalCallback, trendCallback);
        oldButton.insertAdjacentHTML('afterend', newButtonsHtml);
        oldButton.remove();
    }
}

// ============================================================================
// DATA COLLECTION UTILITIES
// ============================================================================

/**
 * Collect parameter data from an indicator card.
 * Handles all parameter types including lists and choices.
 *
 * @param {HTMLElement} card - The indicator card element
 * @returns {Object} Object with parameter name-value pairs
 */
function collectIndicatorParams(card) {
    const parameters = {};
    const paramInputs = card.querySelectorAll('[data-indicator-param]');

    paramInputs.forEach(input => {
        const paramName = input.dataset.indicatorParam;
        const paramType = input.dataset.paramType;

        if (paramType === 'list') {
            const listboxType = input.dataset.listboxType;
            if (listboxType === 'selected') {
                // Dual listbox - get all options from selected listbox
                parameters[paramName] = Array.from(input.options).map(opt => opt.value);
            } else if (!listboxType) {
                // Comma-separated list input
                const listValue = input.value.trim();
                parameters[paramName] = listValue ? listValue.split(',').map(v => v.trim()) : [];
            }
        } else if (input.tagName === 'SELECT') {
            parameters[paramName] = input.value;
        } else {
            const paramValue = input.type === 'number' ? parseFloat(input.value) : input.value;
            parameters[paramName] = paramValue;
        }
    });

    return parameters;
}

/**
 * Collect full indicator data from a card.
 *
 * @param {HTMLElement} card - The indicator card element
 * @returns {Object} Complete indicator configuration object
 */
function collectIndicatorData(card) {
    const nameInput = card.querySelector('[data-indicator-field="name"]');
    const classSelect = card.querySelector('[data-indicator-field="indicator_class"]');
    const aggInput = card.querySelector('[data-indicator-field="agg_config"]');

    return {
        name: nameInput ? nameInput.value : '',
        indicator_class: classSelect ? classSelect.value : '',
        type: 'Indicator',
        agg_config: aggInput ? aggInput.value : '1m-normal',
        calc_on_pip: false,
        parameters: collectIndicatorParams(card)
    };
}

/**
 * Collect all indicators from the indicators container.
 *
 * @param {string} containerId - ID of the indicators container
 * @returns {Array} Array of indicator configuration objects
 */
function collectAllIndicators(containerId = 'indicatorsContainer') {
    const container = document.getElementById(containerId);
    if (!container) return [];

    const indicators = [];
    const cards = container.querySelectorAll('.indicator-card');

    cards.forEach(card => {
        const data = collectIndicatorData(card);
        if (data.name) {
            indicators.push(data);
        }
    });

    return indicators;
}

// ============================================================================
// EXPORTS (for module usage if needed)
// ============================================================================

// Make functions globally available
if (typeof window !== 'undefined') {
    window.IndicatorFormHandler = {
        // Store access
        IndicatorStore,
        getIndicatorClasses,

        // Loading functions
        loadAllIndicatorClasses,
        loadSignalIndicatorClasses,
        loadTrendIndicatorClasses,
        loadAllIndicatorTypes,

        // Dropdown generation
        generateIndicatorClassOptions,
        generateSignalIndicatorClassOptions,
        generateTrendIndicatorClassOptions,

        // Form generation
        renderIndicatorParamsFromValues,
        generateIndicatorParamsFromSchema,
        generateParamInputHtml,

        // Card generation
        createIndicatorCardHtml,
        createNewIndicator,

        // Type utilities
        getIndicatorTypeForClass,
        isIndicatorType,
        filterIndicatorsByType,

        // Two-button UI
        generateIndicatorButtonsHtml,
        upgradeToTwoButtonUI,

        // Data collection
        collectIndicatorParams,
        collectIndicatorData,
        collectAllIndicators
    };
}
