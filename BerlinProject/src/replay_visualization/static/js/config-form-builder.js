/**
 * Reusable Configuration Form Builder
 * Generates dynamic forms from JSON configuration objects
 */

class ConfigFormBuilder {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            showGAFields: true, // Set to false for replay visualization
            indicatorTypes: [
                'macd_histogram_crossover',
                'sma_crossover',
                'rsi_crossover',
                'bollinger_bands',
                'stochastic_crossover'
            ],
            ...options
        };
        this.formData = {};
        this.validators = {};
    }

    /**
     * Generate complete form from configuration object
     */
    generateForm(config) {
        this.formData = JSON.parse(JSON.stringify(config)); // Deep clone
        this.container.innerHTML = '';
        
        // Create form wrapper
        const form = this.createElement('form', 'config-form', 'needs-validation');
        form.setAttribute('novalidate', '');
        
        // Create single unified grid container for all cards
        const cardsContainer = this.createElement('div', 'row');
        
        // Handle different config structures
        let monitorData = null;
        let isNestedStructure = false;
        
        if (config.monitor) {
            // GA/Nested structure: {test_name, monitor: {...}, indicators: [...]}
            monitorData = config.monitor;
            isNestedStructure = true;
        } else if (config.name && config.trade_executor) {
            // Direct monitor structure: {name, trade_executor, enter_long, exit_long, bars}
            monitorData = config;
            isNestedStructure = false;
        }
        
        // Add test name card
        if (isNestedStructure && config.test_name) {
            cardsContainer.appendChild(this.createTestNameCard(config.test_name));
        }
        
        // Add monitor info cards
        if (monitorData) {
            cardsContainer.appendChild(this.createMonitorNameCard(monitorData, isNestedStructure));
            cardsContainer.appendChild(this.createMonitorDescriptionCard(monitorData, isNestedStructure));
            
            // Trade executor card
            if (monitorData.trade_executor) {
                cardsContainer.appendChild(this.createTradeExecutorCard(monitorData.trade_executor, isNestedStructure));
            }
            
            // Enter/Exit condition cards
            if (monitorData.enter_long) {
                monitorData.enter_long.forEach((condition, index) => {
                    cardsContainer.appendChild(this.createConditionCard('enter_long', condition, index, isNestedStructure));
                });
            }
            
            if (monitorData.exit_long) {
                monitorData.exit_long.forEach((condition, index) => {
                    cardsContainer.appendChild(this.createConditionCard('exit_long', condition, index, isNestedStructure));
                });
            }
            
            // Bars cards
            if (monitorData.bars) {
                Object.entries(monitorData.bars).forEach(([barName, barConfig]) => {
                    cardsContainer.appendChild(this.createBarCard(barName, barConfig, isNestedStructure));
                });
            }
        }
        
        // Indicator cards
        if (config.indicators) {
            config.indicators.forEach((indicator, index) => {
                cardsContainer.appendChild(this.createIndicatorItem(indicator, index));
            });
        }
        
        // Add buttons for adding new items (only for replay visualization)
        cardsContainer.appendChild(this.createAddButtonsCard(isNestedStructure));
        
        form.appendChild(cardsContainer);
        
        // Form actions
        form.appendChild(this.createFormActions());
        
        this.container.appendChild(form);
        this.attachEventHandlers();
        
        return form;
    }

    /**
     * Create test name card
     */
    createTestNameCard(testName) {
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const card = this.createElement('div', 'card h-100');
        const cardHeader = this.createElement('div', 'card-header compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body');
        
        // Header
        const title = this.createElement('div', 'fw-bold compact-title');
        title.innerHTML = '<i class="fas fa-tag"></i> Test Name';
        cardHeader.appendChild(title);
        
        // Body
        const input = this.createElement('input', 'form-control form-control-sm');
        input.type = 'text';
        input.name = 'test_name';
        input.value = testName || '';
        input.placeholder = 'Enter test name';
        cardBody.appendChild(input);
        
        card.appendChild(cardHeader);
        card.appendChild(cardBody);
        cardWrapper.appendChild(card);
        
        return cardWrapper;
    }

    /**
     * Create monitor name card
     */
    createMonitorNameCard(monitorData, isNestedStructure) {
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const card = this.createElement('div', 'card h-100');
        const cardHeader = this.createElement('div', 'card-header compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body');
        
        // Header
        const title = this.createElement('div', 'fw-bold compact-title');
        title.innerHTML = '<i class="fas fa-eye"></i> Monitor Name';
        cardHeader.appendChild(title);
        
        // Body
        const pathPrefix = isNestedStructure ? 'monitor.' : '';
        const input = this.createElement('input', 'form-control form-control-sm');
        input.type = 'text';
        input.name = pathPrefix + 'name';
        input.value = monitorData.name || '';
        input.placeholder = 'Monitor name';
        cardBody.appendChild(input);
        
        card.appendChild(cardHeader);
        card.appendChild(cardBody);
        cardWrapper.appendChild(card);
        
        return cardWrapper;
    }

    /**
     * Create monitor description card
     */
    createMonitorDescriptionCard(monitorData, isNestedStructure) {
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const card = this.createElement('div', 'card h-100');
        const cardHeader = this.createElement('div', 'card-header compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body');
        
        // Header
        const title = this.createElement('div', 'fw-bold compact-title');
        title.innerHTML = '<i class="fas fa-file-text"></i> Description';
        cardHeader.appendChild(title);
        
        // Body
        const pathPrefix = isNestedStructure ? 'monitor.' : '';
        const textarea = this.createElement('textarea', 'form-control form-control-sm');
        textarea.name = pathPrefix + 'description';
        textarea.value = monitorData.description || '';
        textarea.placeholder = 'Monitor description';
        textarea.rows = 2;
        cardBody.appendChild(textarea);
        
        card.appendChild(cardHeader);
        card.appendChild(cardBody);
        cardWrapper.appendChild(card);
        
        return cardWrapper;
    }

    /**
     * Create trade executor card
     */
    createTradeExecutorCard(tradeExecutor, isNestedStructure) {
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const card = this.createElement('div', 'card h-100');
        const cardHeader = this.createElement('div', 'card-header compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body');
        
        // Header
        const title = this.createElement('div', 'fw-bold compact-title');
        title.innerHTML = '<i class="fas fa-exchange-alt"></i> Trade Executor';
        cardHeader.appendChild(title);
        
        // Body - compact fields
        const pathPrefix = isNestedStructure ? 'monitor.' : '';
        const compactForm = this.createElement('div', 'compact-form');
        
        // Type field
        const typeField = this.createElement('div', 'mb-2');
        const typeSelect = this.createElement('select', 'form-select form-select-sm');
        typeSelect.name = pathPrefix + 'trade_executor.type';
        ['PaperTradeExecutor', 'LiveTradeExecutor', 'BacktestExecutor'].forEach(type => {
            const option = this.createElement('option');
            option.value = type;
            option.textContent = type;
            if (type === tradeExecutor.type) option.selected = true;
            typeSelect.appendChild(option);
        });
        typeField.appendChild(typeSelect);
        compactForm.appendChild(typeField);
        
        // Account value field
        const accountField = this.createElement('div', 'mb-2');
        const accountInput = this.createElement('input', 'form-control form-control-sm');
        accountInput.type = 'number';
        accountInput.name = pathPrefix + 'trade_executor.account_value';
        accountInput.value = tradeExecutor.account_value || 10000;
        accountInput.placeholder = 'Account Value';
        accountField.appendChild(accountInput);
        compactForm.appendChild(accountField);
        
        // Risk percentage field
        const riskField = this.createElement('div', 'mb-2');
        const riskInput = this.createElement('input', 'form-control form-control-sm');
        riskInput.type = 'number';
        riskInput.name = pathPrefix + 'trade_executor.risk_percentage';
        riskInput.value = tradeExecutor.risk_percentage || 1;
        riskInput.step = '0.1';
        riskInput.placeholder = 'Risk %';
        riskField.appendChild(riskInput);
        compactForm.appendChild(riskField);
        
        cardBody.appendChild(compactForm);
        
        card.appendChild(cardHeader);
        card.appendChild(cardBody);
        cardWrapper.appendChild(card);
        
        return cardWrapper;
    }

    /**
     * Create condition card
     */
    createConditionCard(conditionType, condition, index, isNestedStructure) {
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const card = this.createElement('div', 'card h-100');
        const cardHeader = this.createElement('div', 'card-header d-flex justify-content-between align-items-center compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body');
        
        // Header
        const titleContainer = this.createElement('div', 'd-flex flex-column');
        const mainTitle = this.createElement('div', 'fw-bold text-truncate compact-title');
        mainTitle.textContent = condition.name || conditionType;
        
        const subtitle = this.createElement('small', 'text-muted text-truncate');
        subtitle.textContent = conditionType === 'enter_long' ? 'Enter Long' : 'Exit Long';
        
        titleContainer.appendChild(mainTitle);
        titleContainer.appendChild(subtitle);
        cardHeader.appendChild(titleContainer);
        
        const removeBtn = this.createElement('button', 'btn btn-outline-danger btn-xs');
        removeBtn.type = 'button';
        removeBtn.innerHTML = '<i class="fas fa-trash fa-xs"></i>';
        removeBtn.onclick = () => this.removeCondition(conditionType, index, isNestedStructure);
        cardHeader.appendChild(removeBtn);
        
        // Body
        const pathPrefix = isNestedStructure ? 'monitor.' : '';
        const compactForm = this.createElement('div', 'compact-form');
        
        // Name field
        const nameField = this.createElement('div', 'mb-2');
        const nameInput = this.createElement('input', 'form-control form-control-sm');
        nameInput.type = 'text';
        nameInput.name = `${pathPrefix}${conditionType}.${index}.name`;
        nameInput.value = condition.name || '';
        nameInput.placeholder = 'Condition Name';
        nameField.appendChild(nameInput);
        compactForm.appendChild(nameField);
        
        // Threshold field
        const thresholdField = this.createElement('div', 'mb-2');
        const thresholdInput = this.createElement('input', 'form-control form-control-sm');
        thresholdInput.type = 'number';
        thresholdInput.name = `${pathPrefix}${conditionType}.${index}.threshold`;
        thresholdInput.value = condition.threshold || 0;
        thresholdInput.step = '0.001';
        thresholdInput.placeholder = 'Threshold';
        thresholdField.appendChild(thresholdInput);
        compactForm.appendChild(thresholdField);
        
        cardBody.appendChild(compactForm);
        
        card.appendChild(cardHeader);
        card.appendChild(cardBody);
        cardWrapper.appendChild(card);
        
        return cardWrapper;
    }

    /**
     * Create bar card
     */
    createBarCard(barName, barConfig, isNestedStructure) {
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const card = this.createElement('div', 'card h-100');
        const cardHeader = this.createElement('div', 'card-header d-flex justify-content-between align-items-center compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body');
        
        // Header
        const titleContainer = this.createElement('div', 'd-flex flex-column');
        const mainTitle = this.createElement('div', 'fw-bold text-truncate compact-title');
        mainTitle.textContent = barName;
        
        const subtitle = this.createElement('small', 'text-muted text-truncate');
        subtitle.textContent = barConfig.type || 'Bar Config';
        
        titleContainer.appendChild(mainTitle);
        titleContainer.appendChild(subtitle);
        cardHeader.appendChild(titleContainer);
        
        const removeBtn = this.createElement('button', 'btn btn-outline-danger btn-xs');
        removeBtn.type = 'button';
        removeBtn.innerHTML = '<i class="fas fa-trash fa-xs"></i>';
        removeBtn.onclick = () => this.removeBar(barName, isNestedStructure);
        cardHeader.appendChild(removeBtn);
        
        // Body
        const pathPrefix = isNestedStructure ? 'monitor.' : '';
        const compactForm = this.createElement('div', 'compact-form');
        
        // Type field
        const typeField = this.createElement('div', 'mb-2');
        const typeSelect = this.createElement('select', 'form-select form-select-sm');
        typeSelect.name = `${pathPrefix}bars.${barName}.type`;
        ['bull', 'bear'].forEach(type => {
            const option = this.createElement('option');
            option.value = type;
            option.textContent = type;
            if (type === barConfig.type) option.selected = true;
            typeSelect.appendChild(option);
        });
        typeField.appendChild(typeSelect);
        compactForm.appendChild(typeField);
        
        // Indicators display
        if (barConfig.indicators) {
            const indicatorsInfo = this.createElement('div', 'compact-params');
            const indicatorsLabel = this.createElement('small', 'text-muted fw-bold');
            indicatorsLabel.textContent = 'Indicators:';
            indicatorsInfo.appendChild(indicatorsLabel);
            
            const indicatorsList = this.createElement('div', 'params-list');
            Object.entries(barConfig.indicators).forEach(([indicatorName, weight]) => {
                const indicatorBadge = this.createElement('span', 'badge bg-secondary me-1 mb-1 param-badge');
                indicatorBadge.textContent = `${indicatorName}: ${weight}`;
                indicatorBadge.onclick = () => this.editBarIndicator(barName, indicatorName, weight, pathPrefix);
                indicatorBadge.style.cursor = 'pointer';
                indicatorBadge.title = 'Click to edit weight';
                indicatorsList.appendChild(indicatorBadge);
            });
            indicatorsInfo.appendChild(indicatorsList);
            compactForm.appendChild(indicatorsInfo);
        }
        
        cardBody.appendChild(compactForm);
        
        card.appendChild(cardHeader);
        card.appendChild(cardBody);
        cardWrapper.appendChild(card);
        
        return cardWrapper;
    }

    /**
     * Create add buttons card
     */
    createAddButtonsCard(isNestedStructure) {
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const card = this.createElement('div', 'card h-100 border-dashed');
        const cardHeader = this.createElement('div', 'card-header compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body d-flex flex-column justify-content-center');
        
        // Header
        const title = this.createElement('div', 'fw-bold compact-title');
        title.innerHTML = '<i class="fas fa-plus"></i> Add Items';
        cardHeader.appendChild(title);
        
        // Body with buttons
        const buttonsContainer = this.createElement('div', 'd-flex flex-column gap-2');
        
        const buttons = [
            { text: 'Indicator', icon: 'fa-chart-line', onclick: () => this.addIndicator() },
            { text: 'Enter Long', icon: 'fa-arrow-up', onclick: () => this.addCondition('enter_long', isNestedStructure) },
            { text: 'Exit Long', icon: 'fa-arrow-down', onclick: () => this.addCondition('exit_long', isNestedStructure) },
            { text: 'Bar Config', icon: 'fa-bars', onclick: () => this.addBar(isNestedStructure) }
        ];
        
        buttons.forEach(btn => {
            const button = this.createElement('button', 'btn btn-outline-primary btn-sm');
            button.type = 'button';
            button.innerHTML = `<i class="fas ${btn.icon}"></i> ${btn.text}`;
            button.onclick = btn.onclick;
            buttonsContainer.appendChild(button);
        });
        
        cardBody.appendChild(buttonsContainer);
        
        card.appendChild(cardHeader);
        card.appendChild(cardBody);
        cardWrapper.appendChild(card);
        
        return cardWrapper;
    }

    /**
     * Create monitor configuration section
     */
    createMonitorSection(monitor, isNestedStructure = true) {
        const section = this.createSection('Monitor Configuration', 'monitor-config');
        const body = section.querySelector('.card-body');
        
        // Determine field path prefix based on structure
        const pathPrefix = isNestedStructure ? 'monitor.' : '';
        
        // Basic monitor info
        body.appendChild(this.createTextField(pathPrefix + 'name', 'Monitor Name', monitor.name));
        body.appendChild(this.createTextAreaField(pathPrefix + 'description', 'Description', monitor.description));
        
        // Trade executor subsection
        if (monitor.trade_executor) {
            body.appendChild(this.createTradeExecutorSubsection(monitor.trade_executor, pathPrefix));
        }
        
        // Enter/Exit conditions
        body.appendChild(this.createConditionsSubsection('enter_long', 'Enter Long Conditions', monitor.enter_long || [], pathPrefix));
        body.appendChild(this.createConditionsSubsection('exit_long', 'Exit Long Conditions', monitor.exit_long || [], pathPrefix));
        
        // Bars configuration
        body.appendChild(this.createBarsSubsection(monitor.bars || {}, pathPrefix));
        
        return section;
    }

    /**
     * Create trade executor subsection
     */
    createTradeExecutorSubsection(tradeExecutor, pathPrefix = 'monitor.') {
        const subsection = this.createSubsection('Trade Executor', 'trade-executor');
        
        const fields = [
            { key: 'default_position_size', label: 'Default Position Size', type: 'number', step: '0.01' },
            { key: 'stop_loss_pct', label: 'Stop Loss %', type: 'number', step: '0.001' },
            { key: 'take_profit_pct', label: 'Take Profit %', type: 'number', step: '0.001' },
            { key: 'ignore_bear_signals', label: 'Ignore Bear Signals', type: 'checkbox' },
            { key: 'trailing_stop_loss', label: 'Trailing Stop Loss', type: 'checkbox' },
            { key: 'trailing_stop_distance_pct', label: 'Trailing Stop Distance %', type: 'number', step: '0.001' },
            { key: 'trailing_stop_activation_pct', label: 'Trailing Stop Activation %', type: 'number', step: '0.001' }
        ];
        
        fields.forEach(field => {
            const fieldPath = `${pathPrefix}trade_executor.${field.key}`;
            if (field.type === 'checkbox') {
                subsection.appendChild(this.createCheckboxField(fieldPath, field.label, tradeExecutor[field.key]));
            } else {
                subsection.appendChild(this.createNumberField(fieldPath, field.label, tradeExecutor[field.key], field.step));
            }
        });
        
        return subsection;
    }

    /**
     * Create conditions subsection (enter_long/exit_long)
     */
    createConditionsSubsection(conditionType, label, conditions, pathPrefix = 'monitor.') {
        const subsection = this.createSubsection(label, conditionType);
        
        // Create responsive grid container for compact condition cards
        const conditionsContainer = this.createElement('div', 'conditions-container row');
        subsection.appendChild(conditionsContainer);
        
        conditions.forEach((condition, index) => {
            conditionsContainer.appendChild(this.createConditionItem(conditionType, condition, index, pathPrefix));
        });
        
        // Add button
        const addBtnContainer = this.createElement('div', 'col-12 mb-3');
        const addBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addBtn.type = 'button';
        addBtn.innerHTML = `<i class="fas fa-plus"></i> Add ${label.slice(0, -1)}`;
        addBtn.onclick = () => this.addCondition(conditionType, pathPrefix);
        addBtnContainer.appendChild(addBtn);
        conditionsContainer.appendChild(addBtnContainer);
        
        return subsection;
    }

    /**
     * Create individual condition item (compact card)
     */
    createConditionItem(conditionType, condition, index) {
        // Create responsive card wrapper for compact layout
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const item = this.createElement('div', 'condition-item card h-100');
        const cardHeader = this.createElement('div', 'card-header d-flex justify-content-between align-items-center compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body');
        
        // Compact header with condition info
        const titleContainer = this.createElement('div', 'd-flex flex-column');
        const mainTitle = this.createElement('div', 'fw-bold text-truncate compact-title');
        mainTitle.textContent = condition.name || 'Condition';
        mainTitle.title = `${condition.name} - Threshold: ${condition.threshold}`;
        
        const subtitle = this.createElement('small', 'text-muted text-truncate');
        subtitle.textContent = `Threshold: ${condition.threshold}`;
        
        titleContainer.appendChild(mainTitle);
        titleContainer.appendChild(subtitle);
        cardHeader.appendChild(titleContainer);
        
        const removeBtn = this.createElement('button', 'btn btn-outline-danger btn-xs');
        removeBtn.type = 'button';
        removeBtn.innerHTML = '<i class="fas fa-trash fa-xs"></i>';
        removeBtn.onclick = () => this.removeCondition(conditionType, index);
        cardHeader.appendChild(removeBtn);
        
        // Compact body with essential fields
        const compactForm = this.createElement('div', 'compact-form');
        
        // Name field (compact)
        const nameField = this.createElement('div', 'mb-2');
        const nameInput = this.createElement('input', 'form-control form-control-sm');
        nameInput.type = 'text';
        nameInput.name = `monitor.${conditionType}.${index}.name`;
        nameInput.value = condition.name || '';
        nameInput.placeholder = 'Condition Name';
        nameField.appendChild(nameInput);
        compactForm.appendChild(nameField);
        
        // Threshold field (compact)
        const thresholdField = this.createElement('div', 'mb-2');
        const thresholdInput = this.createElement('input', 'form-control form-control-sm');
        thresholdInput.type = 'number';
        thresholdInput.name = `monitor.${conditionType}.${index}.threshold`;
        thresholdInput.value = condition.threshold || 0;
        thresholdInput.step = '0.001';
        thresholdInput.placeholder = 'Threshold';
        thresholdField.appendChild(thresholdInput);
        compactForm.appendChild(thresholdField);
        
        cardBody.appendChild(compactForm);
        
        item.appendChild(cardHeader);
        item.appendChild(cardBody);
        cardWrapper.appendChild(item);
        
        return cardWrapper;
    }

    /**
     * Create bars subsection
     */
    createBarsSubsection(bars, pathPrefix = 'monitor.') {
        const subsection = this.createSubsection('Bars Configuration', 'bars');
        
        // Create responsive grid container for compact bar cards
        const barsContainer = this.createElement('div', 'bars-container row');
        subsection.appendChild(barsContainer);
        
        Object.entries(bars).forEach(([barName, barConfig]) => {
            barsContainer.appendChild(this.createBarItem(barName, barConfig, pathPrefix));
        });
        
        // Add button
        const addBtnContainer = this.createElement('div', 'col-12 mb-3');
        const addBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addBtn.type = 'button';
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Bar';
        addBtn.onclick = () => this.addBar(pathPrefix);
        addBtnContainer.appendChild(addBtn);
        barsContainer.appendChild(addBtnContainer);
        
        return subsection;
    }

    /**
     * Create individual bar item
     */
    createBarItem(barName, barConfig, pathPrefix = 'monitor.') {
        // Create responsive card wrapper for compact layout
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const item = this.createElement('div', 'bar-item card h-100');
        const cardHeader = this.createElement('div', 'card-header d-flex justify-content-between align-items-center compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body');
        
        // Compact header with bar info
        const titleContainer = this.createElement('div', 'd-flex flex-column');
        const mainTitle = this.createElement('div', 'fw-bold text-truncate compact-title');
        mainTitle.textContent = barName;
        mainTitle.title = `${barName} (${barConfig.type})`;
        
        const subtitle = this.createElement('small', 'text-muted text-truncate');
        subtitle.textContent = barConfig.type || 'bull';
        
        titleContainer.appendChild(mainTitle);
        titleContainer.appendChild(subtitle);
        cardHeader.appendChild(titleContainer);
        
        const removeBtn = this.createElement('button', 'btn btn-outline-danger btn-xs');
        removeBtn.type = 'button';
        removeBtn.innerHTML = '<i class="fas fa-trash fa-xs"></i>';
        removeBtn.onclick = () => this.removeBar(barName, pathPrefix);
        cardHeader.appendChild(removeBtn);
        
        // Compact body with essential fields
        const compactForm = this.createElement('div', 'compact-form');
        
        // Type field (compact)
        const typeField = this.createElement('div', 'mb-2');
        const typeSelect = this.createElement('select', 'form-select form-select-sm');
        typeSelect.name = `${pathPrefix}bars.${barName}.type`;
        ['bull', 'bear'].forEach(type => {
            const option = this.createElement('option');
            option.value = type;
            option.textContent = type;
            if (type === barConfig.type) option.selected = true;
            typeSelect.appendChild(option);
        });
        typeField.appendChild(typeSelect);
        compactForm.appendChild(typeField);
        
        // Description field (compact)
        const descField = this.createElement('div', 'mb-2');
        const descInput = this.createElement('input', 'form-control form-control-sm');
        descInput.type = 'text';
        descInput.name = `${pathPrefix}bars.${barName}.description`;
        descInput.value = barConfig.description || '';
        descInput.placeholder = 'Description';
        descField.appendChild(descInput);
        compactForm.appendChild(descField);
        
        // Compact indicators summary
        if (barConfig.indicators && Object.keys(barConfig.indicators).length > 0) {
            const indicatorsInfo = this.createElement('div', 'compact-params');
            const indicatorsLabel = this.createElement('small', 'text-muted fw-bold');
            indicatorsLabel.textContent = 'Indicators:';
            indicatorsInfo.appendChild(indicatorsLabel);
            
            const indicatorsList = this.createElement('div', 'params-list');
            Object.entries(barConfig.indicators).forEach(([name, weight]) => {
                const indicatorBadge = this.createElement('span', 'badge bg-secondary me-1 mb-1 param-badge');
                indicatorBadge.textContent = `${name}: ${weight}`;
                indicatorBadge.onclick = () => this.editBarIndicator(barName, name, weight, pathPrefix);
                indicatorBadge.style.cursor = 'pointer';
                indicatorBadge.title = 'Click to edit';
                indicatorsList.appendChild(indicatorBadge);
            });
            indicatorsInfo.appendChild(indicatorsList);
            compactForm.appendChild(indicatorsInfo);
        }
        
        // Add indicator button
        const addIndicatorBtn = this.createElement('button', 'btn btn-outline-primary btn-xs w-100 mt-2');
        addIndicatorBtn.type = 'button';
        addIndicatorBtn.innerHTML = '<i class="fas fa-plus fa-xs"></i> Add Indicator';
        addIndicatorBtn.onclick = () => this.addIndicatorToBar(barName, pathPrefix);
        compactForm.appendChild(addIndicatorBtn);
        
        cardBody.appendChild(compactForm);
        
        item.appendChild(cardHeader);
        item.appendChild(cardBody);
        cardWrapper.appendChild(item);
        
        return cardWrapper;
    }

    /**
     * Create individual indicator item within a bar
     */
    createBarIndicatorItem(barName, indicatorName, weight, pathPrefix = 'monitor.') {
        const indicatorRow = this.createElement('div', 'row mb-2 align-items-end');
        
        const nameCol = this.createElement('div', 'col-md-6');
        nameCol.appendChild(this.createTextField(`${pathPrefix}bars.${barName}.indicators.${indicatorName}`, 'Indicator Name', indicatorName, true));
        indicatorRow.appendChild(nameCol);
        
        const weightCol = this.createElement('div', 'col-md-4');
        weightCol.appendChild(this.createNumberField(`${pathPrefix}bars.${barName}.indicators.${indicatorName}`, 'Weight', weight, '0.1'));
        indicatorRow.appendChild(weightCol);
        
        const actionCol = this.createElement('div', 'col-md-2');
        const removeIndicatorBtn = this.createElement('button', 'btn btn-outline-danger btn-sm');
        removeIndicatorBtn.type = 'button';
        removeIndicatorBtn.innerHTML = '<i class="fas fa-trash"></i>';
        removeIndicatorBtn.onclick = () => this.removeIndicatorFromBar(barName, indicatorName, pathPrefix);
        actionCol.appendChild(removeIndicatorBtn);
        indicatorRow.appendChild(actionCol);
        
        return indicatorRow;
    }

    /**
     * Create indicators section
     */
    createIndicatorsSection(indicators) {
        const section = this.createSection('Indicators Configuration', 'indicators');
        const body = section.querySelector('.card-body');
        
        // Create responsive grid container for compact cards
        const indicatorsContainer = this.createElement('div', 'indicators-container row');
        body.appendChild(indicatorsContainer);
        
        indicators.forEach((indicator, index) => {
            indicatorsContainer.appendChild(this.createIndicatorItem(indicator, index));
        });
        
        // Add button
        const addBtnContainer = this.createElement('div', 'col-12 mb-3');
        const addBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addBtn.type = 'button';
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Indicator';
        addBtn.onclick = () => this.addIndicator();
        addBtnContainer.appendChild(addBtn);
        indicatorsContainer.appendChild(addBtnContainer);
        
        return section;
    }

    /**
     * Create individual indicator item
     */
    createIndicatorItem(indicator, index) {
        // Create responsive card wrapper for compact layout
        const cardWrapper = this.createElement('div', 'col-xl-3 col-lg-4 col-md-6 col-12 mb-3');
        
        const item = this.createElement('div', 'indicator-item card h-100');
        const cardHeader = this.createElement('div', 'card-header d-flex justify-content-between align-items-center compact-card-header');
        const cardBody = this.createElement('div', 'card-body compact-card-body');
        
        // Compact header with title and remove button
        const titleContainer = this.createElement('div', 'd-flex flex-column');
        const mainTitle = this.createElement('div', 'fw-bold text-truncate compact-title');
        mainTitle.textContent = indicator.name || 'Indicator';
        mainTitle.title = `${indicator.name} (${indicator.function})`;
        
        const subtitle = this.createElement('small', 'text-muted text-truncate');
        subtitle.textContent = indicator.function || 'Function';
        
        titleContainer.appendChild(mainTitle);
        titleContainer.appendChild(subtitle);
        cardHeader.appendChild(titleContainer);
        
        const removeBtn = this.createElement('button', 'btn btn-outline-danger btn-xs');
        removeBtn.type = 'button';
        removeBtn.innerHTML = '<i class="fas fa-trash fa-xs"></i>';
        removeBtn.onclick = () => this.removeIndicator(index);
        cardHeader.appendChild(removeBtn);
        
        // Compact body with essential fields only
        const compactForm = this.createElement('div', 'compact-form');
        
        // Name field (compact)
        const nameField = this.createElement('div', 'mb-2');
        const nameInput = this.createElement('input', 'form-control form-control-sm');
        nameInput.type = 'text';
        nameInput.name = `indicators.${index}.name`;
        nameInput.value = indicator.name || '';
        nameInput.placeholder = 'Indicator Name';
        nameField.appendChild(nameInput);
        compactForm.appendChild(nameField);
        
        // Function field (compact)
        const functionField = this.createElement('div', 'mb-2');
        const functionSelect = this.createElement('select', 'form-select form-select-sm');
        functionSelect.name = `indicators.${index}.function`;
        const functionTypes = window.IndicatorParameterUtils ? 
            window.IndicatorParameterUtils.getIndicatorTypes() : 
            this.options.indicatorTypes;
        functionTypes.forEach(type => {
            const option = this.createElement('option');
            option.value = type;
            option.textContent = type;
            if (type === indicator.function) option.selected = true;
            functionSelect.appendChild(option);
        });
        
        // Add change handler
        functionSelect.addEventListener('change', (e) => {
            this.onIndicatorFunctionChange(index, e.target.value);
        });
        functionField.appendChild(functionSelect);
        compactForm.appendChild(functionField);
        
        // Agg Config field (compact)
        const aggField = this.createElement('div', 'mb-2');
        const aggSelect = this.createElement('select', 'form-select form-select-sm');
        aggSelect.name = `indicators.${index}.agg_config`;
        const aggOptions = window.IndicatorParameterUtils ? 
            window.IndicatorParameterUtils.getAggConfigs() : 
            ['1m-normal', '5m-normal', '15m-normal', '30m-normal', '1h-normal', '4h-normal', '1d-normal'];
        aggOptions.forEach(option => {
            const opt = this.createElement('option');
            opt.value = option;
            opt.textContent = option;
            if (option === indicator.agg_config) opt.selected = true;
            aggSelect.appendChild(opt);
        });
        aggField.appendChild(aggSelect);
        compactForm.appendChild(aggField);
        
        // Compact parameters summary
        if (indicator.parameters && Object.keys(indicator.parameters).length > 0) {
            const paramsInfo = this.createElement('div', 'compact-params');
            const paramsLabel = this.createElement('small', 'text-muted fw-bold');
            paramsLabel.textContent = 'Parameters:';
            paramsInfo.appendChild(paramsLabel);
            
            const paramsList = this.createElement('div', 'params-list');
            Object.entries(indicator.parameters).forEach(([key, value]) => {
                const paramBadge = this.createElement('span', 'badge bg-secondary me-1 mb-1 param-badge');
                paramBadge.textContent = `${key}: ${value}`;
                paramBadge.onclick = () => this.editParameter(index, key, value);
                paramBadge.style.cursor = 'pointer';
                paramBadge.title = 'Click to edit';
                paramsList.appendChild(paramBadge);
            });
            paramsInfo.appendChild(paramsList);
            compactForm.appendChild(paramsInfo);
        }
        
        cardBody.appendChild(compactForm);
        
        item.appendChild(cardHeader);
        item.appendChild(cardBody);
        cardWrapper.appendChild(item);
        
        return cardWrapper;
    }

    /**
     * Create parameters subsection for indicators
     */
    createParametersSubsection(parameters, indicatorIndex) {
        const subsection = this.createElement('div', 'mt-3');
        const label = this.createElement('label', 'form-label fw-bold');
        label.textContent = 'Parameters';
        subsection.appendChild(label);
        
        const parametersContainer = this.createElement('div', 'parameters-container');
        
        // Get parameter definitions if available
        const indicator = this.formData.indicators[indicatorIndex];
        const paramDefinitions = window.IndicatorParameterUtils ? 
            window.IndicatorParameterUtils.getParameterDefinition(indicator.function) : 
            null;
        
        Object.entries(parameters).forEach(([paramName, paramValue]) => {
            const paramDef = paramDefinitions?.parameters?.[paramName];
            
            const paramRow = this.createElement('div', 'row mb-2 align-items-end');
            
            // Parameter name (readonly)
            const nameCol = this.createElement('div', 'col-md-3');
            const nameLabel = this.createElement('label', 'form-label fw-bold');
            nameLabel.textContent = paramName;
            if (paramDef?.description) {
                nameLabel.title = paramDef.description;
                nameLabel.classList.add('text-info');
            }
            nameCol.appendChild(nameLabel);
            paramRow.appendChild(nameCol);
            
            // Parameter value field
            const valueCol = this.createElement('div', 'col-md-6');
            const valueField = this.createParameterField(
                `indicators.${indicatorIndex}.parameters.${paramName}`, 
                paramValue, 
                paramDef
            );
            valueCol.appendChild(valueField);
            paramRow.appendChild(valueCol);
            
            // Description (if available)
            if (paramDef?.description) {
                const descCol = this.createElement('div', 'col-md-3');
                const descText = this.createElement('small', 'text-muted');
                descText.textContent = paramDef.description;
                descCol.appendChild(descText);
                paramRow.appendChild(descCol);
            }
            
            parametersContainer.appendChild(paramRow);
        });
        
        subsection.appendChild(parametersContainer);
        return subsection;
    }

    /**
     * Create parameter field with proper validation based on definition
     */
    createParameterField(fieldName, value, paramDef) {
        if (!paramDef) {
            return this.createValueField(fieldName, value);
        }
        
        const group = this.createElement('div', 'mb-0');
        let input;
        
        if (paramDef.type === 'select') {
            input = this.createElement('select', 'form-select form-select-sm');
            input.name = fieldName;
            input.id = fieldName;
            
            paramDef.options.forEach(option => {
                const optionElem = this.createElement('option');
                optionElem.value = option;
                optionElem.textContent = option;
                if (option === value) optionElem.selected = true;
                input.appendChild(optionElem);
            });
            
        } else if (paramDef.type === 'int' || paramDef.type === 'float') {
            input = this.createElement('input', 'form-control form-control-sm');
            input.type = 'number';
            input.name = fieldName;
            input.id = fieldName;
            input.value = value || paramDef.default || 0;
            
            if (paramDef.min !== undefined) input.min = paramDef.min;
            if (paramDef.max !== undefined) input.max = paramDef.max;
            if (paramDef.step !== undefined) input.step = paramDef.step;
            if (paramDef.type === 'int') input.step = input.step || 1;
            if (paramDef.type === 'float') input.step = input.step || 0.001;
            
        } else {
            // Default to text input
            input = this.createElement('input', 'form-control form-control-sm');
            input.type = 'text';
            input.name = fieldName;
            input.id = fieldName;
            input.value = value || paramDef.default || '';
        }
        
        if (paramDef.required) {
            input.required = true;
        }
        
        group.appendChild(input);
        return group;
    }

    /**
     * Create ranges subsection for GA optimization
     */
    createRangesSubsection(ranges, indicatorIndex) {
        const subsection = this.createElement('div', 'mt-3');
        const label = this.createElement('label', 'form-label fw-bold');
        label.textContent = 'Ranges (GA Optimization)';
        subsection.appendChild(label);
        
        const rangesContainer = this.createElement('div', 'ranges-container');
        
        Object.entries(ranges).forEach(([rangeName, rangeConfig]) => {
            if (rangeConfig.t === 'skip') return;
            
            const rangeRow = this.createElement('div', 'row mb-2 align-items-center');
            
            const nameCol = this.createElement('div', 'col-md-3');
            const nameLabel = this.createElement('label', 'form-label');
            nameLabel.textContent = rangeName;
            nameCol.appendChild(nameLabel);
            rangeRow.appendChild(nameCol);
            
            const typeCol = this.createElement('div', 'col-md-2');
            typeCol.appendChild(this.createSelectField(`indicators.${indicatorIndex}.ranges.${rangeName}.t`, 'Type', rangeConfig.t, ['int', 'float']));
            rangeRow.appendChild(typeCol);
            
            const minCol = this.createElement('div', 'col-md-3');
            minCol.appendChild(this.createNumberField(`indicators.${indicatorIndex}.ranges.${rangeName}.r.0`, 'Min', rangeConfig.r[0], rangeConfig.t === 'int' ? '1' : '0.001'));
            rangeRow.appendChild(minCol);
            
            const maxCol = this.createElement('div', 'col-md-3');
            maxCol.appendChild(this.createNumberField(`indicators.${indicatorIndex}.ranges.${rangeName}.r.1`, 'Max', rangeConfig.r[1], rangeConfig.t === 'int' ? '1' : '0.001'));
            rangeRow.appendChild(maxCol);
            
            rangesContainer.appendChild(rangeRow);
        });
        
        subsection.appendChild(rangesContainer);
        return subsection;
    }

    /**
     * Helper method to create value field based on type
     */
    createValueField(path, value) {
        if (typeof value === 'boolean') {
            return this.createCheckboxField(path, '', value).querySelector('input');
        } else if (typeof value === 'number') {
            return this.createNumberField(path, '', value, typeof value % 1 === 0 ? '1' : '0.001').querySelector('input');
        } else {
            return this.createTextField(path, '', value).querySelector('input');
        }
    }

    /**
     * Helper methods for creating form elements
     */
    createElement(tag, classes = '', extraClass = '') {
        const element = document.createElement(tag);
        if (classes) element.className = classes;
        if (extraClass) element.classList.add(extraClass);
        return element;
    }

    createSection(title, id) {
        const section = this.createElement('div', 'config-section card mb-4');
        section.id = id;
        
        const header = this.createElement('div', 'card-header');
        header.style.cursor = 'pointer';
        header.style.userSelect = 'none';
        
        const headerContent = this.createElement('div', 'd-flex justify-content-between align-items-center');
        
        const headerTitle = this.createElement('h5', 'mb-0');
        headerTitle.textContent = title;
        headerContent.appendChild(headerTitle);
        
        const collapseIcon = this.createElement('i', 'fas fa-chevron-down');
        collapseIcon.style.transition = 'transform 0.3s ease';
        headerContent.appendChild(collapseIcon);
        
        header.appendChild(headerContent);
        
        const body = this.createElement('div', 'card-body');
        body.id = `${id}-body`;
        
        // Add click handler for collapse functionality
        header.onclick = () => this.toggleSection(id);
        
        section.appendChild(header);
        section.appendChild(body);
        
        return section;
    }

    toggleSection(sectionId) {
        const body = document.getElementById(`${sectionId}-body`);
        const icon = document.querySelector(`#${sectionId} .fa-chevron-down`);
        
        if (!body || !icon) return;
        
        if (body.style.display === 'none') {
            body.style.display = 'block';
            icon.style.transform = 'rotate(0deg)';
        } else {
            body.style.display = 'none';
            icon.style.transform = 'rotate(-90deg)';
        }
    }

    createSubsection(title, id) {
        const subsection = this.createElement('div', 'config-subsection mb-3');
        subsection.id = id;
        
        const title_elem = this.createElement('h6', 'fw-bold mb-3');
        title_elem.textContent = title;
        subsection.appendChild(title_elem);
        
        return subsection;
    }

    createTextField(name, label, value = '') {
        const group = this.createElement('div', 'mb-3');
        
        if (label) {
            const labelElem = this.createElement('label', 'form-label');
            labelElem.textContent = label;
            labelElem.setAttribute('for', name);
            group.appendChild(labelElem);
        }
        
        const input = this.createElement('input', 'form-control');
        input.type = 'text';
        input.name = name;
        input.id = name;
        input.value = value || '';
        
        group.appendChild(input);
        return group;
    }

    createTextAreaField(name, label, value = '') {
        const group = this.createElement('div', 'mb-3');
        
        const labelElem = this.createElement('label', 'form-label');
        labelElem.textContent = label;
        labelElem.setAttribute('for', name);
        group.appendChild(labelElem);
        
        const textarea = this.createElement('textarea', 'form-control');
        textarea.name = name;
        textarea.id = name;
        textarea.rows = 3;
        textarea.value = value || '';
        
        group.appendChild(textarea);
        return group;
    }

    createNumberField(name, label, value = 0, step = '1') {
        const group = this.createElement('div', 'mb-3');
        
        if (label) {
            const labelElem = this.createElement('label', 'form-label');
            labelElem.textContent = label;
            labelElem.setAttribute('for', name);
            group.appendChild(labelElem);
        }
        
        const input = this.createElement('input', 'form-control');
        input.type = 'number';
        input.name = name;
        input.id = name;
        input.value = value || 0;
        input.step = step;
        
        group.appendChild(input);
        return group;
    }

    createCheckboxField(name, label, checked = false) {
        const group = this.createElement('div', 'mb-3 form-check');
        
        const input = this.createElement('input', 'form-check-input');
        input.type = 'checkbox';
        input.name = name;
        input.id = name;
        input.checked = checked;
        
        const labelElem = this.createElement('label', 'form-check-label');
        labelElem.textContent = label;
        labelElem.setAttribute('for', name);
        
        group.appendChild(input);
        group.appendChild(labelElem);
        return group;
    }

    createSelectField(name, label, value = '', options = []) {
        const group = this.createElement('div', 'mb-3');
        
        if (label) {
            const labelElem = this.createElement('label', 'form-label');
            labelElem.textContent = label;
            labelElem.setAttribute('for', name);
            group.appendChild(labelElem);
        }
        
        const select = this.createElement('select', 'form-select');
        select.name = name;
        select.id = name;
        
        options.forEach(option => {
            const optionElem = this.createElement('option');
            optionElem.value = option;
            optionElem.textContent = option;
            if (option === value) {
                optionElem.selected = true;
            }
            select.appendChild(optionElem);
        });
        
        group.appendChild(select);
        return group;
    }

    createFormActions() {
        const actions = this.createElement('div', 'form-actions mt-4 d-flex gap-2');
        
        const saveBtn = this.createElement('button', 'btn btn-success');
        saveBtn.type = 'button';
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Configuration';
        saveBtn.onclick = () => this.saveConfiguration();
        
        const resetBtn = this.createElement('button', 'btn btn-secondary');
        resetBtn.type = 'button';
        resetBtn.innerHTML = '<i class="fas fa-undo"></i> Reset';
        resetBtn.onclick = () => this.resetForm();
        
        actions.appendChild(saveBtn);
        actions.appendChild(resetBtn);
        
        return actions;
    }

    /**
     * Event handlers and form management
     */
    attachEventHandlers() {
        // Add real-time validation
        const inputs = this.container.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('input', (e) => this.validateField(e.target));
            input.addEventListener('change', (e) => this.updateFormData(e.target));
        });
    }

    validateField(field) {
        field.classList.remove('is-invalid', 'is-valid');
        
        let isValid = field.checkValidity();
        
        // Additional validation using parameter definitions
        if (window.IndicatorParameterUtils && field.name.includes('indicators.') && field.name.includes('.parameters.')) {
            const pathParts = field.name.split('.');
            const indicatorIndex = parseInt(pathParts[1]);
            const paramName = pathParts[3];
            
            const indicator = this.formData.indicators?.[indicatorIndex];
            if (indicator) {
                const paramDef = window.IndicatorParameterUtils
                    .getParameterDefinition(indicator.function)?.parameters?.[paramName];
                
                if (paramDef) {
                    const value = field.value;
                    
                    // Type-specific validation
                    if (paramDef.type === 'int' && value !== '' && !Number.isInteger(Number(value))) {
                        isValid = false;
                    } else if (paramDef.type === 'float' && value !== '' && isNaN(Number(value))) {
                        isValid = false;
                    }
                    
                    // Range validation
                    const numValue = Number(value);
                    if (!isNaN(numValue)) {
                        if (paramDef.min !== undefined && numValue < paramDef.min) isValid = false;
                        if (paramDef.max !== undefined && numValue > paramDef.max) isValid = false;
                    }
                }
            }
        }
        
        if (isValid) {
            field.classList.add('is-valid');
        } else {
            field.classList.add('is-invalid');
        }
        
        return isValid;
    }

    updateFormData(field) {
        // Update internal form data structure
        const path = field.name;
        const value = field.type === 'checkbox' ? field.checked : 
                     field.type === 'number' ? parseFloat(field.value) || 0 : 
                     field.value;
        
        this.setNestedValue(this.formData, path, value);
    }

    setNestedValue(obj, path, value) {
        const keys = path.split('.');
        let current = obj;
        
        for (let i = 0; i < keys.length - 1; i++) {
            const key = keys[i];
            if (!current[key]) {
                current[key] = {};
            }
            current = current[key];
        }
        
        current[keys[keys.length - 1]] = value;
    }

    /**
     * Dynamic add/remove methods
     */
    addCondition(conditionType) {
        if (!this.formData.monitor) this.formData.monitor = {};
        if (!this.formData.monitor[conditionType]) this.formData.monitor[conditionType] = [];
        
        // Add new condition with default values
        const newCondition = {
            name: `new_condition_${Date.now()}`,
            threshold: 0.5
        };
        
        this.formData.monitor[conditionType].push(newCondition);
        
        // Regenerate the conditions section
        this.regenerateConditionsSection(conditionType);
    }

    removeCondition(conditionType, index) {
        if (!this.formData.monitor || !this.formData.monitor[conditionType]) return;
        
        // Remove from data
        this.formData.monitor[conditionType].splice(index, 1);
        
        // Regenerate the conditions section
        this.regenerateConditionsSection(conditionType);
    }

    regenerateConditionsSection(conditionType) {
        const container = this.container.querySelector(`#${conditionType} .conditions-container.row`);
        if (!container) return;
        
        container.innerHTML = '';
        
        const conditions = this.formData.monitor[conditionType] || [];
        conditions.forEach((condition, index) => {
            container.appendChild(this.createConditionItem(conditionType, condition, index));
        });
        
        // Re-add the add button
        const addBtnContainer = this.createElement('div', 'col-12 mb-3');
        const addBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addBtn.type = 'button';
        addBtn.innerHTML = `<i class="fas fa-plus"></i> Add Condition`;
        addBtn.onclick = () => this.addCondition(conditionType, 'monitor.');
        addBtnContainer.appendChild(addBtn);
        container.appendChild(addBtnContainer);
    }

    addBar(pathPrefix = 'monitor.') {
        // Handle both nested and flat structures
        const barsPath = pathPrefix ? `${pathPrefix.replace('.', '')}.bars` : 'bars';
        
        if (pathPrefix === 'monitor.') {
            if (!this.formData.monitor) this.formData.monitor = {};
            if (!this.formData.monitor.bars) this.formData.monitor.bars = {};
        } else {
            if (!this.formData.bars) this.formData.bars = {};
        }
        
        // Generate unique bar name
        const barName = `new_bar_${Date.now()}`;
        
        // Add new bar with default structure
        const newBar = {
            type: "bull",
            description: "New bar description",
            indicators: {}
        };
        
        if (pathPrefix === 'monitor.') {
            this.formData.monitor.bars[barName] = newBar;
        } else {
            this.formData.bars[barName] = newBar;
        }
        
        // Regenerate bars section
        this.regenerateBarsSection(pathPrefix);
    }

    removeBar(barName, pathPrefix = 'monitor.') {
        if (pathPrefix === 'monitor.') {
            if (!this.formData.monitor || !this.formData.monitor.bars) return;
            delete this.formData.monitor.bars[barName];
        } else {
            if (!this.formData.bars) return;
            delete this.formData.bars[barName];
        }
        
        // Regenerate bars section
        this.regenerateBarsSection(pathPrefix);
    }

    regenerateBarsSection(pathPrefix = 'monitor.') {
        const container = this.container.querySelector('#bars .bars-container.row');
        if (!container) return;
        
        container.innerHTML = '';
        
        const bars = pathPrefix === 'monitor.' ? 
            (this.formData.monitor?.bars || {}) : 
            (this.formData.bars || {});
            
        Object.entries(bars).forEach(([barName, barConfig]) => {
            container.appendChild(this.createBarItem(barName, barConfig, pathPrefix));
        });
        
        // Re-add the add button
        const addBtnContainer = this.createElement('div', 'col-12 mb-3');
        const addBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addBtn.type = 'button';
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Bar';
        addBtn.onclick = () => this.addBar(pathPrefix);
        addBtnContainer.appendChild(addBtn);
        container.appendChild(addBtnContainer);
    }

    addIndicatorToBar(barName, pathPrefix = 'monitor.') {
        // Prompt user for indicator name
        const indicatorName = prompt('Enter indicator name:');
        if (!indicatorName) return;
        
        // Initialize structure if needed
        if (pathPrefix === 'monitor.') {
            if (!this.formData.monitor) this.formData.monitor = {};
            if (!this.formData.monitor.bars) this.formData.monitor.bars = {};
            if (!this.formData.monitor.bars[barName]) this.formData.monitor.bars[barName] = {};
            if (!this.formData.monitor.bars[barName].indicators) this.formData.monitor.bars[barName].indicators = {};
            
            // Add indicator with default weight
            this.formData.monitor.bars[barName].indicators[indicatorName] = 1.0;
        } else {
            if (!this.formData.bars) this.formData.bars = {};
            if (!this.formData.bars[barName]) this.formData.bars[barName] = {};
            if (!this.formData.bars[barName].indicators) this.formData.bars[barName].indicators = {};
            
            // Add indicator with default weight
            this.formData.bars[barName].indicators[indicatorName] = 1.0;
        }
        
        // Regenerate bars section to show new indicator
        this.regenerateBarsSection(pathPrefix);
    }

    removeIndicatorFromBar(barName, indicatorName, pathPrefix = 'monitor.') {
        if (pathPrefix === 'monitor.') {
            if (!this.formData.monitor?.bars?.[barName]?.indicators) return;
            delete this.formData.monitor.bars[barName].indicators[indicatorName];
        } else {
            if (!this.formData.bars?.[barName]?.indicators) return;
            delete this.formData.bars[barName].indicators[indicatorName];
        }
        
        // Regenerate bars section to reflect removal
        this.regenerateBarsSection(pathPrefix);
    }

    addIndicator() {
        if (!this.formData.indicators) this.formData.indicators = [];
        
        // Create new indicator with default type
        const defaultType = window.IndicatorParameterUtils ? 
            window.IndicatorParameterUtils.getIndicatorTypes()[0] : 
            'macd_histogram_crossover';
        
        const newIndicator = window.IndicatorParameterUtils ? 
            window.IndicatorParameterUtils.createIndicatorTemplate(defaultType) :
            {
                name: `indicator_${Date.now()}`,
                type: "Indicator", 
                function: defaultType,
                agg_config: "5m-normal",
                calc_on_pip: false,
                parameters: {},
                ranges: {}
            };
        
        this.formData.indicators.push(newIndicator);
        
        // Regenerate indicators section
        this.regenerateIndicatorsSection();
    }

    removeIndicator(index) {
        if (!this.formData.indicators) return;
        
        // Remove from data
        this.formData.indicators.splice(index, 1);
        
        // Regenerate indicators section
        this.regenerateIndicatorsSection();
    }

    regenerateIndicatorsSection() {
        const container = this.container.querySelector('#indicators .indicators-container.row');
        if (!container) return;
        
        container.innerHTML = '';
        
        const indicators = this.formData.indicators || [];
        indicators.forEach((indicator, index) => {
            container.appendChild(this.createIndicatorItem(indicator, index));
        });
        
        // Re-add the add button
        const addBtnContainer = this.createElement('div', 'col-12 mb-3');
        const addBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addBtn.type = 'button';
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Indicator';
        addBtn.onclick = () => this.addIndicator();
        addBtnContainer.appendChild(addBtn);
        container.appendChild(addBtnContainer);
    }

    /**
     * Handle indicator function change - regenerate parameters
     */
    onIndicatorFunctionChange(index, newFunction) {
        if (!this.formData.indicators || !this.formData.indicators[index]) return;
        
        // Update function
        this.formData.indicators[index].function = newFunction;
        
        // Regenerate parameters and ranges if utility is available
        if (window.IndicatorParameterUtils) {
            this.formData.indicators[index].parameters = 
                window.IndicatorParameterUtils.generateDefaultParameters(newFunction);
            
            if (this.options.showGAFields) {
                this.formData.indicators[index].ranges = 
                    window.IndicatorParameterUtils.generateGARanges(newFunction);
            }
        }
        
        // Regenerate just this indicator
        const container = this.container.querySelector('#indicators .indicators-container');
        const indicatorElements = container.querySelectorAll('.indicator-item');
        
        if (indicatorElements[index]) {
            const newIndicatorElement = this.createIndicatorItem(this.formData.indicators[index], index);
            container.replaceChild(newIndicatorElement, indicatorElements[index]);
        }
    }

    /**
     * Form actions
     */
    saveConfiguration() {
        // Collect all form data and send to backend
        console.log('Saving configuration:', this.formData);
        
        // Trigger save event
        const saveEvent = new CustomEvent('configSave', {
            detail: this.formData
        });
        this.container.dispatchEvent(saveEvent);
    }

    resetForm() {
        // Reset form to original state
        window.location.reload();
    }

    /**
     * Edit parameter in a compact way
     */
    editParameter(indicatorIndex, paramKey, currentValue) {
        const newValue = prompt(`Edit ${paramKey}:`, currentValue);
        if (newValue !== null && newValue !== currentValue) {
            // Update form data
            if (!this.formData.indicators[indicatorIndex].parameters) {
                this.formData.indicators[indicatorIndex].parameters = {};
            }
            this.formData.indicators[indicatorIndex].parameters[paramKey] = newValue;
            
            // Regenerate the indicator card
            this.regenerateIndicatorCard(indicatorIndex);
        }
    }

    /**
     * Edit bar indicator weight
     */
    editBarIndicator(barName, indicatorName, currentWeight, pathPrefix = 'monitor.') {
        const newWeight = prompt(`Edit weight for ${indicatorName}:`, currentWeight);
        if (newWeight !== null && newWeight !== currentWeight) {
            const weightValue = parseFloat(newWeight) || 0;
            
            // Update form data
            if (pathPrefix === 'monitor.') {
                if (!this.formData.monitor) this.formData.monitor = {};
                if (!this.formData.monitor.bars) this.formData.monitor.bars = {};
                if (!this.formData.monitor.bars[barName]) this.formData.monitor.bars[barName] = {};
                if (!this.formData.monitor.bars[barName].indicators) this.formData.monitor.bars[barName].indicators = {};
                this.formData.monitor.bars[barName].indicators[indicatorName] = weightValue;
            } else {
                if (!this.formData.bars) this.formData.bars = {};
                if (!this.formData.bars[barName]) this.formData.bars[barName] = {};
                if (!this.formData.bars[barName].indicators) this.formData.bars[barName].indicators = {};
                this.formData.bars[barName].indicators[indicatorName] = weightValue;
            }
            
            // Regenerate bars section
            this.regenerateBarsSection(pathPrefix);
        }
    }
    
    /**
     * Regenerate a single indicator card
     */
    regenerateIndicatorCard(index) {
        const container = this.container.querySelector('.indicators-container.row');
        if (!container) return;
        
        // Find and replace the specific card
        const cards = container.querySelectorAll('[class*="col-xl-3"]');
        if (cards[index]) {
            const newCard = this.createIndicatorItem(this.formData.indicators[index], index);
            cards[index].replaceWith(newCard);
        }
    }

    /**
     * Add condition
     */
    addCondition(conditionType, isNestedStructure) {
        const pathPrefix = isNestedStructure ? 'monitor.' : '';
        const conditionsPath = isNestedStructure ? 
            (this.formData.monitor = this.formData.monitor || {})[conditionType] = this.formData.monitor[conditionType] || [] :
            (this.formData[conditionType] = this.formData[conditionType] || []);
        
        const newCondition = {
            name: `${conditionType}_condition`,
            threshold: 0
        };
        
        if (isNestedStructure) {
            this.formData.monitor[conditionType].push(newCondition);
        } else {
            this.formData[conditionType].push(newCondition);
        }
        
        // Regenerate form
        this.regenerateForm();
    }

    /**
     * Remove condition
     */
    removeCondition(conditionType, index, isNestedStructure) {
        if (isNestedStructure) {
            if (this.formData.monitor && this.formData.monitor[conditionType]) {
                this.formData.monitor[conditionType].splice(index, 1);
            }
        } else {
            if (this.formData[conditionType]) {
                this.formData[conditionType].splice(index, 1);
            }
        }
        
        // Regenerate form
        this.regenerateForm();
    }

    /**
     * Add bar
     */
    addBar(isNestedStructure) {
        const barName = prompt('Enter bar name:', 'new_bar');
        if (!barName) return;
        
        const newBar = {
            type: 'bull',
            indicators: {}
        };
        
        if (isNestedStructure) {
            if (!this.formData.monitor) this.formData.monitor = {};
            if (!this.formData.monitor.bars) this.formData.monitor.bars = {};
            this.formData.monitor.bars[barName] = newBar;
        } else {
            if (!this.formData.bars) this.formData.bars = {};
            this.formData.bars[barName] = newBar;
        }
        
        // Regenerate form
        this.regenerateForm();
    }

    /**
     * Remove bar
     */
    removeBar(barName, isNestedStructure) {
        if (isNestedStructure) {
            if (this.formData.monitor && this.formData.monitor.bars) {
                delete this.formData.monitor.bars[barName];
            }
        } else {
            if (this.formData.bars) {
                delete this.formData.bars[barName];
            }
        }
        
        // Regenerate form
        this.regenerateForm();
    }

    /**
     * Regenerate entire form
     */
    regenerateForm() {
        this.generateForm(this.formData);
    }

    /**
     * Get current form data
     */
    getFormData() {
        return this.formData;
    }
}

// Export for use in other modules
window.ConfigFormBuilder = ConfigFormBuilder;