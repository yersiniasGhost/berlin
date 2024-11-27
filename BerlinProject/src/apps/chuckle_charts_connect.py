from models.monitor_configuration import MonitorConfiguration
from models.monitor_model import Monitor
from models.indicator_definition import IndicatorDefinition
from data_streamer import DataStreamer
from operations.chuckle_charts_web import ChuckleChartsWeb
from config.types import CANDLE_STICK_PATTERN
from mongo_tools.tick_history_tools import TickHistoryTools, RANDOM_MODE, STREAMING_MODE

import logging

# Set pymongo logger level to WARNING
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

indicator_definitions = [
    {
        "name": "macd_cross_bull",
        "type": "Indicator",
        "function": "macd_histogram_crossover",
        "parameters": {
            "slow": 26,
            "fast": 12,
            "signal": 9,
            "histogram_threshold": 0.08,
            "lookback": 10,
            "trend": "bullish"
        },
        "ranges": {
            "slow": {"t": "int", "r": [11, 30]},
            "fast": {"t": "int", "r": [3, 11]},
            "signal": {"t": "int", "r": [3, 11]},
            "histogram_threshold": {"t": "float", "r": [0.02, 0.2]},
            "lookback": {"t": "int", "r": [2, 15]},
            "trend": {"t": "skip"}
        }
    },
    {"name": "bollinger_bull",
     "function": "bol_bands_lower_band_bounce",
     "type": "Indicator",
     "parameters": {
         "period": 25,
         "sd": 2,
         "candle_bounce_number": 3,
         "bounce_trigger": 0.5,
         "lookback": 10,
         "trend": "bearish"
     },
     "ranges": {
         "bounce_trigger": {
             "t": "float",
             "r": [
                 0.1,
                 0.6
             ]
         },
         "lookback": {
             "t": "int",
             "r": [
                 5,
                 15
             ]
         }
     }
     },
    {
        "name": "smaX_bull",
        "function": "sma_crossover",
        "type": "Indicator",
        "parameters": {
            "period": 10,
            "crossover_value": 0.001,
            "lookback": 3,
            "trend": "bullish"
        },
        "ranges": {
            "period": {
                "t": "int",
                "r": [
                    5,
                    25
                ]
            },
            "crossover_value": {
                "t": "float",
                "r": [0.0001, 0.001]},
            "lookback": {
                "t": "int",
                "r": [2, 15]
            }
        }
    },
    {
        "name": "bollinger_bear",
        "function": "bol_bands_lower_band_bounce",
        "type": "Indicator",
        "parameters": {
            "period": 10,
            "sd": 2,
            "candle_bounce_number": 5,
            "bounce_trigger": 0.2,
            "lookback": 10,
            "trend": "bearish"
        },
        "ranges": {
            "bounce_trigger": {
                "t": "float",
                "r": [
                    0.1,
                    0.6
                ]
            },
            "lookback": {
                "t": "int",
                "r": [2, 15]
            },
            "candle_bounce_number": {
                "t": "int",
                "r": [2, 8]
            },
            "period": {
                "t": "int",
                "r": [
                    5,
                    25
                ]
            },
            "sd": {
                "t": "float",
                "r": [
                    1.25,
                    2.75
                ]
            }
        }
    },
    {
        "name": "smaX_bear",
        "function": "sma_crossover",
        "type": "Indicator",
        "parameters": {
            "period": 10,
            "crossover_value": 0.00075,
            "lookback": 5,
            "trend": "bearish"
        }
    },
    {"name": "Three Black Crows", "parameters": {"talib": "CDL3BLACKCROWS", "lookback": 3},
     "type": CANDLE_STICK_PATTERN},
    {"name": "Hammer", "parameters": {"talib": "CDLHAMMER", "lookback": 3}, "type": CANDLE_STICK_PATTERN},
    # {"name": "Shooting Star", "parameters": {"talib": "CDLSHOOTINGSTAR", "lookback": 3}, "type": CANDLE_STICK_PATTERN},
    # {"name": "Doji", "parameters": {"talib": "CDLDOJI", "lookback": 3}, "type": CANDLE_STICK_PATTERN},
    {"name": "Engulfing Bull", "parameters": {"talib": "CDLENGULFING", "lookback": 3, "bull": True},
     "type": CANDLE_STICK_PATTERN},
    {"name": "Engulfing Bear", "parameters": {"talib": "CDLENGULFING", "lookback": 3, "bull": False},
     "type": CANDLE_STICK_PATTERN},
    {"name": "Morning Star", "parameters": {"talib": "CDLMORNINGSTAR", "lookback": 3}, "type": CANDLE_STICK_PATTERN},
    # {"name": "Evening Star", "parameters": {"talib": "CDLEVENINGSTAR", "lookback": 3}, "type": CANDLE_STICK_PATTERN},
    # {"name": "Piercing Line", "parameters": {"talib": "CDLPIERCING", "lookback": 3}, "type": CANDLE_STICK_PATTERN},
    {"name": "Dark Cloud Cover", "parameters": {"talib": "CDLDARKCLOUDCOVER", "lookback": 3},
     "type": CANDLE_STICK_PATTERN},
    {"name": "Hammer pattern", "parameters": {"talib": "CDLHAMMER", "lookback": 3}, "type": CANDLE_STICK_PATTERN}
]
model_config = {"preprocess_config": "test_ds"}
monitor_config = {
    "_id": "65f2d5555555555555555555",
    "user_id": "65f2d6666666666666666666",
    "name": "My Test Strategy",
    "description": "A test monitor using SMA and MACD",
    "threshold": 0.8,
    "bear_threshold": 0.8,
    "triggers": {
        "bollinger_bull": 1.0,
        "macd_cross_bull": 5.0,
        "smaX_bull": 3.0,
        "Hammer pattern": 1.0, "Dark Cloud Cover": 1.0, "Morning Star": 1.0, "Engulfing Bull": 1.0,
        "Hammer": 1.0, "Three Black Crows": 1.0,
    },
    "bear_triggers": {
        "bollinger_bear": 1.0,
        "smaX_bear": 2.0,
        "Engulfing Bear": 1.0
    }
}
data_config = {"type": "TickHistory",
               "configs": [
                   {
                       "ticker": "NVDA",
                       "start_date": "2024-11-12",
                       "end_date": "2024-11-20",
                       "time_increments": 1
                   }
               ]}

if __name__ == "__main__":

    indicators = []
    for ind_def in indicator_definitions:
        indicators.append(IndicatorDefinition(**ind_def))
    monitor_configuration = MonitorConfiguration(name="chuckle_charts", indicators=indicators)
    monitor = Monitor(**monitor_config)

    indicator_tool = ChuckleChartsWeb("Optimizer", monitor)
    data_streamer = DataStreamer(data_config, model_config)
    data_streamer.data_link.delay = 2  # add_options({"delay": 1})
    data_streamer.data_link.set_iteration_mode(STREAMING_MODE, 2)
    data_streamer.replace_monitor_configuration(monitor_configuration)
    data_streamer.connect_tool(indicator_tool)
    data_streamer.run()
