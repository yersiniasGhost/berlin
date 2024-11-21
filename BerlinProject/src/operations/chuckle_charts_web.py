from typing import Dict, Optional
import numpy as np

from config.pyobject_id import PyObjectId
from config.types import INDICATOR_COLLECTION
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration
from models.monitor_model import Monitor
from mongo_tools.mongo import Mongo
from .web_socket_client import WebSocketClient
from .restful_messager import RestfulMessenger


class ChuckleChartsWeb(ExternalTool):

    def __init__(self, name: str, monitor: Monitor, mlf_uri: str = "http://localhost:3000"):
        # self.websocket_client = WebSocketClient(mlf_uri, "need identifier")
        self.mlf_uri = mlf_uri
        self.name = name
        self.monitor = monitor
        self.indicators_with_weights = {}


    @classmethod
    def get_indicator_config(cls, indicator_id: PyObjectId) -> MonitorConfiguration:
        """Get indicator config from MongoDB"""
        collection = Mongo().database[INDICATOR_COLLECTION]
        data = collection.find_one({"_id": indicator_id})
        if not data:
            raise ValueError(f"Indicator not found: {indicator_id}")
        return MonitorConfiguration(**data)

    def indicator_vector(self, indicator_results: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        self.indicators_with_weights = {}
        bull_trigger = self.calculate_trigger(indicator_results, self.monitor.triggers, "bulls")
        bear_trigger = self.calculate_trigger(indicator_results, self.monitor.bear_triggers, "bears")
        self.indicators_with_weights['total_bull'] = bull_trigger
        self.indicators_with_weights['total_bear'] = bear_trigger
        self.indicators_with_weights['tick'] = {'date': tick.timestamp, 'ohlc': [tick.open, tick.high, tick.low, tick.close]}
        self.indicators_with_weights['raw_indicators'] = raw_indicators
        self.update_chuckle()

    def update_chuckle(self):
        # This is now a synchronous call that handles the async operation internally
        # self.websocket_client.send_data(self.indicators_with_weights)
        messenger = RestfulMessenger(self.mlf_uri)
        response = messenger.post('/backtest/update', self.indicators_with_weights)

    def cleanup(self):
        # Make sure to call this when shutting down
        # self.websocket_client.close()
        pass

    def calculate_trigger(self, indicator_results: Dict[str, float], weights: Dict[str, float],
                          indicator_type: str) -> float:
        # indicator results is a dict of (for now) indicator name to the trigger value
        total_weight = 0.0
        trigger = 0.0
        data = {}

        for name, weight in weights.items():

            indicator_value = indicator_results[name]
            weighted_value = weight * indicator_value
            trigger += weighted_value
            data[name] = {"value": indicator_value, "weighted": weighted_value}
            total_weight += weight

        if total_weight == 0.0:
            return 0.0
        normalized_trigger = trigger / total_weight
        self.indicators_with_weights[indicator_type] = data
        return normalized_trigger

    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        pass
