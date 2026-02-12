"""
Refactored technical indicators using the new configurable base system.

Each indicator is defined in its own module. This file re-exports them all
for backward compatibility -- importing this module registers every indicator
with the IndicatorRegistry singleton.
"""

from indicator_triggers.sma_indicator import SMAIndicator
from indicator_triggers.sma_crossover_indicator import SMACrossoverIndicator
from indicator_triggers.macd_histogram_crossover_indicator import MACDHistogramCrossoverIndicator
from indicator_triggers.bollinger_bands_indicator import BollingerBandsLowerBandBounceIndicator
from indicator_triggers.support_resistance_indicator import SupportResistanceIndicator
from indicator_triggers.cdl_pattern_indicator import CDLPatternIndicator
from indicator_triggers.rsi_indicator import RSIIndicator

__all__ = [
    "SMAIndicator",
    "SMACrossoverIndicator",
    "MACDHistogramCrossoverIndicator",
    "BollingerBandsLowerBandBounceIndicator",
    "SupportResistanceIndicator",
    "CDLPatternIndicator",
    "RSIIndicator",
]
