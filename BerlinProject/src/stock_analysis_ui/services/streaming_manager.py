import logging
from typing import Dict, List, Tuple
from collections import defaultdict
from data_streamer.candle_aggregator import CandleAggregator

logger = logging.getLogger("StreamingManager")


class StreamingManager:
    def __init__(self, data_link=None):
        self.streamers_by_symbol = defaultdict(list)
        self.data_link = data_link
        self.aggregators = defaultdict(dict)

    def register_streamer(self, symbol: str, monitor_config, data_streamer):
        """
        Register a DataStreamer with its symbol and monitor configuration.
        Extract required timeframes from monitor config.
        """
        # Extract timeframes from monitor config indicators
        required_timeframes = self._extract_timeframes_from_config(monitor_config)

        logger.info(f"Registering DataStreamer for {symbol} with timeframes: {required_timeframes}")
        self.streamers_by_symbol[symbol].append(data_streamer)

        # Add to (symbol, timeframe) tracking and create aggregators
        for timeframe in required_timeframes:
            # Create aggregator if it doesn't exist
            if timeframe not in self.aggregators[symbol]:
                aggregator = CandleAggregator(symbol, timeframe)
                self.aggregators[symbol][timeframe] = aggregator
                logger.info(f"Created CandleAggregator for {symbol}-{timeframe}")


    def _extract_timeframes_from_config(self, monitor_config) -> List[str]:
        """Extract unique timeframes from monitor configuration indicators"""
        timeframes = set()

        # Check if monitor_config has indicators
        if hasattr(monitor_config, 'indicators'):
            for indicator in monitor_config.indicators:
                # Check for time_increment attribute
                if hasattr(indicator, 'time_increment'):
                    timeframes.add(indicator.time_increment)
                else:
                    # Default to 1m if not specified
                    timeframes.add("1m")

        # If no indicators found, default to 1m
        if not timeframes:
            timeframes.add("1m")

        return list(timeframes)

    def route_pip_data_old(self, pip_data: Dict):
        """
        Route incoming PIP data to all relevant CandleAggregators.
        Handle completed candles returned by aggregators.
        """
        # Extract symbol from PIP
        symbol = pip_data.get('key')

        # Send PIP to all aggregators for this symbol
        if symbol in self.aggregators:
            for aggregator in self.aggregators[symbol].values():
                # Process PIP and get any completed candle
                aggregator.process_pip(pip_data)

        for streamer in self.streamers_by_symbol[symbol]:
            streamer.process_tick(self.aggregators[symbol])

    def route_pip_data_old(self, pip_data: Dict):
        symbol = pip_data.get('key')

        csas = self.aggregators[symbol]

        for csa in csas.values():
            completed_candle = csa.process_pip(pip_data)
            if completed_candle:
                pass

    def route_pip_data(self, pip_data: Dict):
        """
        Route incoming PIP data to ALL relevant CandleAggregators.
        This handles both symbol-based and unique combination-based aggregators.
        """
        logger.info(f"🔥 ROUTE_PIP_DATA CALLED with data: {pip_data}")

        # Extract symbol from PIP
        symbol = pip_data.get('key')
        if not symbol:
            logger.warning("No symbol in PIP data")
            return

        logger.info(f"🚀 Routing PIP data for {symbol}")

        # Process ALL aggregators that should receive this symbol's data
        aggregators_processed = 0
        completed_candles = []

        # Get all aggregator keys that should receive this symbol's data
        relevant_keys = []

        # 1. Direct symbol match
        if symbol in self.aggregators:
            relevant_keys.append(symbol)

        # 2. Unique combination keys that start with this symbol
        for key in self.aggregators.keys():
            if key.startswith(f"{symbol}_") and key != symbol:
                relevant_keys.append(key)

        if not relevant_keys:
            logger.warning(f"❌ No aggregators found for symbol {symbol}")
            logger.warning(f"Available aggregator keys: {list(self.aggregators.keys())}")
            return

        logger.info(f"✅ Found {len(relevant_keys)} aggregator sets for {symbol}: {relevant_keys}")

        # Process each relevant aggregator set
        for aggregator_key in relevant_keys:
            aggregator_set = self.aggregators[aggregator_key]

            for timeframe, aggregator in aggregator_set.items():
                completed_candle = aggregator.process_pip(pip_data)
                aggregators_processed += 1

                if completed_candle:
                    logger.info(
                        f"🕯️ Completed candle for {symbol} ({aggregator_key}) in {timeframe}: ${completed_candle.close:.2f}")
                    completed_candles.append((aggregator_key, timeframe, completed_candle))

        if completed_candles:
            logger.info(f"📊 Generated {len(completed_candles)} completed candles for {symbol}")

        logger.info(f"✅ Processed PIP for {symbol} across {aggregators_processed} aggregators")

    def start_streaming(self):
        """
        Start receiving PIP data from the data link.
        Register this manager as a chart handler.
        """
        if self.data_link:
            # Register as chart data handler
            self.data_link.add_chart_handler(self.route_pip_data)
            logger.info(
                f"Started streaming for symbols / timeframes")
        else:
            logger.error("No data link configured")

    def stop_streaming(self):
        """Stop streaming and clear handlers"""
        if self.data_link and hasattr(self.data_link, 'chart_handlers'):
            # Remove this manager from chart handlers
            if self.route_pip_data in self.data_link.chart_handlers:
                self.data_link.chart_handlers.remove(self.route_pip_data)

        logger.info("Stopped streaming")

    def get_status(self) -> Dict:
        """Get current status of the streaming manager"""
        return {
            "total_streamers": len(self.streamers_by_symbol),
            "total_aggregators": sum(len(timeframes) for timeframes in self.aggregators.values()),
            "aggregators_by_symbol": {symbol: list(timeframes.keys()) for symbol, timeframes in
                                      self.aggregators.items()}
        }
