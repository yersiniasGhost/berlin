/**
 * Indicator Parameter Definitions
 * Defines the parameters, validation rules, and defaults for each indicator function
 */

const INDICATOR_PARAMETER_DEFINITIONS = {
    "macd_histogram_crossover": {
        "description": "MACD Histogram Crossover - Detects when MACD histogram crosses above/below threshold",
        "parameters": {
            "slow": {
                "type": "int",
                "min": 12,
                "max": 50,
                "default": 26,
                "description": "Slow EMA period for MACD calculation",
                "required": true
            },
            "fast": {
                "type": "int", 
                "min": 7,
                "max": 25,
                "default": 12,
                "description": "Fast EMA period for MACD calculation",
                "required": true
            },
            "signal": {
                "type": "int",
                "min": 6,
                "max": 15,
                "default": 9,
                "description": "Signal line EMA period",
                "required": true
            },
            "histogram_threshold": {
                "type": "float",
                "min": 0.005,
                "max": 0.15,
                "step": 0.001,
                "default": 0.08,
                "description": "Histogram crossover threshold value",
                "required": true
            },
            "lookback": {
                "type": "int",
                "min": 5,
                "max": 25,
                "default": 10,
                "description": "Number of periods to look back",
                "required": true
            },
            "trend": {
                "type": "select",
                "options": ["bullish", "bearish"],
                "default": "bullish",
                "description": "Signal direction (bullish or bearish)",
                "required": true
            }
        }
    },

    "sma_crossover": {
        "description": "Simple Moving Average Crossover - Detects when price crosses above/below SMA",
        "parameters": {
            "period": {
                "type": "int",
                "min": 5,
                "max": 50,
                "default": 20,
                "description": "SMA period (number of candles)",
                "required": true
            },
            "crossover_value": {
                "type": "float",
                "min": 0.0001,
                "max": 0.05,
                "step": 0.0001,
                "default": 0.01,
                "description": "Percentage threshold for crossover detection",
                "required": true
            },
            "lookback": {
                "type": "int",
                "min": 5,
                "max": 25,
                "default": 10,
                "description": "Number of periods to look back",
                "required": true
            },
            "trend": {
                "type": "select",
                "options": ["bullish", "bearish"],
                "default": "bullish",
                "description": "Signal direction (bullish or bearish)",
                "required": true
            }
        }
    },

    "bol_bands_lower_band_bounce": {
        "description": "Bollinger Bands Bounce - Detects bounce off upper or lower Bollinger band",
        "parameters": {
            "period": {
                "type": "int",
                "min": 10,
                "max": 50,
                "default": 20,
                "description": "Bollinger band calculation period",
                "required": true
            },
            "sd": {
                "type": "float",
                "min": 1.0,
                "max": 3.0,
                "step": 0.1,
                "default": 2.0,
                "description": "Standard deviation multiplier for bands",
                "required": true
            },
            "candle_bounce_number": {
                "type": "int",
                "min": 1,
                "max": 10,
                "default": 3,
                "description": "Number of candles to check for band touch",
                "required": true
            },
            "bounce_trigger": {
                "type": "float",
                "min": 0.1,
                "max": 0.8,
                "step": 0.05,
                "default": 0.25,
                "description": "Percentage of band range to trigger bounce signal",
                "required": true
            },
            "lookback": {
                "type": "int",
                "min": 5,
                "max": 25,
                "default": 10,
                "description": "Number of periods to look back",
                "required": true
            },
            "trend": {
                "type": "select",
                "options": ["bullish", "bearish"],
                "default": "bullish",
                "description": "Signal direction (bullish or bearish)",
                "required": true
            }
        }
    },

    // Additional indicators can be easily added here
    "rsi_crossover": {
        "description": "RSI Crossover - Detects when RSI crosses overbought/oversold levels",
        "parameters": {
            "period": {
                "type": "int",
                "min": 7,
                "max": 30,
                "default": 14,
                "description": "RSI calculation period",
                "required": true
            },
            "upper_threshold": {
                "type": "float",
                "min": 60,
                "max": 90,
                "step": 1,
                "default": 70,
                "description": "Overbought threshold level",
                "required": true
            },
            "lower_threshold": {
                "type": "float",
                "min": 10,
                "max": 40,
                "step": 1,
                "default": 30,
                "description": "Oversold threshold level",
                "required": true
            },
            "lookback": {
                "type": "int",
                "min": 5,
                "max": 25,
                "default": 10,
                "description": "Number of periods to look back",
                "required": true
            },
            "trend": {
                "type": "select",
                "options": ["bullish", "bearish"],
                "default": "bullish",
                "description": "Signal direction (bullish or bearish)",
                "required": true
            }
        }
    },

    "stochastic_crossover": {
        "description": "Stochastic Oscillator Crossover - Detects %K and %D line crossovers",
        "parameters": {
            "k_period": {
                "type": "int",
                "min": 5,
                "max": 21,
                "default": 14,
                "description": "%K period for stochastic calculation",
                "required": true
            },
            "d_period": {
                "type": "int",
                "min": 3,
                "max": 10,
                "default": 3,
                "description": "%D period (smoothing period)",
                "required": true
            },
            "upper_threshold": {
                "type": "float",
                "min": 60,
                "max": 90,
                "step": 1,
                "default": 80,
                "description": "Overbought threshold level",
                "required": true
            },
            "lower_threshold": {
                "type": "float",
                "min": 10,
                "max": 40,
                "step": 1,
                "default": 20,
                "description": "Oversold threshold level", 
                "required": true
            },
            "lookback": {
                "type": "int",
                "min": 5,
                "max": 25,
                "default": 10,
                "description": "Number of periods to look back",
                "required": true
            },
            "trend": {
                "type": "select",
                "options": ["bullish", "bearish"],
                "default": "bullish",
                "description": "Signal direction (bullish or bearish)",
                "required": true
            }
        }
    }
};

