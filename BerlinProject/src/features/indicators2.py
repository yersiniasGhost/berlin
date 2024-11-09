from typing import Dict, List

import numpy as np
from scipy.signal import argrelextrema

from environments.tick_data import TickData
import numpy as np
from scipy.signal import argrelextrema


def calculate_resistance(data: np.array, sensitivity: int = 10) -> np.array:
    maxima_indices = argrelextrema(data, np.greater_equal, order=sensitivity)[0]
    return maxima_indices


def calculate_support(data: np.array, sensitivity: int = 10) -> np.array:
    minima_indices = argrelextrema(data, np.less_equal, order=sensitivity)[0]
    return minima_indices


# sensitivity: used for calculating the initial support lines, looks to see if it is max of n in front and behind it.
# local_max_sensitivity: for making sure it does not trigger off the initial new support line and actaully "bounces"
# support_range: float for checking if it goes within a range of the current support. then considers it a trigger
#  bounce level: percentage of support line + support line it has to hit to consider a trigger
# break_level amount under the support line it has to go to consider it a breakthrough
#  trend: bullish or bearish

def support_level(tick_data: List[TickData], parameters: dict) -> np.ndarray:
    # sensitivity: int, local_max_sensitivity: int, support_range: float,
    # bounce_level: float,
    # break_level: float, trend: str

    data = np.array([tick.close for tick in tick_data])

    support_minima = calculate_support(data, parameters['sensitivity'])
    local_maxima = calculate_resistance(data, parameters['local_max_sensitivity'])
    signals = np.zeros(len(data))

    # Lists to store support levels and their indices
    support_levels = []
    support_indices = []
    current_support_level = None  # Track the current support level
    last_support_index = None  # Track the index of the most recent support level

    for i in range(2, len(data)):
        # Check if current index is a calculated support minima
        if i in support_minima:
            # Set the current support level to the new local minimum
            current_support_level = data[i]
            support_levels.append(current_support_level)
            support_indices.append(i)
            last_support_index = i  # Update last support index

        # Only perform calculations if a support level has been defined
        if current_support_level is not None:
            lower_bound = current_support_level * (1 - parameters['support_range'])
            upper_bound = current_support_level * (1 + parameters['support_range'])

            # Check if there's a resistance point between the last support and the current point
            bounce_condition = any((last_support_index < res_idx < i) for res_idx in local_maxima)

            if parameters['trend'] == 'bullish' and bounce_condition:
                bounce_trigger = current_support_level * (1 + parameters['bounce_level'])
                # Check for a bullish bounce signal
                if lower_bound < data[i - 1] < upper_bound:
                    if data[i - 1] < bounce_trigger < data[i]:
                        signals[i] = 1

            if parameters['trend'] == 'bearish':
                breakthrough_trigger = current_support_level * (1 - parameters['break_level'])
                # Check for a bearish breakthrough signal before updating support
                if bounce_condition and any(data[i - 2:i] > breakthrough_trigger) and data[i] < breakthrough_trigger:
                    signals[i] = 1

        # After checking for signals, update the support level if the current price is lower
        if current_support_level is None or data[i] < current_support_level:
            current_support_level = data[i]
            support_levels.append(current_support_level)
            support_indices.append(i)
            last_support_index = i  # Update last support index when support changes

    return signals


def resistance_level(tick_data: List[TickData], parameters: dict):
    data = np.array([tick.close for tick in tick_data])
    resistance_maxima = calculate_resistance(data, parameters['sensitivity'])
    local_minima = calculate_support(data, parameters['local_min_sensitivity'])
    signals = np.zeros(len(data))

    # Lists to store resistance levels and their indices
    resistance_levels = []
    resistance_indices = []
    current_resistance_level = None  # Track the current resistance level
    last_resistance_index = None  # Track the index of the most recent resistance level

    for i in range(2, len(data)):
        # Check if current index is a calculated resistance maxima
        if i in resistance_maxima:
            # Set the current resistance level to the new local maximum
            current_resistance_level = data[i]
            resistance_levels.append(current_resistance_level)
            resistance_indices.append(i)
            last_resistance_index = i  # Update last resistance index

        # Only perform calculations if a resistance level has been defined
        if current_resistance_level is not None:
            lower_bound = current_resistance_level * (1 - parameters['resistance_range'])
            upper_bound = current_resistance_level * (1 + parameters['resistance_range'])

            # Check for a local minimum between the last resistance and the current point
            bounce_condition = any(last_resistance_index < min_idx < i for min_idx in local_minima)

            if parameters['trend'] == 'bearish' and bounce_condition:
                bounce_trigger = current_resistance_level * (1 - parameters['bounce_level'])
                # Check for a bearish bounce signal
                if lower_bound < data[i - 1] < upper_bound:
                    if data[i - 1] > bounce_trigger > data[i]:
                        signals[i] = 1

            if parameters['trend'] == 'bullish':
                breakthrough_trigger = current_resistance_level * (1 + parameters['break_level'])
                # Check for a bullish breakthrough signal
                if any(data[i - 2:i] < breakthrough_trigger) and data[i] > breakthrough_trigger:
                    signals[i] = 1

        # After checking for signals, update the resistance level if the current price is higher
        if current_resistance_level is None or data[i] > current_resistance_level:
            current_resistance_level = data[i]
            resistance_levels.append(current_resistance_level)
            resistance_indices.append(i)
            last_resistance_index = i  # Update last resistance index when resistance changes

    return signals
