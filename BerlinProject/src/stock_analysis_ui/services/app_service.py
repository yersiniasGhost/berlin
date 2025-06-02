# File: BerlinProject/src/stock_analysis_ui/services/app_service.py
# PRODUCTION VERSION - All debug code removed

"""
Application service with proper candle aggregation
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from flask_socketio import SocketIO
from collections import defaultdict

from data_streamer import IndicatorProcessor

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..', '..'))

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_streamer import DataStreamer
from data_streamer.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from stock_analysis_ui.services.ui_external_tool import UIExternalTool
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
from environments.tick_data import TickData

logger = logging.getLogger('AppService')


class AppService:
    """
    Application service with candle aggregation and indicator processing
    """

    def __init__(self, socketio: SocketIO, auth_manager: SchwabAuthManager):
        self.socketio: SocketIO = socketio
        self.auth_manager: SchwabAuthManager = auth_manager

        # Core components
        self.data_link: Optional[SchwabDataLink] = None
        self.ui_tool: UIExternalTool = UIExternalTool(socketio)

        # State tracking
        self.is_streaming: bool = False
        self.combinations: Dict[str, Dict] = {}
        self.card_counter: int = 0
        self.subscribed_symbols: set = set()

        # Candle aggregators: symbol -> {timeframe -> CandleAggregator}
        self.aggregators: Dict[str, Dict[str, CandleAggregator]] = defaultdict(dict)

        logger.info("AppService initialized")

    def start_streaming(self) -> bool:
        """Initialize streaming infrastructure"""
        if self.is_streaming:
            return True

        try:
            logger.info("Starting streaming infrastructure...")

            # Setup data link
            self.data_link = SchwabDataLink()
            self.data_link.access_token = self.auth_manager.access_token
            self.data_link.refresh_token = self.auth_manager.refresh_token
            self.data_link.user_prefs = self.auth_manager.user_prefs

            if not self.data_link.connect_stream():
                logger.error("Failed to connect to Schwab streaming")
                return False

            self.is_streaming = True
            logger.info("Streaming infrastructure started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            self.is_streaming = False
            return False

    def add_combination(self, symbol: str, config_file: str) -> Dict:
        """Add a new combination with candle aggregation"""
        try:
            if not self.is_streaming:
                if not self.start_streaming():
                    return {"success": False, "error": "Failed to start streaming"}

            # Auto-generate card ID
            self.card_counter += 1
            card_id = f"card{self.card_counter}"

            # Load monitor configuration
            monitor_config = self._load_monitor_config(config_file)
            if not monitor_config:
                return {"success": False, "error": f"Failed to load config: {config_file}"}

            # Get required timeframes from indicators
            timeframes = monitor_config.get_time_increments()

            # Create aggregators for each required timeframe
            if symbol not in self.aggregators:
                self.aggregators[symbol] = {}

            for timeframe in timeframes:
                if timeframe not in self.aggregators[symbol]:
                    aggregator = CandleAggregator(symbol, timeframe)
                    # Load historical data
                    count = aggregator.prepopulate_data(self.data_link)
                    self.aggregators[symbol][timeframe] = aggregator
                    logger.info(f"Created aggregator for {symbol}-{timeframe}, loaded {count} candles")

            # Create DataStreamer
            data_streamer = DataStreamer(
                card_id=card_id,
                symbol=symbol,
                monitor_config=monitor_config
            )

            # Connect UI tool
            data_streamer.connect_tool(self.ui_tool)

            # Store combination
            self.combinations[card_id] = {
                'card_id': card_id,
                'symbol': symbol,
                'config_file': config_file,
                'monitor_config': monitor_config,
                'data_streamer': data_streamer,
                'timeframes': timeframes
            }

            # Subscribe to quotes for this symbol
            self._ensure_symbol_subscription(symbol)

            # Send initial data to UI
            self._send_initial_data(card_id, symbol)

            logger.info(f"Successfully added combination: {card_id} ({symbol})")

            return {
                "success": True,
                "card_id": card_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name
            }

        except Exception as e:
            logger.error(f"Error adding combination: {e}")
            return {"success": False, "error": str(e)}

    def _send_initial_data(self, card_id: str, symbol: str):
        """Send initial price data to UI"""
        try:
            # Get current price from any aggregator
            current_price = 0.0
            for timeframe, aggregator in self.aggregators[symbol].items():
                current_candle = aggregator.get_current_candle()
                if current_candle and current_candle.close > 0:
                    current_price = current_candle.close
                    break

            if current_price > 0:
                # Send initial price update
                self.ui_tool.price_update(
                    card_id=card_id,
                    symbol=symbol,
                    tick=self._create_mock_tick(symbol, current_price)
                )

        except Exception as e:
            logger.error(f"Error sending initial data for {card_id}: {e}")

    def _create_mock_tick(self, symbol: str, price: float) -> TickData:
        """Create a mock tick for initial data"""
        return TickData(
            symbol=symbol,
            timestamp=datetime.now(),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=1000,
            time_increment="1m"
        )

    def remove_combination(self, card_id: str) -> Dict:
        """Remove a combination"""
        try:
            if card_id not in self.combinations:
                return {"success": False, "error": "Combination not found"}

            del self.combinations[card_id]
            logger.info(f"Removed combination: {card_id}")

            return {"success": True}

        except Exception as e:
            logger.error(f"Error removing combination: {e}")
            return {"success": False, "error": str(e)}

    def get_combinations(self) -> Dict:
        """Get all active combinations"""
        return {
            "combinations": [
                {
                    "card_id": card_id,
                    "symbol": data["symbol"],
                    "monitor_config_name": data["monitor_config"].name
                }
                for card_id, data in self.combinations.items()
            ],
            "total": len(self.combinations)
        }

    def _ensure_symbol_subscription(self, symbol: str):
        """Subscribe to quotes for symbol and set up PIP processing"""
        try:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.add(symbol)
                all_symbols = list(self.subscribed_symbols)

                self.data_link.subscribe_quotes(all_symbols)

                # Set up quote handler for this symbol
                def quote_handler(quote_data):
                    if quote_data.get('key') == symbol:
                        self._process_pip_for_symbol(symbol, quote_data)

                self.data_link.add_quote_handler(quote_handler)

        except Exception as e:
            logger.error(f"Error subscribing to symbol {symbol}: {e}")

    def _process_pip_for_symbol(self, symbol: str, quote_data: Dict):
        """Process PIP data for a symbol - aggregate into candles"""
        try:
            # Process PIP through all aggregators for this symbol
            if symbol in self.aggregators:
                for timeframe, aggregator in self.aggregators[symbol].items():
                    # Process PIP and check if candle completed
                    completed_candle = aggregator.process_pip(quote_data)

                    if completed_candle:
                        # Process indicators for combinations that use this timeframe
                        self._process_completed_candle(symbol, timeframe, completed_candle)

            # Also send current price updates to UI
            self._send_current_price_updates(symbol, quote_data)

        except Exception as e:
            logger.error(f"Error processing PIP for {symbol}: {e}")

    def _process_completed_candle(self, symbol: str, timeframe: str, completed_candle):
        """Process indicators ONLY when their specific timeframe completes"""
        try:
            print(f"🕯️ {symbol}-{timeframe} candle completed @ ${completed_candle.close:.2f}")

            processed_combinations = 0
            for card_id, combination in self.combinations.items():
                if combination['symbol'] == symbol:

                    # NEW LOGIC: Only process indicators that match THIS timeframe
                    timeframe_indicators = [
                        ind for ind in combination['monitor_config'].indicators
                        if getattr(ind, 'time_increment', '1m') == timeframe
                    ]

                    if timeframe_indicators:
                        processed_combinations += 1

                        print(f"⚙️ Processing {len(timeframe_indicators)} {timeframe} indicators for {card_id}")
                        for ind in timeframe_indicators:
                            print(f"   📊 {ind.name} ({timeframe})")

                        # Get historical data for ALL timeframes (for context)
                        historical_data = self._get_historical_data_for_combination(symbol, combination['timeframes'])

                        # Create a timeframe-specific processor
                        timeframe_config = MonitorConfiguration(
                            name=f"{combination['monitor_config'].name}_{timeframe}",
                            indicators=timeframe_indicators
                        )
                        # Copy bars configuration
                        if hasattr(combination['monitor_config'], 'bars'):
                            timeframe_config.bars = combination['monitor_config'].bars

                        # Process only these indicators
                        processor = IndicatorProcessor(timeframe_config)
                        indicator_results, raw_indicators, bar_scores = processor.calculate_indicators(historical_data)

                        # Send to UI tool
                        for tool in combination['data_streamer'].external_tools:
                            tool.indicator_vector(
                                card_id=card_id,
                                symbol=symbol,
                                tick=completed_candle,
                                indicators=indicator_results,
                                bar_scores=bar_scores,
                                raw_indicators=raw_indicators
                            )

            print(f"🔄 Processed {processed_combinations} combinations for {symbol}-{timeframe}")

        except Exception as e:
            logger.error(f"Error processing completed candle: {e}")

    def _send_current_price_updates(self, symbol: str, quote_data: Dict):
        """Send current price updates to UI for real-time display"""
        try:
            # Extract price from quote
            price = None
            for field in ['3', '2', '1', '5']:
                if field in quote_data:
                    try:
                        price = float(quote_data[field])
                        if price > 0:
                            break
                    except:
                        continue

            if not price:
                return

            # Create current tick
            current_tick = self._create_mock_tick(symbol, price)

            # Send to all combinations with this symbol
            for card_id, combination in self.combinations.items():
                if combination['symbol'] == symbol:
                    self.ui_tool.price_update(
                        card_id=card_id,
                        symbol=symbol,
                        tick=current_tick
                    )

        except Exception as e:
            logger.error(f"Error sending current price updates: {e}")

    def _get_historical_data_for_combination(self, symbol: str, timeframes: set) -> List:
        """Get historical data for all timeframes used by a combination"""
        historical_data = []

        for timeframe in timeframes:
            if symbol in self.aggregators and timeframe in self.aggregators[symbol]:
                aggregator = self.aggregators[symbol][timeframe]
                history = aggregator.get_history()
                historical_data.extend(history)

        # Sort by timestamp
        historical_data.sort(key=lambda x: x.timestamp)
        return historical_data

    def _load_monitor_config(self, config_file: str) -> Optional[MonitorConfiguration]:
        """Load monitor configuration from JSON file"""
        try:
            # Try different paths
            possible_paths = [
                config_file,
                os.path.join(os.path.dirname(__file__), '..', config_file),
                os.path.join(os.path.dirname(__file__), '..', '..', config_file)
            ]

            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break

            if not config_path:
                logger.error(f"Config file not found: {config_file}")
                return None

            with open(config_path, 'r') as f:
                config_data = json.load(f)

            # Extract monitor and indicators
            monitor_data = config_data.get('monitor', {})
            indicators_data = config_data.get('indicators', [])

            # Create IndicatorDefinition objects
            indicators = []
            for ind_data in indicators_data:
                indicator = IndicatorDefinition(
                    name=ind_data['name'],
                    type=ind_data['type'],
                    function=ind_data['function'],
                    parameters=ind_data['parameters'],
                    time_increment=ind_data.get('time_increment', '1m')
                )
                indicators.append(indicator)

            # Create MonitorConfiguration
            monitor_config = MonitorConfiguration(
                name=monitor_data.get('name', 'Trading Signals'),
                indicators=indicators
            )

            # Add bars if present
            if 'bars' in monitor_data:
                monitor_config.bars = monitor_data['bars']

            return monitor_config

        except Exception as e:
            logger.error(f"Error loading monitor config: {e}")
            return None

    def get_available_configs(self) -> List[str]:
        """Get available monitor configuration files"""
        config_files = []

        # Look in current directory and parent directories
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dirs = [
            os.path.join(current_dir, '..'),
            os.path.join(current_dir, '..', '..'),
            '.'
        ]

        for config_dir in config_dirs:
            if os.path.exists(config_dir):
                for file in os.listdir(config_dir):
                    if file.endswith('.json') and ('monitor' in file.lower() or 'config' in file.lower()):
                        if file not in config_files:
                            config_files.append(file)

        if not config_files:
            config_files = ['monitor_config_example_time_intervals.json']

        return sorted(config_files)

    def stop_streaming(self) -> bool:
        """Stop all streaming"""
        try:
            self.is_streaming = False

            if self.data_link:
                self.data_link.disconnect()

            logger.info("Streaming stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            return False

    def _calculate_indicator_history(self, historical_data: List[TickData],
                                     monitor_config: MonitorConfiguration,
                                     lookback_periods: int = 50) -> Dict:
        """Calculate indicator values over historical periods"""
        try:
            if len(historical_data) < lookback_periods:
                lookback_periods = len(historical_data)

            indicator_history = {
                'timestamps': [],
                'indicators': {},
                'bar_scores': {},
                'periods': lookback_periods
            }

            # Initialize indicator arrays
            for indicator in monitor_config.indicators:
                indicator_history['indicators'][indicator.name] = []

            # Initialize bar arrays
            if hasattr(monitor_config, 'bars'):
                for bar_name in monitor_config.bars.keys():
                    indicator_history['bar_scores'][bar_name] = []

            # Calculate indicators for each historical period
            processor = IndicatorProcessor(monitor_config)

            # Sample historical data at regular intervals
            step_size = max(1, len(historical_data) // lookback_periods)

            for i in range(lookback_periods, len(historical_data), step_size):
                # Get data up to this point
                data_slice = historical_data[:i]

                if len(data_slice) > 20:  # Ensure enough data for calculation
                    indicators, raw_indicators, bar_scores = processor.calculate_indicators(data_slice)

                    # Store timestamp
                    indicator_history['timestamps'].append(data_slice[-1].timestamp.isoformat())

                    # Store indicator values
                    for indicator_name in indicator_history['indicators'].keys():
                        value = indicators.get(indicator_name, 0.0)
                        indicator_history['indicators'][indicator_name].append(value)

                    # Store bar scores
                    for bar_name in indicator_history['bar_scores'].keys():
                        value = bar_scores.get(bar_name, 0.0)
                        indicator_history['bar_scores'][bar_name].append(value)

            return indicator_history

        except Exception as e:
            logger.error(f"Error calculating indicator history: {e}")
            return {'timestamps': [], 'indicators': {}, 'bar_scores': {}, 'periods': 0}
