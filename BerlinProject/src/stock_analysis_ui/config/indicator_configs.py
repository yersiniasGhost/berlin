from typing import Dict, List, Any

# Constants for indicator types
INDICATOR_TYPE = "INDICATOR_TYPE"
CANDLE_STICK_PATTERN = "CANDLE_STICK_PATTERN"

# Default indicator configuration
DEFAULT_INDICATORS = [
    {
        "name": "sma_crossover",
        "type": INDICATOR_TYPE,
        "function": "sma_crossover",
        "parameters": {
            "period": 20,
            "crossover_value": 0.002,
            "trend": "bullish",
            "lookback": 10
        }
    },
    {
        "name": "macd_signal",
        "type": INDICATOR_TYPE,
        "function": "macd_histogram_crossover",
        "parameters": {
            "fast": 12,
            "slow": 26,
            "signal": 9,
            "histogram_threshold": 0.1,
            "trend": "bullish",
            "lookback": 15
        }
    },
    {
        "name": "bollinger_bounce",
        "type": INDICATOR_TYPE,
        "function": "bol_bands_lower_band_bounce",
        "parameters": {
            "period": 20,
            "sd": 2,
            "candle_bounce_number": 3,
            "bounce_trigger": 0.3,
            "lookback": 10,
            "trend": "bullish"
        }
    },
]

# Available indicator templates that users can add
AVAILABLE_INDICATORS = [
    {
        "name": "sma_crossover_bullish",
        "display_name": "SMA Crossover (Bullish)",
        "type": INDICATOR_TYPE,
        "function": "sma_crossover",
        "parameters": {
            "period": 20,
            "crossover_value": 0.002,
            "trend": "bullish",
            "lookback": 10
        }
    },
    {
        "name": "sma_crossover_bearish",
        "display_name": "SMA Crossover (Bearish)",
        "type": INDICATOR_TYPE,
        "function": "sma_crossover",
        "parameters": {
            "period": 20,
            "crossover_value": 0.002,
            "trend": "bearish",
            "lookback": 10
        }
    },
    {
        "name": "macd_signal_bullish",
        "display_name": "MACD Signal (Bullish)",
        "type": INDICATOR_TYPE,
        "function": "macd_histogram_crossover",
        "parameters": {
            "fast": 12,
            "slow": 26,
            "signal": 9,
            "histogram_threshold": 0.1,
            "trend": "bullish",
            "lookback": 15
        }
    },
    {
        "name": "macd_signal_bearish",
        "display_name": "MACD Signal (Bearish)",
        "type": INDICATOR_TYPE,
        "function": "macd_histogram_crossover",
        "parameters": {
            "fast": 12,
            "slow": 26,
            "signal": 9,
            "histogram_threshold": 0.1,
            "trend": "bearish",
            "lookback": 15
        }
    },
    {
        "name": "bollinger_bounce_bullish",
        "display_name": "Bollinger Band Bounce (Bullish)",
        "type": INDICATOR_TYPE,
        "function": "bol_bands_lower_band_bounce",
        "parameters": {
            "period": 20,
            "sd": 2,
            "candle_bounce_number": 3,
            "bounce_trigger": 0.3,
            "lookback": 10,
            "trend": "bullish"
        }
    },
    {
        "name": "bollinger_bounce_bearish",
        "display_name": "Bollinger Band Bounce (Bearish)",
        "type": INDICATOR_TYPE,
        "function": "bol_bands_lower_band_bounce",
        "parameters": {
            "period": 20,
            "sd": 2,
            "candle_bounce_number": 3,
            "bounce_trigger": 0.3,
            "lookback": 10,
            "trend": "bearish"
        }
    },
    {
        "name": "support_level_bullish",
        "display_name": "Support Level (Bullish)",
        "type": INDICATOR_TYPE,
        "function": "support_level",
        "parameters": {
            "sensitivity": 30,
            "local_max_sensitivity": 1,
            "support_range": 0.01,
            "bounce_level": 0.005,
            "break_level": 0.0002,
            "trend": "bullish",
            "lookback": 10
        }
    },
    {
        "name": "resistance_level_bullish",
        "display_name": "Resistance Level (Bullish)",
        "type": INDICATOR_TYPE,
        "function": "resistance_level",
        "parameters": {
            "sensitivity": 20,
            "local_min_sensitivity": 1,
            "resistance_range": 0.005,
            "bounce_level": 0.005,
            "break_level": 0.003,
            "trend": "bullish",
            "lookback": 10
        }
    }
]

# Default weights for indicators
DEFAULT_WEIGHTS = {
    "sma_crossover": 3.0,
    "macd_signal": 7.0,
    "bollinger_bounce": 5.0,
    "support_level_bullish": 4.0,
    "resistance_level_bullish": 4.0
}

def create_monitor_configuration(indicators: List[Dict[str, Any]], name: str = "trading_signals") -> Dict[str, Any]:
    """Create a monitor configuration from a list of indicators"""
    return {
        "name": name,
        "indicators": indicators
    }