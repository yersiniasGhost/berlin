/**
 * Data Configuration Form Builder
 * Simple form for editing data configuration (ticker, start_date, end_date)
 */

class DataConfigForm {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.formData = {};
    }

    /**
     * Generate data configuration form
     */
    generateForm(dataConfig = {}) {
        this.formData = { ...dataConfig };
        this.container.innerHTML = '';
        
        // Create form wrapper
        const form = this.createElement('form', 'data-config-form');
        form.setAttribute('novalidate', '');
        
        // Form header
        const header = this.createElement('div', 'form-header mb-4');
        const title = this.createElement('h5', 'mb-0');
        title.innerHTML = '<i class="fas fa-chart-line"></i> Data Configuration';
        header.appendChild(title);
        form.appendChild(header);
        
        // Create form fields
        form.appendChild(this.createTickerField(dataConfig.ticker || ''));
        form.appendChild(this.createDateRangeFields(dataConfig.start_date || '', dataConfig.end_date || ''));
        
        // Form actions
        form.appendChild(this.createFormActions());
        
        this.container.appendChild(form);
        this.attachEventHandlers();
        
        return form;
    }

    /**
     * Create ticker field
     */
    createTickerField(ticker) {
        const group = this.createElement('div', 'mb-3');
        
        const label = this.createElement('label', 'form-label fw-bold');
        label.textContent = 'Stock Ticker Symbol';
        label.setAttribute('for', 'ticker');
        group.appendChild(label);
        
        const inputGroup = this.createElement('div', 'input-group');
        
        const prepend = this.createElement('span', 'input-group-text');
        prepend.innerHTML = '<i class="fas fa-dollar-sign"></i>';
        inputGroup.appendChild(prepend);
        
        const input = this.createElement('input', 'form-control');
        input.type = 'text';
        input.name = 'ticker';
        input.id = 'ticker';
        input.value = ticker;
        input.placeholder = 'e.g., NVDA, AAPL, TSLA';
        input.required = true;
        input.pattern = '[A-Z]{1,5}';
        input.title = 'Enter a valid stock ticker symbol (1-5 uppercase letters)';
        inputGroup.appendChild(input);
        
        group.appendChild(inputGroup);
        
        // Add validation feedback
        const invalidFeedback = this.createElement('div', 'invalid-feedback');
        invalidFeedback.textContent = 'Please enter a valid stock ticker symbol.';
        group.appendChild(invalidFeedback);
        
        return group;
    }

    /**
     * Create date range fields
     */
    createDateRangeFields(startDate, endDate) {
        const group = this.createElement('div', 'mb-3');
        
        const label = this.createElement('label', 'form-label fw-bold');
        label.textContent = 'Date Range';
        group.appendChild(label);
        
        const row = this.createElement('div', 'row');
        
        // Start date
        const startCol = this.createElement('div', 'col-md-6');
        const startGroup = this.createElement('div', 'input-group mb-3');
        
        const startPrepend = this.createElement('span', 'input-group-text');
        startPrepend.innerHTML = '<i class="fas fa-calendar-alt"></i>';
        startGroup.appendChild(startPrepend);
        
        const startInput = this.createElement('input', 'form-control');
        startInput.type = 'date';
        startInput.name = 'start_date';
        startInput.id = 'start_date';
        startInput.value = startDate;
        startInput.required = true;
        startGroup.appendChild(startInput);
        
        const startLabel = this.createElement('label', 'form-label small text-muted');
        startLabel.textContent = 'Start Date';
        startLabel.setAttribute('for', 'start_date');
        
        startCol.appendChild(startLabel);
        startCol.appendChild(startGroup);
        row.appendChild(startCol);
        
        // End date
        const endCol = this.createElement('div', 'col-md-6');
        const endGroup = this.createElement('div', 'input-group mb-3');
        
        const endPrepend = this.createElement('span', 'input-group-text');
        endPrepend.innerHTML = '<i class="fas fa-calendar-alt"></i>';
        endGroup.appendChild(endPrepend);
        
        const endInput = this.createElement('input', 'form-control');
        endInput.type = 'date';
        endInput.name = 'end_date';
        endInput.id = 'end_date';
        endInput.value = endDate;
        endInput.required = true;
        endGroup.appendChild(endInput);
        
        const endLabel = this.createElement('label', 'form-label small text-muted');
        endLabel.textContent = 'End Date';
        endLabel.setAttribute('for', 'end_date');
        
        endCol.appendChild(endLabel);
        endCol.appendChild(endGroup);
        row.appendChild(endCol);
        
        group.appendChild(row);
        
        // Add date range validation feedback
        const invalidFeedback = this.createElement('div', 'invalid-feedback');
        invalidFeedback.textContent = 'Please select a valid date range.';
        group.appendChild(invalidFeedback);
        
        return group;
    }

    /**
     * Create form actions
     */
    createFormActions() {
        const actions = this.createElement('div', 'form-actions mt-4 d-flex gap-2 justify-content-end');
        
        const saveBtn = this.createElement('button', 'btn btn-primary');
        saveBtn.type = 'button';
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Data Config';
        saveBtn.onclick = () => this.saveConfiguration();
        
        const presetBtn = this.createElement('button', 'btn btn-outline-secondary dropdown-toggle');
        presetBtn.type = 'button';
        presetBtn.setAttribute('data-bs-toggle', 'dropdown');
        presetBtn.innerHTML = '<i class="fas fa-clock"></i> Presets';
        
        const dropdown = this.createElement('ul', 'dropdown-menu');
        
        // Common presets
        const presets = [
            { label: 'Last Month', days: 30 },
            { label: 'Last 3 Months', days: 90 },
            { label: 'Last 6 Months', days: 180 },
            { label: 'Last Year', days: 365 }
        ];
        
        presets.forEach(preset => {
            const item = this.createElement('li');
            const link = this.createElement('a', 'dropdown-item');
            link.href = '#';
            link.textContent = preset.label;
            link.onclick = (e) => {
                e.preventDefault();
                this.applyDatePreset(preset.days);
            };
            item.appendChild(link);
            dropdown.appendChild(item);
        });
        
        // Create dropdown wrapper
        const dropdownWrapper = this.createElement('div', 'dropdown');
        dropdownWrapper.appendChild(presetBtn);
        dropdownWrapper.appendChild(dropdown);
        
        actions.appendChild(dropdownWrapper);
        actions.appendChild(saveBtn);
        
        return actions;
    }

    /**
     * Apply date preset
     */
    applyDatePreset(days) {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - days);
        
        // Format dates for input fields
        const formatDate = (date) => {
            return date.toISOString().split('T')[0];
        };
        
        const startInput = this.container.querySelector('#start_date');
        const endInput = this.container.querySelector('#end_date');
        
        startInput.value = formatDate(startDate);
        endInput.value = formatDate(endDate);
        
        // Update form data
        this.formData.start_date = startInput.value;
        this.formData.end_date = endInput.value;
        
        // Validate the fields
        this.validateField(startInput);
        this.validateField(endInput);
    }

    /**
     * Helper method to create elements
     */
    createElement(tag, classes = '') {
        const element = document.createElement(tag);
        if (classes) element.className = classes;
        return element;
    }

    /**
     * Attach event handlers
     */
    attachEventHandlers() {
        const inputs = this.container.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('input', (e) => this.validateField(e.target));
            input.addEventListener('change', (e) => this.updateFormData(e.target));
        });
        
        // Add date range validation
        const startDate = this.container.querySelector('#start_date');
        const endDate = this.container.querySelector('#end_date');
        
        if (startDate && endDate) {
            startDate.addEventListener('change', () => this.validateDateRange());
            endDate.addEventListener('change', () => this.validateDateRange());
        }
    }

    /**
     * Validate individual field
     */
    validateField(field) {
        field.classList.remove('is-invalid', 'is-valid');
        
        if (field.checkValidity()) {
            field.classList.add('is-valid');
            return true;
        } else {
            field.classList.add('is-invalid');
            return false;
        }
    }

    /**
     * Validate date range
     */
    validateDateRange() {
        const startDate = this.container.querySelector('#start_date');
        const endDate = this.container.querySelector('#end_date');
        
        if (!startDate.value || !endDate.value) return;
        
        const start = new Date(startDate.value);
        const end = new Date(endDate.value);
        
        if (start >= end) {
            startDate.classList.add('is-invalid');
            endDate.classList.add('is-invalid');
            return false;
        } else {
            startDate.classList.remove('is-invalid');
            endDate.classList.remove('is-invalid');
            startDate.classList.add('is-valid');
            endDate.classList.add('is-valid');
            return true;
        }
    }

    /**
     * Update form data
     */
    updateFormData(field) {
        this.formData[field.name] = field.value;
    }

    /**
     * Save configuration
     */
    saveConfiguration() {
        // Validate all fields
        const inputs = this.container.querySelectorAll('input[required]');
        let isValid = true;
        
        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });
        
        // Validate date range
        if (!this.validateDateRange()) {
            isValid = false;
        }
        
        if (!isValid) {
            // Show error message
            this.showMessage('Please fix validation errors before saving.', 'error');
            return;
        }
        
        // Update form data with current values
        inputs.forEach(input => {
            this.formData[input.name] = input.value;
        });
        
        console.log('Saving data configuration:', this.formData);
        
        // Trigger save event
        const saveEvent = new CustomEvent('dataConfigSave', {
            detail: this.formData
        });
        this.container.dispatchEvent(saveEvent);
        
        this.showMessage('Data configuration saved successfully!', 'success');
    }

    /**
     * Show message to user
     */
    showMessage(message, type = 'info') {
        // Remove existing messages
        const existingMessages = this.container.querySelectorAll('.alert');
        existingMessages.forEach(msg => msg.remove());
        
        // Create new message
        const alertClass = type === 'error' ? 'alert-danger' : 
                          type === 'success' ? 'alert-success' : 'alert-info';
        
        const alert = this.createElement(`alert alert-dismissible fade show ${alertClass}`);
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        this.container.insertBefore(alert, this.container.firstChild);
        
        // Auto-dismiss after 3 seconds for success messages
        if (type === 'success') {
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.remove();
                }
            }, 3000);
        }
    }

    /**
     * Get current form data
     */
    getFormData() {
        return this.formData;
    }

    /**
     * Reset form
     */
    resetForm() {
        const inputs = this.container.querySelectorAll('input');
        inputs.forEach(input => {
            input.value = '';
            input.classList.remove('is-valid', 'is-invalid');
        });
        this.formData = {};
    }
}

// Export for use in other modules
window.DataConfigForm = DataConfigForm;