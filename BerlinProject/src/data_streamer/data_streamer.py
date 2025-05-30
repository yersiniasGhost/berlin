# File: BerlinProject/src/data_streamer/data_streamer.py
# UPDATED VERSION for proper candle-based indicator calculation

"""
DataStreamer with proper candle-based indicator processing
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
            card_id: Unique card identifier (card1, card2, etc.)
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

        logger.info(f"DataStreamer initialized: {card_id} ({symbol})")

    def process_candle_completion(self, historical_data: List[TickData], completed_candle: TickData) -> None:
        """
        Process indicators when a candle completes (not on every PIP)

        Args:
            historical_data: Historical candle data for indicator calculation
            completed_candle: The newly completed candle
        """
        if not self.indicators or not historical_data:
            return

        try:
            logger.info(f"DataStreamer {self.card_id}: Processing candle completion for {self.symbol}")

            # Use historical data + completed candle for indicator calculation
            full_history = historical_data + [completed_candle]

            # Calculate indicators using the full history
            indicator_results, raw_indicators, bar_scores = self.indicators.calculate_indicators(full_history)

            logger.info(f"DataStreamer {self.card_id}: Calculated indicators on candle completion - "
                        f"indicators: {len(indicator_results)}, bars: {len(bar_scores or {})}")

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
            import traceback
            traceback.print_exc()

    def process_tick(self, tick: TickData) -> None:
        """
        Legacy method - now only used for initial data processing
        For live data, use process_candle_completion() instead
        """
        if not tick:
            return

        # Ensure tick has symbol
        if not hasattr(tick, 'symbol') or not tick.symbol:
            tick.symbol = self.symbol

        logger.debug(f"DataStreamer {self.card_id}: Processing initial tick for {self.symbol} @ ${tick.close:.2f}")

        # For initial data processing, still calculate indicators
        if self.indicators:
            try:
                # Calculate indicators using just this tick (for initial display)
                indicator_results, raw_indicators, bar_scores = self.indicators.calculate_indicators([tick])

                if indicator_results:
                    logger.info(f"DataStreamer {self.card_id}: Calculated initial indicators")

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
        logger.info(f"Connected external tool to DataStreamer {self.card_id}")

    def get_symbol(self) -> str:
        """Get symbol"""
        return self.symbol

    def get_card_id(self) -> str:
        """Get card ID"""
        return self.card_id