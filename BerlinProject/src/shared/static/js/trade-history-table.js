/**
 * Trade History Table Component
 *
 * Reusable trade history table with:
 * - P&L toggle (percent/dollars/both)
 * - Details button with chart zoom
 * - Timezone support
 * - Dark/light theme support
 *
 * Used by both stock_analysis_ui (Card Details) and visualization_apps (Replay).
 */

/**
 * TradeHistoryTable - Renders and manages a trade history table
 */
class TradeHistoryTable {
    /**
     * Create a TradeHistoryTable instance
     * @param {Object} options - Configuration options
     * @param {string} options.tableBodyId - ID of the table body element
     * @param {string} options.pnlToggleId - ID of the P&L display mode select element
     * @param {string} options.timezoneSelectId - ID of the timezone select element
     * @param {string} options.theme - 'dark' or 'light' (default: 'light')
     * @param {Function} options.onDetailsClick - Callback when Details button is clicked
     * @param {Object} options.chartsRegistry - Registry of charts for synchronization
     */
    constructor(options = {}) {
        this.tableBodyId = options.tableBodyId || 'tradeHistoryTable';
        this.pnlToggleId = options.pnlToggleId || 'pnlDisplayMode';
        this.timezoneSelectId = options.timezoneSelectId || 'timezoneSelect';
        this.theme = options.theme || 'light';
        this.onDetailsClick = options.onDetailsClick || null;
        this.chartsRegistry = options.chartsRegistry || window.indicatorCharts || {};

        // Data storage
        this.trades = [];
        this.tradeDetails = {};
        this.currentTimezone = 'America/New_York';
        this.pnlDisplayMode = 'both';

        // Bind event handlers
        this._bindEvents();
    }

    /**
     * Bind event handlers for P&L toggle and timezone changes
     */
    _bindEvents() {
        // P&L display mode toggle
        const pnlToggle = document.getElementById(this.pnlToggleId);
        if (pnlToggle) {
            pnlToggle.addEventListener('change', (e) => {
                this.pnlDisplayMode = e.target.value;
                this.updatePnLDisplay();
            });
        }

        // Timezone change
        const timezoneSelect = document.getElementById(this.timezoneSelectId);
        if (timezoneSelect) {
            timezoneSelect.addEventListener('change', (e) => {
                this.currentTimezone = e.target.value;
                this.render(this.trades, this.tradeDetails);
            });
        }
    }

