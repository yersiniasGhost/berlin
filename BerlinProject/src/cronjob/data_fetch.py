from typing import Dict, Collection, List, Any, Optional

import pandas as pd
from pymongo import MongoClient
import yfinance as yf
from datetime import datetime, timedelta
import sys
import time

from mlf_utils.timezone_utils import now_et, ET, MARKET_OPEN_SECONDS, MARKET_CLOSE_SECONDS
from mlf_utils.ticker_config import get_tracked_tickers, TRACKED_INTERVALS


class DataFetch:
    def __init__(self, mongo_collection: Collection):
        self.collection: Collection = mongo_collection

    def seconds_from_midnight(self, time_str: str) -> int:
        """Convert HH:MM:SS to seconds from midnight"""
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s

    def process_interval_data(self, df: pd.DataFrame, day: int) -> Dict[str, Dict[str, float]]:
        """Process a day's worth of interval data into the required format"""
        day_data: Dict[str, Dict[str, float]] = {}

        for idx, row in df.iterrows():
            # Convert timestamp to seconds from midnight
            seconds: int = self.seconds_from_midnight(idx.strftime('%H:%M:%S'))

            # Only include regular market hours (9:30 AM - 4:00 PM ET)
            if MARKET_OPEN_SECONDS <= seconds <= MARKET_CLOSE_SECONDS:
                day_data[str(seconds)] = {
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close'])
                }

        return day_data

    def update_ticker_data(self, ticker: str, interval: int) -> None:
        """Update data for a specific ticker and interval"""
        # Get current date in Eastern Time (market timezone)
        # Using ET ensures correct date boundaries for market data
        now: datetime = now_et()

        # Calculate start date (1 day ago to ensure we get recent data)
        start_date: datetime = now - timedelta(days=1)

        try:
            # Download data from Yahoo Finance
            stock: yf.Ticker = yf.Ticker(ticker)
            df: pd.DataFrame = stock.history(
                start=start_date,
                end=now,
                interval=f'{interval}m'
            )

            if df.empty:
                print(f"No data found for {ticker}")
                return

            # Ensure timestamps are in Eastern Time (market timezone)
            # yfinance returns ET for US stocks, but we explicitly convert to be safe
            df.index = pd.to_datetime(df.index)
            if df.index.tz is not None:
                df.index = df.index.tz_convert('America/New_York')
            else:
                # If no timezone, localize to ET (assume it's already in ET)
                df.index = df.index.tz_localize('America/New_York')

            # Group data by month and year
            grouped = df.groupby([df.index.year, df.index.month])

            for (year, month), month_df in grouped:
                # Group by day within month
                day_groups = month_df.groupby(month_df.index.day)

                # Check if document exists
                existing_doc: Optional[Dict[str, Any]] = self.collection.find_one({
                    'ticker': ticker,
                    'year': int(year),
                    'month': int(month),
                    'time_increments': interval
                })

                if existing_doc:
                    # Update existing document
                    data: Dict[str, Dict[str, Dict[str, float]]] = existing_doc.get('data', {})
                    for day, day_df in day_groups:
                        day_data = self.process_interval_data(day_df, int(day))
                        if day_data:  # Only update if we have data
                            data[str(day)] = day_data

                    self.collection.update_one(
                        {'_id': existing_doc['_id']},
                        {'$set': {'data': data}}
                    )
                else:
                    # Create new document
                    data: Dict[str, Dict[str, Dict[str, float]]] = {}
                    for day, day_df in day_groups:
                        day_data = self.process_interval_data(day_df, int(day))
                        if day_data:  # Only include if we have data
                            data[str(day)] = day_data

                    if data:  # Only insert if we have data
                        doc: Dict[str, Any] = {
                            'ticker': ticker,
                            'year': int(year),
                            'month': int(month),
                            'time_increments': interval,
                            'data': data
                        }
                        self.collection.insert_one(doc)

            print(f"Successfully updated {ticker} {interval}m data")

        except Exception as e:
            print(f"Error processing {ticker}: {str(e)}")


def main() -> None:
    # MongoDB connection
    client = MongoClient('mongodb://localhost:27017/')
    db = client['MTA_devel']
    collection = db['tick_history']

    # Initialize loader
    loader: DataFetch = DataFetch(collection)

    # Use centralized ticker configuration
    tickers: List[str] = get_tracked_tickers()

    # Use centralized interval configuration
    intervals: List[int] = TRACKED_INTERVALS

    # Process each ticker and interval
    for ticker in tickers:
        for interval in intervals:
            print(f"Processing {ticker} {interval}m data...")
            loader.update_ticker_data(ticker, interval)
            time.sleep(1)  # Sleep to avoid rate limiting


if __name__ == "__main__":
    main()