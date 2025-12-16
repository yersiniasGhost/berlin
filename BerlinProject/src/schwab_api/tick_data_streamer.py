import os
import time
import json
import pandas as pd
from datetime import datetime
from schwab_api.streamer_client import SchwabStreamerClient
from typing import Dict, List, Any, Optional
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("TickStreamer")


class TickDataProcessor:
    """
    Process and store real-time tick data received from Schwab API.
    """

    def __init__(self, symbols: List[str]):
        """
        Initialize the tick data processor.

        Args:
            symbols: List of stock symbols to track
        """
        self.symbols = symbols
        self.tick_data = {}
        self.last_tick_time = {}

        # Initialize data structure for each symbol
        for symbol in symbols:
            self.tick_data[symbol] = []
            self.last_tick_time[symbol] = None

        # Setup output directory
        self.output_dir = 'tick_data'
        os.makedirs(self.output_dir, exist_ok=True)

    def process_tick(self, tick: Dict[str, Any]):
        """
        Process a single tick and store it.

        Args:
            tick: Tick data dictionary
        """
        symbol = tick.get('key')
        if not symbol or symbol not in self.symbols:
            return

        # Extract relevant fields
        timestamp = tick.get('35', int(time.time() * 1000))  # Trade time or current time
        bid = tick.get('1')
        ask = tick.get('2')
        last = tick.get('3')
        bid_size = tick.get('4')
        ask_size = tick.get('5')
        volume = tick.get('8')
