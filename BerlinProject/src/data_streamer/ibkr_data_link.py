import threading
import time
from typing import Set, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.common import TickerId, BarData
from ibapi.ticktype import TickType

from data_streamer.data_link import DataLink
from models.tick_data import TickData
from config.env_vars import EnvVars
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("IBKRDataLink")



class IBKRDataLink(DataLink, EWrapper, EClient):
    """
    Interactive Brokers data link for streaming market data and loading historical data.
    Connects to IB Gateway and converts IBKR data to TickData objects before passing to DataStreamers.
    """

    def __init__(self, host: str = None, port: int = None, client_id: int = None):
        """
        Initialize IBKR data link

        Args:
            host: IB Gateway host (uses IBKR_HOST from .env if not provided)
            port: IB Gateway port (uses IBKR_PORT from .env if not provided)
            client_id: Unique client ID (uses IBKR_CLIENT_ID from .env if not provided)
        """
        DataLink.__init__(self)
        EClient.__init__(self, self)

        # Load environment variables
        env = EnvVars()

        self.host = host or env.ibkr_host or "127.0.0.1"
        self.port = int(port or env.ibkr_port or 4002)
        self.client_id = int(client_id or env.ibkr_client_id or 1)

        # Connection state
        self.is_connected = False
        self.next_req_id = 1000
        self.connection_lock = threading.Lock()

        # Symbol management
        self.subscribed_symbols: Set[str] = set()
        self.symbol_to_req_id: Dict[str, int] = {}
        self.req_id_to_symbol: Dict[int, str] = {}
        self.contracts: Dict[str, Contract] = {}

        # Real-time data tracking via keepUpToDate historical requests
        self.live_data_requests: Dict[int, str] = {}  # Track which req_ids are for live updates
        self.symbol_timeframes: Dict[str, str] = {}  # Track timeframe per symbol
        self.current_building_candles: Dict[str, TickData] = {}  # Track current building candle per symbol
        self.default_timeframe = env.get_env('DEFAULT_TIMEFRAME', '1m')
        self.extended_hours = env.get_bool('IBKR_EXTENDED_HOURS', 'true')

        # Historical data tracking (only used during initial setup for keepUpToDate requests)
        self.initial_data_loading: Dict[int, bool] = {}  # Track if we're still loading initial data

        # Quote handlers for data dumping
        self.quote_handlers = []

        # Start message processing thread
        self.msg_thread = None

        logger.info(f"Initialized IBKRDataLink for {host}:{port} (client_id: {client_id})")

    def _get_next_req_id(self) -> int:
        """Get next unique request ID"""
        req_id = self.next_req_id
        self.next_req_id += 1
        return req_id

    def _create_stock_contract(self, symbol: str) -> Contract:
        """Create a stock contract for the given symbol"""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def connect_stream(self) -> bool:
        """Connect to IB Gateway"""
        try:
            with self.connection_lock:
                if self.is_connected:
                    logger.info("Already connected to IB Gateway")
                    return True

                logger.info(f"Connecting to IB Gateway at {self.host}:{self.port}")
                self.connect(self.host, self.port, self.client_id)

                # Start message processing thread
                self.msg_thread = threading.Thread(target=self.run, daemon=True)
                self.msg_thread.start()

                # Wait for connection
                timeout = 10
                start_time = time.time()
                while not self.is_connected:
                    if time.time() - start_time > timeout:
                        logger.error("Connection timeout")
                        return False
                    time.sleep(0.1)

                logger.info("Successfully connected to IB Gateway")
                return True

        except Exception as e:
            logger.error(f"Error connecting to IB Gateway: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from IB Gateway"""
        try:
            with self.connection_lock:
                if not self.is_connected:
                    return

                logger.info("Disconnecting from IB Gateway")

                # Cancel all market data subscriptions
                for req_id in self.symbol_to_req_id.values():
                    self.cancelMktData(req_id)

                # Disconnect
                EClient.disconnect(self)
                self.is_connected = False

                # Cancel all live data subscriptions
                for req_id in list(self.live_data_requests.keys()):
                    self.cancelHistoricalData(req_id)

                # Clear data
                self.subscribed_symbols.clear()
                self.symbol_to_req_id.clear()
                self.req_id_to_symbol.clear()
                self.contracts.clear()
                self.live_data_requests.clear()
                self.symbol_timeframes.clear()
                self.current_building_candles.clear()

                logger.info("Disconnected from IB Gateway")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    def add_symbol_subscription(self, symbol: str, timeframe: str = None) -> bool:
        """Add symbol to subscription list and start streaming"""
        try:
            if not self.is_connected:
                logger.error("Not connected to IB Gateway")
                return False

            if symbol in self.subscribed_symbols:
                logger.info(f"Already subscribed to {symbol}")
                return True

            # Create contract
            contract = self._create_stock_contract(symbol)
            self.contracts[symbol] = contract

            # Add to subscribed symbols
            self.subscribed_symbols.add(symbol)

            # Start live data updates using keepUpToDate
            req_id = self._get_next_req_id()
            self.symbol_to_req_id[symbol] = req_id
            self.req_id_to_symbol[req_id] = symbol
            self.live_data_requests[req_id] = symbol

            # Use provided timeframe or default
            actual_timeframe = timeframe or self.default_timeframe

            # Store timeframe for this symbol
            self.symbol_timeframes[symbol] = actual_timeframe

            # Mark this request as initially loading
            self.initial_data_loading[req_id] = True

            # Request live historical data with keepUpToDate=True
            success = self._request_live_data(symbol, req_id, actual_timeframe)

            if success:
                logger.info(f"Started live data updates for {symbol} using keepUpToDate")
                return True
            else:
                # Cleanup on failure
                self.subscribed_symbols.discard(symbol)
                if req_id in self.symbol_to_req_id.values():
                    del self.symbol_to_req_id[symbol]
                if req_id in self.req_id_to_symbol:
                    del self.req_id_to_symbol[req_id]
                if req_id in self.live_data_requests:
                    del self.live_data_requests[req_id]
                return False

        except Exception as e:
            logger.error(f"Error subscribing to {symbol}: {e}")
            return False

    def add_quote_handler(self, handler):
        """Add a quote handler function for data dumping"""
        self.quote_handlers.append(handler)

    def _get_candle_start_time(self, timestamp: datetime, timeframe: str) -> datetime:
        """Get the start time for a candle containing this timestamp"""
        if timeframe == "1m":
            return timestamp.replace(second=0, microsecond=0)
        elif timeframe == "5m":
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == "15m":
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == "30m":
            minute = (timestamp.minute // 30) * 30
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == "1h":
            return timestamp.replace(minute=0, second=0, microsecond=0)
        else:
            return timestamp.replace(second=0, microsecond=0)

    def _is_candle_complete(self, candle_timestamp: datetime, timeframe: str, current_time: datetime) -> bool:
        """Check if a candle is complete based on timeframe"""
        candle_start = self._get_candle_start_time(candle_timestamp, timeframe)

        if timeframe == "1m":
            candle_end = candle_start + timedelta(minutes=1)
        elif timeframe == "5m":
            candle_end = candle_start + timedelta(minutes=5)
        elif timeframe == "15m":
            candle_end = candle_start + timedelta(minutes=15)
        elif timeframe == "30m":
            candle_end = candle_start + timedelta(minutes=30)
        elif timeframe == "1h":
            candle_end = candle_start + timedelta(hours=1)
        else:
            candle_end = candle_start + timedelta(minutes=1)

        return current_time >= candle_end

    def _process_live_candle_update(self, symbol: str, new_candle: TickData, timeframe: str):
        """Process live candle update with smart replace/append logic"""
        try:
            current_time = datetime.now()
            current_building = self.current_building_candles.get(symbol)

            # Normalize candle timestamp to proper timeframe boundary
            candle_start = self._get_candle_start_time(new_candle.timestamp, timeframe)
            new_candle.timestamp = candle_start

            if current_building is None:
                # First candle for this symbol - just start building
                self.current_building_candles[symbol] = new_candle
                logger.info(f"Started building {timeframe} candle for {symbol}: ${new_candle.close}")
                self._send_candle_update(symbol, new_candle, "replace")

            elif current_building.timestamp == candle_start:
                # Same candle timeframe - replace the building candle
                self.current_building_candles[symbol] = new_candle
                logger.info(f"Updated building {timeframe} candle for {symbol}: ${new_candle.close}")
                self._send_candle_update(symbol, new_candle, "replace")

            else:
                # Different timeframe - previous candle is complete, new one starts

                # Check if previous candle should be marked as complete
                prev_complete = self._is_candle_complete(current_building.timestamp, timeframe, current_time)

                if prev_complete:
                    logger.info(f"Completed {timeframe} candle for {symbol}: {current_building.timestamp} - ${current_building.close}")
                    self._send_candle_update(symbol, current_building, "append")

                # Start new building candle
                self.current_building_candles[symbol] = new_candle
                logger.info(f"Started new {timeframe} candle for {symbol}: {new_candle.timestamp} - ${new_candle.close}")
                self._send_candle_update(symbol, new_candle, "replace")

            # Create raw quote data for handlers (data dumping)
            raw_quote = {
                'key': symbol,
                '3': str(new_candle.close),  # Close price
                '8': str(new_candle.volume),  # Volume
                '38': str(int(time.time() * 1000))  # Current timestamp
            }

            # Call quote handlers
            for handler in self.quote_handlers:
                try:
                    handler(raw_quote)
                except Exception as e:
                    logger.error(f"Error in quote handler: {e}")

        except Exception as e:
            logger.error(f"Error processing live candle update for {symbol}: {e}")

    def _send_candle_update(self, symbol: str, tick_data: TickData, action: str):
        """Send candle update to DataStreamers with action indicator"""
        try:
            # Add action metadata to the TickData for DataStreamer to use
            # We'll use a custom attribute (though this is a bit hacky)
            tick_data.action = action  # "replace" or "append"

            logger.info(f"Sending {action} for {symbol}: ${tick_data.close} ({tick_data.time_increment}) at {tick_data.timestamp}")

            # Send to DataStreamers
            if symbol in self.data_streamers:
                for data_streamer in self.data_streamers[symbol]:
                    try:
                        data_streamer.process_tick(tick_data)
                    except Exception as ds_error:
                        logger.error(f"Error in DataStreamer for {symbol}: {ds_error}")
            else:
                logger.debug(f"No DataStreamers registered for symbol: {symbol}")

        except Exception as e:
            logger.error(f"Error sending candle update for {symbol}: {e}")

    # EWrapper callback methods

    def connectAck(self):
        """Called when connection is acknowledged"""
        logger.info("Connection acknowledged by IB Gateway")

    def connectionClosed(self):
        """Called when connection is closed"""
        logger.info("Connection closed")
        self.is_connected = False

    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson = ""):
        """Handle errors from IB Gateway"""
        if errorCode in [2104, 2106, 2158]:  # Market data warnings
            logger.info(f"Market data info ({errorCode}): {errorString}")
        elif errorCode == 200:  # No security definition found
            symbol = self.req_id_to_symbol.get(reqId, "Unknown")
            logger.error(f"No security definition found for {symbol}")
        else:
            logger.error(f"Error {errorCode} (req {reqId}): {errorString}")

    def nextValidId(self, orderId: int):
        """Called with next valid order ID - indicates connection is ready"""
        logger.info(f"Connection ready, next valid ID: {orderId}")
        self.next_req_id = max(self.next_req_id, orderId + 1000)
        self.is_connected = True

    def _request_live_data(self, symbol: str, req_id: int, timeframe: str) -> bool:
        """Request live historical data with keepUpToDate=True"""
        try:
            contract = self.contracts[symbol]

            # Map timeframe to IB API format
            bar_size_map = {
                "1m": "1 min",
                "5m": "5 mins",
                "15m": "15 mins",
                "30m": "30 mins",
                "1h": "1 hour"
            }

            bar_size = bar_size_map.get(timeframe, "1 min")

            # For keepUpToDate requests, don't specify end time - let IB determine current time
            duration = "2 D"

            logger.info(f"Requesting live data for {symbol} ({timeframe}) with keepUpToDate=True")

            # Request historical data with keepUpToDate=True for live updates
            # Note: Empty string for end time when using keepUpToDate
            rth_only = 0 if self.extended_hours else 1  # RTH = 0 for extended hours, 1 for regular hours only
            self.reqHistoricalData(
                req_id, contract, "", duration, bar_size,
                "TRADES", rth_only, 1, True, []
            )

            return True

        except Exception as e:
            logger.error(f"Error requesting live data for {symbol}: {e}")
            return False

    def historicalData(self, reqId: int, bar: BarData):
        """Handle historical data bars from keepUpToDate requests"""
        try:
            # All requests should be live data requests with keepUpToDate=True
            if reqId in self.live_data_requests:
                symbol = self.live_data_requests[reqId]
                timeframe = self.symbol_timeframes.get(symbol, "1m")

                # Convert bar to TickData
                timestamp = datetime.strptime(bar.date, "%Y%m%d %H:%M:%S")
                tick_data = TickData(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume) if bar.volume != -1 else 0,
                    time_increment=timeframe
                )

                # Check if we're still loading initial data vs live updates
                is_initial_loading = self.initial_data_loading.get(reqId, True)

                if is_initial_loading:
                    # During initial load, send all candles as "append" to build history
                    logger.info(f"Initial data for {symbol}: ${tick_data.close} at {tick_data.timestamp}")
                    self._send_candle_update(symbol, tick_data, "append")
                else:
                    # After initial load, use smart replace/append logic
                    self._process_live_candle_update(symbol, tick_data, timeframe)

        except Exception as e:
            logger.error(f"Error processing historical data: {e}")

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Called when initial historical data load is complete for keepUpToDate requests"""
        if reqId in self.live_data_requests:
            symbol = self.live_data_requests[reqId]
            logger.info(f"Initial historical data loaded for {symbol}, switching to live updates")

            # Mark that initial loading is complete - future data will be live updates
            self.initial_data_loading[reqId] = False