    /**
     * Format a timestamp in the selected timezone
     * @param {number} timestamp - Timestamp in milliseconds
     * @returns {string} Formatted date/time string
     */
    formatDateTime(timestamp) {
        // Use timezone-utils if available, otherwise fallback
        if (typeof formatDateTimeInTimezone === 'function') {
            return formatDateTimeInTimezone(timestamp, this.currentTimezone, {
                timeZone: this.currentTimezone,
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            });
        }

        // Fallback formatting
        const date = new Date(timestamp);
        return date.toLocaleString('en-US', {
            timeZone: this.currentTimezone,
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    }

    /**
     * Render the trade history table
     * @param {Array} trades - Array of trade objects
     * @param {Object} tradeDetails - Object mapping timestamp -> trade details
     */
    render(trades, tradeDetails = {}) {
        this.trades = trades || [];
        this.tradeDetails = tradeDetails || {};

        const tableBody = document.getElementById(this.tableBodyId);
        if (!tableBody) {
            console.warn(`TradeHistoryTable: Element #${this.tableBodyId} not found`);
            return;
        }

        if (!this.trades || this.trades.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="10" class="text-center text-muted">No trades to display</td>
                </tr>
            `;
            return;
        }

        // Track cumulative P&L
        let cumulativePnLPct = 0;
        let cumulativePnLDollars = 0;
        let lastEntryPrice = 0;
        let lastPositionSize = 0;

        const rows = this.trades.map((trade, index) => {
            // Track entry price/size for dollar P&L calculation
            if (trade.type === 'buy') {
                lastEntryPrice = trade.price || 0;
                lastPositionSize = trade.size || trade.quantity || 0;
            }

            // Get P&L values
            let pnlPct = trade.pnl || 0;
            let pnlDollars = trade.pnl_dollars || 0;

            // Calculate dollar P&L if not provided
            if (trade.type === 'sell' && lastEntryPrice > 0 && !trade.pnl_dollars) {
                pnlDollars = lastPositionSize * ((trade.price || 0) - lastEntryPrice);
            }

            // Update cumulative
            if (trade.type === 'sell') {
                cumulativePnLPct += pnlPct;
                cumulativePnLDollars += pnlDollars;
            }

            // CSS classes for P&L coloring
            const pnlPctClass = pnlPct > 0 ? 'text-success' : (pnlPct < 0 ? 'text-danger' : '');
            const pnlDollarsClass = pnlDollars > 0 ? 'text-success' : (pnlDollars < 0 ? 'text-danger' : '');
            const cumPctClass = cumulativePnLPct >= 0 ? 'text-success' : 'text-danger';
            const cumDollarsClass = cumulativePnLDollars >= 0 ? 'text-success' : 'text-danger';

            // Format date/time
            const dateTimeStr = this.formatDateTime(trade.timestamp);

            // Format P&L values (show dash for entry trades)
            const pnlPctDisplay = trade.type === 'sell' ? `${pnlPct.toFixed(2)}%` : '-';
            const pnlDollarsDisplay = trade.type === 'sell' ? `$${pnlDollars.toFixed(2)}` : '-';
            const cumPctDisplay = trade.type === 'sell' ? `${cumulativePnLPct.toFixed(2)}%` : '-';
            const cumDollarsDisplay = trade.type === 'sell' ? `$${cumulativePnLDollars.toFixed(2)}` : '-';

            // Badge colors based on theme
            const buyBadgeClass = this.theme === 'dark' ? 'bg-success' : 'bg-success';
            const sellBadgeClass = this.theme === 'dark' ? 'bg-danger' : 'bg-danger';

            return `
                <tr data-timestamp="${trade.timestamp}">
                    <td class="small">${dateTimeStr}</td>
                    <td><span class="badge ${trade.type === 'buy' ? buyBadgeClass : sellBadgeClass}">${trade.type}</span></td>
                    <td>$${(trade.price || 0).toFixed(2)}</td>
                    <td>${trade.size || trade.quantity || 0}</td>
                    <td class="pnl-col-pct ${pnlPctClass}">${pnlPctDisplay}</td>
                    <td class="pnl-col-dollars ${pnlDollarsClass}">${pnlDollarsDisplay}</td>
                    <td class="pnl-col-pct ${cumPctClass}">${cumPctDisplay}</td>
                    <td class="pnl-col-dollars ${cumDollarsClass}">${cumDollarsDisplay}</td>
                    <td class="small">${trade.reason || '-'}</td>
                    <td><button class="btn btn-sm btn-outline-primary details-btn" data-timestamp="${trade.timestamp}">Details</button></td>
                </tr>
            `;
        }).join('');

        tableBody.innerHTML = rows;

        // Bind details button click handlers
        this._bindDetailsButtons();

        // Apply current P&L display mode
        this.updatePnLDisplay();

        console.log(`TradeHistoryTable: Rendered ${this.trades.length} trades`);
    }

    /**
     * Bind click handlers to all Details buttons
     */
    _bindDetailsButtons() {
        const tableBody = document.getElementById(this.tableBodyId);
        if (!tableBody) return;

        tableBody.querySelectorAll('.details-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const timestamp = parseInt(e.target.dataset.timestamp);
                this.showTradeDetails(timestamp);
            });
        });
    }

    /**
     * Show trade details modal and zoom charts
     * @param {number} timestamp - Trade timestamp in milliseconds
     */
    showTradeDetails(timestamp) {
        const details = this.tradeDetails[timestamp];

        // Zoom all charts to trade timestamp
        this._zoomChartsToTrade(timestamp);

        // Call custom handler if provided
        if (this.onDetailsClick) {
            this.onDetailsClick(timestamp, details);
            return;
        }

        // Default modal behavior
        if (!details) {
            console.warn(`No trade details available for timestamp ${timestamp}`);
            return;
        }

        this._showDetailsModal(details);
    }

    /**
     * Zoom all charts to center on a trade timestamp
     * @param {number} timestamp - Trade timestamp in milliseconds
     */
    _zoomChartsToTrade(timestamp) {
        // Calculate zoom window (5 minutes on each side)
        const zoomPadding = 5 * 60 * 1000; // 5 minutes
        const min = timestamp - zoomPadding;
        const max = timestamp + zoomPadding;

        // Use global sync function if available
        if (typeof window.syncAllChartsFromDetails === 'function') {
            window.syncAllChartsFromDetails(min, max);
            return;
        }

        // Fallback: manually sync charts
        this._syncAllChartsFromDetails(min, max);
    }

    /**
     * Sync all charts to a specific time range
     * @param {number} min - Start of zoom window in ms
     * @param {number} max - End of zoom window in ms
     */
    _syncAllChartsFromDetails(min, max) {
        // Prevent recursion
        if (window.syncInProgress) {
            console.log('Sync in progress, forcing zoom for trade details');
        }
        window.syncInProgress = true;

        try {
            let syncedCount = 0;
            Object.values(this.chartsRegistry).forEach(chart => {
                if (chart && chart.xAxis && chart.xAxis[0]) {
                    chart.xAxis[0].setExtremes(min, max, true, false);
                    syncedCount++;
                }
            });
            console.log(`Zoomed ${syncedCount} charts to trade timestamp`);
        } finally {
            setTimeout(() => {
                window.syncInProgress = false;
            }, 50);
        }
    }

    /**
     * Show the trade details modal
     * @param {Object} details - Trade details object
     */
    _showDetailsModal(details) {
        // Build modal content
        let content = `<div class="trade-details-content">`;
        content += `<h5 class="mb-3">${details.action || 'Trade'}</h5>`;
        content += `<p><strong>Date/Time:</strong> ${details.datetime || 'N/A'}</p>`;

        if (details.type === 'entry') {
            content += `<p><strong>Entry Price:</strong> $${(details.price || 0).toFixed(2)}</p>`;
            content += `<p><strong>Position Size:</strong> ${details.position_size || 'N/A'}</p>`;

            // Trigger info
            if (details.trigger_info) {
                content += `<hr><h6>Trigger Reason</h6>`;
                content += `<p><strong>Trigger Bar:</strong> ${details.trigger_info.bar_name || 'N/A'}</p>`;
                content += `<p><strong>Bar Score:</strong> ${(details.trigger_info.bar_score || 0).toFixed(4)} >= ${(details.trigger_info.threshold || 0).toFixed(4)}</p>`;
            }

            // Exit targets
            content += `<hr><h6>Exit Targets</h6>`;
            content += `<p><strong>Stop Loss:</strong> $${(details.stop_loss || 0).toFixed(2)} (${((details.stop_loss_pct || 0) * 100).toFixed(2)}% below entry)</p>`;

            if (details.take_profit_type === 'dollars') {
                content += `<p><strong>Take Profit:</strong> $${(details.take_profit || 0).toFixed(2)} <span class="badge bg-info">$${(details.take_profit_dollars || 0).toFixed(2)} target</span></p>`;
            } else {
                content += `<p><strong>Take Profit:</strong> $${(details.take_profit || 0).toFixed(2)} (${((details.take_profit_pct || 0) * 100).toFixed(2)}% above entry)</p>`;
            }

            if (details.trailing_stop_loss) {
                content += `<p><strong>Trailing Stop:</strong> $${(details.trailing_stop_price || 0).toFixed(2)}</p>`;
                content += `<p class="small text-muted">Distance: ${((details.trailing_stop_distance_pct || 0) * 100).toFixed(2)}%, Activation: ${((details.trailing_stop_activation_pct || 0) * 100).toFixed(2)}%</p>`;
            }
        } else {
            // Exit trade details
            content += `<p><strong>Entry Price:</strong> $${(details.entry_price || 0).toFixed(2)}</p>`;
            content += `<p><strong>Exit Price:</strong> $${(details.exit_price || 0).toFixed(2)}</p>`;
            content += `<p><strong>Position Size:</strong> ${details.position_size || 'N/A'}</p>`;

            const pnlDollars = details.pnl_dollars !== undefined ? details.pnl_dollars :
                (details.position_size && details.exit_price && details.entry_price ?
                    details.position_size * (details.exit_price - details.entry_price) : 0);
            const pnlClass = (details.pnl_pct || 0) >= 0 ? 'text-success' : 'text-danger';
            content += `<p><strong>P&L:</strong> <span class="${pnlClass}">${(details.pnl_pct || 0).toFixed(2)}% ($${pnlDollars.toFixed(2)})</span></p>`;

            // Trigger info for exit
            if (details.trigger_info) {
                content += `<hr><h6>Exit Reason</h6>`;
                content += `<p><strong>Reason:</strong> ${details.trigger_info.reason || 'N/A'}</p>`;
                if (details.trigger_info.bar_name) {
                    content += `<p><strong>Trigger Bar:</strong> ${details.trigger_info.bar_name}</p>`;
                    content += `<p><strong>Bar Score:</strong> ${(details.trigger_info.bar_score || 0).toFixed(4)} >= ${(details.trigger_info.threshold || 0).toFixed(4)}</p>`;
                }
                if (details.trigger_info.trigger_price) {
                    content += `<p><strong>Trigger Price:</strong> $${(details.trigger_info.trigger_price || 0).toFixed(2)}</p>`;
                }
            }
        }

        // Bar scores at trade time
        if (details.bar_scores && Object.keys(details.bar_scores).length > 0) {
            content += `<hr><h6>Bar Scores at Trade</h6>`;
            content += `<table class="table table-sm table-bordered"><tbody>`;
            for (const [barName, score] of Object.entries(details.bar_scores)) {
                content += `<tr><td>${barName}</td><td>${(score || 0).toFixed(4)}</td></tr>`;
            }
            content += `</tbody></table>`;
        }

        // Indicator values at trade time
        if (details.indicators && Object.keys(details.indicators).length > 0) {
            content += `<hr><h6>Indicator Values at Trade</h6>`;
            content += `<table class="table table-sm table-bordered"><tbody>`;
            for (const [indName, value] of Object.entries(details.indicators)) {
                const displayValue = typeof value === 'number' ? value.toFixed(4) : value;
                content += `<tr><td>${indName}</td><td>${displayValue}</td></tr>`;
            }
            content += `</tbody></table>`;
        }

        content += `</div>`;

        // Update modal content and show
        const modalContent = document.getElementById('tradeDetailsContent');
        if (modalContent) {
            modalContent.innerHTML = content;

            // Show modal using Bootstrap
            const modal = document.getElementById('tradeDetailsModal');
            if (modal && typeof bootstrap !== 'undefined') {
                const bsModal = new bootstrap.Modal(modal);
                bsModal.show();
            }
        }
    }

    /**
     * Update P&L column visibility based on display mode
     */
    updatePnLDisplay() {
        const mode = this.pnlDisplayMode;

        document.querySelectorAll('.pnl-col-pct').forEach(col => {
            col.style.display = (mode === 'percent' || mode === 'both') ? '' : 'none';
        });

        document.querySelectorAll('.pnl-col-dollars').forEach(col => {
            col.style.display = (mode === 'dollars' || mode === 'both') ? '' : 'none';
        });
    }

    /**
     * Set the theme (affects badge colors)
     * @param {string} theme - 'dark' or 'light'
     */
    setTheme(theme) {
        this.theme = theme;
        // Re-render if we have data
        if (this.trades && this.trades.length > 0) {
            this.render(this.trades, this.tradeDetails);
        }
    }

    /**
     * Set the charts registry for synchronization
     * @param {Object} registry - Charts registry object
     */
    setChartsRegistry(registry) {
        this.chartsRegistry = registry;
    }

    /**
     * Clear the table
     */
    clear() {
        this.trades = [];
        this.tradeDetails = {};

        const tableBody = document.getElementById(this.tableBodyId);
        if (tableBody) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="10" class="text-center text-muted">No trades to display</td>
                </tr>
            `;
        }
    }
}

// Export for use in other scripts
window.TradeHistoryTable = TradeHistoryTable;
