from datetime import datetime
from typing import List, Dict, Optional
from pymongo import MongoClient

from models.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration
from candle_aggregator.candle_aggregator import CandleAggregator
from candle_aggregator.candle_aggregator_normal import CANormal
from candle_aggregator.candle_aggregator_heiken import CAHeiken


class YahooFinanceHistorical:
    """
    1. Query MongoDB for date range
    2. Convert nested data to TickData objects
    3. Process ALL data through aggregators
    4. Store completed candles in aggregator histories
    """

    def __init__(self, db_host='localhost', db_port=27017, db_name='MTA_devel'):
        self.client = MongoClient(db_host, db_port, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self.collection = self.db['tick_history']

        self.aggregators: Dict[str, CandleAggregator] = {}
        self.ticker: str = ""
        self.total_ticks_processed: int = 0

    def process_historical_data(self, ticker: str, start_date: str, end_date: str,
                                monitor_config: MonitorConfiguration) -> bool:

        print(f"Processing historical data for {ticker}")

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
                print(f"❌ No data found for {ticker}")
                return []

            print(f"Found {len(documents)} MongoDB documents")
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
                            tick = TickData(
                                symbol=ticker,
                                timestamp=dt,
                                open=ohlc['open'],
                                high=ohlc['high'],
                                low=ohlc['low'],
                                close=ohlc['close'],
                                volume=ohlc.get('volume', 0),
                                time_increment="RAW"
                            )
                            raw_ticks.append(tick)

            # Sort chronologically
            raw_ticks.sort(key=lambda x: x.timestamp)

            print(f"Loaded {len(raw_ticks):,} raw ticks")
            return raw_ticks

        except Exception as e:
            print(f"Error loading data: {e}")
            return []

    def _create_aggregators(self, ticker: str, monitor_config: MonitorConfiguration):
        """
        Create aggregators for all required timeframes
        """
        self.ticker = ticker
        timeframes = monitor_config.get_time_increments()
        aggregator_type = monitor_config.get_aggregator_type()

        self.aggregators = {}

        for timeframe in timeframes:
            if aggregator_type == "heiken":
                aggregator = CAHeiken(ticker, timeframe)
            else:
                aggregator = CANormal(ticker, timeframe)

            self.aggregators[timeframe] = aggregator

        print(f"Created {len(self.aggregators)} {aggregator_type} aggregators: {list(timeframes)}")

    def _create_aggregators(self, ticker: str, monitor_config: MonitorConfiguration):
        """Create aggregators based on agg_config"""
        self.ticker = ticker
        aggregator_configs = monitor_config.get_aggregator_configs()  # NEW
        self.aggregators = {}

        for timeframe, agg_type in aggregator_configs.items():
            if agg_type == "heiken":
                aggregator = CAHeiken(ticker, timeframe)
            else:
                aggregator = CANormal(ticker, timeframe)

            self.aggregators[timeframe] = aggregator

        print(f"Created {len(self.aggregators)} aggregators: {aggregator_configs}")


    def _process_all_ticks(self, raw_ticks: List[TickData]):
        """
        Process all ticks through all aggregators
        """
        print(f"Processing {len(raw_ticks):,} ticks through aggregators...")

        self.total_ticks_processed = 0

        for tick in raw_ticks:
            # Update each aggregator
            for timeframe, aggregator in self.aggregators.items():
                aggregator.process_tick(tick)

            self.total_ticks_processed += 1

        print(f"Finished processing {self.total_ticks_processed:,} ticks")

    def _report_results(self):
        """
        Report final candle counts
        """
        print(f"\nAGGREGATOR RESULTS:")

        for timeframe, aggregator in self.aggregators.items():
            history = aggregator.get_history()
            current = aggregator.get_current_candle()

            total_candles = len(history) + (1 if current else 0)

            print(
                f"  {timeframe}: {len(history)} completed + {1 if current else 0} current = {total_candles} total candles")

            if history:
                first_candle = history[0]
                last_candle = history[-1] if history else current
                print(f"    Range: {first_candle.timestamp} to {last_candle.timestamp}")

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
