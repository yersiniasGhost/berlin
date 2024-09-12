from typing import Optional, List
from dataclasses import dataclass
import json
import numpy as np
from features.features import calculate_sma_tick

#next tick
@dataclass
class TickData:
    close: float
    open: float
    high: float
    low: float
    volume: Optional[int] = None



class DataPreprocessor:

    def __init__(self, model_config: dict):
        self.model_config = model_config
        self.feature_vector = model_config["feature_vector"]
        self.history: List[TickData] = []
        self.tick: Optional[TickData] = None

    def get_price_array(self, price_type: str) -> np.array:
        output = [getattr(tick, price_type) for tick in self.history]
        return np.array(output)

    def next_tick(self, tick: TickData)-> List:
        self.history.append(tick)
        self.tick = tick

        # Perform any required normalization on historical data
        ...

        output_vector = []
        for feature in self.feature_vector:
            feature_data = self.calculate(feature)
            output_vector.append(feature_data)

        return output_vector

    def calculate(self, feature: dict) -> float:
        name = feature['name']
        if name in ['open', 'close', 'high', 'low']:
            if 'history' in feature:
                pass
            else:
                return getattr(self.tick, name)

        elif name == 'SMA':
            period = feature['parameters']['sma']
            price_data = self.get_price_array('close')
            if len(price_data) >= period:
                sma_value = calculate_sma_tick(period, price_data)[-1]
                return sma_value
            else:
                return None




    # @classmethod
    # def return_value_array(cls, data, price_type):
    #     return np.array([d[price_type] for d in data])

    # @classmethod
    # def data_prep(cls, ohlc_data_path):
    #     # Read the config file
    #     with open(model_config_path, 'r') as file:
    #         config = json.load(file)
    #
    #     # Read the OHLC data file
    #     with open(ohlc_data_path, 'r') as file:
    #         data = json.load(file)
    #
    #     result = []
    #     feature_vector = config.get('feature_vector', [])
    #
    #     for i in range(len(data['data'])):
    #         tick_data = {}
    #
    #         for feature in feature_vector:
    #             name = feature['name']
    #
    #             if name in ['open', 'close', 'high', 'low']:
    #                 tick_data[name] = data['data'][i][name]
    #
    #             elif name == 'SMA':
    #                 period = feature['parameters']['sma']
    #                 price_data = cls.return_value_array(data['data'][:i + 1], 'close')
    #                 if len(price_data) >= period:
    #                     sma_value = calculate_sma_tick(period, price_data)[-1]
    #                     tick_data['SMA'] = sma_value
    #                 else:
    #                     tick_data['SMA'] = None
    #
    #         result.append(tick_data)
    #
    #     return result


