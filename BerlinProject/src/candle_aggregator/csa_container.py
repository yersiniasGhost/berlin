from typing import Dict, Any, List
from mongo_tools.mongo_db_connect import MongoDBConnect
from candle_aggregator.candle_aggregator_normal import CANormal
from candle_aggregator.candle_aggregator_heiken import CAHeiken
from candle_aggregator.candle_aggregator import CandleAggregator


class CSAContainer:

    def __init__(self, data_config: Dict[str, Any], aggregator_list: List[str]):
        self.data_config = data_config
        self.aggregator_list = aggregator_list

        self.ticker = data_config['ticker']
        self.start_date = data_config['start_date']
        self.end_date = data_config['end_date']

        self.aggregators: Dict[str, CandleAggregator] = {}

        self._create_aggregators()

    def _create_aggregators(self):
        mongo_connect = MongoDBConnect()
        raw_ticks = mongo_connect._load_raw_ticks(self.ticker, self.start_date, self.end_date)
        mongo_connect.close()

        if not raw_ticks:
            print(f"Warning: No ticks loaded for {self.ticker} {self.start_date} to {self.end_date}")
            return

        for agg_key in self.aggregator_list:
            parts = agg_key.split('-')
            timeframe = parts[0]
            agg_type = parts[1] if len(parts) > 1 else 'normal'

            if agg_type == "heiken":
                aggregator = CAHeiken(self.ticker, timeframe)
            else:
                aggregator = CANormal(self.ticker, timeframe)

            for tick in raw_ticks:
                aggregator.process_tick(tick)

            self.aggregators[agg_key] = aggregator

        print(f"Created {len(self.aggregators)} aggregators for {self.ticker} {self.start_date} to {self.end_date} ({len(raw_ticks)} ticks)")

    def get_aggregators(self) -> Dict[str, CandleAggregator]:
        return self.aggregators

    def get_aggregator(self, agg_key: str) -> CandleAggregator:
        return self.aggregators.get(agg_key)