/**
 * Shared Data Configuration Utilities
 * Handles ticker dropdown population and date range display
 * Used by: Optimizer, Replay, Indicator tools
 */

// Store ticker info globally for all components
window.availableTickersCache = null;

/**
 * Load available tickers with date ranges from backend
 * @param {string} apiEndpoint - The API endpoint to fetch tickers (default: /replay/api/get_available_tickers)
 * @returns {Promise<Object>} - Object with tickers array and default_ticker
 */
async function loadAvailableTickers(apiEndpoint = '/replay/api/get_available_tickers') {
    // Return cached data if available
    if (window.availableTickersCache) {
        return window.availableTickersCache;
    }

    try {
        const response = await fetch(apiEndpoint);
        const result = await response.json();

        if (result.success) {
            window.availableTickersCache = {
                tickers: result.tickers,
                default_ticker: result.default_ticker
            };
            return window.availableTickersCache;
        } else {
            console.error('Failed to load tickers:', result.error);
            return { tickers: [], default_ticker: 'NVDA' };
        }
    } catch (error) {
        console.error('Error loading tickers:', error);
        return { tickers: [], default_ticker: 'NVDA' };
    }
}

/**
 * Populate a ticker dropdown with available tickers
 * @param {string} selectId - The ID of the select element
 * @param {string} dateRangeId - The ID of the date range display element (optional)
 * @param {string} defaultTicker - Default ticker to select (optional)
 */
async function populateTickerDropdown(selectId, dateRangeId = null, defaultTicker = null) {
    const tickerSelect = document.getElementById(selectId);
    if (!tickerSelect) return;

    const data = await loadAvailableTickers();
    const tickers = data.tickers;
    const defaultVal = defaultTicker || data.default_ticker;

    tickerSelect.innerHTML = '';

    // Add tickers with data first
    const tickersWithData = tickers.filter(t => t.has_data);
    const tickersWithoutData = tickers.filter(t => !t.has_data);

    if (tickersWithData.length > 0) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = 'Available Data';
        tickersWithData.forEach(t => {
            const option = document.createElement('option');
            option.value = t.ticker;
            option.textContent = t.ticker;  // Just show ticker symbol
            option.dataset.startDate = t.start_date;
            option.dataset.endDate = t.end_date;
            if (t.ticker === defaultVal) {
                option.selected = true;
            }
            optgroup.appendChild(option);
        });
        tickerSelect.appendChild(optgroup);
    }

    if (tickersWithoutData.length > 0) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = 'No Data Available';
        tickersWithoutData.forEach(t => {
            const option = document.createElement('option');
            option.value = t.ticker;
            option.textContent = t.ticker;  // Just show ticker symbol
            option.disabled = true;
            optgroup.appendChild(option);
        });
        tickerSelect.appendChild(optgroup);
    }

    // Update date range display
    if (dateRangeId) {
        updateTickerDateRange(selectId, dateRangeId);
    }

    // Add change listener for date range updates
    if (dateRangeId) {
        tickerSelect.addEventListener('change', () => updateTickerDateRange(selectId, dateRangeId));
    }
}

/**
 * Update the date range display for a ticker
 * @param {string} selectId - The ID of the select element
 * @param {string} dateRangeId - The ID of the date range display element
 */
function updateTickerDateRange(selectId, dateRangeId) {
    const tickerSelect = document.getElementById(selectId);
    const dateRangeEl = document.getElementById(dateRangeId);
    if (!tickerSelect || !dateRangeEl) return;

    const ticker = tickerSelect.value;
    const data = window.availableTickersCache;
    if (!data) return;

    const tickerInfo = data.tickers.find(t => t.ticker === ticker);
    if (tickerInfo && tickerInfo.has_data) {
        // Format dates more compactly (MM/DD/YY)
        const startParts = tickerInfo.start_date.split('-');
        const endParts = tickerInfo.end_date.split('-');
        const startFormatted = `${startParts[1]}/${startParts[2]}/${startParts[0].slice(2)}`;
        const endFormatted = `${endParts[1]}/${endParts[2]}/${endParts[0].slice(2)}`;
        dateRangeEl.textContent = `${startFormatted} - ${endFormatted}`;
        dateRangeEl.classList.remove('text-danger');
        dateRangeEl.classList.add('text-muted');
    } else {
        dateRangeEl.textContent = 'No data';
        dateRangeEl.classList.remove('text-muted');
        dateRangeEl.classList.add('text-danger');
    }
}

/**
 * Get ticker info by symbol
 * @param {string} ticker - The ticker symbol
 * @returns {Object|null} - Ticker info object or null
 */
function getTickerInfo(ticker) {
    const data = window.availableTickersCache;
    if (!data) return null;
    return data.tickers.find(t => t.ticker === ticker);
}

/**
 * Initialize all ticker dropdowns on the page
 * Finds all elements with class 'data-ticker-select' and populates them
 */
async function initializeAllTickerDropdowns() {
    const tickerSelects = document.querySelectorAll('.data-ticker-select');

    // Load tickers once
    await loadAvailableTickers();

    tickerSelects.forEach(select => {
        const selectId = select.id;
        // Derive date range ID from select ID (e.g., dataTicker -> dataTickerDateRange)
        const dateRangeId = selectId + 'DateRange';
        const dateRangeEl = document.getElementById(dateRangeId);

        populateTickerDropdown(selectId, dateRangeEl ? dateRangeId : null);
    });
}

// Auto-initialize on DOMContentLoaded if not already handled
document.addEventListener('DOMContentLoaded', function() {
    // Only auto-init if there are ticker selects with the marker class
    const tickerSelects = document.querySelectorAll('.data-ticker-select');
    if (tickerSelects.length > 0) {
        initializeAllTickerDropdowns();
    }
});
