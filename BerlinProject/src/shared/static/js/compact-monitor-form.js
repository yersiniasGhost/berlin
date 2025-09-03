/**
 * Compact Monitor Configuration Form Component
 * Creates a collapsible, organized interface for editing monitor configurations
 */
class CompactMonitorForm {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            showDataConfig: options.showDataConfig || false,
            showRanges: options.showRanges || false,
            showGAHyperparameters: options.showGAHyperparameters || false,
            ...options
        };
        this.monitorConfig = null;
        this.dataConfig = null;
    }

    /**
     * Generate the compact form UI
     */
    generateForm(monitorConfig, dataConfig = null) {
        this.monitorConfig = monitorConfig;
        this.dataConfig = dataConfig;

        if (!this.container) {
            console.error('Container not found for CompactMonitorForm');
            return;
        }

        this.container.innerHTML = this.createFormHTML();
        this.attachEventListeners();
        this.populateForm();
    }

    /**
     * Create the main form HTML structure
     */
    createFormHTML() {
        return `
            <div class="compact-monitor-form">
                ${this.options.showDataConfig ? this.createDataConfigSection() : ''}
                ${this.createTradeExecutionSection()}
                ${this.createMonitorSection()}
                ${this.createTriggersSection()}
                ${this.createBarsSection()}
                ${this.createIndicatorsSection()}
                ${this.options.showGAHyperparameters ? this.createObjectivesSection() : ''}
                ${this.options.showGAHyperparameters ? this.createGAHyperparametersSection() : ''}
                
                <div class="form-actions mt-3">
                    <button type="button" class="btn btn-primary" id="saveMonitorConfig">
                        <i class="fas fa-save"></i> Save Configuration
                    </button>
                    <button type="button" class="btn btn-outline-secondary" id="resetMonitorConfig">
                        <i class="fas fa-undo"></i> Reset
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Create data configuration section (for replay_visualization)
     */
    createDataConfigSection() {
        return `
            <div class="compact-section">
                <div class="compact-header" data-target="dataConfigPanel">
                    <h6><i class="fas fa-chart-line me-2"></i>Data Configuration</h6>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </div>
                <div class="compact-content collapsed" id="dataConfigPanel">
                    <div class="row g-2">
                        <div class="col-md-4">
                            <label class="form-label">Ticker</label>
                            <input type="text" class="form-control form-control-sm" name="ticker" placeholder="e.g., AAPL">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Start Date</label>
                            <input type="date" class="form-control form-control-sm" name="start_date">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">End Date</label>
                            <input type="date" class="form-control form-control-sm" name="end_date">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create trade execution section
     */
    createTradeExecutionSection() {
        return `
            <div class="compact-section">
                <div class="compact-header" data-target="tradeExecPanel">
                    <h6><i class="fas fa-dollar-sign me-2"></i>Trade Execution</h6>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </div>
                <div class="compact-content collapsed" id="tradeExecPanel">
                    <div class="row g-2">
                        <div class="col-md-3">
                            <label class="form-label">Position Size</label>
                            <input type="number" class="form-control form-control-sm" name="default_position_size" step="0.01" placeholder="100.0">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Stop Loss %</label>
                            <input type="number" class="form-control form-control-sm" name="stop_loss_pct" step="0.001" placeholder="0.01">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Take Profit %</label>
                            <input type="number" class="form-control form-control-sm" name="take_profit_pct" step="0.001" placeholder="0.02">
                        </div>
                        <div class="col-md-3">
                            <div class="form-check mt-4">
                                <input type="checkbox" class="form-check-input" name="ignore_bear_signals">
                                <label class="form-check-label">Ignore Bear Signals</label>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="form-check">
                                <input type="checkbox" class="form-check-input" name="trailing_stop_loss">
                                <label class="form-check-label">Trailing Stop Loss</label>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Trailing Distance %</label>
                            <input type="number" class="form-control form-control-sm" name="trailing_stop_distance_pct" step="0.001" placeholder="0.01">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Trailing Activation %</label>
                            <input type="number" class="form-control form-control-sm" name="trailing_stop_activation_pct" step="0.001" placeholder="0.005">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create monitor section
     */
    createMonitorSection() {
        return `
            <div class="compact-section">
                <div class="compact-header" data-target="monitorPanel">
                    <h6><i class="fas fa-cogs me-2"></i>Monitor Info</h6>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </div>
                <div class="compact-content collapsed" id="monitorPanel">
                    <div class="row g-2">
                        <div class="col-md-6">
                            <label class="form-label">Monitor Name</label>
                            <input type="text" class="form-control form-control-sm" name="monitor_name" placeholder="My Monitor">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Description</label>
                            <input type="text" class="form-control form-control-sm" name="monitor_description" placeholder="Monitor description">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create triggers section for enter_long and exit_long
     */
    createTriggersSection() {
        return `
            <div class="compact-section">
                <div class="compact-header" data-target="triggersPanel">
                    <h6><i class="fas fa-bullseye me-2"></i>Entry & Exit Triggers</h6>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </div>
                <div class="compact-content collapsed" id="triggersPanel">
                    <div class="row g-3">
                        <div class="col-md-6">
                            <h6>Enter Long Triggers</h6>
                            <div id="enterLongList">
                                <!-- Enter long triggers will be populated here -->
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-success" id="addEnterLongBtn">
                                <i class="fas fa-plus me-1"></i>Add Enter Trigger
                            </button>
                        </div>
                        <div class="col-md-6">
                            <h6>Exit Long Triggers</h6>
                            <div id="exitLongList">
                                <!-- Exit long triggers will be populated here -->
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-danger" id="addExitLongBtn">
                                <i class="fas fa-plus me-1"></i>Add Exit Trigger
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create bars section for bar configurations
     */
    createBarsSection() {
        return `
            <div class="compact-section">
                <div class="compact-header" data-target="barsPanel">
                    <h6><i class="fas fa-chart-bar me-2"></i>Bar Configurations</h6>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </div>
                <div class="compact-content collapsed" id="barsPanel">
                    <div class="bars-container">
                        <div class="mb-2">
                            <button type="button" class="btn btn-sm btn-outline-primary" id="addBarBtn">
                                <i class="fas fa-plus me-1"></i>Add Bar Configuration
                            </button>
                        </div>
                        <div id="barsList">
                            <!-- Bar configurations will be populated here -->
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create objectives section
     */
    createObjectivesSection() {
        return `
            <div class="compact-section">
                <div class="compact-header" data-target="objectivesPanel">
                    <h6><i class="fas fa-target me-2"></i>Optimization Objectives</h6>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </div>
                <div class="compact-content collapsed" id="objectivesPanel">
                    <div class="objectives-container">
                        <div class="mb-2">
                            <button type="button" class="btn btn-sm btn-outline-primary" id="addObjectiveBtn">
                                <i class="fas fa-plus me-1"></i>Add Objective
                            </button>
                        </div>
                        <div id="objectivesList">
                            <!-- Objectives will be populated here -->
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create GA hyperparameters section
     */
    createGAHyperparametersSection() {
        return `
            <div class="compact-section">
                <div class="compact-header" data-target="gaHyperparametersPanel">
                    <h6><i class="fas fa-dna me-2"></i>GA Hyperparameters</h6>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </div>
                <div class="compact-content collapsed" id="gaHyperparametersPanel">
                    <div class="row g-2">
                        <div class="col-md-4">
                            <label class="form-label">Generations</label>
                            <input type="number" class="form-control form-control-sm" name="number_of_iterations" placeholder="100">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Population Size</label>
                            <input type="number" class="form-control form-control-sm" name="population_size" placeholder="50">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Elite Size</label>
                            <input type="number" class="form-control form-control-sm" name="elite_size" placeholder="12">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Elites to Save</label>
                            <input type="number" class="form-control form-control-sm" name="elites_to_save" placeholder="5" min="1" max="20">
                            <div class="form-text">Number of elite monitors to save as JSON files</div>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Propagation Fraction</label>
                            <input type="number" class="form-control form-control-sm" name="propagation_fraction" step="0.01" placeholder="0.4">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Mutation Chance</label>
                            <input type="number" class="form-control form-control-sm" name="chance_of_mutation" step="0.01" placeholder="0.05">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Crossover Chance</label>
                            <input type="number" class="form-control form-control-sm" name="chance_of_crossover" step="0.01" placeholder="0.03">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create indicators section
     */
    createIndicatorsSection() {
        return `
            <div class="compact-section">
                <div class="compact-header" data-target="indicatorsPanel">
                    <h6><i class="fas fa-chart-area me-2"></i>Indicators</h6>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </div>
                <div class="compact-content collapsed" id="indicatorsPanel">
                    <div class="indicators-container">
                        <div class="mb-2">
                            <button type="button" class="btn btn-sm btn-outline-primary" id="addIndicatorBtn">
                                <i class="fas fa-plus me-1"></i>Add Indicator
                            </button>
                        </div>
                        <div id="indicatorsList">
                            <!-- Indicators will be populated here -->
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create trigger panel for enter_long/exit_long
     */
    createTriggerPanel(trigger, index, type) {
        const triggerId = `${type}_trigger_${index}`;
        return `
            <div class="trigger-panel mb-2" data-index="${index}" data-type="${type}">
                <div class="compact-header compact-subheader" data-target="${triggerId}">
                    <h6><i class="fas fa-bullseye me-2"></i>${trigger.name || 'New Trigger'}</h6>
                    <div>
                        <button type="button" class="btn btn-sm btn-outline-danger me-2 remove-trigger" data-index="${index}" data-type="${type}">
                            <i class="fas fa-trash"></i>
                        </button>
                        <i class="fas fa-chevron-down collapse-icon"></i>
                    </div>
                </div>
                <div class="compact-content collapsed" id="${triggerId}">
                    <div class="row g-2">
                        <div class="col-md-6">
                            <label class="form-label">Trigger Name</label>
                            <input type="text" class="form-control form-control-sm" name="${type}[${index}][name]" value="${trigger.name || ''}" placeholder="e.g., macd_bull_strong">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Threshold</label>
                            <input type="number" class="form-control form-control-sm" name="${type}[${index}][threshold]" value="${trigger.threshold || ''}" step="0.01" placeholder="0.8">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create bar configuration panel
     */
    createBarPanel(barName, barConfig, index) {
        const barId = `bar_${index}`;
        const indicatorsHtml = Object.entries(barConfig.indicators || {}).map(([indName, weight], indIndex) => 
            `<div class="row g-2 mb-2" data-indicator-index="${indIndex}">
                <div class="col-md-8">
                    <input type="text" class="form-control form-control-sm" name="bars[${index}][indicators][${indIndex}][name]" value="${indName}" placeholder="Indicator name">
                </div>
                <div class="col-md-3">
                    <input type="number" class="form-control form-control-sm" name="bars[${index}][indicators][${indIndex}][weight]" value="${weight}" step="0.1" placeholder="Weight">
                </div>
                <div class="col-md-1">
                    <button type="button" class="btn btn-sm btn-outline-danger remove-bar-indicator" data-bar-index="${index}" data-indicator-index="${indIndex}">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>`
        ).join('');

        return `
            <div class="bar-panel mb-2" data-index="${index}" data-name="${barName}">
                <div class="compact-header compact-subheader" data-target="${barId}">
                    <h6><i class="fas fa-chart-bar me-2"></i>${barName || 'New Bar'}</h6>
                    <div>
                        <button type="button" class="btn btn-sm btn-outline-danger me-2 remove-bar" data-index="${index}">
                            <i class="fas fa-trash"></i>
                        </button>
                        <i class="fas fa-chevron-down collapse-icon"></i>
                    </div>
                </div>
                <div class="compact-content collapsed" id="${barId}">
                    <div class="row g-2">
                        <div class="col-md-4">
                            <label class="form-label">Bar Name</label>
                            <input type="text" class="form-control form-control-sm" name="bars[${index}][name]" value="${barName || ''}" placeholder="e.g., macd_bull_strong">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Type</label>
                            <select class="form-control form-control-sm" name="bars[${index}][type]">
                                <option value="bull" ${barConfig.type === 'bull' ? 'selected' : ''}>Bull</option>
                                <option value="bear" ${barConfig.type === 'bear' ? 'selected' : ''}>Bear</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Description</label>
                            <input type="text" class="form-control form-control-sm" name="bars[${index}][description]" value="${barConfig.description || ''}" placeholder="Bar description">
                        </div>
                        <div class="col-12">
                            <label class="form-label">Indicators & Weights</label>
                            <div id="barIndicators_${index}">
                                ${indicatorsHtml}
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-primary add-bar-indicator" data-bar-index="${index}">
                                <i class="fas fa-plus me-1"></i>Add Indicator
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create individual indicator panel
     */
    createIndicatorPanel(indicator, index) {
        const indicatorId = `indicator_${index}`;
        const showRanges = this.options.showRanges || false;
        const rangesHtml = showRanges && indicator.ranges ? 
            `<div class="col-12">
                <label class="form-label">Ranges (JSON)</label>
                <textarea class="form-control form-control-sm" name="indicators[${index}][ranges]" rows="3" placeholder='{"slow": {"t": "int", "r": [12, 35]}, "fast": {"t": "int", "r": [7, 18]}}'>${JSON.stringify(indicator.ranges || {}, null, 2)}</textarea>
            </div>` : '';

        return `
            <div class="indicator-panel mb-2" data-index="${index}">
                <div class="compact-header compact-subheader" data-target="${indicatorId}">
                    <h6><i class="fas fa-chart-line me-2"></i>${indicator.name || 'New Indicator'}</h6>
                    <div>
                        <button type="button" class="btn btn-sm btn-outline-danger me-2 remove-indicator" data-index="${index}">
                            <i class="fas fa-trash"></i>
                        </button>
                        <i class="fas fa-chevron-down collapse-icon"></i>
                    </div>
                </div>
                <div class="compact-content collapsed" id="${indicatorId}">
                    <div class="row g-2">
                        <div class="col-md-3">
                            <label class="form-label">Name</label>
                            <input type="text" class="form-control form-control-sm" name="indicators[${index}][name]" value="${indicator.name || ''}" placeholder="e.g., macd1m">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Type</label>
                            <input type="text" class="form-control form-control-sm" name="indicators[${index}][type]" value="${indicator.type || ''}" placeholder="e.g., Indicator">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Function</label>
                            <input type="text" class="form-control form-control-sm" name="indicators[${index}][function]" value="${indicator.function || ''}" placeholder="e.g., macd_histogram_crossover">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Agg Config</label>
                            <input type="text" class="form-control form-control-sm" name="indicators[${index}][agg_config]" value="${indicator.agg_config || '1m-normal'}" placeholder="1m-normal">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Parameters (JSON)</label>
                            <textarea class="form-control form-control-sm" name="indicators[${index}][parameters]" rows="3" placeholder='{"fast": 12, "slow": 26, "signal": 9, "lookback": 10}'>${JSON.stringify(indicator.parameters || {}, null, 2)}</textarea>
                        </div>
                        <div class="col-md-6">
                            <div class="row g-2">
                                <div class="col-12">
                                    <div class="form-check">
                                        <input type="checkbox" class="form-check-input" name="indicators[${index}][calc_on_pip]" ${indicator.calc_on_pip ? 'checked' : ''}>
                                        <label class="form-check-label">Calculate on PIP</label>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <label class="form-label">Weight</label>
                                    <input type="number" class="form-control form-control-sm" name="indicators[${index}][weight]" value="${indicator.weight || 1}" step="0.1">
                                </div>
                                <div class="col-6">
                                    <label class="form-label">Lookback</label>
                                    <input type="number" class="form-control form-control-sm" name="indicators[${index}][lookback]" value="${(indicator.parameters && indicator.parameters.lookback) || 10}">
                                </div>
                            </div>
                        </div>
                        ${rangesHtml}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Collapsible headers
        this.container.querySelectorAll('.compact-header').forEach(header => {
            header.addEventListener('click', (e) => {
                if (e.target.closest('.remove-indicator') || e.target.closest('button')) {
                    return; // Don't toggle if clicking button
                }
                this.toggleSection(header);
            });
        });

        // Add indicator button
        const addBtn = this.container.querySelector('#addIndicatorBtn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.addNewIndicator());
        }

        // Add trigger buttons
        const addEnterBtn = this.container.querySelector('#addEnterLongBtn');
        if (addEnterBtn) {
            addEnterBtn.addEventListener('click', () => this.addNewTrigger('enter_long'));
        }

        const addExitBtn = this.container.querySelector('#addExitLongBtn');
        if (addExitBtn) {
            addExitBtn.addEventListener('click', () => this.addNewTrigger('exit_long'));
        }

        // Add bar button
        const addBarBtn = this.container.querySelector('#addBarBtn');
        if (addBarBtn) {
            addBarBtn.addEventListener('click', () => this.addNewBar());
        }

        // Add objective button
        const addObjectiveBtn = this.container.querySelector('#addObjectiveBtn');
        if (addObjectiveBtn) {
            addObjectiveBtn.addEventListener('click', () => this.addNewObjective());
        }

        // Save configuration
        const saveBtn = this.container.querySelector('#saveMonitorConfig');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveConfiguration());
        }

        // Reset configuration
        const resetBtn = this.container.querySelector('#resetMonitorConfig');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetConfiguration());
        }

        // Remove buttons (delegated)
        this.container.addEventListener('click', (e) => {
            if (e.target.closest('.remove-indicator')) {
                const index = e.target.closest('.remove-indicator').dataset.index;
                this.removeIndicator(parseInt(index));
            }
            if (e.target.closest('.remove-trigger')) {
                const index = e.target.closest('.remove-trigger').dataset.index;
                const type = e.target.closest('.remove-trigger').dataset.type;
                this.removeTrigger(parseInt(index), type);
            }
            if (e.target.closest('.remove-bar')) {
                const index = e.target.closest('.remove-bar').dataset.index;
                this.removeBar(parseInt(index));
            }
            if (e.target.closest('.add-bar-indicator')) {
                const barIndex = e.target.closest('.add-bar-indicator').dataset.barIndex;
                this.addBarIndicator(parseInt(barIndex));
            }
            if (e.target.closest('.remove-bar-indicator')) {
                const barIndex = e.target.closest('.remove-bar-indicator').dataset.barIndex;
                const indicatorIndex = e.target.closest('.remove-bar-indicator').dataset.indicatorIndex;
                this.removeBarIndicator(parseInt(barIndex), parseInt(indicatorIndex));
            }
            if (e.target.closest('.remove-objective')) {
                const index = e.target.closest('.remove-objective').dataset.index;
                this.removeObjective(parseInt(index));
            }
        });

        // Update indicator names when name field changes
        this.container.addEventListener('input', (e) => {
            if (e.target.name && e.target.name.includes('[name]')) {
                const panel = e.target.closest('.indicator-panel');
                const header = panel.querySelector('.compact-subheader h6');
                header.innerHTML = `<i class="fas fa-chart-line me-2"></i>${e.target.value || 'New Indicator'}`;
            }
        });
    }

    /**
     * Attach event listeners specifically to trigger panels
     */
    attachTriggerEventListeners() {
        // Attach collapsible functionality to trigger headers
        this.container.querySelectorAll('.trigger-panel .compact-subheader').forEach(header => {
            // Remove existing listeners to avoid duplicates
            const newHeader = header.cloneNode(true);
            header.parentNode.replaceChild(newHeader, header);
            
            // Add click listener for collapse functionality
            newHeader.addEventListener('click', (e) => {
                if (e.target.closest('.remove-trigger') || e.target.closest('button')) {
                    return; // Don't toggle if clicking button
                }
                this.toggleSection(newHeader);
            });
        });
    }

    /**
     * Attach event listeners specifically to bar panels
     */
    attachBarEventListeners() {
        // Attach collapsible functionality to bar headers
        this.container.querySelectorAll('.bar-panel .compact-subheader').forEach(header => {
            // Remove existing listeners to avoid duplicates
            const newHeader = header.cloneNode(true);
            header.parentNode.replaceChild(newHeader, header);
            
            // Add click listener for collapse functionality
            newHeader.addEventListener('click', (e) => {
                if (e.target.closest('.remove-bar') || e.target.closest('button')) {
                    return; // Don't toggle if clicking button
                }
                this.toggleSection(newHeader);
            });
        });
    }

    /**
     * Attach event listeners specifically to indicator panels
     */
    attachIndicatorEventListeners() {
        // Attach collapsible functionality to indicator headers
        this.container.querySelectorAll('.indicator-panel .compact-subheader').forEach(header => {
            // Remove existing listeners to avoid duplicates
            const newHeader = header.cloneNode(true);
            header.parentNode.replaceChild(newHeader, header);
            
            // Add click listener for collapse functionality
            newHeader.addEventListener('click', (e) => {
                if (e.target.closest('.remove-indicator') || e.target.closest('button')) {
                    return; // Don't toggle if clicking button
                }
                this.toggleSection(newHeader);
            });
        });
    }

    /**
     * Toggle section visibility
     */
    toggleSection(header) {
        const targetId = header.dataset.target;
        const content = document.getElementById(targetId);
        const icon = header.querySelector('.collapse-icon');

        if (content.classList.contains('collapsed')) {
            content.classList.remove('collapsed');
            icon.classList.add('rotated');
        } else {
            content.classList.add('collapsed');
            icon.classList.remove('rotated');
        }
    }

    /**
     * Populate form with configuration data
     */
    populateForm() {
        // Populate data config fields
        if (this.dataConfig && this.options.showDataConfig) {
            this.container.querySelector('[name="ticker"]').value = this.dataConfig.ticker || '';
            this.container.querySelector('[name="start_date"]').value = this.dataConfig.start_date || '';
            this.container.querySelector('[name="end_date"]').value = this.dataConfig.end_date || '';
        }

        if (!this.monitorConfig) return;

        // Populate monitor fields
        const monitor = this.monitorConfig.monitor || this.monitorConfig;
        this.container.querySelector('[name="monitor_name"]').value = monitor.name || '';
        this.container.querySelector('[name="monitor_description"]').value = monitor.description || '';

        // Populate trade executor fields
        const tradeExec = monitor.trade_executor || {};
        this.container.querySelector('[name="default_position_size"]').value = tradeExec.default_position_size || '';
        this.container.querySelector('[name="stop_loss_pct"]').value = tradeExec.stop_loss_pct || '';
        this.container.querySelector('[name="take_profit_pct"]').value = tradeExec.take_profit_pct || '';
        this.container.querySelector('[name="ignore_bear_signals"]').checked = tradeExec.ignore_bear_signals || false;
        this.container.querySelector('[name="trailing_stop_loss"]').checked = tradeExec.trailing_stop_loss || false;
        this.container.querySelector('[name="trailing_stop_distance_pct"]').value = tradeExec.trailing_stop_distance_pct || '';
        this.container.querySelector('[name="trailing_stop_activation_pct"]').value = tradeExec.trailing_stop_activation_pct || '';

        // Populate triggers
        this.populateTriggers();
        
        // Populate bars
        this.populateBars();
        
        // Populate indicators
        this.populateIndicators();
        
        // Populate GA hyperparameters if enabled
        if (this.options.showGAHyperparameters) {
            this.populateObjectives();
            this.populateGAHyperparameters();
        }
    }

    /**
     * Populate triggers (enter_long and exit_long)
     */
    populateTriggers() {
        const monitorData = this.monitorConfig.monitor || this.monitorConfig;
        
        // Populate enter_long triggers
        const enterLongList = this.container.querySelector('#enterLongList');
        if (enterLongList) {
            enterLongList.innerHTML = '';
            const enterLong = monitorData.enter_long || [];
            if (enterLong.length > 0) {
                enterLong.forEach((trigger, index) => {
                    enterLongList.innerHTML += this.createTriggerPanel(trigger, index, 'enter_long');
                });
            } else {
                enterLongList.innerHTML = '<div class="text-muted text-center py-2">No enter triggers</div>';
            }
        }
        
        // Populate exit_long triggers
        const exitLongList = this.container.querySelector('#exitLongList');
        if (exitLongList) {
            exitLongList.innerHTML = '';
            const exitLong = monitorData.exit_long || [];
            if (exitLong.length > 0) {
                exitLong.forEach((trigger, index) => {
                    exitLongList.innerHTML += this.createTriggerPanel(trigger, index, 'exit_long');
                });
            } else {
                exitLongList.innerHTML = '<div class="text-muted text-center py-2">No exit triggers</div>';
            }
        }
        
        // Reattach event listeners
        this.attachTriggerEventListeners();
    }

    /**
     * Populate bars configurations
     */
    populateBars() {
        const barsList = this.container.querySelector('#barsList');
        if (!barsList) return;

        barsList.innerHTML = '';
        const monitorData = this.monitorConfig.monitor || this.monitorConfig;
        const bars = monitorData.bars || {};
        
        if (Object.keys(bars).length > 0) {
            let index = 0;
            Object.entries(bars).forEach(([barName, barConfig]) => {
                barsList.innerHTML += this.createBarPanel(barName, barConfig, index);
                index++;
            });
            // Reattach event listeners
            this.attachBarEventListeners();
        } else {
            barsList.innerHTML = '<div class="text-muted text-center py-3">No bar configurations added yet</div>';
        }
    }

    /**
     * Create objective panel
     */
    createObjectivePanel(objective, index) {
        const objectiveId = `objective_${index}`;
        return `
            <div class="objective-panel mb-2" data-index="${index}">
                <div class="compact-header compact-subheader" data-target="${objectiveId}">
                    <h6><i class="fas fa-target me-2"></i>${objective.objective || 'New Objective'}</h6>
                    <div>
                        <button type="button" class="btn btn-sm btn-outline-danger me-2 remove-objective" data-index="${index}">
                            <i class="fas fa-trash"></i>
                        </button>
                        <i class="fas fa-chevron-down collapse-icon"></i>
                    </div>
                </div>
                <div class="compact-content collapsed" id="${objectiveId}">
                    <div class="row g-2">
                        <div class="col-md-8">
                            <label class="form-label">Objective Type</label>
                            <select class="form-control form-control-sm" name="objectives[${index}][objective]">
                                <option value="MaximizeProfit" ${objective.objective === 'MaximizeProfit' ? 'selected' : ''}>Maximize Profit</option>
                                <option value="MaximizeNetPnL" ${objective.objective === 'MaximizeNetPnL' ? 'selected' : ''}>Maximize Net P&L</option>
                                <option value="MinimizeLosingTrades" ${objective.objective === 'MinimizeLosingTrades' ? 'selected' : ''}>Minimize Losing Trades</option>
                                <option value="MinimizeLoss" ${objective.objective === 'MinimizeLoss' ? 'selected' : ''}>Minimize Loss</option>
                                <option value="MaximizeWinningTrades" ${objective.objective === 'MaximizeWinningTrades' ? 'selected' : ''}>Maximize Winning Trades</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Weight</label>
                            <input type="number" class="form-control form-control-sm" name="objectives[${index}][weight]" value="${objective.weight || 1}" step="0.1">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Populate objectives
     */
    populateObjectives() {
        const objectivesList = this.container.querySelector('#objectivesList');
        if (!objectivesList) return;

        objectivesList.innerHTML = '';
        
        let objectives = this.monitorConfig.objectives || [];
        
        // If no objectives exist, add some defaults
        if (objectives.length === 0) {
            objectives = [
                { objective: 'MaximizeProfit', weight: 1.0 },
                { objective: 'MaximizeNetPnL', weight: 5.0 },
                { objective: 'MinimizeLosingTrades', weight: 5.0 }
            ];
            // Store the defaults in the config
            this.monitorConfig.objectives = objectives;
        }
        
        objectives.forEach((objective, index) => {
            objectivesList.innerHTML += this.createObjectivePanel(objective, index);
        });
        // Reattach event listeners
        this.attachObjectiveEventListeners();
    }

    /**
     * Add new objective
     */
    addNewObjective() {
        if (!this.monitorConfig.objectives) {
            this.monitorConfig.objectives = [];
        }

        const newObjective = {
            objective: 'MaximizeProfit',
            weight: 1.0
        };

        this.monitorConfig.objectives.push(newObjective);
        this.populateObjectives();
    }

    /**
     * Remove objective
     */
    removeObjective(index) {
        if (this.monitorConfig.objectives && index >= 0 && index < this.monitorConfig.objectives.length) {
            this.monitorConfig.objectives.splice(index, 1);
            this.populateObjectives();
        }
    }

    /**
     * Attach event listeners to objective panels
     */
    attachObjectiveEventListeners() {
        // Attach collapsible functionality to objective headers
        this.container.querySelectorAll('.objective-panel .compact-subheader').forEach(header => {
            // Remove existing listeners to avoid duplicates
            const newHeader = header.cloneNode(true);
            header.parentNode.replaceChild(newHeader, header);
            
            // Add click listener for collapse functionality
            newHeader.addEventListener('click', (e) => {
                if (e.target.closest('.remove-objective') || e.target.closest('button')) {
                    return; // Don't toggle if clicking button
                }
                this.toggleSection(newHeader);
            });
        });
    }

    /**
     * Populate GA hyperparameters
     */
    populateGAHyperparameters() {
        if (!this.monitorConfig.ga_hyperparameters) return;
        
        const params = this.monitorConfig.ga_hyperparameters;
        
        const setField = (name, value) => {
            const field = this.container.querySelector(`[name="${name}"]`);
            if (field && value !== undefined) {
                field.value = value;
            }
        };
        
        setField('number_of_iterations', params.number_of_iterations);
        setField('population_size', params.population_size);
        setField('elite_size', params.elite_size);
        setField('elites_to_save', params.elites_to_save);
        setField('propagation_fraction', params.propagation_fraction);
        setField('chance_of_mutation', params.chance_of_mutation);
        setField('chance_of_crossover', params.chance_of_crossover);
    }

    /**
     * Populate indicators list
     */
    populateIndicators() {
        const indicatorsList = this.container.querySelector('#indicatorsList');
        if (!indicatorsList) return;

        indicatorsList.innerHTML = '';
        
        // Get indicators from the top level, not from inside monitor
        const indicators = this.monitorConfig.indicators || [];
        if (indicators.length > 0) {
            indicators.forEach((indicator, index) => {
                indicatorsList.innerHTML += this.createIndicatorPanel(indicator, index);
            });
            // Reattach event listeners to newly created indicator panels
            this.attachIndicatorEventListeners();
        } else {
            indicatorsList.innerHTML = '<div class="text-muted text-center py-3">No indicators added yet</div>';
        }
    }

    /**
     * Add new trigger
     */
    addNewTrigger(type) {
        const monitorData = this.monitorConfig.monitor || this.monitorConfig;
        if (!monitorData[type]) {
            monitorData[type] = [];
        }

        const newTrigger = {
            name: '',
            threshold: 0.8
        };

        monitorData[type].push(newTrigger);
        this.populateTriggers();
    }

    /**
     * Remove trigger
     */
    removeTrigger(index, type) {
        const monitorData = this.monitorConfig.monitor || this.monitorConfig;
        if (monitorData[type] && index >= 0 && index < monitorData[type].length) {
            monitorData[type].splice(index, 1);
            this.populateTriggers();
        }
    }

    /**
     * Add new bar configuration
     */
    addNewBar() {
        const monitorData = this.monitorConfig.monitor || this.monitorConfig;
        if (!monitorData.bars) {
            monitorData.bars = {};
        }

        const newBarName = `new_bar_${Object.keys(monitorData.bars).length + 1}`;
        monitorData.bars[newBarName] = {
            type: 'bull',
            description: '',
            indicators: {}
        };

        this.populateBars();
    }

    /**
     * Remove bar configuration
     */
    removeBar(index) {
        const monitorData = this.monitorConfig.monitor || this.monitorConfig;
        if (monitorData.bars) {
            const barNames = Object.keys(monitorData.bars);
            if (index >= 0 && index < barNames.length) {
                delete monitorData.bars[barNames[index]];
                this.populateBars();
            }
        }
    }

    /**
     * Add indicator to bar
     */
    addBarIndicator(barIndex) {
        const monitorData = this.monitorConfig.monitor || this.monitorConfig;
        const barNames = Object.keys(monitorData.bars || {});
        if (barIndex >= 0 && barIndex < barNames.length) {
            const barName = barNames[barIndex];
            if (!monitorData.bars[barName].indicators) {
                monitorData.bars[barName].indicators = {};
            }
            const newIndicatorName = `new_indicator_${Object.keys(monitorData.bars[barName].indicators).length + 1}`;
            monitorData.bars[barName].indicators[newIndicatorName] = 1.0;
            this.populateBars();
        }
    }

    /**
     * Remove indicator from bar
     */
    removeBarIndicator(barIndex, indicatorIndex) {
        const monitorData = this.monitorConfig.monitor || this.monitorConfig;
        const barNames = Object.keys(monitorData.bars || {});
        if (barIndex >= 0 && barIndex < barNames.length) {
            const barName = barNames[barIndex];
            const indicatorNames = Object.keys(monitorData.bars[barName].indicators || {});
            if (indicatorIndex >= 0 && indicatorIndex < indicatorNames.length) {
                delete monitorData.bars[barName].indicators[indicatorNames[indicatorIndex]];
                this.populateBars();
            }
        }
    }

    /**
     * Add new indicator
     */
    addNewIndicator() {
        if (!this.monitorConfig.indicators) {
            this.monitorConfig.indicators = [];
        }

        const newIndicator = {
            name: '',
            type: 'Indicator',
            function: '',
            parameters: {},
            agg_config: '1m-normal',
            calc_on_pip: false
        };

        if (this.options.showRanges) {
            newIndicator.ranges = {};
        }

        this.monitorConfig.indicators.push(newIndicator);
        this.populateIndicators();
    }

    /**
     * Remove indicator
     */
    removeIndicator(index) {
        if (this.monitorConfig.indicators && index >= 0 && index < this.monitorConfig.indicators.length) {
            this.monitorConfig.indicators.splice(index, 1);
            this.populateIndicators();
        }
    }

    /**
     * Get form data
     */
    getFormData() {
        const data = {};

        // Helper function to get input value by name
        const getValue = (name) => {
            const element = this.container.querySelector(`[name="${name}"]`);
            return element ? element.value : '';
        };

        // Helper function to get checkbox value by name
        const getCheckboxValue = (name) => {
            const element = this.container.querySelector(`[name="${name}"]`);
            return element ? element.checked : false;
        };

        // Build data config if enabled
        if (this.options.showDataConfig) {
            data.dataConfig = {
                ticker: getValue('ticker'),
                start_date: getValue('start_date'),
                end_date: getValue('end_date')
            };
        }

        // Build monitor config
        data.monitorConfig = {
            test_name: this.monitorConfig.test_name || 'Monitor Configuration',
            monitor: {
                name: getValue('monitor_name'),
                description: getValue('monitor_description'),
                trade_executor: {
                    default_position_size: parseFloat(getValue('default_position_size')) || undefined,
                    stop_loss_pct: parseFloat(getValue('stop_loss_pct')) || undefined,
                    take_profit_pct: parseFloat(getValue('take_profit_pct')) || undefined,
                    ignore_bear_signals: getCheckboxValue('ignore_bear_signals'),
                    trailing_stop_loss: getCheckboxValue('trailing_stop_loss'),
                    trailing_stop_distance_pct: parseFloat(getValue('trailing_stop_distance_pct')) || undefined,
                    trailing_stop_activation_pct: parseFloat(getValue('trailing_stop_activation_pct')) || undefined
                },
                enter_long: [],
                exit_long: [],
                bars: {}
            },
            indicators: []
        };

        // Build triggers (enter_long and exit_long)
        const enterTriggers = this.container.querySelectorAll('.trigger-panel[data-type="enter_long"]');
        enterTriggers.forEach((panel, index) => {
            const trigger = {
                name: getValue(`enter_long[${index}][name]`),
                threshold: parseFloat(getValue(`enter_long[${index}][threshold]`)) || 0.8
            };
            data.monitorConfig.monitor.enter_long.push(trigger);
        });

        const exitTriggers = this.container.querySelectorAll('.trigger-panel[data-type="exit_long"]');
        exitTriggers.forEach((panel, index) => {
            const trigger = {
                name: getValue(`exit_long[${index}][name]`),
                threshold: parseFloat(getValue(`exit_long[${index}][threshold]`)) || 0.8
            };
            data.monitorConfig.monitor.exit_long.push(trigger);
        });

        // Build bars configurations
        const barPanels = this.container.querySelectorAll('.bar-panel');
        barPanels.forEach((panel, index) => {
            const barName = getValue(`bars[${index}][name]`);
            if (barName) {
                const barConfig = {
                    type: getValue(`bars[${index}][type]`),
                    description: getValue(`bars[${index}][description]`),
                    indicators: {}
                };
                
                // Get indicators for this bar
                const indicatorRows = panel.querySelectorAll('[data-indicator-index]');
                indicatorRows.forEach((row, indIndex) => {
                    const indName = getValue(`bars[${index}][indicators][${indIndex}][name]`);
                    const indWeight = parseFloat(getValue(`bars[${index}][indicators][${indIndex}][weight]`));
                    if (indName && !isNaN(indWeight)) {
                        barConfig.indicators[indName] = indWeight;
                    }
                });
                
                data.monitorConfig.monitor.bars[barName] = barConfig;
            }
        });

        // Build indicators
        const indicators = this.container.querySelectorAll('.indicator-panel');
        indicators.forEach((panel, index) => {
            const parametersTextarea = panel.querySelector(`[name="indicators[${index}][parameters]"]`);
            let parameters = {};
            
            try {
                parameters = parametersTextarea.value ? JSON.parse(parametersTextarea.value) : {};
            } catch (e) {
                console.warn(`Invalid JSON in indicator ${index} parameters:`, e);
                parameters = {};
            }

            const indicator = {
                name: getValue(`indicators[${index}][name]`),
                type: getValue(`indicators[${index}][type]`),
                function: getValue(`indicators[${index}][function]`),
                parameters: parameters,
                agg_config: getValue(`indicators[${index}][agg_config]`),
                calc_on_pip: getCheckboxValue(`indicators[${index}][calc_on_pip]`)
            };

            // Include ranges if showRanges is enabled
            if (this.options.showRanges) {
                const rangesTextarea = panel.querySelector(`[name="indicators[${index}][ranges]"]`);
                let ranges = {};
                
                try {
                    ranges = rangesTextarea && rangesTextarea.value ? JSON.parse(rangesTextarea.value) : {};
                } catch (e) {
                    console.warn(`Invalid JSON in indicator ${index} ranges:`, e);
                    ranges = {};
                }
                
                indicator.ranges = ranges;
            }

            data.monitorConfig.indicators.push(indicator);
        });

        // Build objectives if enabled
        if (this.options.showGAHyperparameters) {
            data.monitorConfig.objectives = [];
            const objectives = this.container.querySelectorAll('.objective-panel');
            
            if (objectives.length > 0) {
                objectives.forEach((panel, index) => {
                    const objective = {
                        objective: getValue(`objectives[${index}][objective]`),
                        weight: parseFloat(getValue(`objectives[${index}][weight]`)) || 1.0
                    };
                    data.monitorConfig.objectives.push(objective);
                });
            } else {
                // Fallback: include defaults if no objective panels found
                data.monitorConfig.objectives = [
                    { objective: 'MaximizeProfit', weight: 1.0 },
                    { objective: 'MaximizeNetPnL', weight: 5.0 },
                    { objective: 'MinimizeLosingTrades', weight: 5.0 }
                ];
            }
        }

        // Build GA hyperparameters if enabled
        if (this.options.showGAHyperparameters) {
            data.monitorConfig.ga_hyperparameters = {
                number_of_iterations: parseInt(getValue('number_of_iterations')) || undefined,
                population_size: parseInt(getValue('population_size')) || undefined,
                elite_size: parseInt(getValue('elite_size')) || undefined,
                elites_to_save: parseInt(getValue('elites_to_save')) || 5,
                propagation_fraction: parseFloat(getValue('propagation_fraction')) || undefined,
                chance_of_mutation: parseFloat(getValue('chance_of_mutation')) || undefined,
                chance_of_crossover: parseFloat(getValue('chance_of_crossover')) || undefined
            };
        }

        return data;
    }

    /**
     * Save configuration
     */
    saveConfiguration() {
        const data = this.getFormData();
        
        // Debug logging
        console.log('Saving config with data:', data);
        if (data.monitorConfig.objectives) {
            console.log('Objectives found:', data.monitorConfig.objectives);
        } else {
            console.log('No objectives in saved data!');
        }
        
        // Dispatch custom event for parent to handle
        const event = new CustomEvent('monitorConfigSave', {
            detail: data
        });
        this.container.dispatchEvent(event);
    }

    /**
     * Reset configuration
     */
    resetConfiguration() {
        if (confirm('Are you sure you want to reset all changes?')) {
            this.populateForm();
        }
    }
}

