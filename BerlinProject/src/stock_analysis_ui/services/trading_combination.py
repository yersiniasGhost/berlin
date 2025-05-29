import logging
from typing import Optional, Set
from datetime import datetime

from data_streamer.data_streamer import DataStreamer
from models.monitor_configuration import MonitorConfiguration

logger = logging.getLogger('TradingCombination')


class TradingCombination:
    """
    Wrapper for a trading combination with simple ID routing
    Represents one symbol + monitor config combination
    """

    def __init__(self, symbol: str, monitor_config: MonitorConfiguration, card_id: Optional[str] = None):
        # Generate simple combination_id
        self.combination_id = card_id or f"{symbol}_{monitor_config.name}_{id(self)}"
        self.symbol = symbol
        self.monitor_config = monitor_config

        # Create DataStreamer with combination_id
        self.data_streamer = DataStreamer(
            combination_id=self.combination_id,  # Pass the ID to DataStreamer
            model_configuration={"feature_vector": [{"name": "close"}]},
            indicator_configuration=monitor_config
        )

        # Unique aggregator key for StreamingManager routing
        self.unique_aggregator_key = f"{symbol}_{self.combination_id}"

        # Extract timeframes from monitor config
        self.timeframes: Set[str] = monitor_config.get_time_increments()

        # Metadata for UI and management
        self.metadata = {
            'combination_id': self.combination_id,
            'symbol': symbol,
            'monitor_config_name': monitor_config.name,
            'timeframes': list(self.timeframes),
            'unique_aggregator_key': self.unique_aggregator_key,
            'created_at': datetime.now().isoformat(),
            'indicators_count': len(monitor_config.indicators) if monitor_config.indicators else 0,
            'bars_config': getattr(monitor_config, 'bars', {})
        }

        logger.info(f"Created TradingCombination with ID: {self.combination_id} ({symbol})")

    def get_combination_id(self) -> str:
        """Get the combination ID"""
        return self.combination_id

    def get_symbol(self) -> str:
        """Get the symbol"""
        return self.symbol

    def get_timeframes(self) -> Set[str]:
        """Get required timeframes"""
        return self.timeframes

    def get_unique_aggregator_key(self) -> str:
        """Get the unique aggregator key for StreamingManager"""
        return self.unique_aggregator_key

    def get_metadata(self) -> dict:
        """Get combination metadata"""
        return self.metadata.copy()

    def connect_to_external_tool(self, external_tool) -> None:
        """Connect the DataStreamer to an external tool"""
        self.data_streamer.connect_tool(external_tool)
        logger.info(f"Connected {self.combination_id} to external tool")

    def process_indicators(self, aggregators: dict) -> None:
        """Process indicators using the provided aggregators"""
        try:
            self.data_streamer.process_tick(aggregators)
            logger.debug(f"Processed indicators for {self.combination_id}")
        except Exception as e:
            logger.error(f"Error processing indicators for {self.combination_id}: {e}")
            raise

    def __str__(self) -> str:
        return f"TradingCombination({self.combination_id}: {self.symbol} + {self.monitor_config.name})"

    def __repr__(self) -> str:
        return (f"TradingCombination(combination_id='{self.combination_id}', "
                f"symbol='{self.symbol}', config='{self.monitor_config.name}')")