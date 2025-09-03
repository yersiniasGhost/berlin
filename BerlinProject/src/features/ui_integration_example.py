"""
Example integration of the configurable indicator system with Flask UI applications.
This demonstrates how to integrate the indicator system with existing apps.
"""

from flask import Flask, render_template_string
from typing import List, Dict, Any
import numpy as np

from features.indicator_api import indicator_api, config_manager
from features.indicator_base import BaseIndicator, IndicatorConfiguration
from features.indicator_base import IndicatorRegistry
from models.tick_data import TickData

# HTML template for indicator configuration UI
INDICATOR_CONFIG_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Indicator Configuration</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .indicator-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 20px; }
        .indicator-list { border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
        .config-panel { border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
        .indicator-item { 
            padding: 10px; margin: 5px 0; border: 1px solid #eee; 
            cursor: pointer; border-radius: 3px; 
        }
        .indicator-item:hover { background: #f5f5f5; }
        .indicator-item.active { background: #e3f2fd; border-color: #2196f3; }
        .form-group { margin: 15px 0; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group select { 
            width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 3px; 
        }
        .form-group input[type="range"] { width: calc(100% - 60px); display: inline-block; }
        .range-value { display: inline-block; width: 50px; text-align: right; }
        .button { 
            padding: 10px 20px; background: #2196f3; color: white; 
            border: none; border-radius: 3px; cursor: pointer; margin: 5px;
        }
        .button:hover { background: #1976d2; }
        .button.secondary { background: #666; }
        .saved-configs { margin-top: 20px; }
        .config-item { 
            padding: 10px; margin: 5px 0; border: 1px solid #eee; 
            border-radius: 3px; display: flex; justify-content: space-between; align-items: center;
        }
        .error { color: red; font-size: 14px; }
        .success { color: green; font-size: 14px; }
    </style>
</head>
<body>
    <div id="app" class="container">
        <h1>Indicator Configuration Manager</h1>
        
        <div class="indicator-grid">
            <!-- Available Indicators -->
            <div class="indicator-list">
                <h3>Available Indicators</h3>
                <div v-for="indicator in availableIndicators" :key="indicator.name" 
                     @click="selectIndicator(indicator)" 
                     :class="['indicator-item', {active: selectedIndicator?.name === indicator.name}]">
                    <strong>{{ indicator.display_name }}</strong>
                    <p>{{ indicator.description }}</p>
                </div>
            </div>
            
            <!-- Configuration Panel -->
            <div class="config-panel">
                <h3>Configuration</h3>
                
                <div v-if="selectedIndicator">
                    <h4>{{ selectedSchema?.display_name }}</h4>
                    <p>{{ selectedSchema?.description }}</p>
                    
                    <form @submit.prevent="saveConfiguration">
                        <div class="form-group">
                            <label>Configuration Name:</label>
                            <input v-model="configName" type="text" required placeholder="Enter configuration name">
                        </div>
                        
                        <div v-for="(group, groupName) in selectedSchema?.parameter_groups" :key="groupName">
                            <h5>{{ groupName }}</h5>
                            
                            <div v-for="param in group" :key="param.name" class="form-group">
                                <label>{{ param.display_name }}:</label>
                                
                                <!-- Integer/Float with range -->
                                <div v-if="param.type === 'integer' || param.type === 'float'">
                                    <input v-if="param.min !== undefined && param.max !== undefined" 
                                           v-model.number="parameterValues[param.name]"
                                           type="range" 
                                           :min="param.min" 
                                           :max="param.max" 
                                           :step="param.step || 1">
                                    <span class="range-value">{{ parameterValues[param.name] }}</span>
                                    
                                    <input v-else
                                           v-model.number="parameterValues[param.name]"
                                           :type="param.type === 'integer' ? 'number' : 'number'"
                                           :step="param.step || (param.type === 'integer' ? 1 : 0.01)">
                                </div>
                                
                                <!-- Boolean -->
                                <input v-else-if="param.type === 'boolean'"
                                       v-model="parameterValues[param.name]"
                                       type="checkbox">
                                
                                <!-- Choice -->
                                <select v-else-if="param.type === 'choice'"
                                        v-model="parameterValues[param.name]">
                                    <option v-for="choice in param.choices" :key="choice" :value="choice">
                                        {{ choice }}
                                    </option>
                                </select>
                                
                                <!-- String -->
                                <input v-else
                                       v-model="parameterValues[param.name]"
                                       type="text">
                                
                                <small>{{ param.description }}</small>
                            </div>
                        </div>
                        
                        <button type="submit" class="button">Save Configuration</button>
                        <button type="button" @click="testConfiguration" class="button secondary">Test</button>
                    </form>
                    
                    <div v-if="message" :class="messageType">{{ message }}</div>
                </div>
                
                <div v-else>
                    <p>Select an indicator to configure its parameters.</p>
                </div>
            </div>
        </div>
        
        <!-- Saved Configurations -->
        <div class="saved-configs">
            <h3>Saved Configurations</h3>
            <button @click="loadSavedConfigurations" class="button secondary">Refresh</button>
            
            <div v-for="config in savedConfigurations" :key="config.id" class="config-item">
                <div>
                    <strong>{{ config.display_name }}</strong>
                    <small>({{ config.indicator_name }}, {{ config.parameter_count }} parameters)</small>
                </div>
                <div>
                    <button @click="loadConfiguration(config.id)" class="button secondary">Load</button>
                    <button @click="deleteConfiguration(config.id)" class="button secondary">Delete</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        const { createApp } = Vue;
        
        createApp({
            data() {
                return {
                    availableIndicators: [],
                    selectedIndicator: null,
                    selectedSchema: null,
                    parameterValues: {},
                    configName: '',
                    savedConfigurations: [],
                    message: '',
                    messageType: 'success'
                };
            },
            
            async mounted() {
                await this.loadAvailableIndicators();
                await this.loadSavedConfigurations();
            },
            
            methods: {
                async loadAvailableIndicators() {
                    try {
                        const response = await fetch('/api/indicators/available');
                        const data = await response.json();
                        this.availableIndicators = data.indicators;
                    } catch (error) {
                        console.error('Error loading indicators:', error);
                    }
                },
                
                async selectIndicator(indicator) {
                    this.selectedIndicator = indicator;
                    
                    try {
                        const response = await fetch(`/api/indicators/schema/${indicator.name}`);
                        const data = await response.json();
                        this.selectedSchema = data.schema;
                        
                        // Initialize parameter values with defaults
                        this.parameterValues = {};
                        for (const group of Object.values(this.selectedSchema.parameter_groups)) {
                            for (const param of group) {
                                this.parameterValues[param.name] = param.default;
                            }
                        }
                        
                        this.configName = `${indicator.display_name} Config`;
                        
                    } catch (error) {
                        console.error('Error loading schema:', error);
                    }
                },
                
                async saveConfiguration() {
                    try {
                        const configData = {
                            indicator_name: this.selectedIndicator.name,
                            display_name: this.configName,
                            parameters: { ...this.parameterValues },
                            enabled: true
                        };
                        
                        const response = await fetch('/api/indicators/configurations', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(configData)
                        });
                        
                        const result = await response.json();
                        
                        if (result.success) {
                            this.showMessage('Configuration saved successfully!', 'success');
                            await this.loadSavedConfigurations();
                        } else {
                            this.showMessage(`Error: ${result.error}`, 'error');
                        }
                        
                    } catch (error) {
                        this.showMessage(`Error saving configuration: ${error.message}`, 'error');
                    }
                },
                
                async testConfiguration() {
                    // This would test the configuration with sample data
                    this.showMessage('Configuration test functionality would go here', 'success');
                },
                
                async loadSavedConfigurations() {
                    try {
                        const response = await fetch('/api/indicators/configurations');
                        const data = await response.json();
                        this.savedConfigurations = data.configurations;
                    } catch (error) {
                        console.error('Error loading saved configurations:', error);
                    }
                },
                
                async loadConfiguration(configId) {
                    try {
                        const response = await fetch(`/api/indicators/configurations/${configId}`);
                        const data = await response.json();
                        
                        if (data.success) {
                            const config = data.configuration;
                            
                            // Find and select the indicator
                            const indicator = this.availableIndicators.find(i => i.name === config.indicator_name);
                            if (indicator) {
                                await this.selectIndicator(indicator);
                                this.configName = config.display_name;
                                this.parameterValues = { ...config.parameters };
                            }
                            
                            this.showMessage('Configuration loaded successfully!', 'success');
                        }
                    } catch (error) {
                        this.showMessage(`Error loading configuration: ${error.message}`, 'error');
                    }
                },
                
                async deleteConfiguration(configId) {
                    if (!confirm('Are you sure you want to delete this configuration?')) {
                        return;
                    }
                    
                    try {
                        const response = await fetch(`/api/indicators/configurations/${configId}`, {
                            method: 'DELETE'
                        });
                        
                        const result = await response.json();
                        
                        if (result.success) {
                            this.showMessage('Configuration deleted successfully!', 'success');
                            await this.loadSavedConfigurations();
                        } else {
                            this.showMessage(`Error: ${result.error}`, 'error');
                        }
                        
                    } catch (error) {
                        this.showMessage(`Error deleting configuration: ${error.message}`, 'error');
                    }
                },
                
                showMessage(msg, type) {
                    this.message = msg;
                    this.messageType = type;
                    setTimeout(() => {
                        this.message = '';
                    }, 5000);
                }
            }
        }).mount('#app');
    </script>
</body>
</html>
'''


def create_indicator_ui_app():
    """Create a standalone Flask app for indicator configuration."""
    app = Flask(__name__)
    app.register_blueprint(indicator_api)
    
    @app.route('/')
    def index():
        try:
            return render_template_string(INDICATOR_CONFIG_TEMPLATE)
        except Exception as e:
            return f"<h1>Template Error</h1><p>Error rendering template: {str(e)}</p><p>Please check the template syntax.</p>"
    
    return app


def integrate_with_existing_app(app: Flask):
    """Integrate indicator system with an existing Flask app."""
    
    # Register the API blueprint
    app.register_blueprint(indicator_api)
    
    # Add indicator configuration route
    @app.route('/indicator-config')
    def indicator_config():
        return render_template_string(INDICATOR_CONFIG_TEMPLATE)
    
    # Add utility functions for indicator usage
    @app.context_processor
    def inject_indicator_utilities():
        return {
            'get_indicator_configs': lambda: config_manager.list_configurations(),
            'create_indicator_from_config': lambda config_id: config_manager.create_indicator_instance(config_id)
        }


class IndicatorRunner:
    """Utility class for running indicators on data."""
    
    def __init__(self):
        self.active_indicators: Dict[str, BaseIndicator] = {}
    
    def load_indicator_set(self, config_ids: List[str]) -> Dict[str, str]:
        """Load a set of indicators from configurations."""
        results = {}
        
        for config_id in config_ids:
            try:
                indicator = config_manager.create_indicator_instance(config_id)
                if indicator:
                    self.active_indicators[config_id] = indicator
                    results[config_id] = "loaded"
                else:
                    results[config_id] = "config not found"
            except Exception as e:
                results[config_id] = f"error: {str(e)}"
        
        return results
    
    def run_indicators(self, tick_data: List[TickData]) -> Dict[str, Any]:
        """Run all loaded indicators on tick data."""
        results = {}
        
        for config_id, indicator in self.active_indicators.items():
            try:
                if indicator.config.enabled:
                    result = indicator.calculate(tick_data)
                    results[config_id] = {
                        'indicator_name': indicator.name,
                        'display_name': indicator.config.display_name,
                        'values': result.tolist(),
                        'success': True
                    }
                else:
                    results[config_id] = {
                        'indicator_name': indicator.name,
                        'display_name': indicator.config.display_name,
                        'success': False,
                        'reason': 'disabled'
                    }
            except Exception as e:
                results[config_id] = {
                    'indicator_name': indicator.name,
                    'display_name': indicator.config.display_name,
                    'success': False,
                    'error': str(e)
                }
        
        return results
    
    def get_signal_summary(self, tick_data: List[TickData]) -> Dict[str, Any]:
        """Get a summary of all signals from active indicators."""
        results = self.run_indicators(tick_data)
        summary = {
            'total_indicators': len(results),
            'successful': 0,
            'failed': 0,
            'signals_found': 0,
            'latest_signals': {}
        }
        
        for config_id, result in results.items():
            if result['success']:
                summary['successful'] += 1
                values = result['values']
                
                # Count signals (non-zero values)
                signal_count = sum(1 for v in values if not (np.isnan(v) or v == 0))
                if signal_count > 0:
                    summary['signals_found'] += signal_count
                    
                    # Get latest signal
                    latest_signal_idx = None
                    for i in range(len(values) - 1, -1, -1):
                        if not (np.isnan(values[i]) or values[i] == 0):
                            latest_signal_idx = i
                            break
                    
                    if latest_signal_idx is not None:
                        summary['latest_signals'][config_id] = {
                            'display_name': result['display_name'],
                            'signal_index': latest_signal_idx,
                            'signal_value': values[latest_signal_idx],
                            'bars_ago': len(values) - 1 - latest_signal_idx
                        }
            else:
                summary['failed'] += 1
        
        return summary


# Example usage function
def example_usage():
    """Example of how to use the refactored indicator system."""
    
    # Create some sample configurations
    sma_config = IndicatorConfiguration(
        indicator_name="sma_crossover",
        display_name="SMA 20 Bullish Crossover",
        parameters={
            "period": 20,
            "crossover_value": 0.015,
            "trend": "bullish"
        }
    )
    
    macd_config = IndicatorConfiguration(
        indicator_name="macd_histogram_crossover",
        display_name="MACD Bullish Signal",
        parameters={
            "fast": 12,
            "slow": 26,
            "signal": 9,
            "histogram_threshold": 0.001,
            "trend": "bullish"
        }
    )
    
    # Save configurations
    config_manager.save_configuration(sma_config, "sma_bullish_20")
    config_manager.save_configuration(macd_config, "macd_bullish_default")
    
    # Create indicator runner
    runner = IndicatorRunner()
    runner.load_indicator_set(["sma_bullish_20", "macd_bullish_default"])
    
    # Example tick data (would come from your data source)
    # tick_data = [TickData(...), TickData(...), ...]
    
    # Run indicators and get results
    # results = runner.run_indicators(tick_data)
    # summary = runner.get_signal_summary(tick_data)
    
    print("Example configurations created and runner initialized")


if __name__ == "__main__":
    # Run example
    example_usage()
    
    # Create standalone app
    app = create_indicator_ui_app()
    app.run(debug=True, port=5001)