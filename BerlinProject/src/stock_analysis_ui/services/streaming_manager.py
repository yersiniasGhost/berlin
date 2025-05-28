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

    def route_pip_data(self, pip_data: Dict):
        symbol = pip_data.get('key')

        csas = self.aggregators[symbol]

        for csa in csas.values():
            completed_candle = csa.process_pip(pip_data)
            if completed_candle:
                pass

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
