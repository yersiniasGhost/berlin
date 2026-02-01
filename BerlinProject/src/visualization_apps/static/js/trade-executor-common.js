/**
 * Trade Executor Common Functions
 * Shared functionality for Trade Executor forms across all visualization apps
 */

/**
 * Convert decimal to percentage for display (0.02 -> 2)
 * @param {number} decimal - Decimal value (e.g., 0.02)
 * @returns {number} Percentage value (e.g., 2)
 */
function decimalToPercent(decimal) {
    return decimal * 100;
}

/**
 * Convert percentage to decimal for storage (2 -> 0.02)
 * @param {number} percent - Percentage value (e.g., 2)
 * @returns {number} Decimal value (e.g., 0.02)
 */
function percentToDecimal(percent) {
    return percent / 100;
}

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
    const haltAfterTargetSection = document.getElementById('haltAfterTargetSection');

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
        if (haltAfterTargetSection) haltAfterTargetSection.style.display = '';
        updateRisePerShare();
        updateProfitCalculations();
    } else {
        pctContainer.style.display = '';
        dollarsContainer.style.display = 'none';
        if (positionSizeContainer) positionSizeContainer.style.display = 'none';
        if (risePerShareContainer) risePerShareContainer.style.display = 'none';
        if (estimatedPriceSection) estimatedPriceSection.style.display = 'none';
        if (haltAfterTargetSection) haltAfterTargetSection.style.display = 'none';
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
}

/**
 * Calculate and display profit percentage
 * Formula: profit_percent = (take_profit_dollars / position_cost) * 100
 */
function updateProfitPercent() {
    const positionCost = parseFloat(document.getElementById('positionCost')?.value) || 0;
    const takeProfitDollars = parseFloat(document.getElementById('takeProfitDollars')?.value) || 0;
    const profitPercentInput = document.getElementById('profitPercent');

    if (!profitPercentInput) return;

    if (positionCost > 0 && takeProfitDollars > 0) {
        const profitPercent = (takeProfitDollars / positionCost) * 100;
        profitPercentInput.value = profitPercent.toFixed(2);
    } else {
        profitPercentInput.value = '--';
    }
}

/**
 * Handler when Position Size is changed by user
 * Updates: Position Cost, Rise/Share, Profit %
 */
function updateFromPositionSize() {
    const estimatedPrice = parseFloat(document.getElementById('estimatedPrice')?.value) || 0;
    const positionSize = parseFloat(document.getElementById('positionSize')?.value) || 0;
    const positionCostInput = document.getElementById('positionCost');

    // Calculate and update Position Cost from Position Size
    if (positionCostInput && estimatedPrice > 0 && positionSize > 0) {
        const positionCost = estimatedPrice * positionSize;
        positionCostInput.value = positionCost.toFixed(2);
    } else if (positionCostInput) {
        positionCostInput.value = '';
    }

    // Update dependent calculations
    updateRisePerShare();
    updateProfitPercent();
}

/**
 * Handler when Position Cost is changed by user
 * Updates: Position Size, Rise/Share, Profit %
 */
function updateFromPositionCost() {
    const estimatedPrice = parseFloat(document.getElementById('estimatedPrice')?.value) || 0;
    const positionCost = parseFloat(document.getElementById('positionCost')?.value) || 0;
    const positionSizeInput = document.getElementById('positionSize');

    // Calculate and update Position Size from Position Cost
    if (positionSizeInput && estimatedPrice > 0 && positionCost > 0) {
        const positionSize = positionCost / estimatedPrice;
        // Round to whole shares
        positionSizeInput.value = Math.round(positionSize);
    } else if (positionSizeInput) {
        positionSizeInput.value = '';
    }

    // Update dependent calculations
    updateRisePerShare();
    updateProfitPercent();
}

/**
 * Handler when Take Profit Dollars is changed by user
 * Updates: Rise/Share, Profit %
 */
