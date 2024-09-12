import numpy as np
import talib

#
def calculate_sma_tick(period: int, data: np.array, history: int = 0) -> float:
    sma = talib.SMA(data[-(period+history):], period)
    return sma[-(history+1):]


#
# def calculate_sma(data: dict, timeperiods, price_type='close'):
#     prices = np.array([d[price_type] for d in data])
#
#     result = [d.copy() for d in data]
#
#     for period in timeperiods:
#         # Calculate SMA using TA-Lib
#         sma = talib.SMA(prices, timeperiod=period)
#
#         # Add SMA values to the result
#         for i, sma_value in enumerate(sma):
#             result[i][f'SMA_{period}'] = sma_value if not np.isnan(sma_value) else None
#
#     return result

#
