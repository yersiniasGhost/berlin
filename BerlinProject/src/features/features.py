import numpy as np
import talib

#
def calculate_sma_tick(period: int, data: np.array, history: int = 0) -> float:
    sma = talib.SMA(data[-(period+history):], period)
    return sma[-(history+1):]


# def calculate_macd_tick(data: np.array, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9,
#                         history: int = 0) -> tuple:
#     macd, signal, hist = talib.MACD(data, fastperiod=fast_period, slowperiod=slow_period, signalperiod=signal_period)
#
#     macd_values = macd[-(history + 1):]
#     signal_values = signal[-(history + 1):]
#     hist_values = hist[-(history + 1):]
#
#     return macd_values, signal_values, hist_values


def calculate_macd_tick(data: np.array, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9,
                        history: int = 0) -> tuple:
    macd, signal, hist = talib.MACD(data, fastperiod=fast_period, slowperiod=slow_period, signalperiod=signal_period)

    print(f"MACD: {macd}")
    print(f"Signal: {signal}")
    print(f"Histogram: {hist}")

    if history == 0:
        last_macd = macd[-1]
        last_signal = signal[-1]
        last_hist = hist[-1]
        return last_macd, last_signal, last_hist
    else:
        macd_values = macd[-(history + 1):]
        signal_values = signal[-(history + 1):]
        hist_values = hist[-(history + 1):]
        return macd_values, signal_values, hist_values


# data = np.arange(1, 31, dtype=float)
# # Calculate MACD values for the last value in the array
# macd, signal, hist = calculate_macd_tick(data, fast_period=8, slow_period=20, signal_period=5)
#