function updateFromTakeProfitDollars() {
    updateRisePerShare();
    updateProfitPercent();
}

/**
 * Handler when Estimated Price is changed by user
 * Recalculates Position Size from Position Cost (keeps Position Cost as the anchor)
 * Updates: Position Size, Rise/Share, Profit %
 */
function updateProfitCalculations() {
    // When estimated price changes, recalculate position size from position cost
    updateFromPositionCost();
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
    // Convert decimal to percentage for display (0.02 -> 2)
    if (stopLoss) stopLoss.value = decimalToPercent(tradeExecutor.stop_loss_pct || 0.02);
    if (takeProfit) takeProfit.value = decimalToPercent(tradeExecutor.take_profit_pct || 0.04);

    // Take profit type and dollar amount
    const takeProfitType = document.getElementById('takeProfitType');
    const takeProfitDollars = document.getElementById('takeProfitDollars');
    const haltAfterTarget = document.getElementById('haltAfterTarget');

    if (takeProfitType) {
        takeProfitType.value = tradeExecutor.take_profit_type || 'percent';
    }
    if (takeProfitDollars) {
        takeProfitDollars.value = tradeExecutor.take_profit_dollars || 0;
    }
    if (haltAfterTarget) {
        haltAfterTarget.checked = tradeExecutor.halt_after_target || false;
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
    // Convert decimal to percentage for display (0.01 -> 1, 0.005 -> 0.5)
    if (trailingDistance) trailingDistance.value = decimalToPercent(tradeExecutor.trailing_stop_distance_pct || 0.01);
    if (trailingActivation) trailingActivation.value = decimalToPercent(tradeExecutor.trailing_stop_activation_pct || 0.005);

    // Behavior
    const ignoreBearSignals = document.getElementById('ignoreBearSignals');
    if (ignoreBearSignals) ignoreBearSignals.checked = tradeExecutor.ignore_bear_signals || false;

    const exitByEndOfDay = document.getElementById('exitByEndOfDay');
    if (exitByEndOfDay) exitByEndOfDay.checked = tradeExecutor.exit_by_end_of_day || false;
}

/**
 * Collect Trade Executor configuration from form fields
 * @returns {Object} Trade executor configuration object
 */
function collectTradeExecutorForm() {
    // Convert user-entered percentages (e.g., 2) to decimals (e.g., 0.02) for storage
    const stopLossPercent = parseFloat(document.getElementById('stopLoss')?.value) || 2;
    const takeProfitPercent = parseFloat(document.getElementById('takeProfit')?.value) || 4;
    const trailingDistancePercent = parseFloat(document.getElementById('trailingDistance')?.value) || 1;
    const trailingActivationPercent = parseFloat(document.getElementById('trailingActivation')?.value) || 0.5;

    const config = {
        default_position_size: parseFloat(document.getElementById('positionSize')?.value) || 100,
        stop_loss_pct: percentToDecimal(stopLossPercent),
        take_profit_pct: percentToDecimal(takeProfitPercent),
        take_profit_type: document.getElementById('takeProfitType')?.value || 'percent',
        take_profit_dollars: parseFloat(document.getElementById('takeProfitDollars')?.value) || 0,
        halt_after_target: document.getElementById('haltAfterTarget')?.checked || false,
        trailing_stop_loss: document.getElementById('trailingStopEnabled')?.checked || false,
        trailing_stop_distance_pct: percentToDecimal(trailingDistancePercent),
        trailing_stop_activation_pct: percentToDecimal(trailingActivationPercent),
        ignore_bear_signals: document.getElementById('ignoreBearSignals')?.checked || false,
        exit_by_end_of_day: document.getElementById('exitByEndOfDay')?.checked || false
    };

    // Include estimated price if provided (optional, for profit calculation reference)
    const estimatedPrice = parseFloat(document.getElementById('estimatedPrice')?.value);
    if (estimatedPrice > 0) {
        config.estimated_price = estimatedPrice;
    }

    return config;
}
