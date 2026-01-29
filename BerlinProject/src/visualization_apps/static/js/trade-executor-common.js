/**
 * Trade Executor Common Functions
 * Shared functionality for Trade Executor forms across all visualization apps
 */

/**
 * Toggle take profit input visibility based on selected type
 * Shows/hides: percentage input, dollar input, position size, rise per share calculation,
 * and the estimated price section with position cost and profit percentage
 */
function toggleTakeProfitInputs() {
    const takeProfitType = document.getElementById('takeProfitType');
    const pctContainer = document.getElementById('takeProfitPctContainer');
    const dollarsContainer = document.getElementById('takeProfitDollarsContainer');
    const positionSizeContainer = document.getElementById('positionSizeContainer');
    const risePerShareContainer = document.getElementById('risePerShareContainer');
    const estimatedPriceSection = document.getElementById('estimatedPriceSection');

    if (!takeProfitType || !pctContainer || !dollarsContainer) {
        return; // Elements not present on this page
    }

    const isDollarMode = takeProfitType.value === 'dollars';

    if (isDollarMode) {
        pctContainer.style.display = 'none';
        dollarsContainer.style.display = '';
        if (positionSizeContainer) positionSizeContainer.style.display = '';
        if (risePerShareContainer) risePerShareContainer.style.display = '';
        if (estimatedPriceSection) estimatedPriceSection.style.display = '';
        updateRisePerShare();
        updateProfitCalculations();
    } else {
        pctContainer.style.display = '';
        dollarsContainer.style.display = 'none';
        if (positionSizeContainer) positionSizeContainer.style.display = 'none';
        if (risePerShareContainer) risePerShareContainer.style.display = 'none';
        if (estimatedPriceSection) estimatedPriceSection.style.display = 'none';
    }
}

/**
 * Calculate and display the required rise per share for dollar-based take profit
 * Formula: rise_per_share = take_profit_dollars / position_size
 */
function updateRisePerShare() {
    const takeProfitDollars = parseFloat(document.getElementById('takeProfitDollars')?.value) || 0;
    const positionSize = parseFloat(document.getElementById('positionSize')?.value) || 0;
    const risePerShareInput = document.getElementById('risePerShare');

    if (!risePerShareInput) return;

    if (positionSize > 0 && takeProfitDollars > 0) {
        const risePerShare = takeProfitDollars / positionSize;
        risePerShareInput.value = risePerShare.toFixed(4);
    } else {
        risePerShareInput.value = '--';
    }

    // Also update profit calculations when position size or dollars change
    updateProfitCalculations();
}

/**
 * Calculate and display position cost and profit percentage based on estimated entry price
 * Formulas:
 *   position_cost = estimated_price * position_size
 *   profit_percent = (take_profit_dollars / position_cost) * 100
 */
function updateProfitCalculations() {
    const estimatedPrice = parseFloat(document.getElementById('estimatedPrice')?.value) || 0;
    const positionSize = parseFloat(document.getElementById('positionSize')?.value) || 0;
    const takeProfitDollars = parseFloat(document.getElementById('takeProfitDollars')?.value) || 0;

    const positionCostInput = document.getElementById('positionCost');
    const profitPercentInput = document.getElementById('profitPercent');

    if (!positionCostInput || !profitPercentInput) return;

    if (estimatedPrice > 0 && positionSize > 0) {
        // Calculate position cost
        const positionCost = estimatedPrice * positionSize;
        positionCostInput.value = positionCost.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });

        // Calculate profit percentage
        if (takeProfitDollars > 0) {
            const profitPercent = (takeProfitDollars / positionCost) * 100;
            profitPercentInput.value = profitPercent.toFixed(2);
        } else {
            profitPercentInput.value = '--';
        }
    } else {
        positionCostInput.value = '--';
        profitPercentInput.value = '--';
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

    // Estimated price (optional, for profit calculation display)
    const estimatedPrice = document.getElementById('estimatedPrice');
    if (estimatedPrice && tradeExecutor.estimated_price) {
        estimatedPrice.value = tradeExecutor.estimated_price;
    }

    toggleTakeProfitInputs();  // Also triggers updateRisePerShare() and updateProfitCalculations() for dollar mode

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
    const config = {
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

    // Include estimated price if provided (optional, for profit calculation reference)
    const estimatedPrice = parseFloat(document.getElementById('estimatedPrice')?.value);
    if (estimatedPrice > 0) {
        config.estimated_price = estimatedPrice;
    }

    return config;
}
