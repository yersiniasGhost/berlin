/**
 * Shared utilities for monitor configuration editing.
 * Used by both optimizer-config.js and replay-config.js
 */

// ============================================================================
// DEFAULT DATA CONFIGURATION - DYNAMIC DATES
// ============================================================================

/**
 * Format a Date object as YYYY-MM-DD string.
 * @param {Date} date - The date to format
 * @returns {string} Date in YYYY-MM-DD format
 */
function formatDateYYYYMMDD(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * Get the default data configuration with dynamic dates.
 * Start date: 2 weeks ago, End date: tomorrow
 * @returns {Object} Default data configuration object
 */
function getDefaultDataConfig() {
    const today = new Date();
    const twoWeeksAgo = new Date(today);
    twoWeeksAgo.setDate(today.getDate() - 14);
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);

    return {
        ticker: "NVDA",
        start_date: formatDateYYYYMMDD(twoWeeksAgo),
        end_date: formatDateYYYYMMDD(tomorrow),
        include_extended_hours: true
    };
}

/**
 * Global default data configuration (computed once on load).
 * Use this constant or call getDefaultDataConfig() for fresh dates.
 */
const DEFAULT_DATA_CONFIG = getDefaultDataConfig();

// ============================================================================
// TREND INDICATOR FIELD PRESERVATION & BUILDING
// ============================================================================

/**
 * Preserves trend indicator fields from original bar config to new bar config.
 * These fields (trend_indicators, trend_logic, trend_threshold) are not yet
 * editable in the UI, so we preserve them when the config is modified.
 *
 * @param {Object} barConfig - The new bar configuration being built
 * @param {Object} originalBarConfig - The original bar configuration to preserve from
 * @returns {Object} The barConfig with trend fields preserved
 */
function preserveTrendIndicatorFields(barConfig, originalBarConfig) {
    if (!originalBarConfig) return barConfig;

    if (originalBarConfig.trend_indicators) {
        barConfig.trend_indicators = originalBarConfig.trend_indicators;
    }
    if (originalBarConfig.trend_logic) {
        barConfig.trend_logic = originalBarConfig.trend_logic;
    }
    if (originalBarConfig.trend_threshold !== undefined) {
        barConfig.trend_threshold = originalBarConfig.trend_threshold;
    }

    return barConfig;
}

/**
 * Builds a complete bar configuration from UI elements and original config.
 *
 * @param {Object} basicConfig - Basic config with type, description, indicators
 * @param {Object} originalBarConfig - Original bar config for preserving non-UI fields
 * @returns {Object} Complete bar configuration
 */
function buildBarConfig(basicConfig, originalBarConfig) {
    const barConfig = { ...basicConfig };
    return preserveTrendIndicatorFields(barConfig, originalBarConfig);
}

// ============================================================================
// TREND INDICATOR UI GENERATION
// ============================================================================

/**
 * Generates HTML for the trend indicators section of a bar card.
 *
 * @param {Object} trendIndicators - The trend_indicators config object
 * @param {string} trendLogic - The trend_logic value ('AND', 'OR', 'AVG')
 * @param {number} trendThreshold - The trend_threshold value
 * @param {Function} generateOptionsFunc - Function to generate indicator name options
 * @returns {string} HTML string for the trend indicators section
 */
