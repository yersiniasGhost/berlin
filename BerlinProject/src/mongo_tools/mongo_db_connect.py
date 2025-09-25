from datetime import datetime
from typing import List, Dict, Optional
from pymongo import MongoClient

from models.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration
from candle_aggregator.candle_aggregator import CandleAggregator
from candle_aggregator.candle_aggregator_normal import CANormal
from candle_aggregator.candle_aggregator_heiken import CAHeiken
from config.env_vars import EnvVars


# we use mongodb and the collection tick_history_polygon now.

class MongoDBConnect:
    """
    1. Query MongoDB for date range
    2. Convert nested data to TickData objects
    3. Process ALL data through aggregators
    4. Store completed candles in aggregator histories
    """

    #

    def __init__(self):
        # Get configuration from environment variables
        env = EnvVars()
        self.client = MongoClient(env.mongo_host, env.mongo_port, serverSelectionTimeoutMS=5000)
        self.db = self.client[env.mongo_database]
        self.collection = self.db[env.mongo_collection]

        self.aggregators: Dict[str, CandleAggregator] = {}
        self.ticker: str = ""
        self.total_ticks_processed: int = 0

    def _parse_float_value(self, value):
        """
        Parse float values that may be stored as strings with 'float: ' prefix

        Args:
            value: Could be a float, string, or string with 'float: ' prefix

        Returns:
            float: Parsed float value
        """
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            # Handle "float: 186.952392578125" format
            if value.startswith("float: "):
                parsed_value = float(value[7:])  # Remove "float: " prefix
                # Debug: Parsed string value
                return parsed_value
            # Handle direct string numbers
            parsed_value = float(value)
            # Debug: Parsed string value
            return parsed_value

        # Debug: Default fallback for value
        return 0.0  # Default fallback

    def process_historical_data(self, ticker: str, start_date: str, end_date: str,
                                monitor_config: MonitorConfiguration) -> bool:

        # Processing data for ticker and date range

        # Clear any existing data to ensure fresh load
        self.aggregators.clear()
        self.ticker = ticker
        self.total_ticks_processed = 0

        raw_ticks = self._load_raw_ticks(ticker, start_date, end_date)
        if not raw_ticks:
            return False

        self._create_aggregators(ticker, monitor_config)
        self._process_all_ticks(raw_ticks)
        self._report_results()

        return True

    def _load_raw_ticks(self, ticker: str, start_date: str, end_date: str) -> List[TickData]:
        """
        Query MongoDB and convert to TickData objects
        """
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            query = {
                'ticker': ticker,
                'year': {'$gte': start.year, '$lte': end.year},
                'month': {'$gte': start.month, '$lte': end.month}
            }

            documents = list(self.collection.find(query).sort([('year', 1), ('month', 1)]))

            if not documents:
                # No data found for ticker
                return []

            # Found MongoDB documents
            raw_ticks = []

            for doc in documents:
                year = doc['year']
                month = doc['month']
                data_dict = doc.get('data', {})

                for day_str, day_data in data_dict.items():
                    day = int(day_str)

                    for timestamp_str, ohlc in day_data.items():
                        timestamp_seconds = int(timestamp_str)

                        # Convert timestamp
                        hours = timestamp_seconds // 3600
                        minutes = (timestamp_seconds % 3600) // 60
                        seconds = timestamp_seconds % 60

                        dt = datetime(year, month, day, hours, minutes, seconds)

                        if start.date() <= dt.date() <= end.date():
                            # Debug: Skip raw OHLC logging for performance

                            # Parse OHLC values using the helper method
                            parsed_open = self._parse_float_value(ohlc['open'])
                            parsed_high = self._parse_float_value(ohlc['high'])
                            parsed_low = self._parse_float_value(ohlc['low'])
                            parsed_close = self._parse_float_value(ohlc['close'])

                            # Debug: Skip parsed OHLC logging for performance

                            tick = TickData(
                                symbol=ticker,
                                timestamp=dt,
                                open=parsed_open,
                                high=parsed_high,
                                low=parsed_low,
                                close=parsed_close,
                                volume=ohlc.get('volume', 0),
                                time_increment="RAW"
                            )
                            raw_ticks.append(tick)

            # Sort chronologically
            raw_ticks.sort(key=lambda x: x.timestamp)

            return raw_ticks

        except Exception as e:
            # Error loading data
            import traceback
            traceback.print_exc()
            return []

    # Fix the _create_aggregators method in YahooFinanceHistorical

    def _create_aggregators(self, ticker: str, monitor_config: MonitorConfiguration):
        """Create aggregators based on agg_config"""
        self.ticker = ticker
        aggregator_configs = monitor_config.get_aggregator_configs()  # Returns {"1m-normal": "normal", "5m-normal": "normal"}
        self.aggregators = {}

        for agg_key, agg_type in aggregator_configs.items():
            timeframe = agg_key.split('-')[0]

            if agg_type == "heiken":
                aggregator = CAHeiken(ticker, timeframe)
            else:
                aggregator = CANormal(ticker, timeframe)

            # Store with the full key for lookup purposes
            self.aggregators[agg_key] = aggregator

        # Created aggregators

        # DEBUG: Print what timeframes are being used
        for agg_key, aggregator in self.aggregators.items():
            # Aggregator timeframe info
            pass

    def _process_all_ticks(self, raw_ticks: List[TickData]):
        """
        Process all ticks through all aggregators
        """
        # Processing ticks through aggregators

        self.total_ticks_processed = 0

        for tick in raw_ticks:
            # Update each aggregator
            for timeframe, aggregator in self.aggregators.items():
                aggregator.process_tick(tick)

            self.total_ticks_processed += 1

        # Finished processing ticks

    def _report_results(self):
        """
        Report final candle counts
        """
        # AGGREGATOR RESULTS

        for timeframe, aggregator in self.aggregators.items():
            history = aggregator.get_history()
            current = aggregator.get_current_candle()

            total_candles = len(history) + (1 if current else 0)

            # Aggregator results summary

            if history:
                first_candle = history[0]
                last_candle = history[-1] if history else current
                # Candle range info

                # Skip candle details for performance

    def get_aggregator(self, timeframe: str) -> Optional[CandleAggregator]:
        """
        Get specific aggregator with all processed history
        """
        return self.aggregators.get(timeframe)

    def get_all_aggregators(self) -> Dict[str, CandleAggregator]:
        """
        Get all aggregators with processed histories
        """
        return self.aggregators.copy()

    def get_candle_history(self, timeframe: str) -> List[TickData]:
        """
        Get completed candle history for timeframe
        """
        aggregator = self.aggregators.get(timeframe)
        if aggregator:
            return aggregator.get_history()
        return []

    def get_all_candle_data(self) -> Dict[str, List[TickData]]:
        """
        Get all candle data for all timeframes
        """
        result = {}

        for timeframe, aggregator in self.aggregators.items():
            # Include completed history + current candle
            history = aggregator.get_history().copy()
            current = aggregator.get_current_candle()

            if current:
                history.append(current)

            result[timeframe] = history

        return result

    def close(self):
        self.client.close()
