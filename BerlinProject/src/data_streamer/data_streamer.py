# File: BerlinProject/src/data_streamer/data_streamer.py

"""
Simplified DataStreamer - back to basics with card_id
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
    Simplified DataStreamer with card_id for routing
    """

    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration):
        """
        Initialize simplified DataStreamer

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

        # Store recent data for indicator calculation
        self.recent_ticks: List[TickData] = []
        self.max_history: int = 500

        logger.info(f"DataStreamer initialized: {card_id} ({symbol})")

    def process_tick(self, tick: TickData) -> None:
        """
        Process a single tick - calculate indicators and send to UI

        Args:
            tick: Latest tick data
        """
        if not tick:
            return

        # Ensure tick has symbol
        if not hasattr(tick, 'symbol') or not tick.symbol:
            tick.symbol = self.symbol

        # Add to recent ticks for indicator calculation
        self.recent_ticks.append(tick)

        # Limit history size
        if len(self.recent_ticks) > self.max_history:
            self.recent_ticks = self.recent_ticks[-self.max_history:]

        logger.debug(f"DataStreamer {self.card_id}: Processing tick for {self.symbol} @ ${tick.close:.2f}")

        # Calculate indicators if we have enough data
        if self.indicators and len(self.recent_ticks) >= 20:  # Need minimum data for indicators
            try:
                # Calculate indicators using recent tick history
                indicator_results, raw_indicators, bar_scores = self.indicators.calculate_indicators(self.recent_ticks)

                logger.info(f"DataStreamer {self.card_id}: Calculated indicators - "
                            f"indicators: {len(indicator_results)}, bars: {len(bar_scores or {})}")

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
                logger.error(f"Error calculating indicators for {self.card_id}: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Not enough data for indicators yet, just send price update
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

    def get_current_price(self) -> float:
        """Get current price"""
        if self.recent_ticks:
            return self.recent_ticks[-1].close
        return 0.0

    def get_symbol(self) -> str:
        """Get symbol"""
        return self.symbol

    def get_card_id(self) -> str:
        """Get card ID"""
        return self.card_id