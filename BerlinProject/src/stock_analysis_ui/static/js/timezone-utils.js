/**
 * Timezone Utilities Module
 * Shared timezone handling for trading UI applications.
 *
 * Provides:
 * - Timezone selection (ET, PT, UTC)
 * - Time formatting in selected timezone
 * - Highcharts timezone configuration
 * - LocalStorage persistence of timezone preference
 *
 * Usage:
 *   1. Include this script in your HTML
 *   2. Add timezone selector HTML (see getTimezoneSelectorHTML())
 *   3. Call initializeTimezone() on page load
 *   4. Use formatTimeInTimezone() for time display
 */

// Current timezone state
window.currentTimezone = window.currentTimezone || 'America/New_York';

// Timezone configurations
const TIMEZONE_CONFIG = {
    'America/New_York': { label: 'ET', name: 'Eastern Time' },
    'America/Los_Angeles': { label: 'PT', name: 'Pacific Time' },
    'UTC': { label: 'UTC', name: 'Coordinated Universal Time' }
};

/**
 * Get the timezone offset in minutes for Highcharts
 * Highcharts uses positive values for west of UTC
 */
function getTimezoneOffset(timezone) {
    try {
        // Create a date and get the actual offset for that timezone
        const date = new Date();
        const options = { timeZone: timezone, timeZoneName: 'shortOffset' };
        const formatter = new Intl.DateTimeFormat('en-US', options);
        const parts = formatter.formatToParts(date);
        const tzPart = parts.find(p => p.type === 'timeZoneName');

        if (tzPart) {
            // Parse offset like "GMT-5" or "GMT+0"
            const match = tzPart.value.match(/GMT([+-]?)(\d+)?/);
            if (match) {
                const sign = match[1] === '+' ? -1 : 1;  // Highcharts uses opposite sign
                const hours = parseInt(match[2] || '0');
                return sign * hours * 60;
            }
        }
    } catch (e) {
        console.warn('Error calculating timezone offset:', e);
    }

    // Fallback offsets (standard time approximations)
    const fallbackOffsets = {
        'America/New_York': 5 * 60,      // ET (UTC-5)
        'America/Los_Angeles': 8 * 60,   // PT (UTC-8)
        'UTC': 0
    };
    return fallbackOffsets[timezone] || 0;
}

/**
 * Format a timestamp in the selected timezone
 * @param {number|string|Date} timestamp - Timestamp (ms, ISO string, or Date)
 * @param {string} timezone - Timezone identifier
 * @param {object} options - Intl.DateTimeFormat options override
 * @returns {string} Formatted time string
 */
function formatTimeInTimezone(timestamp, timezone, options = null) {
    timezone = timezone || window.currentTimezone;

    let date;
    if (typeof timestamp === 'number') {
        date = new Date(timestamp);
    } else if (typeof timestamp === 'string') {
        date = new Date(timestamp);
    } else if (timestamp instanceof Date) {
        date = timestamp;
    } else {
        return '--';
    }

    if (isNaN(date.getTime())) {
        return '--';
    }

    const defaultOptions = {
        timeZone: timezone,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    };

    return date.toLocaleTimeString('en-US', options || defaultOptions);
}

/**
 * Format a timestamp with date and time in the selected timezone
 */
function formatDateTimeInTimezone(timestamp, timezone, options = null) {
    timezone = timezone || window.currentTimezone;

    let date;
    if (typeof timestamp === 'number') {
        date = new Date(timestamp);
    } else if (typeof timestamp === 'string') {
        date = new Date(timestamp);
    } else if (timestamp instanceof Date) {
        date = timestamp;
    } else {
        return '--';
    }

    if (isNaN(date.getTime())) {
        return '--';
    }

    const defaultOptions = {
        timeZone: timezone,
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };

    return date.toLocaleString('en-US', options || defaultOptions);
}

/**
 * Handle timezone selection change
 * @param {string} timezone - New timezone identifier
 * @param {object} options - Callback options
 */
function onTimezoneChange(timezone, options = {}) {
    window.currentTimezone = timezone;
    console.log(`Timezone changed to: ${timezone} (${TIMEZONE_CONFIG[timezone]?.name || timezone})`);

    // Store preference in localStorage
    localStorage.setItem('preferredTimezone', timezone);

    // Update Highcharts global options if Highcharts is available
    if (typeof Highcharts !== 'undefined') {
        Highcharts.setOptions({
            time: {
                timezoneOffset: getTimezoneOffset(timezone)
            }
        });
    }

    // Call custom callback if provided
    if (options.onUpdate && typeof options.onUpdate === 'function') {
        options.onUpdate(timezone);
    }

    // Dispatch custom event for other listeners
    window.dispatchEvent(new CustomEvent('timezoneChanged', {
        detail: { timezone, offset: getTimezoneOffset(timezone) }
    }));
}

/**
 * Initialize timezone settings from localStorage or default
 * @param {string} selectorId - ID of the timezone select element
 * @returns {string} The initialized timezone
 */
function initializeTimezone(selectorId = 'timezoneSelect') {
    const savedTimezone = localStorage.getItem('preferredTimezone');
    if (savedTimezone && TIMEZONE_CONFIG[savedTimezone]) {
        window.currentTimezone = savedTimezone;
    }

    // Update select element if it exists
    const selector = document.getElementById(selectorId);
    if (selector) {
        selector.value = window.currentTimezone;
    }

    // Set Highcharts global timezone if available
    if (typeof Highcharts !== 'undefined') {
        Highcharts.setOptions({
            time: {
                timezoneOffset: getTimezoneOffset(window.currentTimezone)
            }
        });
    }

    console.log(`Timezone initialized: ${window.currentTimezone}`);
    return window.currentTimezone;
}

/**
 * Get HTML for timezone selector dropdown
 * @param {string} selectId - ID for the select element
 * @param {string} onChangeHandler - Name of the change handler function
 * @returns {string} HTML string for the timezone selector
 */
function getTimezoneSelectorHTML(selectId = 'timezoneSelect', onChangeHandler = 'onTimezoneChange') {
    const options = Object.entries(TIMEZONE_CONFIG)
        .map(([tz, config]) => `<option value="${tz}">${config.label}</option>`)
        .join('\n');

    return `
        <div class="timezone-selector">
            <span class="timezone-label">TZ</span>
            <select id="${selectId}" class="timezone-select" onchange="${onChangeHandler}(this.value)">
                ${options}
            </select>
        </div>
    `;
}

/**
 * Get CSS styles for timezone selector
 * @returns {string} CSS string for timezone selector styling
 */
function getTimezoneSelectorCSS() {
    return `
        .timezone-selector {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-left: 1rem;
            padding-left: 1rem;
            border-left: 1px solid #30363d;
        }

        .timezone-label {
            color: #7d8590;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .timezone-select {
            padding: 0.4rem 0.75rem;
            background: #21262d;
            border: 1px solid #30363d;
            color: #e6edf3;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.875rem;
            transition: all 0.2s ease;
        }

        .timezone-select:hover {
            background: #30363d;
            border-color: #484f58;
        }

        .timezone-select:focus {
            outline: none;
            border-color: #58a6ff;
            box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.2);
        }
    `;
}

// Export for module systems (if used)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getTimezoneOffset,
        formatTimeInTimezone,
        formatDateTimeInTimezone,
        onTimezoneChange,
        initializeTimezone,
        getTimezoneSelectorHTML,
        getTimezoneSelectorCSS,
        TIMEZONE_CONFIG
    };
}
