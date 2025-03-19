import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('DataProcessor')


class DataProcessor:
    def __init__(self):
        self.symbol_data = {}  # Store data for each symbol
        self.last_real_prices = {}  # Track the last valid price for each symbol

    def process_historical_data(self, symbol, data):
        """Process historical data and establish a baseline for streaming"""
        if not data:
            logger.warning(f"No historical data for {symbol}")
            return []

        # Convert to pandas DataFrame for easier manipulation
        try:
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Sort by timestamp (ascending)
            df = df.sort_values('timestamp')

            # Convert numeric columns
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Fill any NaN values with previous valid values
            df = df.fillna(method='ffill')

            # Check for large gaps in data (more than 1 hour)
            # If found, split the data into segments to avoid straight lines
            split_dfs = []
            current_df = df.copy()

            if not current_df.empty:
                for i in range(1, len(current_df)):
                    current_time = current_df.iloc[i]['timestamp']
                    prev_time = current_df.iloc[i - 1]['timestamp']
                    time_diff = (current_time - prev_time).total_seconds() / 60  # diff in minutes

                    # If gap is more than 60 minutes, end this segment and start a new one
                    if time_diff > 60:
                        # End the previous segment
                        split_dfs.append(current_df.iloc[:i])
                        # Start a new segment
                        current_df = current_df.iloc[i:]

                # Add the last segment
                if not current_df.empty:
                    split_dfs.append(current_df)

                # If we have segments, process them separately
                if split_dfs:
                    final_df = pd.concat([df.iloc[:0]] * 0)  # Empty dataframe with same structure

                    for segment in split_dfs:
                        # Only keep the last few points before a gap and first few after to minimize straight lines
                        final_df = pd.concat([final_df, segment])
                else:
                    final_df = df
            else:
                final_df = df

            # Store last valid price
            if not final_df.empty:
                last_row = final_df.iloc[-1]
                self.last_real_prices[symbol] = last_row['close']
                logger.info(f"Set last real price for {symbol}: {self.last_real_prices[symbol]}")

            # Store the processed data
            self.symbol_data[symbol] = final_df

            # Return as list of dicts
            return final_df.to_dict('records')

        except Exception as e:
            logger.error(f"Error processing historical data for {symbol}: {e}")
            return data  # Return original data if processing fails

    def process_streaming_update(self, symbol, new_data):
        """Process incoming streaming data point"""
        try:
            if symbol not in self.symbol_data:
                logger.warning(f"No historical data for {symbol}, initializing")
                self.symbol_data[symbol] = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

            df = self.symbol_data[symbol]

            # Verify the new data is valid
            new_close = float(new_data.get('close', 0))

            # Check for problematic values (0 or extreme jumps)
            if new_close == 0 or new_close is None:
                # Use the last valid price instead
                if symbol in self.last_real_prices:
                    new_close = self.last_real_prices[symbol]
                    logger.warning(f"Replaced zero price for {symbol} with last valid price: {new_close}")
                else:
                    # Find a reasonable default if we have any history
                    if not df.empty:
                        new_close = df['close'].iloc[-1]
                    else:
                        logger.error(f"No valid price history for {symbol}")
            else:
                # Check for extreme price jumps (more than 10%)
                if symbol in self.last_real_prices:
                    last_price = self.last_real_prices[symbol]
                    pct_change = abs((new_close - last_price) / last_price) if last_price else 0

                    if pct_change > 0.10:  # 10% change threshold
                        logger.warning(f"Extreme price jump detected for {symbol}: {pct_change:.2%} change")
                        # Could implement more sophisticated filtering here

            # Update the last valid price
            if new_close > 0:
                self.last_real_prices[symbol] = new_close

            # Format the new data point
            new_timestamp = pd.to_datetime(new_data.get('timestamp', datetime.now()))
            new_point = {
                'timestamp': new_timestamp,
                'open': float(new_data.get('open', new_close)),
                'high': float(new_data.get('high', new_close)),
                'low': float(new_data.get('low', new_close)),
                'close': new_close,
                'volume': int(new_data.get('volume', 0))
            }

            # Check for large time gap between historical and streaming data
            if not df.empty:
                last_timestamp = df['timestamp'].iloc[-1]
                time_diff = (new_timestamp - last_timestamp).total_seconds() / 60  # diff in minutes

                # If gap is more than 30 minutes, add a NaN point to break the line
                if time_diff > 30:
                    # Create a gap point 1 minute after the last historical point
                    gap_timestamp = last_timestamp + pd.Timedelta(minutes=1)
                    gap_point = pd.DataFrame([{
                        'timestamp': gap_timestamp,
                        'open': None,
                        'high': None,
                        'low': None,
                        'close': None,
                        'volume': 0
                    }])

                    # Create another gap point 1 minute before the new streaming point
                    gap_timestamp2 = new_timestamp - pd.Timedelta(minutes=1)
                    gap_point2 = pd.DataFrame([{
                        'timestamp': gap_timestamp2,
                        'open': None,
                        'high': None,
                        'low': None,
                        'close': None,
                        'volume': 0
                    }])

                    # Append the gap points and the new point
                    self.symbol_data[symbol] = pd.concat([df, gap_point, gap_point2, pd.DataFrame([new_point])],
                                                         ignore_index=True)
                else:
                    # Normal case - append the new point
                    self.symbol_data[symbol] = pd.concat([df, pd.DataFrame([new_point])], ignore_index=True)
            else:
                # First point - just add it
                self.symbol_data[symbol] = pd.concat([df, pd.DataFrame([new_point])], ignore_index=True)

            # Sort and keep only the most recent data points (limit to 1000)
            self.symbol_data[symbol] = self.symbol_data[symbol].sort_values('timestamp').tail(1000)

            # Return the full updated dataset
            return self.symbol_data[symbol].dropna().to_dict('records')

        except Exception as e:
            logger.error(f"Error processing streaming update for {symbol}: {e}")
            # Return current data
            return self.symbol_data.get(symbol, pd.DataFrame()).dropna().to_dict('records')

    def get_aggregated_data(self, symbol, timeframe='1m'):
        """Get data aggregated to the specified timeframe"""
        if symbol not in self.symbol_data or self.symbol_data[symbol].empty:
            return []

        df = self.symbol_data[symbol].copy()

        try:
            # Set timestamp as index for resampling
            df.set_index('timestamp', inplace=True)

            # Determine resample rule based on timeframe
            if timeframe == '1m':
                rule = '1min'
            elif timeframe == '5m':
                rule = '5min'
            elif timeframe == '15m':
                rule = '15min'
            elif timeframe == '30m':
                rule = '30min'
            elif timeframe == '1h':
                rule = '1H'
            else:
                rule = '1min'  # Default

            # Resample the data
            resampled = df.resample(rule).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

            # Reset index and format timestamp
            resampled.reset_index(inplace=True)
            resampled['timestamp'] = resampled['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

            return resampled.to_dict('records')

        except Exception as e:
            logger.error(f"Error resampling data for {symbol}: {e}")
            df.reset_index(inplace=True)
            return df.to_dict('records')