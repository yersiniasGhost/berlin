from typing import Dict, Optional, List
import numpy as np
from datetime import datetime
from data_streamer.external_tool import ExternalTool
from models.tick_data import TickData
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("SchwabAdapter")


class SchwabDataStreamAdapter(ExternalTool):
    """
    Adapter to connect Schwab streaming data to the DataStreamer framework

    Implements the ExternalTool interface to convert Schwab streaming data
    into the format expected by the DataStreamer.
    """

    def __init__(self, symbols: List[str] = None):
        """
        Initialize the adapter

        Args:
            symbols: List of stock symbols to track
        """
        self.symbols = symbols or []
        self.latest_data = {}

        # Callbacks for different data types
        self.feature_callbacks = []
        self.indicator_callbacks = []
        self.sample_callbacks = []

    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        """
        Process feature vector data

        Args:
            fv: Feature vector
            tick: Tick data
        """
        for callback in self.feature_callbacks:
            callback(fv, tick)

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        """
        Process indicator vector data

        Args:
            indicators: Dictionary of indicators
            tick: Tick data
            index: Index of the tick
            raw_indicators: Raw indicator values
        """
        for callback in self.indicator_callbacks:
            callback(indicators, tick, index, raw_indicators)

    def present_sample(self, sample: dict, index: int):
        """
        Handle sample presentation

        Args:
            sample: Sample data
            index: Index of the sample
        """
        for callback in self.sample_callbacks:
            callback(sample, index)

    def reset_next_sample(self):
        """Reset state for next sample"""
        pass

    def handle_quote_data(self, data):
        """
        Process quote data from Schwab

        Args:
            data: List of quote data items
        """
        for quote in data:
            symbol = quote.get('key', '')
            if symbol and symbol in self.symbols:
                try:
                    # Extract relevant fields
                    timestamp = datetime.now()
                    price = float(quote.get('3', 0.0))  # Last price
                    bid = float(quote.get('1', 0.0))  # Bid price
                    ask = float(quote.get('2', 0.0))  # Ask price
                    volume = int(quote.get('8', 0))  # Volume

                    # Create TickData object
                    tick_data = TickData(
                        symbol=symbol,
                        timestamp=timestamp,
                        price=price,
                        volume=volume,
                        bid=bid,
                        ask=ask,
                        open_price=price,
                        high_price=price,
                        low_price=price,
                        close_price=price
                    )

                    self.latest_data[symbol] = tick_data
                    logger.debug(f"Processed quote for {symbol}: {price}")

                except Exception as e:
                    logger.error(f"Error processing quote for {symbol}: {e}")

    def handle_chart_data(self, data):
        """
        Process chart data from Schwab

        Args:
            data: List of chart data items
        """
        for chart_entry in data:
            symbol = chart_entry.get('key', '')
            if symbol and symbol in self.symbols:
                try:
                    # Extract timestamp
                    timestamp_ms = int(chart_entry.get('7', 0))
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

                    # Extract OHLCV data
                    open_price = float(chart_entry.get('2', 0.0))
                    high_price = float(chart_entry.get('3', 0.0))
                    low_price = float(chart_entry.get('4', 0.0))
                    close_price = float(chart_entry.get('5', 0.0))
                    volume = int(chart_entry.get('6', 0))

                    # Create TickData object
                    tick_data = TickData(
                        symbol=symbol,
                        timestamp=timestamp,
                        price=close_price,
                        volume=volume,
                        bid=close_price,  # Use close as bid for simplicity
                        ask=close_price,  # Use close as ask for simplicity
                        open_price=open_price,
                        high_price=high_price,
                        low_price=low_price,
                        close_price=close_price
                    )

                    self.latest_data[symbol] = tick_data
                    logger.debug(
                        f"Processed candle for {symbol} at {timestamp}: O:{open_price} H:{high_price} L:{low_price} C:{close_price} V:{volume}")

                    # Convert to feature vector and process
                    fv = self._convert_to_feature_vector(tick_data)
                    self.feature_vector(fv, tick_data)

                except Exception as e:
                    logger.error(f"Error processing chart data for {symbol}: {e}")

    def _convert_to_feature_vector(self, tick_data: TickData) -> np.array:
        """
        Convert TickData to feature vector

        Args:
            tick_data: TickData object

        Returns:
            numpy array of features
        """
        # Create simple feature vector with OHLCV data
        return np.array([
            tick_data.open_price,
            tick_data.high_price,
            tick_data.low_price,
            tick_data.close_price,
            tick_data.volume
        ])

    def add_feature_callback(self, callback):
        """Add callback for feature vector data"""
        self.feature_callbacks.append(callback)

    def add_indicator_callback(self, callback):
        """Add callback for indicator vector data"""
        self.indicator_callbacks.append(callback)

    def add_sample_callback(self, callback):
        """Add callback for sample data"""
        self.sample_callbacks.append(callback)