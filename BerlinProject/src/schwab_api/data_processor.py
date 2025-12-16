import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("DataProcessor")


class DataProcessor:
    """
    Process and manage streaming and historical market data.
    Handles data cleaning, aggregation, and transformation for display.
    """

    def __init__(self):
        """Initialize the data processor"""
        # Cache for storing processed data by symbol
        self.data_cache = {}
        # Define standard timeframes and their aggregation periods
        self.timeframes = {
            '1m': {'minutes': 1},
            '5m': {'minutes': 5},
            '15m': {'minutes': 15},
            '30m': {'minutes': 30},
            '1h': {'hours': 1},
            '4h': {'hours': 4},
            '1d': {'days': 1}
        }

    def process_historical_data(self, symbol: str, data: List[Dict]) -> List[Dict]:
        """
        Process historical data for a symbol

        Args:
            symbol: Stock symbol
            data: List of historical data points

        Returns:
            List of processed data points
        """
        if not data:
            return []

        # Clean and validate data
        cleaned_data = []
        for point in data:
            # Make sure all required fields are present and in the correct format
            try:
                # Create a clean data point with consistent formatting
                clean_point = {
                    'timestamp': point.get('timestamp', ''),
                    'open': float(point.get('open', 0.0)),
                    'high': float(point.get('high', 0.0)),
                    'low': float(point.get('low', 0.0)),
                    'close': float(point.get('close', 0.0)),
                    'volume': int(point.get('volume', 0))
                }
                cleaned_data.append(clean_point)
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid data point for {symbol}: {e}")

        # Sort by timestamp
        cleaned_data.sort(key=lambda x: x['timestamp'])

        # Cache the processed data
        self.data_cache[symbol] = cleaned_data

        return cleaned_data

    def process_quote_update(self, symbol: str, quote: Dict) -> List[Dict]:
        """
        Process a new quote update for a symbol

        Args:
            symbol: Stock symbol
            quote: Quote data

        Returns:
            Updated list of data points
        """
        if symbol not in self.data_cache:
            self.data_cache[symbol] = []

        # If we have no data yet, create a new candle
        if not self.data_cache[symbol]:
            candle = {
                'timestamp': quote.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                'open': float(quote.get('last', 0.0)),
                'high': float(quote.get('last', 0.0)),
                'low': float(quote.get('last', 0.0)),
                'close': float(quote.get('last', 0.0)),
                'volume': int(quote.get('volume', 0))
            }
            self.data_cache[symbol].append(candle)
            return self.data_cache[symbol]

        # Update the last candle with latest quote
        latest_candle = self.data_cache[symbol][-1]
        last_price = float(quote.get('last', latest_candle['close']))

        latest_candle['close'] = last_price
        latest_candle['high'] = max(latest_candle['high'], last_price)
        latest_candle['low'] = min(latest_candle['low'], last_price)

        # Update volume if available
        if 'volume' in quote:
            latest_candle['volume'] = int(quote.get('volume', 0))

        return self.data_cache[symbol]

    def process_chart_update(self, symbol: str, candle: Dict) -> List[Dict]:
        """
        Process a new chart candle update for a symbol

        Args:
            symbol: Stock symbol
            candle: Candle data (OHLCV)

        Returns:
            Updated list of candles
        """
        if symbol not in self.data_cache:
            self.data_cache[symbol] = []

        # Find if we already have a candle with this timestamp
        existing_candle_idx = None
        for idx, existing_candle in enumerate(self.data_cache[symbol]):
            if existing_candle['timestamp'] == candle['timestamp']:
                existing_candle_idx = idx
                break

        if existing_candle_idx is not None:
            # Update existing candle
            self.data_cache[symbol][existing_candle_idx] = candle
        else:
            # Add new candle, maintain sorted order by timestamp
            self.data_cache[symbol].append(candle)
            self.data_cache[symbol].sort(key=lambda x: x['timestamp'])

        # Limit number of candles to prevent memory issues
        max_candles = 1000
        if len(self.data_cache[symbol]) > max_candles:
            self.data_cache[symbol] = self.data_cache[symbol][-max_candles:]

        return self.data_cache[symbol]

    def process_streaming_update(self, symbol: str, data_point: Dict) -> List[Dict]:
        """
        Process a streaming update for a symbol (could be quote or candle)

        Args:
            symbol: Stock symbol
            data_point: Streaming data update

        Returns:
            Updated list of data points
        """
        # Determine if this is a quote or a candle based on available fields
        if all(field in data_point for field in ['open', 'high', 'low', 'close']):
            # This is a candle update
            return self.process_chart_update(symbol, data_point)
        else:
            # This is a quote update
            return self.process_quote_update(symbol, data_point)

    def get_aggregated_data(self, symbol: str, timeframe: str = '1m') -> List[Dict]:
        """
        Get data aggregated to the specified timeframe

        Args:
            symbol: Stock symbol
            timeframe: Timeframe for aggregation (e.g., '1m', '5m', '1h')

        Returns:
            List of aggregated candles
        """
        if symbol not in self.data_cache or not self.data_cache[symbol]:
            return []

        # If requesting default timeframe (1m), return the cached data
        if timeframe == '1m':
            return self.data_cache[symbol]

        # For other timeframes, we need to aggregate
        try:
            # Convert data to pandas DataFrame for easier aggregation
            df = pd.DataFrame(self.data_cache[symbol])

            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Set timestamp as index
            df.set_index('timestamp', inplace=True)

            # Get aggregation period
            agg_period = self.timeframes.get(timeframe, {'minutes': 1})

            # Resample based on the timeframe
            if 'minutes' in agg_period:
                rule = f"{agg_period['minutes']}min"
            elif 'hours' in agg_period:
                rule = f"{agg_period['hours']}H"
            elif 'days' in agg_period:
                rule = f"{agg_period['days']}D"
            else:
                rule = '1min'  # Default

            # Perform resampling
            resampled = df.resample(rule).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })

            # Drop any rows with NaN values (incomplete candles)
            resampled.dropna(inplace=True)

            # Reset index to convert timestamp back to a column
            resampled.reset_index(inplace=True)

            # Convert timestamp to string format
            resampled['timestamp'] = resampled['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

            # Convert to list of dictionaries
            result = resampled.to_dict('records')

            return result

        except Exception as e:
            logger.error(f"Error aggregating data for {symbol} to {timeframe}: {e}")
            return self.data_cache[symbol]  # Return raw data if aggregation fails