function generateTrendIndicatorsSectionHtml(trendIndicators, trendLogic, trendThreshold, generateOptionsFunc) {
    const trendInds = trendIndicators || {};

    let trendIndicatorsHtml = '';
    for (const [indName, config] of Object.entries(trendInds)) {
        const weight = typeof config === 'object' ? (config.weight || 1.0) : config;
        const mode = typeof config === 'object' ? (config.mode || 'soft') : 'soft';

        trendIndicatorsHtml += generateTrendIndicatorRowHtml(indName, weight, mode, generateOptionsFunc);
    }

    return `
        <div class="mt-3 trend-indicators-section">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <label class="form-label mb-0"><strong>Trend Indicators (Gate):</strong></label>
                <div class="d-flex gap-2 align-items-center">
                    <label class="form-label mb-0 small">Logic:</label>
                    <select class="form-select form-select-sm" data-trend-logic style="width: auto;"
                            title="AND: All trends must confirm (min). OR: Any trend confirms (max). AVG: Weighted average using weights.">
                        <option value="AND" ${trendLogic === 'AND' ? 'selected' : ''}>AND (min)</option>
                        <option value="OR" ${trendLogic === 'OR' ? 'selected' : ''}>OR (max)</option>
                        <option value="AVG" ${trendLogic === 'AVG' ? 'selected' : ''}>AVG (weighted)</option>
                    </select>
                    <label class="form-label mb-0 small"
                           title="Gate Threshold: Minimum combined trend gate value required. If gate < threshold, bar score = 0.">
                        Gate Threshold:
                    </label>
                    <input type="number" class="form-control form-control-sm" data-trend-threshold
                           value="${trendThreshold || 0}" step="0.1" min="0" max="1" style="width: 80px;"
                           title="Minimum gate value to pass signals. Example: 0.3 means trend gate must be >= 0.3 or bar score becomes 0.">
                </div>
            </div>
            <!-- Column headers for trend indicator rows -->
            <div class="row g-2 mb-1 text-muted small">
                <div class="col-md-5">Indicator</div>
                <div class="col-md-2" title="Weight: Multiplier for AVG logic. Only affects AVG mode.">Weight (AVG)</div>
                <div class="col-md-3" title="Soft: Continuous 0-1 scaling. Hard: Binary pass/block.">Mode</div>
                <div class="col-md-2"></div>
            </div>
            <div class="trend-indicators-container">
                ${trendIndicatorsHtml}
            </div>
            <button class="btn btn-sm btn-outline-secondary mt-2" onclick="addTrendIndicator(this)">
                <i class="fas fa-plus me-1"></i>Add Trend Indicator
            </button>
        </div>
    `;
}

/**
 * Generates HTML for a single trend indicator row.
 *
 * @param {string} indName - The indicator name
 * @param {number} weight - The weight value
 * @param {string} mode - The mode ('soft' or 'hard')
 * @param {Function} generateOptionsFunc - Function to generate indicator name options
 * @returns {string} HTML string for the trend indicator row
 */
function generateTrendIndicatorRowHtml(indName, weight, mode, generateOptionsFunc) {
    return `
        <div class="row g-2 mb-2 trend-indicator-row">
            <div class="col-md-5">
                <select class="form-select form-select-sm" data-trend-indicator-name>
                    ${generateOptionsFunc(indName)}
                </select>
            </div>
            <div class="col-md-2">
                <input type="number" class="form-control form-control-sm" value="${weight}"
                       data-trend-indicator-weight step="0.1" min="0" max="2"
                       title="Weight for AVG logic. 1.0 = full influence, 0.5 = half. Only used when Logic = AVG.">
            </div>
            <div class="col-md-3">
                <select class="form-select form-select-sm" data-trend-indicator-mode
                        title="Soft: Continuous scaling (trend value 0.5 = 50% signal). Hard: Binary gate (positive = pass, negative = block).">
                    <option value="soft" ${mode === 'soft' ? 'selected' : ''}>Soft (scale)</option>
                    <option value="hard" ${mode === 'hard' ? 'selected' : ''}>Hard (gate)</option>
                </select>
            </div>
            <div class="col-md-2">
                <button class="btn btn-sm btn-danger w-100" onclick="removeTrendIndicator(this)">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `;
}

/**
 * Adds a new trend indicator row to a bar card.
 * Called by onclick handler.
 *
 * @param {HTMLElement} button - The "Add Trend Indicator" button
 */
function addTrendIndicator(button) {
    const barCard = button.closest('.bar-card');
    const container = barCard.querySelector('.trend-indicators-container');

    // Get generateIndicatorNameOptions from the parent scope (varies by page)
    const newRowHtml = generateTrendIndicatorRowHtml('', 1.0, 'soft', generateIndicatorNameOptions);
    container.insertAdjacentHTML('beforeend', newRowHtml);
}

/**
 * Removes a trend indicator row from a bar card.
 * Called by onclick handler.
 *
 * @param {HTMLElement} button - The remove button in the trend indicator row
 */
function removeTrendIndicator(button) {
    const row = button.closest('.trend-indicator-row');
    if (row) {
        row.remove();
    }
}

// ============================================================================
// TREND INDICATOR DATA COLLECTION
// ============================================================================

/**
 * Collects trend indicator data from a bar card's DOM elements.
 *
 * @param {HTMLElement} barCard - The bar card element
 * @returns {Object} Object with trend_indicators, trend_logic, trend_threshold
 */
