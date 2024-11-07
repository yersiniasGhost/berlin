import numpy as np
from scipy.signal import argrelextrema

import numpy as np
from scipy.signal import argrelextrema


def calculate_resistance(data: np.array, sensitivity: int = 10) -> np.array:
    maxima_indices = argrelextrema(data, np.greater_equal, order=sensitivity)[0]
    return maxima_indices


def calculate_support(data: np.array, sensitivity: int = 10) -> np.array:
    minima_indices = argrelextrema(data, np.less_equal, order=sensitivity)[0]
    return minima_indices


def support_level(data: np.array, sensitivity: int, support_range: float, bounce_level: float,
                  break_level: float, trend: str):
    support_minima = calculate_support(data, sensitivity)
    local_minima = calculate_support(data, 2)
    signals = np.zeros(len(data))

    # Lists to store support levels and their indices
    support_levels = []
    support_indices = []
    current_support_level = None  # Track the current support level

    for i in range(2, len(data)):
        # Check if current index is a calculated support minima
        if i in support_minima:
            # Set the current support level to the new local minimum
            current_support_level = data[i]
            support_levels.append(current_support_level)
            support_indices.append(i)

        # Only perform calculations if a support level has been defined
        if current_support_level is not None:
            lower_bound = current_support_level * (1 - support_range)
            upper_bound = current_support_level * (1 + support_range)

            if trend == 'bull':
                bounce_trigger = current_support_level * (1 + bounce_level)
                # Check for a bullish bounce signal
                if lower_bound < data[i - 1] < upper_bound:
                    if data[i - 1] < bounce_trigger < data[i]:
                        signals[i] = 1

            if trend == 'bear':
                breakthrough_trigger = current_support_level * (1 - break_level)
                # Check for a bearish breakthrough signal before updating support
                if any(data[i - 2:i] > breakthrough_trigger) and data[i] < breakthrough_trigger:
                    signals[i] = 1

        # After checking for signals, update the support level if the current price is lower
        if current_support_level is None or data[i] < current_support_level:
            current_support_level = data[i]
            support_levels.append(current_support_level)
            support_indices.append(i)

    return signals, support_levels, support_indices


def resistance_level(data: np.array, sensitivity: int, resistance_range: float, bounce_level: float,
                     break_level: float, trend: str):
    resistance_maxima = calculate_resistance(data, sensitivity)
    signals = np.zeros(len(data))

    # Lists to store resistance levels and their indices
    resistance_levels = []
    resistance_indices = []
    current_resistance_level = None  # Track the current resistance level

    for i in range(2, len(data)):
        # Check if current index is a calculated resistance maxima
        if i in resistance_maxima:
            # Set the current resistance level to the new local minimum
            current_resistance_level = data[i]
            resistance_levels.append(current_resistance_level)
            resistance_indices.append(i)

        # Only perform calculations if a resistance level has been defined
        if current_resistance_level is not None:
            lower_bound = current_resistance_level * (1 - resistance_range)
            upper_bound = current_resistance_level * (1 + resistance_range)

            if trend == 'bear':
                bounce_trigger = current_resistance_level * (1 - bounce_level)
                # Check for a bullish bounce signal
                if lower_bound < data[i - 1] < upper_bound:
                    if data[i - 1] > bounce_trigger > data[i]:
                        signals[i] = 1

            if trend == 'bull':
                breakthrough_trigger = current_resistance_level * (1 + break_level)
                # Check for a bearish breakthrough signal before updating resistance
                if any(data[i - 2:i] < breakthrough_trigger) and data[i] > breakthrough_trigger:
                    signals[i] = 1

        # After checking for signals, update the resistance level if the current price is lower
        if current_resistance_level is None or data[i] > current_resistance_level:
            current_resistance_level = data[i]
            resistance_levels.append(current_resistance_level)
            resistance_indices.append(i)

    return signals, resistance_levels, resistance_indices
