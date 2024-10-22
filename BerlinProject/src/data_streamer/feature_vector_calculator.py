from typing import Optional, List, Dict
from environments.tick_data import TickData
import numpy as np
from features.features import calculate_sma_tick, calculate_macd_tick
from data_streamer.data_preprocessor import DataPreprocessor


class FeatureVectorCalculator:

    def __init__(self, model_config: dict):
        self.model_config = model_config
        self.feature_vector = model_config["feature_vector"]
        self.tick: Optional[TickData] = None
        self.history: Optional[List[TickData]] = None

    def get_price_array(self, price_type: str) -> np.array:
        output = [getattr(tick, price_type) for tick in self.history]
        return np.array(output)

    def next_tick(self, data_preprocessor: DataPreprocessor) -> List:

        self.tick, self.history = data_preprocessor.get_normalized_data()
        output_vector = []
        for feature in self.feature_vector:
            feature_data = self._calculate(feature)
            output_vector = output_vector + feature_data

        return output_vector

    def _calculate(self, feature: dict) -> list:
        name = feature['name']
        if name in ['open', 'close', 'high', 'low']:
            if 'history' in feature:
                h = feature['history']
                if len(self.history) < h:
                    return [None] * h
                return [getattr(tick, name) for tick in self.history[-h:]]
                # raise ValueError("History on high low close not implemented yet")
            else:
                return [getattr(self.tick, name)]

        # TODO: Add history
        elif name == "SMADiff":
            period_fast = feature['parameters']['fast_period']
            period_slow = feature['parameters']['slow_period']
            price_data = self.get_price_array('close')
            if len(price_data) >= period_slow:
                sma_slow = calculate_sma_tick(period_slow, price_data)
                sma_fast = calculate_sma_tick(period_fast, price_data)
                d = sma_fast[-1] - sma_slow[-1]
                return [sma_fast[-1] - sma_slow[-1]]
            else:
                return [None]

        # TODO:  Add history
        elif name == 'SMA':
            period = feature['parameters']['sma']
            price_data = self.get_price_array('close')
            if len(price_data) >= period:
                sma_value = calculate_sma_tick(period, price_data)
                return [sma_value[-1]]
            else:
                return [None]

        elif name == 'MACD':
            fast_period = feature['parameters']['fast_period']
            slow_period = feature['parameters']['slow_period']
            signal_period = feature['parameters']['signal_period']
            price_data = self.get_price_array('close')
            h = feature['history'] if 'history' in feature else 0
            window_size = slow_period + signal_period + h
            if len(price_data) >= window_size:
                try:
                    macd, signal, hist = calculate_macd_tick(price_data, fast_period, slow_period, signal_period, h)
                    nested_list = [macd[-h-1:], signal[-h-1:], hist[-h-1:]]
                    out = np.array(nested_list).flatten().tolist()
                    return out

                except ValueError:
                    return [None] * (3 * (h+1))
            return [None, None, None]


