from typing import Optional, List, Dict
from environments.tick_data import TickData
import numpy as np
from features.features import calculate_sma_tick, calculate_macd_tick


class DataPreprocessor:

    def __init__(self, model_config: dict):
        self.model_config = model_config
        self.feature_vector = model_config["feature_vector"]
        self.history: List[TickData] = []
        self.normalized_data: List[TickData] = []
        self.tick: Optional[TickData] = None
        self.sample_stats = None

    def get_price_array(self, price_type: str) -> np.array:
        output = [getattr(tick, price_type) for tick in self.normalized_data]
        return np.array(output)

    def next_tick(self, tick: TickData) -> List:
        self.history.append(tick)

        # Perform any required normalization on historical data
        # If no normalization use raw tick
        self.normalize_data(tick)

        output_vector = []
        for feature in self.feature_vector:
            feature_data = self._calculate(feature)
            output_vector = output_vector + feature_data

        return output_vector

    def normalize_data(self, tick: TickData):
        norm_method = self.model_config.get("normalization", None)
        if norm_method == "min_max":
            if not self.sample_stats:
                raise ValueError("No stats available for normalization")

            close_stats = self.sample_stats['close']
            min_close = close_stats['min']
            max_close = close_stats['max']
            normalized_close = (tick.close - min_close) / (max_close - min_close)
            normalized_open = (tick.open - min_close) / (max_close - min_close)
            normalized_high = (tick.high - min_close) / (max_close - min_close)
            normalized_low = (tick.low - min_close) / (max_close - min_close)

            normalized_tick = TickData(
                open=normalized_open,
                high=normalized_high,
                low=normalized_low,
                close=normalized_close,
                volume=tick.volume
            )
        else:
            normalized_tick = tick

        self.normalized_data.append(normalized_tick)
        self.tick = normalized_tick

    def reset_state(self, stats: Dict):
        self.history = []
        self.tick = None
        self.sample_stats = stats
        self.normalized_data = []

    def _calculate(self, feature: dict) -> list:
        name = feature['name']
        if name in ['open', 'close', 'high', 'low']:
            if 'history' in feature:
                h = feature['history']
                if len(self.normalized_data) < h:
                    return [None] * h
                return [getattr(tick, name) for tick in self.normalized_data[-h:]]
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


