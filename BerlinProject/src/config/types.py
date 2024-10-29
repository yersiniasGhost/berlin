from typing import Union
from bson.objectid import ObjectId
from config.pyobject_id import PyObjectId

PYMONGO_ID = Union[str, PyObjectId]
MONGO_ID = Union[str, ObjectId]
# DATETIME must be iso formatted string.
DATETIME = str

# Add collection names here
PROFILE_COLLECTION = ("Profiles")
SAMPLE_COLLECTION = ("Samples")
TICK_HISTORY_COLLECTION = ("tick_history")
MONITOR_COLLECTION = ('monitors')
INDICATOR_COLLECTION = ('indicators')

AgentActions = float
RANDOM_TRADER = "random"
MODEL_AGENT = "rl_agent"
BUY = 'Buy'
SELL = 'Sell'
IN = "In"
OUT = "Out"
HOLD = 'Hold'
ACTION = str

PATTERN_MATCH = "Pattern"
CANDLE_STICK_PATTERN = "CDL"
INDICATOR_TYPE = "Indicator"

