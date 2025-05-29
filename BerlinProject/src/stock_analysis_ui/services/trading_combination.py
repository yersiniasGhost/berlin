# File: BerlinProject/src/stock_analysis_ui/services/trading_combination.py

"""
TradingCombination wrapper class for encapsulating DataStreamer + metadata
"""

import uuid
from typing import Dict, Set, Optional
from data_streamer.data_streamer import DataStreamer
from data_streamer.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration


class TradingCombination:
    """
    Wrapper class that encapsulates a DataStreamer with its metadata and unique identifiers
    """

    def __init__(self, symbol: str, monitor_config: MonitorConfiguration,
                 config_file: str = None, card_id: Optional[str] = None):
        """
        Initialize a trading combination

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            monitor_config: MonitorConfiguration object
            config_file: Path to config file (optional, for metadata)
            card_id: Optional custom card ID
        """
        self.symbol: str = symbol
        self.monitor_config: MonitorConfiguration = monitor_config
        self.config_file: str = config_file or "unknown"

        # Generate unique identifiers
        self.combination_id: str = card_id or self._generate_combination_id()
        self.card_id: str = self.combination_id  # Same as combination_id for simplicity
        self.unique_aggregator_key: str = f"{symbol}_{self.combination_id}"

        # Get timeframes from monitor config
        self.timeframes: Set[str] = monitor_config.get_time_increments()

        # Will be populated later
        self.aggregators: Dict[str, CandleAggregator] = {}
        self.data_streamer: Optional[DataStreamer] = None

    def _generate_combination_id(self) -> str:
        """Generate a unique combination ID"""
        short_uuid = str(uuid.uuid4())[:8]
        return f"{self.symbol}_{self.monitor_config.name}_{short_uuid}".replace(' ', '_')

    def create_data_streamer(self) -> DataStreamer:
        """Create and return a DataStreamer with combination_id for routing"""
        model_config = {
            "feature_vector": [
                {"name": "close"},
                {"name": "open"},
                {"name": "high"},
                {"name": "low"}
            ]
        }

        # Create DataStreamer with combination_id for routing
        self.data_streamer = DataStreamer(
            combination_id=self.combination_id,
            model_configuration=model_config,
            indicator_configuration=self.monitor_config
        )

        return self.data_streamer

    def get_metadata(self) -> Dict:
        """Get combination metadata"""
        return {
            'combination_id': self.combination_id,
            'symbol': self.symbol,
            'monitor_config_name': self.monitor_config.name,
            'config_file': self.config_file,
            'card_id': self.card_id,
            'unique_aggregator_key': self.unique_aggregator_key,
            'timeframes': list(self.timeframes),
            'has_data_streamer': self.data_streamer is not None,
            'aggregators_count': len(self.aggregators)
        }

    def __str__(self) -> str:
        return f"TradingCombination(id={self.combination_id}, symbol={self.symbol}, config={self.monitor_config.name})"

    def __repr__(self) -> str:
        return self.__str__()