from typing import List, Dict
import numpy as np
from models import IndicatorDefinition
from environments.tick_data import TickData
from src.features.indicators import *

class IndicatorCalculator:
    
    def __init__(self):
        pass

    def process_tick_data(self, tick: TickData, history: List[TickData], indicator: IndicatorDefinition) -> Dict[str, np.ndarray]:
        if indicator.name== 'sma_crossover':
            return {indicator['name']: sma_crossover(history, indicator['parameters'])}
        
        elif indicator.name== 'macd_histogram_crossover':
            return {indicator['name']: macd_histogram_crossover(history, indicator['parameters'])}

        elif indicator.name== 'bol_bands_lower_band_bounce':
            return {indicator['name']: sma_crossover(history, indicator['parameters'])}

        else:
            raise ValueError(f"Unknown indicator: {indicator['name']}")


        
        name = indicator.name





#  Get back tester going with collected data... Try to add in stop loss, add in priority.
