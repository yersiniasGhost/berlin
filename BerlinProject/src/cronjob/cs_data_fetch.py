from typing import Dict, Collection, List, Any, Optional
import pandas as pd
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import sys
import time
import json
import os
import requests
import base64
from urllib.parse import urlparse, parse_qs

from mlf_utils.log_manager import LogManager
from mlf_utils.ticker_config import get_tracked_tickers, TRACKED_INTERVALS

# Initialize LogManager with log file (must be called first in main apps)
LogManager(log_file='schwab_weekly_fetch.log')
logger = LogManager().get_logger("SchwabDataFetch")


class StandaloneSchwabFetcher:
    """
    Standalone Schwab data fetcher that doesn't import any existing Schwab classes
    to avoid browser opening conflicts
    """

    def __init__(self, mongo_collection: Collection):
        self.collection: Collection = mongo_collection
        # Eastern Time zone for market hours
        self.et_tz = pytz.timezone('US/Eastern')

        # Schwab API credentials
        self.app_key = "QtfsQiLHpno726ZFgRDtvHA3ZItCAkcQ"
        self.app_secret = "RmwUJyBGGgW2r2C7"
        self.redirect_uri = "https://127.0.0.1"

        # Token storage
        self.access_token = None
        self.refresh_token = None
        self.token_path = "schwab_tokens_standalone.json"

        # Load existing tokens if available
        self.load_tokens()

    def load_tokens(self) -> bool:
        """Load tokens from file"""
        if not os.path.exists(self.token_path):
            logger.warning(f"Token file not found: {self.token_path}")
            return False

        try:
            with open(self.token_path, 'r') as f:
                token_data = json.load(f)

            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')

            if self.access_token:
                logger.info("Loaded existing tokens")
                return True
            else:
                logger.warning("No access token in file")
                return False
        except Exception as e:
            logger.error(f"Error loading tokens: {e}")
            return False

    def save_tokens(self) -> bool:
        """Save tokens to file"""
        try:
            token_data = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'timestamp': datetime.now().isoformat()
            }

            with open(self.token_path, 'w') as f:
                json.dump(token_data, f, indent=2)

            logger.info(f"Saved tokens to {self.token_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
            return False

    def authenticate(self) -> bool:
        """Authenticate with Schwab API - NO BROWSER OPENING"""
        logger.info("Starting Schwab authentication...")

        # Construct auth URL
        auth_url = (f"https://api.schwabapi.com/v1/oauth/authorize?"
                    f"client_id={self.app_key}&redirect_uri={self.redirect_uri}")

        print(f"\n" + "=" * 80)
        print(f"SCHWAB AUTHENTICATION REQUIRED")
        print(f"=" * 80)
        print(f"1. MANUALLY open your browser and go to:")
        print(f"   {auth_url}")
        print(f"")
        print(f"2. Log in to your Schwab account")
        print(f"3. Authorize the application")
        print(f"4. Copy the FULL URL from your browser after authorization")
        print(f"   (It will start with: https://127.0.0.1/?code=...)")
        print(f"")
        print(f"5. Paste that URL below and press Enter:")
        print(f"=" * 80)

        returned_url = input("Paste the full authorization URL here: ").strip()

        # Extract code from URL
        try:
            if "code=" in returned_url:
                parsed_url = urlparse(returned_url)
                query_params = parse_qs(parsed_url.query)

                if 'code' in query_params:
                    auth_code = query_params['code'][0]
                    return self.get_tokens(auth_code)
                else:
                    logger.error("No code found in URL")
                    return False
            else:
                logger.error("Invalid URL - must contain 'code='")
                return False
        except Exception as e:
            logger.error(f"Error parsing auth URL: {e}")
            return False

    def get_tokens(self, auth_code: str) -> bool:
        """Exchange auth code for tokens"""
        try:
            # Prepare the token request
            token_url = "https://api.schwabapi.com/v1/oauth/token"

            # Create basic auth header
            credentials = f"{self.app_key}:{self.app_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            data = {
                'grant_type': 'authorization_code',
                'code': auth_code,
                'redirect_uri': self.redirect_uri
            }

            logger.info("Exchanging auth code for tokens...")
            response = requests.post(token_url, headers=headers, data=data)

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')

                if self.access_token:
                    logger.info("✅ Successfully obtained access token")
                    self.save_tokens()
                    return True
                else:
                    logger.error("❌ No access token in response")
                    return False
            else:
                logger.error(f"❌ Token request failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error getting tokens: {e}")
            return False

    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            logger.error("No refresh token available")
            return False

        try:
            token_url = "https://api.schwabapi.com/v1/oauth/token"

            credentials = f"{self.app_key}:{self.app_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token
            }

            response = requests.post(token_url, headers=headers, data=data)

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                # Note: refresh_token may or may not be updated
                if 'refresh_token' in token_data:
                    self.refresh_token = token_data['refresh_token']

                logger.info("✅ Successfully refreshed access token")
                self.save_tokens()
                return True
            else:
                logger.error(f"❌ Token refresh failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False

    def seconds_from_midnight(self, time_str: str) -> int:
        """Convert HH:MM:SS to seconds from midnight"""
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s

    def get_trading_period_range(self, days_back: int = 5) -> tuple[datetime, datetime]:
        """Get the start and end of the most recent trading period"""
        now = datetime.now(self.et_tz)

        # Go back the specified number of days
        start_date = now - timedelta(days=days_back)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # End at current time (or end of most recent trading day)
        end_date = now.replace(hour=20, minute=0, second=0, microsecond=0)

        logger.info(f"Trading period range: {start_date} to {end_date}")
        return start_date, end_date

    def get_date_range_to_clear(self, start_date: datetime, end_date: datetime) -> List[Dict[str, int]]:
        """Get all year/month/day combinations that need to be cleared"""
        date_ranges = []
        current_date = start_date.date()
        end_date_only = end_date.date()

        while current_date <= end_date_only:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                date_ranges.append({
                    'year': current_date.year,
                    'month': current_date.month,
                    'day': current_date.day
                })
            current_date += timedelta(days=1)

        return date_ranges

    def clear_overlapping_data(self, ticker: str, interval: int, date_ranges: List[Dict[str, int]]):
        """Clear existing data for the specified date ranges"""
        cleared_days = 0

        for date_info in date_ranges:
            year = date_info['year']
            month = date_info['month']
            day = date_info['day']

            query = {
                'ticker': ticker,
                'year': year,
                'month': month,
                'time_increments': interval
            }

            existing_doc = self.collection.find_one(query)

            if existing_doc:
                existing_data = existing_doc.get('data', {})
                day_key = str(day)

                if day_key in existing_data:
                    del existing_data[day_key]
                    cleared_days += 1

                    if existing_data:
                        self.collection.update_one(
                            {'_id': existing_doc['_id']},
                            {'$set': {'data': existing_data}}
                        )
                        logger.debug(f"Cleared day {day} from {ticker} {year}-{month}")
                    else:
                        self.collection.delete_one({'_id': existing_doc['_id']})
                        logger.debug(f"Deleted empty document for {ticker} {year}-{month}")

        if cleared_days > 0:
            logger.info(f"Cleared {cleared_days} days of existing data for {ticker} {interval}m")

    def fetch_schwab_data(self, symbol: str, interval: int, start_date: datetime, end_date: datetime) -> Optional[
        List[Dict]]:
        """Fetch data from Schwab API with automatic token refresh"""
        try:
            if not self.access_token:
                logger.error("No access token available")
                return None

            url = "https://api.schwabapi.com/marketdata/v1/pricehistory"
            headers = {'Authorization': f'Bearer {self.access_token}'}

            # Convert interval to Schwab API parameters
            frequency_type = "minute"
            frequency = interval

            # Calculate period in days and validate against Schwab API limits
            period_days = (end_date - start_date).days + 1

            # Schwab API: when periodType=day, valid periods are [1, 2, 3, 4, 5, 10]
            if period_days <= 5:
                period = period_days
            elif period_days <= 10:
                period = 10
            else:
                # For longer periods, we'll use 10 days (max for day periodType)
                period = 10

            params = {
                'symbol': symbol,
                'periodType': 'day',
                'period': period,
                'frequencyType': frequency_type,
                'frequency': frequency,
                'needExtendedHoursData': True  # Include pre/post market
            }

            logger.info(f"Requesting {period} days of data for {symbol} (calculated from {period_days} day range)")

            logger.info(f"Fetching {symbol} {interval}m data from Schwab API...")
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                candles = data.get('candles', [])
                logger.info(f"✅ Retrieved {len(candles)} candles for {symbol}")
                return candles
            elif response.status_code == 401:
                # Token expired, try to refresh
                logger.warning("Access token expired, attempting to refresh...")
                if self.refresh_access_token():
                    # Retry with new token
                    headers = {'Authorization': f'Bearer {self.access_token}'}
                    response = requests.get(url, headers=headers, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        candles = data.get('candles', [])
                        logger.info(f"✅ Retrieved {len(candles)} candles for {symbol} (after refresh)")
                        return candles

                logger.error(f"❌ Authentication failed even after refresh: {response.status_code}")
                return None
            else:
                logger.error(f"❌ Schwab API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error fetching Schwab data for {symbol}: {e}")
            return None

    def process_schwab_candles(self, candles: List[Dict], start_date: datetime, end_date: datetime) -> Dict[
        str, Dict[str, Dict[str, float]]]:
        """Process Schwab candles into the same format as Yahoo Finance data"""
        processed_data: Dict[str, Dict[str, Dict[str, float]]] = {}

        if not candles:
            return processed_data

        for candle in candles:
            try:
                # Convert timestamp from milliseconds
                timestamp_ms = candle['datetime']
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=self.et_tz)

                # Filter to only include data within our target range
                if timestamp < start_date or timestamp > end_date:
                    continue

                # Skip weekends
                if timestamp.weekday() >= 5:
                    continue

                # Get day for grouping
                day = timestamp.day
                day_key = str(day)

                # Initialize day data if needed
                if day_key not in processed_data:
                    processed_data[day_key] = {}

                # Convert timestamp to seconds from midnight (same as Yahoo format)
                seconds = self.seconds_from_midnight(timestamp.strftime('%H:%M:%S'))

                # Store candle data in exact same format as Yahoo
                processed_data[day_key][str(seconds)] = {
                    'open': float(candle['open']),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'close': float(candle['close']),
                    'volume': int(candle.get('volume', 0))
                }

            except Exception as e:
                logger.error(f"Error processing candle: {e}")
                continue

        return processed_data

    def update_ticker_data_schwab(self, ticker: str, interval: int, days_back: int = 5) -> bool:
        """Update data for a specific ticker and interval using Schwab API"""
        try:
            start_date, end_date = self.get_trading_period_range(days_back)

            # Get date ranges that will be affected
            date_ranges = self.get_date_range_to_clear(start_date, end_date)

            # Clear overlapping data FIRST
            logger.info(f"🧹 Clearing overlapping data for {ticker} {interval}m...")
            self.clear_overlapping_data(ticker, interval, date_ranges)

            # Fetch data from Schwab
            candles = self.fetch_schwab_data(ticker, interval, start_date, end_date)

            if not candles:
                logger.warning(f"⚠️  No data retrieved for {ticker}")
                return False

            # Process candles into MongoDB format
            processed_data = self.process_schwab_candles(candles, start_date, end_date)

            if not processed_data:
                logger.warning(f"⚠️  No processed data for {ticker}")
                return False

            logger.info(f"📊 Processed {len(processed_data)} days of data for {ticker}")

            # Group by month and year for storage (same as Yahoo method)
            months_data = {}

            for day_str, day_data in processed_data.items():
                # Find the correct month for this day
                day_num = int(day_str)
                found_month = None

                for check_date in [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]:
                    if check_date.day == day_num and check_date.weekday() < 5:
                        found_month = (check_date.year, check_date.month)
                        break

                if found_month:
                    year, month = found_month
                    month_key = f"{year}-{month}"

                    if month_key not in months_data:
                        months_data[month_key] = {'year': year, 'month': month, 'data': {}}

                    months_data[month_key]['data'][day_str] = day_data

            # Store in MongoDB
            documents_updated = 0
            documents_created = 0

            for month_key, month_info in months_data.items():
                year = month_info['year']
                month = month_info['month']
                month_data = month_info['data']

                # Check if document exists
                existing_doc = self.collection.find_one({
                    'ticker': ticker,
                    'year': year,
                    'month': month,
                    'time_increments': interval
                })

                if existing_doc:
                    # Update existing document
                    existing_data = existing_doc.get('data', {})
                    existing_data.update(month_data)

                    self.collection.update_one(
                        {'_id': existing_doc['_id']},
                        {'$set': {'data': existing_data}}
                    )
                    documents_updated += 1
                    logger.info(f"📝 Updated existing document for {ticker} {year}-{month}")
                else:
                    # Create new document
                    doc = {
                        'ticker': ticker,
                        'year': year,
                        'month': month,
                        'time_increments': interval,
                        'data': month_data
                    }
                    self.collection.insert_one(doc)
                    documents_created += 1
                    logger.info(f"🆕 Created new document for {ticker} {year}-{month}")

            logger.info(f"✅ Successfully processed {ticker} {interval}m: "
                        f"{documents_updated} updated, {documents_created} created")
            return True

        except Exception as e:
            logger.error(f"❌ Error processing {ticker} {interval}m: {str(e)}")
            return False

    def run_schwab_weekly_update(self, tickers: List[str], intervals: List[int], days_back: int = 5) -> Dict[str, Any]:
        """Run the weekly update using Schwab data"""
        start_time = datetime.now()

        results = {
            'start_time': start_time,
            'tickers_processed': 0,
            'tickers_failed': 0,
            'total_operations': len(tickers) * len(intervals),
            'successful_operations': 0,
            'failed_operations': 0,
            'failed_tickers': []
        }

        logger.info(f"🚀 Starting Schwab data update for {len(tickers)} tickers, {len(intervals)} intervals")

        for ticker in tickers:
            ticker_success = True
            for interval in intervals:
                try:
                    success = self.update_ticker_data_schwab(ticker, interval, days_back)
                    if success:
                        results['successful_operations'] += 1
                    else:
                        results['failed_operations'] += 1
                        ticker_success = False

                    # Rate limiting - be nice to Schwab API
                    time.sleep(2)

                except Exception as e:
                    logger.error(f"❌ Unexpected error for {ticker} {interval}m: {e}")
                    results['failed_operations'] += 1
                    ticker_success = False

            if ticker_success:
                results['tickers_processed'] += 1
            else:
                results['tickers_failed'] += 1
                results['failed_tickers'].append(ticker)

            # Brief pause between tickers
            time.sleep(3)

        results['end_time'] = datetime.now()
        results['duration'] = results['end_time'] - results['start_time']

        logger.info(f"⏱️  Schwab update completed in {results['duration']}")
        logger.info(f"📈 Success rate: {results['successful_operations']}/{results['total_operations']} operations")

        if results['failed_tickers']:
            logger.warning(f"⚠️  Failed tickers: {results['failed_tickers']}")

        return results


def main():
    """Main function to run Schwab data fetch"""
    try:
        # MongoDB connection - CORRECTED
        client = MongoClient('mongodb://localhost:27017/')
        db = client['MTA_devel']  # Same database
        collection = db['tick_history_cs']  # New collection for Schwab data

        # Test connection
        client.server_info()
        logger.info("✅ Successfully connected to MongoDB (MTA_devel.tick_history_cs)")

        # Initialize fetcher (standalone version)
        fetcher = StandaloneSchwabFetcher(collection)

        # Check if we need to authenticate
        if not fetcher.access_token:
            logger.info("🔐 No access token found. Starting authentication...")
            if not fetcher.authenticate():
                logger.error("❌ Authentication failed")
                sys.exit(1)

        # Use centralized ticker configuration
        tickers = get_tracked_tickers()

        # Use centralized interval configuration
        intervals = TRACKED_INTERVALS

        # Run the update (get last 5 trading days)
        results = fetcher.run_schwab_weekly_update(tickers, intervals, days_back=5)

        # Log final results
        logger.info("=" * 50)
        logger.info("SCHWAB DATA FETCH SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Duration: {results['duration']}")
        logger.info(f"Tickers processed successfully: {results['tickers_processed']}")
        logger.info(f"Tickers failed: {results['tickers_failed']}")
        logger.info(f"Total operations: {results['total_operations']}")
        logger.info(f"Successful operations: {results['successful_operations']}")
        logger.info(f"Failed operations: {results['failed_operations']}")

        if results['failed_tickers']:
            logger.warning(f"Failed tickers: {', '.join(results['failed_tickers'])}")

        exit_code = 0 if results['failed_operations'] == 0 else 1
        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"❌ Critical error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()