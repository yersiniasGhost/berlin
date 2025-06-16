from typing import List

from models.tick_data import TickData
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


# Use the values from the updated
def calculate_fibonacci_levels(tick_data: List[TickData], parameters: dict) -> tuple[list[np.ndarray], list[int]]:
    data = np.array([tick.close for tick in tick_data])

    # Get support and resistance points
    resistance_maxima = calculate_resistance(data, parameters['sensitivity'])
    support_minima = calculate_support(data, parameters['sensitivity'])
    fibonacci_levels: list[np.ndarray] = []
    fibonacci_indices: list[int] = []
    fib_ratios = np.array([0, 0.236, 0.382, 0.5, 0.618, 0.786, 1], dtype=np.float64)
    current_max = None
    current_min = None

    for i in range(2, len(data)):
        new_levels_found = False
        # update the resistance
        if i in resistance_maxima:
            if current_max is None or data[i] > current_max:
                current_max = data[i]
                new_levels_found = True
        # Update the support
        if i in support_minima:
            if current_min is None or data[i] < current_min:
                current_min = data[i]
                new_levels_found = True
        # Calculate fib levels if we have both high and low
        if (current_max is not None and
                current_min is not None and
                new_levels_found):
            # Price range calculation
            price_range = current_max - current_min
            levels = np.array(current_max - (price_range * fib_ratios), dtype=np.float64)
            fibonacci_levels.append(levels)
            fibonacci_indices.append(i)

    return fibonacci_levels, fibonacci_indices


# For a bullish signal... look if there was prior bullish movement.
# See if after the max is established that it hits one of the retracement levels and starts to increase.
# Check that there is a maxiumum after the minimum.

# def fib_trigger(tick_data: List[TickData], parameters: dict) -> np.ndarray:
#     data = np.array([tick.close for tick in tick_data])
#     fib_data, fib_indices = calculate_fibonacci_levels(tick_data, parameters)
#     signals = np.zeros(len(tick_data))
#
#     bounce_threshold = parameters.get('bounce_threshold')
#     level_threshold = parameters.get('resistance_range')
#
#     for i in range(len(fib_indices)):
#         pass


def fib_trigger(tick_data: List[TickData], parameters: dict) -> np.ndarray:
    """
    Detect bounces off fibonacci levels with configurable look-ahead window
    """
    data = np.array([tick.close for tick in tick_data])
    signals = np.zeros(len(data))

    # Calculate fibonacci levels and track their indices
    fib_data, fib_indices = calculate_fibonacci_levels(tick_data, parameters)

    # Get resistance points for bounce confirmation
    local_maxima = calculate_resistance(data, parameters['local_max_sensitivity'])

    # Get the look ahead window from parameters
    candles_after_bounce = parameters.get('candles_after_bounce', 1)  # Default to 3 if not specified

    current_fib_levels = None  # Current set of fibonacci levels
    last_fib_index = None  # Index where current fib levels were calculated

    for i in range(2, len(data)):
        # Update fibonacci levels if we're at a calculation point
        if i in fib_indices:
            idx = fib_indices.index(i)
            current_fib_levels = fib_data[idx]
            last_fib_index = i

        # Only check for signals if we have fibonacci levels established
        if current_fib_levels is not None and last_fib_index is not None:
            # Check if there's a resistance point between the last fib calculation and current point
            bounce_condition = any((last_fib_index < res_idx < i) for res_idx in local_maxima)

            if parameters['trend'] == 'bullish' and bounce_condition:
                # Check each fibonacci level for potential bounce
                for fib_level in current_fib_levels:
                    lower_bound = fib_level * (1 - parameters['resistance_range'])
                    upper_bound = fib_level * (1 + parameters['resistance_range'])
                    bounce_trigger = fib_level * (1 + parameters['bounce_level'])

                    # Check if price is near fibonacci level
                    if lower_bound < data[i - 1] < upper_bound:
                        # Look ahead for bounce within the specified window
                        look_ahead_end = min(i + candles_after_bounce, len(data))

                        # Check if any point in the look-ahead window shows a bounce
                        for j in range(i, look_ahead_end):
                            if data[i - 1] < bounce_trigger < data[j]:
                                signals[j] = 1
                                break  # Exit once we find a valid bounce

    return signals