function collectTrendIndicatorData(barCard) {
    const result = {};

    // Collect trend logic
    const trendLogicSelect = barCard.querySelector('[data-trend-logic]');
    if (trendLogicSelect) {
        result.trend_logic = trendLogicSelect.value;
    }

    // Collect trend threshold
    const trendThresholdInput = barCard.querySelector('[data-trend-threshold]');
    if (trendThresholdInput) {
        result.trend_threshold = parseFloat(trendThresholdInput.value) || 0.0;
    }

    // Collect trend indicators
    const trendIndicators = {};
    const trendRows = barCard.querySelectorAll('.trend-indicator-row');
    trendRows.forEach(row => {
        const nameSelect = row.querySelector('[data-trend-indicator-name]');
        const weightInput = row.querySelector('[data-trend-indicator-weight]');
        const modeSelect = row.querySelector('[data-trend-indicator-mode]');

        if (nameSelect && nameSelect.value) {
            trendIndicators[nameSelect.value] = {
                weight: weightInput ? parseFloat(weightInput.value) || 1.0 : 1.0,
                mode: modeSelect ? modeSelect.value : 'soft'
            };
        }
    });

    if (Object.keys(trendIndicators).length > 0) {
        result.trend_indicators = trendIndicators;
    }

    return result;
}

/**
 * Builds a complete bar configuration including trend indicators from UI.
 * This is an enhanced version of buildBarConfig that collects trend data from DOM.
 *
 * @param {Object} basicConfig - Basic config with type, description, indicators
 * @param {HTMLElement} barCard - The bar card DOM element to collect trend data from
 * @returns {Object} Complete bar configuration with trend indicators
 */
function buildBarConfigFromUI(basicConfig, barCard) {
    const barConfig = { ...basicConfig };

    // Collect trend indicator data from UI
    const trendData = collectTrendIndicatorData(barCard);

    if (trendData.trend_indicators) {
        barConfig.trend_indicators = trendData.trend_indicators;
    }
    if (trendData.trend_logic) {
        barConfig.trend_logic = trendData.trend_logic;
    }
    if (trendData.trend_threshold !== undefined) {
        barConfig.trend_threshold = trendData.trend_threshold;
    }

    return barConfig;
}

// ============================================================================
// SAVE & DOWNLOAD UTILITIES
// ============================================================================

/**
 * Download JSON data as a file.
 *
 * @param {Object} data - The data to download
 * @param {string} filename - The filename for the download
 */
function downloadJsonFile(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Show a notification toast for save operations.
 *
 * @param {string} message - The message to display
 * @param {string} type - The type of notification ('success', 'danger', 'warning', 'info')
 */
function showSaveNotification(message, type = 'info') {
    const toastId = 'save-toast-' + Date.now();
    const iconClass = type === 'success' ? 'check-circle' :
                      type === 'danger' ? 'exclamation-circle' :
                      type === 'warning' ? 'exclamation-triangle' : 'info-circle';

    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${iconClass} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;

    // Create container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }

    toastContainer.insertAdjacentHTML('beforeend', toastHtml);

    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 5000 });
    toast.show();

    // Remove toast element after it's hidden
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

/**
 * Generate a safe filename from a name string.
 *
 * @param {string} name - The name to convert
 * @param {string} suffix - Suffix to add before .json
 * @returns {string} Safe filename with timestamp
 */
function generateSafeFilename(name, suffix = 'monitor') {
    const safeName = (name || suffix)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');
    const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    return `${timestamp}_${safeName}_${suffix}.json`;
}

// ============================================================================
// VALIDATION ERROR DISPLAY
// ============================================================================

/**
 * Display validation errors in a user-friendly format.
 * Each error contains indicator name and specific parameter issues.
 *
 * @param {Array} validationErrors - Array of validation error strings
 * @param {Function} showAlertFn - The showAlert function to use for display
 */
function showValidationErrors(validationErrors, showAlertFn) {
    if (!validationErrors || validationErrors.length === 0) {
        showAlertFn('Configuration validation failed', 'danger');
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
            } else if (line.includes('•')) {
                // Catch any bullet-pointed errors
                errorMessage += `   ${line.trim()}\n`;
            }
        });
    });

    console.error('Validation Errors:', validationErrors);
    showAlertFn(errorMessage, 'danger');
}

/**
 * Handle API response that may contain validation errors.
 * Returns true if validation errors were handled, false otherwise.
 *
 * @param {Object} result - The API response object
 * @param {Function} showAlertFn - The showAlert function to use for display
 * @returns {boolean} True if validation errors were found and handled
 */
function handleValidationErrorResponse(result, showAlertFn) {
    if (result.has_validation_errors && result.validation_errors) {
        showValidationErrors(result.validation_errors, showAlertFn);
        return true;
    }
    return false;
}
