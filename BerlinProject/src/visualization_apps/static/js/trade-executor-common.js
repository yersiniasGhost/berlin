/**
 * Trade Executor Common Functions
 * Shared functionality for Trade Executor forms across all visualization apps
 */

/**
 * Toggle take profit input visibility based on selected type
 */
function toggleTakeProfitInputs() {
    const takeProfitType = document.getElementById('takeProfitType');
    const pctContainer = document.getElementById('takeProfitPctContainer');
    const dollarsContainer = document.getElementById('takeProfitDollarsContainer');

    if (!takeProfitType || !pctContainer || !dollarsContainer) {
        return; // Elements not present on this page
    }

    if (takeProfitType.value === 'percent') {
        pctContainer.style.display = '';
        dollarsContainer.style.display = 'none';
    } else {
        pctContainer.style.display = 'none';
        dollarsContainer.style.display = '';
    }
}

/**
 * Load Trade Executor configuration into form fields
 * @param {Object} tradeExecutor - Trade executor configuration object
 */
function loadTradeExecutorForm(tradeExecutor) {
    if (!tradeExecutor) return;

    // Position settings
    const positionSize = document.getElementById('positionSize');
    const stopLoss = document.getElementById('stopLoss');
    const takeProfit = document.getElementById('takeProfit');

    if (positionSize) positionSize.value = tradeExecutor.default_position_size || 100;
    if (stopLoss) stopLoss.value = tradeExecutor.stop_loss_pct || 0.02;
    if (takeProfit) takeProfit.value = tradeExecutor.take_profit_pct || 0.04;

    // Take profit type and dollar amount
    const takeProfitType = document.getElementById('takeProfitType');
    const takeProfitDollars = document.getElementById('takeProfitDollars');

    if (takeProfitType) {
        takeProfitType.value = tradeExecutor.take_profit_type || 'percent';
    }
    if (takeProfitDollars) {
        takeProfitDollars.value = tradeExecutor.take_profit_dollars || 0;
    }
    toggleTakeProfitInputs();

    // Trailing stop settings
    const trailingStopEnabled = document.getElementById('trailingStopEnabled');
    const trailingDistance = document.getElementById('trailingDistance');
    const trailingActivation = document.getElementById('trailingActivation');

    if (trailingStopEnabled) trailingStopEnabled.checked = tradeExecutor.trailing_stop_loss || false;
    if (trailingDistance) trailingDistance.value = tradeExecutor.trailing_stop_distance_pct || 0.01;
    if (trailingActivation) trailingActivation.value = tradeExecutor.trailing_stop_activation_pct || 0.005;

    // Behavior
    const ignoreBearSignals = document.getElementById('ignoreBearSignals');
    if (ignoreBearSignals) ignoreBearSignals.checked = tradeExecutor.ignore_bear_signals || false;
}

/**
 * Collect Trade Executor configuration from form fields
 * @returns {Object} Trade executor configuration object
 */
function collectTradeExecutorForm() {
    return {
        default_position_size: parseFloat(document.getElementById('positionSize')?.value) || 100,
        stop_loss_pct: parseFloat(document.getElementById('stopLoss')?.value) || 0.02,
        take_profit_pct: parseFloat(document.getElementById('takeProfit')?.value) || 0.04,
        take_profit_type: document.getElementById('takeProfitType')?.value || 'percent',
        take_profit_dollars: parseFloat(document.getElementById('takeProfitDollars')?.value) || 0,
        trailing_stop_loss: document.getElementById('trailingStopEnabled')?.checked || false,
        trailing_stop_distance_pct: parseFloat(document.getElementById('trailingDistance')?.value) || 0.01,
        trailing_stop_activation_pct: parseFloat(document.getElementById('trailingActivation')?.value) || 0.005,
        ignore_bear_signals: document.getElementById('ignoreBearSignals')?.checked || false
    };
}
