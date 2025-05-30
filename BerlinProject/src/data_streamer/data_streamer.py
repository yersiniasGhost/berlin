# File: BerlinProject/src/data_streamer/data_streamer.py
# PRODUCTION VERSION - Clean, no debug code

"""
DataStreamer with candle-based indicator processing
"""

import logging
from typing import List, Optional
from datetime import datetime

from environments.tick_data import TickData
from data_streamer.indicator_processor import IndicatorProcessor
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool

logger = logging.getLogger('DataStreamer')


class DataStreamer:
    """
    DataStreamer that processes indicators only on candle completion
    """

    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration):
        """
        Initialize DataStreamer

        Args:
            card_id: Unique card identifier
            symbol: Stock symbol
            monitor_config: Monitor configuration
        """
        self.card_id: str = card_id
        self.symbol: str = symbol
        self.monitor_config: MonitorConfiguration = monitor_config

        # Create indicator processor
        self.indicators: Optional[IndicatorProcessor] = IndicatorProcessor(monitor_config) if monitor_config else None

        # External tools
        self.external_tools: List[ExternalTool] = []

    def process_candle_completion(self, historical_data: List[TickData], completed_candle: TickData) -> None:
        """
        Process indicators when a candle completes

        Args:
            historical_data: Historical candle data for indicator calculation
            completed_candle: The newly completed candle
        """
        if not self.indicators or not historical_data:
            return

        try:
            # Use historical data + completed candle for indicator calculation
            full_history = historical_data + [completed_candle]

            # Calculate indicators using the full history
            indicator_results, raw_indicators, bar_scores = self.indicators.calculate_indicators(full_history)

            # Send to external tools
            for tool in self.external_tools:
                tool.indicator_vector(
                    card_id=self.card_id,
                    symbol=self.symbol,
                    tick=completed_candle,
                    indicators=indicator_results,
                    bar_scores=bar_scores,
                    raw_indicators=raw_indicators
                )

        except Exception as e:
            logger.error(f"Error processing candle completion for {self.card_id}: {e}")

    def process_tick(self, tick: TickData) -> None:
        """
        Process initial tick data (for backward compatibility)

        Args:
            tick: TickData to process
        """
        if not tick:
            return

        # Ensure tick has symbol
        if not hasattr(tick, 'symbol') or not tick.symbol:
            tick.symbol = self.symbol

        # For initial data processing, calculate indicators
        if self.indicators:
            try:
                # Calculate indicators using just this tick
                indicator_results, raw_indicators, bar_scores = self.indicators.calculate_indicators([tick])

                if indicator_results:
                    # Send to external tools
                    for tool in self.external_tools:
                        tool.indicator_vector(
                            card_id=self.card_id,
                            symbol=self.symbol,
                            tick=tick,
                            indicators=indicator_results,
                            bar_scores=bar_scores,
                            raw_indicators=raw_indicators
                        )

            except Exception as e:
                logger.error(f"Error calculating initial indicators for {self.card_id}: {e}")
        else:
            # No indicators, just send price update
            for tool in self.external_tools:
                tool.price_update(
                    card_id=self.card_id,
                    symbol=self.symbol,
                    tick=tick
                )

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool"""
        self.external_tools.append(external_tool)

    def get_symbol(self) -> str:
        """Get symbol"""
        return self.symbol

    def get_card_id(self) -> str:
        """Get card ID"""
        return self.card_id