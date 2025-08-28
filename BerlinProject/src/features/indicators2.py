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

class SupportLevel:
    """Simple horizontal support level"""
    def __init__(self, price, first_index, level_id):
        self.level_id = level_id
        self.price = price  # The horizontal price level
        self.first_index = first_index  # When this level was first established
        self.is_active = True

    def is_broken(self, current_price, break_threshold=0.03):
        """Check if price has moved too far from this support level"""
        lower_bound = self.price * (1 - break_threshold)
        upper_bound = self.price * (1 + break_threshold)
        return current_price < lower_bound or current_price > upper_bound


def create_support_levels(tick_data: List[TickData], parameters: dict) -> List[SupportLevel]:
    """
    Create simple horizontal support levels from support points
    """
    data = np.array([tick.close for tick in tick_data])
    support_minima_indices = calculate_support(data, parameters.get('sensitivity', 5))

    # Convert to support levels
    support_levels = []
    for i, idx in enumerate(support_minima_indices):
        level_id = f"support_{i}"
        level = SupportLevel(data[idx], idx, level_id)
        support_levels.append(level)

    return support_levels


def validate_support_levels(levels: List[SupportLevel], current_price: float) -> List[SupportLevel]:
    """
    Validate support levels - mark broken levels as inactive
    """
    active_levels = []

    for level in levels:
        if not level.is_broken(current_price):
            active_levels.append(level)
        else:
            level.is_active = False

    return active_levels


def get_support_line_details(tick_data: List[TickData], parameters: dict) -> dict:
    """
    Get horizontal support level details for visualization
    """
    data = np.array([tick.close for tick in tick_data])
    support_levels = create_support_levels(tick_data, parameters)
    current_index = len(data) - 1
    current_price = data[current_index]

    # Validate levels
    active_levels = validate_support_levels(support_levels, current_price)

    # Prepare data for UI - convert levels to line format for compatibility
    lines_data = []
    for level in support_levels:
        line_info = {
            'line_id': level.level_id,
            'slope': 0,  # Horizontal line
            'intercept': level.price,  # Price level
            'r_squared': 1.0,
            'is_active': level.is_active,
            'start_index': level.first_index,
            'end_index': current_index + 20,  # Extend into future
            'points': [(level.first_index, level.price)],  # Single support point
            'current_price': level.price,  # Same price (horizontal)
            'slope_history': [
                {
                    'candle_index': level.first_index,
                    'price': level.price,
                    'level_established': True
                }
            ]
        }
        lines_data.append(line_info)

    support_minima = calculate_support(data, parameters.get('sensitivity', 5))

    return {
        'support_lines': lines_data,
        'active_lines_count': len(active_levels),
        'total_lines_count': len(support_levels),
        'support_minima': support_minima.tolist(),
        'parameters_used': parameters
    }


# Legacy functions for compatibility with stock_analysis_ui
def support_level(tick_data: List[TickData], parameters: dict) -> np.ndarray:
    """
    Legacy support level function for compatibility
    """
    data = np.array([tick.close for tick in tick_data])
    signals = np.zeros(len(data))
    
    # Simple bounce detection at support levels
    support_levels = create_support_levels(tick_data, parameters)
    current_price = data[-1] if len(data) > 0 else 0
    
    # Basic bounce logic for the last few candles
    for i in range(max(2, len(data) - 10), len(data)):
        if i >= len(data):
            break
            
        for level in support_levels:
            if level.is_active:
                # Check if price is near support level and bouncing
                near_support = abs(data[i] - level.price) / level.price <= 0.02  # Within 2%
                if near_support and i > 1:
                    if data[i] > data[i-1]:  # Price moving up from support
                        signals[i] = 1
    
    return signals


def resistance_level(tick_data: List[TickData], parameters: dict) -> np.ndarray:
    """
    Legacy resistance level function for compatibility
    """
    data = np.array([tick.close for tick in tick_data])
    signals = np.zeros(len(data))
    
    # Find resistance levels (local maxima)
    resistance_indices = calculate_resistance(data, parameters.get('sensitivity', 5))
    
    # Basic resistance bounce logic for the last few candles
    for i in range(max(2, len(data) - 10), len(data)):
        if i >= len(data):
            break
            
        for res_idx in resistance_indices:
            resistance_price = data[res_idx]
            # Check if price is near resistance level
            near_resistance = abs(data[i] - resistance_price) / resistance_price <= 0.02
            if near_resistance and i > 1:
                if data[i] < data[i-1]:  # Price moving down from resistance
                    signals[i] = 1
    
    return signals