// Common aggregation configurations
const AGG_CONFIGS = [
    "1m-normal",
    "5m-normal", 
    "15m-normal",
    "30m-normal",
    "1h-normal",
    "4h-normal",
    "1d-normal"
];

/**
 * Utility functions for working with parameter definitions
 */
class IndicatorParameterUtils {
    /**
     * Get all available indicator function names
     */
    static getIndicatorTypes() {
        return Object.keys(INDICATOR_PARAMETER_DEFINITIONS);
    }

    /**
     * Get parameter definition for a specific indicator
     */
    static getParameterDefinition(indicatorType) {
        return INDICATOR_PARAMETER_DEFINITIONS[indicatorType] || null;
    }

    /**
     * Generate default parameters for an indicator
     */
    static generateDefaultParameters(indicatorType) {
        const definition = this.getParameterDefinition(indicatorType);
        if (!definition) return {};

        const parameters = {};
        Object.entries(definition.parameters).forEach(([paramName, paramDef]) => {
            parameters[paramName] = paramDef.default;
        });
        
        return parameters;
    }

    /**
     * Generate GA ranges for an indicator (for genetic algorithm optimization)
     */
    static generateGARanges(indicatorType) {
        const definition = this.getParameterDefinition(indicatorType);
        if (!definition) return {};

        const ranges = {};
        Object.entries(definition.parameters).forEach(([paramName, paramDef]) => {
            if (paramDef.type === 'int') {
                ranges[paramName] = {
                    "t": "int",
                    "r": [paramDef.min, paramDef.max]
                };
            } else if (paramDef.type === 'float') {
                ranges[paramName] = {
                    "t": "float", 
                    "r": [paramDef.min, paramDef.max]
                };
            } else {
                // Skip select fields and other non-optimizable parameters
                ranges[paramName] = {
                    "t": "skip"
                };
            }
        });

        return ranges;
    }

    /**
     * Validate parameter values against definition
     */
    static validateParameters(indicatorType, parameters) {
        const definition = this.getParameterDefinition(indicatorType);
        if (!definition) return { isValid: false, errors: ["Unknown indicator type"] };

        const errors = [];
        
        Object.entries(definition.parameters).forEach(([paramName, paramDef]) => {
            const value = parameters[paramName];
            
            // Check required fields
            if (paramDef.required && (value === undefined || value === null || value === '')) {
                errors.push(`${paramName} is required`);
                return;
            }

            if (value !== undefined && value !== null && value !== '') {
                // Type validation
                if (paramDef.type === 'int' && (!Number.isInteger(Number(value)) || isNaN(Number(value)))) {
                    errors.push(`${paramName} must be an integer`);
                } else if (paramDef.type === 'float' && isNaN(Number(value))) {
                    errors.push(`${paramName} must be a number`);
                } else if (paramDef.type === 'select' && !paramDef.options.includes(value)) {
                    errors.push(`${paramName} must be one of: ${paramDef.options.join(', ')}`);
                }

                // Range validation
                const numValue = Number(value);
                if (!isNaN(numValue)) {
                    if (paramDef.min !== undefined && numValue < paramDef.min) {
                        errors.push(`${paramName} must be at least ${paramDef.min}`);
                    }
                    if (paramDef.max !== undefined && numValue > paramDef.max) {
                        errors.push(`${paramName} must be at most ${paramDef.max}`);
                    }
                }
            }
        });

        return {
            isValid: errors.length === 0,
            errors: errors
        };
    }

    /**
     * Create a new indicator template
     */
    static createIndicatorTemplate(indicatorType, name = '') {
        const parameters = this.generateDefaultParameters(indicatorType);
        const ranges = this.generateGARanges(indicatorType);
        
        return {
            name: name || `${indicatorType}_${Date.now()}`,
            type: "Indicator",
            function: indicatorType,
            agg_config: "5m-normal",
            calc_on_pip: false,
            parameters: parameters,
            ranges: ranges
        };
    }

    /**
     * Get aggregation config options
     */
    static getAggConfigs() {
        return AGG_CONFIGS;
    }
}

// Export for use in other modules
window.INDICATOR_PARAMETER_DEFINITIONS = INDICATOR_PARAMETER_DEFINITIONS;
window.IndicatorParameterUtils = IndicatorParameterUtils;