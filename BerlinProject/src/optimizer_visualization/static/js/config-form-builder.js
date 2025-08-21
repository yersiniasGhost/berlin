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
        
        // Generate sections based on config structure
        if (isNestedStructure && config.test_name) {
            form.appendChild(this.createTestNameSection(config.test_name));
        }
        
        if (monitorData) {
            form.appendChild(this.createMonitorSection(monitorData, isNestedStructure));
        }
        
        if (config.indicators) {
            form.appendChild(this.createIndicatorsSection(config.indicators));
        }
        
        // GA-specific sections (only for optimizer)
        if (this.options.showGAFields) {
            if (config.objectives) {
                form.appendChild(this.createObjectivesSection(config.objectives));
            }
            
            if (config.ga_hyperparameters) {
                form.appendChild(this.createGAHyperparametersSection(config.ga_hyperparameters));
            }
        }
        
        // Form actions
        form.appendChild(this.createFormActions());
        
        this.container.appendChild(form);
        this.attachEventHandlers();
        
        return form;
    }

    /**
     * Create test name section
     */
    createTestNameSection(testName) {
        const section = this.createSection('Test Configuration', 'test-config');
        const body = section.querySelector('.card-body');
        
        const testNameField = this.createTextField('test_name', 'Test Name', testName);
        body.appendChild(testNameField);
        
        return section;
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
        
        const conditionsContainer = this.createElement('div', 'conditions-container');
        subsection.appendChild(conditionsContainer);
        
        conditions.forEach((condition, index) => {
            conditionsContainer.appendChild(this.createConditionItem(conditionType, condition, index, pathPrefix));
        });
        
        // Add button
        const addBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addBtn.type = 'button';
        addBtn.innerHTML = `<i class="fas fa-plus"></i> Add ${label.slice(0, -1)}`;
        addBtn.onclick = () => this.addCondition(conditionType, pathPrefix);
        subsection.appendChild(addBtn);
        
        return subsection;
    }

    /**
     * Create individual condition item
     */
    createConditionItem(conditionType, condition, index) {
        const item = this.createElement('div', 'condition-item card mb-2');
        const cardBody = this.createElement('div', 'card-body');
        
        const row = this.createElement('div', 'row align-items-center');
        
        // Name field
        const nameCol = this.createElement('div', 'col-md-5');
        nameCol.appendChild(this.createTextField(`monitor.${conditionType}.${index}.name`, 'Name', condition.name));
        row.appendChild(nameCol);
        
        // Threshold field
        const thresholdCol = this.createElement('div', 'col-md-5');
        thresholdCol.appendChild(this.createNumberField(`monitor.${conditionType}.${index}.threshold`, 'Threshold', condition.threshold, '0.001'));
        row.appendChild(thresholdCol);
        
        // Remove button
        const btnCol = this.createElement('div', 'col-md-2');
        const removeBtn = this.createElement('button', 'btn btn-outline-danger btn-sm');
        removeBtn.type = 'button';
        removeBtn.innerHTML = '<i class="fas fa-trash"></i>';
        removeBtn.onclick = () => this.removeCondition(conditionType, index);
        btnCol.appendChild(removeBtn);
        row.appendChild(btnCol);
        
        cardBody.appendChild(row);
        item.appendChild(cardBody);
        
        return item;
    }

    /**
     * Create bars subsection
     */
    createBarsSubsection(bars, pathPrefix = 'monitor.') {
        const subsection = this.createSubsection('Bars Configuration', 'bars');
        
        const barsContainer = this.createElement('div', 'bars-container');
        subsection.appendChild(barsContainer);
        
        Object.entries(bars).forEach(([barName, barConfig]) => {
            barsContainer.appendChild(this.createBarItem(barName, barConfig, pathPrefix));
        });
        
        // Add button
        const addBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addBtn.type = 'button';
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Bar';
        addBtn.onclick = () => this.addBar(pathPrefix);
        subsection.appendChild(addBtn);
        
        return subsection;
    }

    /**
     * Create individual bar item
     */
    createBarItem(barName, barConfig, pathPrefix = 'monitor.') {
        const item = this.createElement('div', 'bar-item card mb-3');
        const cardHeader = this.createElement('div', 'card-header d-flex justify-content-between align-items-center');
        const cardBody = this.createElement('div', 'card-body');
        
        // Header with bar name and remove button
        const title = this.createElement('h6', 'mb-0');
        title.textContent = barName;
        cardHeader.appendChild(title);
        
        const removeBtn = this.createElement('button', 'btn btn-outline-danger btn-sm');
        removeBtn.type = 'button';
        removeBtn.innerHTML = '<i class="fas fa-trash"></i>';
        removeBtn.onclick = () => this.removeBar(barName, pathPrefix);
        cardHeader.appendChild(removeBtn);
        
        // Bar configuration fields
        const row = this.createElement('div', 'row');
        
        const typeCol = this.createElement('div', 'col-md-6');
        typeCol.appendChild(this.createSelectField(`${pathPrefix}bars.${barName}.type`, 'Type', barConfig.type, ['bull', 'bear']));
        row.appendChild(typeCol);
        
        const descCol = this.createElement('div', 'col-md-6');
        descCol.appendChild(this.createTextField(`${pathPrefix}bars.${barName}.description`, 'Description', barConfig.description));
        row.appendChild(descCol);
        
        cardBody.appendChild(row);
        
        // Indicators subsection
        const indicatorsSection = this.createElement('div', 'mt-3');
        const indicatorsHeader = this.createElement('div', 'd-flex justify-content-between align-items-center mb-2');
        
        const indicatorsLabel = this.createElement('label', 'form-label fw-bold mb-0');
        indicatorsLabel.textContent = 'Indicators & Weights';
        indicatorsHeader.appendChild(indicatorsLabel);
        
        const addIndicatorBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addIndicatorBtn.type = 'button';
        addIndicatorBtn.innerHTML = '<i class="fas fa-plus"></i> Add Indicator';
        addIndicatorBtn.onclick = () => this.addIndicatorToBar(barName, pathPrefix);
        indicatorsHeader.appendChild(addIndicatorBtn);
        
        indicatorsSection.appendChild(indicatorsHeader);
        
        const indicatorsContainer = this.createElement('div', 'indicators-container');
        indicatorsContainer.id = `bar-${barName}-indicators`;
        
        if (barConfig.indicators) {
            Object.entries(barConfig.indicators).forEach(([indicatorName, weight]) => {
                indicatorsContainer.appendChild(this.createBarIndicatorItem(barName, indicatorName, weight, pathPrefix));
            });
        }
        
        indicatorsSection.appendChild(indicatorsContainer);
        cardBody.appendChild(indicatorsSection);
        
        item.appendChild(cardHeader);
        item.appendChild(cardBody);
        
        return item;
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
        
        const indicatorsContainer = this.createElement('div', 'indicators-container');
        body.appendChild(indicatorsContainer);
        
        indicators.forEach((indicator, index) => {
            indicatorsContainer.appendChild(this.createIndicatorItem(indicator, index));
        });
        
        // Add button
        const addBtn = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addBtn.type = 'button';
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Indicator';
        addBtn.onclick = () => this.addIndicator();
        body.appendChild(addBtn);
        
        return section;
    }

    /**
     * Create individual indicator item
     */
    createIndicatorItem(indicator, index) {
        const item = this.createElement('div', 'indicator-item card mb-3');
        const cardHeader = this.createElement('div', 'card-header d-flex justify-content-between align-items-center');
        const cardBody = this.createElement('div', 'card-body');
        
        // Header
        const title = this.createElement('h6', 'mb-0');
        title.textContent = `${indicator.name} (${indicator.function})`;
        cardHeader.appendChild(title);
        
        const removeBtn = this.createElement('button', 'btn btn-outline-danger btn-sm');
        removeBtn.type = 'button';
        removeBtn.innerHTML = '<i class="fas fa-trash"></i>';
        removeBtn.onclick = () => this.removeIndicator(index);
        cardHeader.appendChild(removeBtn);
        
        // Basic fields
        const row1 = this.createElement('div', 'row');
        const nameCol = this.createElement('div', 'col-md-4');
        nameCol.appendChild(this.createTextField(`indicators.${index}.name`, 'Name', indicator.name));
        row1.appendChild(nameCol);
        
        const functionCol = this.createElement('div', 'col-md-4');
        const functionTypes = window.IndicatorParameterUtils ? 
            window.IndicatorParameterUtils.getIndicatorTypes() : 
            this.options.indicatorTypes;
        const functionField = this.createSelectField(`indicators.${index}.function`, 'Function', indicator.function, functionTypes);
        
        // Add change handler to regenerate parameters when function changes
        const functionSelect = functionField.querySelector('select');
        functionSelect.addEventListener('change', (e) => {
            this.onIndicatorFunctionChange(index, e.target.value);
        });
        
        functionCol.appendChild(functionField);
        row1.appendChild(functionCol);
        
        const aggConfigCol = this.createElement('div', 'col-md-4');
        const aggConfigOptions = window.IndicatorParameterUtils ? 
            window.IndicatorParameterUtils.getAggConfigs() : 
            ['1m-normal', '5m-normal', '15m-normal', '30m-normal', '1h-normal', '4h-normal', '1d-normal'];
        aggConfigCol.appendChild(this.createSelectField(`indicators.${index}.agg_config`, 'Agg Config', indicator.agg_config, aggConfigOptions));
        row1.appendChild(aggConfigCol);
        
        cardBody.appendChild(row1);
        
        // Parameters subsection
        cardBody.appendChild(this.createParametersSubsection(indicator.parameters, index));
        
        // Ranges subsection (only for GA optimizer)
        if (this.options.showGAFields && indicator.ranges) {
            cardBody.appendChild(this.createRangesSubsection(indicator.ranges, index));
        }
        
        item.appendChild(cardHeader);
        item.appendChild(cardBody);
        
        return item;
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
        const container = this.container.querySelector(`#${conditionType} .conditions-container`);
        if (!container) return;
        
        container.innerHTML = '';
        
        const conditions = this.formData.monitor[conditionType] || [];
        conditions.forEach((condition, index) => {
            container.appendChild(this.createConditionItem(conditionType, condition, index));
        });
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
        const container = this.container.querySelector('#bars .bars-container');
        if (!container) return;
        
        container.innerHTML = '';
        
        const bars = pathPrefix === 'monitor.' ? 
            (this.formData.monitor?.bars || {}) : 
            (this.formData.bars || {});
            
        Object.entries(bars).forEach(([barName, barConfig]) => {
            container.appendChild(this.createBarItem(barName, barConfig, pathPrefix));
        });
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
        const container = this.container.querySelector('#indicators .indicators-container');
        if (!container) return;
        
        container.innerHTML = '';
        
        const indicators = this.formData.indicators || [];
        indicators.forEach((indicator, index) => {
            container.appendChild(this.createIndicatorItem(indicator, index));
        });
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
     * Create objectives section for GA configuration
     */
    createObjectivesSection(objectives) {
        const section = this.createSection('Optimization Objectives', 'objectives');
        const body = section.querySelector('.card-body');
        
        const objectivesContainer = this.createElement('div', 'objectives-container');
        body.appendChild(objectivesContainer);
        
        // Add objectives
        objectives.forEach((objective, index) => {
            const objectiveItem = this.createObjectiveItem(objective, index);
            objectivesContainer.appendChild(objectiveItem);
        });
        
        // Add objective button
        const addButton = this.createElement('button', 'btn btn-outline-primary btn-sm');
        addButton.textContent = '+ Add Objective';
        addButton.type = 'button';
        addButton.onclick = () => this.addObjective();
        body.appendChild(addButton);
        
        return section;
    }

    /**
     * Create individual objective item
     */
    createObjectiveItem(objective, index) {
        const item = this.createElement('div', 'card mb-2');
        
        const cardBody = this.createElement('div', 'card-body');
        
        // Objective type selection
        const objectiveField = this.createElement('div', 'row mb-2');
        const col1 = this.createElement('div', 'col-md-6');
        const label1 = this.createElement('label', 'form-label');
        label1.textContent = 'Objective';
        const select = this.createElement('select', 'form-select');
        select.name = `objectives.${index}.objective`;
        
        const objectiveTypes = ['MaximizeProfit', 'MinimizeDrawdown', 'MaximizeSharpeRatio', 'MaximizeWinRate'];
        objectiveTypes.forEach(type => {
            const option = this.createElement('option');
            option.value = type;
            option.textContent = type;
            option.selected = objective.objective === type;
            select.appendChild(option);
        });
        
        select.onchange = (e) => {
            this.formData.objectives[index].objective = e.target.value;
        };
        
        col1.appendChild(label1);
        col1.appendChild(select);
        objectiveField.appendChild(col1);
        
        // Weight field
        const col2 = this.createElement('div', 'col-md-4');
        const weightField = this.createNumberField(`objectives.${index}.weight`, 'Weight', objective.weight, '0.1');
        col2.appendChild(weightField);
        objectiveField.appendChild(col2);
        
        // Remove button
        const col3 = this.createElement('div', 'col-md-2 d-flex align-items-end');
        const removeBtn = this.createElement('button', 'btn btn-outline-danger btn-sm');
        removeBtn.textContent = 'Remove';
        removeBtn.type = 'button';
        removeBtn.onclick = () => this.removeObjective(index);
        col3.appendChild(removeBtn);
        objectiveField.appendChild(col3);
        
        cardBody.appendChild(objectiveField);
        
        // Parameters (if any)
        if (objective.parameters) {
            const paramsLabel = this.createElement('label', 'form-label');
            paramsLabel.textContent = 'Parameters (JSON)';
            const paramsTextarea = this.createElement('textarea', 'form-control');
            paramsTextarea.rows = 2;
            paramsTextarea.value = JSON.stringify(objective.parameters, null, 2);
            paramsTextarea.onchange = (e) => {
                try {
                    this.formData.objectives[index].parameters = JSON.parse(e.target.value);
                } catch (err) {
                    console.error('Invalid JSON in parameters:', err);
                }
            };
            cardBody.appendChild(paramsLabel);
            cardBody.appendChild(paramsTextarea);
        }
        
        item.appendChild(cardBody);
        return item;
    }

    /**
     * Add new objective
     */
    addObjective() {
        const newObjective = {
            objective: 'MaximizeProfit',
            weight: 1.0,
            parameters: {}
        };
        
        this.formData.objectives.push(newObjective);
        
        // Regenerate objectives section
        const container = this.container.querySelector('#objectives .objectives-container');
        const objectiveItem = this.createObjectiveItem(newObjective, this.formData.objectives.length - 1);
        container.appendChild(objectiveItem);
    }

    /**
     * Remove objective
     */
    removeObjective(index) {
        this.formData.objectives.splice(index, 1);
        
        // Regenerate objectives section
        const section = this.container.querySelector('#objectives');
        const newSection = this.createObjectivesSection(this.formData.objectives);
        section.parentNode.replaceChild(newSection, section);
    }

    /**
     * Create GA hyperparameters section
     */
    createGAHyperparametersSection(gaHyperparameters) {
        const section = this.createSection('Genetic Algorithm Parameters', 'ga-hyperparameters');
        const body = section.querySelector('.card-body');
        
        const fields = [
            { key: 'number_of_iterations', label: 'Number of Iterations', type: 'number', step: '1', min: '10' },
            { key: 'population_size', label: 'Population Size', type: 'number', step: '1', min: '20' },
            { key: 'propagation_fraction', label: 'Propagation Fraction', type: 'number', step: '0.01', min: '0.1', max: '0.9' },
            { key: 'elite_size', label: 'Elite Size', type: 'number', step: '1', min: '1' },
            { key: 'chance_of_mutation', label: 'Chance of Mutation', type: 'number', step: '0.01', min: '0.01', max: '1.0' },
            { key: 'selection_algorithm', label: 'Selection Algorithm', type: 'select', options: ['tournament', 'roulette', 'rank'] }
        ];
        
        fields.forEach(field => {
            if (field.type === 'select') {
                const selectField = this.createSelectField(`ga_hyperparameters.${field.key}`, field.label, gaHyperparameters[field.key], field.options);
                const selectElement = selectField.querySelector('select');
                selectElement.addEventListener('change', (e) => this.updateFormData(e.target));
                body.appendChild(selectField);
            } else {
                const numberField = this.createNumberField(`ga_hyperparameters.${field.key}`, field.label, gaHyperparameters[field.key], field.step);
                if (field.min) numberField.querySelector('input').min = field.min;
                if (field.max) numberField.querySelector('input').max = field.max;
                body.appendChild(numberField);
            }
        });
        
        return section;
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
     * Get current form data
     */
    getFormData() {
        return this.formData;
    }
}

// Export for use in other modules
window.ConfigFormBuilder = ConfigFormBuilder;