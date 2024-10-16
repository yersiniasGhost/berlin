import numpy as np
import talib


#
def calculate_sma_tick(period: int, data: np.array, history: int = 0) -> float:
    sma = talib.SMA(data[-(period + history):], period)
    return sma[-(history + 1):]


def calculate_macd_tick(data: np.array, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9,
                        history: int = 0) -> tuple:
    window_size = slow_period + signal_period + history
    window_data = data[-window_size:]

    if window_size > len(window_data):
        raise ValueError(
            f"Insufficient data for expected window size {window_size} and data length: {len(window_data)}")

    macd, signal, hist = talib.MACD(window_data, fast_period, slow_period, signal_period)

    macd_values = macd[-(history + 1):]
    signal_values = signal[-(history + 1):]
    hist_values = hist[-(history + 1):]
    return macd_values, signal_values, hist_values
