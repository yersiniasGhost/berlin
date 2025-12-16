#!/usr/bin/env python3
"""
Polygon.io Weekly Stock Data Updater - MongoDB Version
Finds the latest timestamp for each ticker and fetches only new data
Designed for cron job execution (run weekly)
Respects rate limits but more aggressive than initial fetch (10 calls/minute)
"""

import os
import time
import smtplib
import traceback
from datetime import datetime, timedelta
from polygon import RESTClient
from pymongo import MongoClient
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple

from mlf_utils.log_manager import LogManager

# Same ticker list as original script
MAJOR_STOCKS = [
    # Mega-cap Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    # Other Major Tech
    "AVGO", "ORCL", "ADBE", "CRM", "AMD", "INTC", "QCOM", "TXN",
    # Finance
    "BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS",
    # Consumer/Retail
    "WMT", "HD", "PG", "KO", "PEP", "MCD", "NKE", "DIS",
    # Healthcare/Pharma
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK",
    # Hot/Trending Stocks
    "PLTR", "SOFI", "RIVN", "LCID"
]

# More aggressive rate limiting for weekly updates (since less data)
API_CALLS_PER_MINUTE = 10  # More aggressive than original 5
SECONDS_BETWEEN_CALLS = 60 / API_CALLS_PER_MINUTE  # 6 seconds between calls
MAX_RETRIES = 3
RETRY_DELAY = 65

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "warnd114@gmail.com"  # Your email for notifications

# Initialize LogManager with log file (must be called first in main apps)
LOG_FILE = os.path.expanduser("~/stock_updater.log")
LogManager(log_file=LOG_FILE)
logger = LogManager().get_logger("PolygonDataFetch")


class RateLimiter:
    """Rate limiter optimized for weekly updates"""

    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call_time = 0
        self.call_count = 0
        self.minute_start = time.time()

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        current_time = time.time()

        # Reset counter every minute
        if current_time - self.minute_start >= 60:
            self.call_count = 0
            self.minute_start = current_time

        # If we've hit the limit for this minute, wait
        if self.call_count >= self.calls_per_minute:
            wait_time = 60 - (current_time - self.minute_start)
            if wait_time > 0:
                logger.info(f"⏳ Rate limit reached. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time + 1)  # Add 1 second buffer
                self.call_count = 0
                self.minute_start = time.time()

        # Also ensure minimum time between calls
        time_since_last = current_time - self.last_call_time
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            logger.info(f"⏱️  Waiting {wait_time:.1f}s before next API call...")
            time.sleep(wait_time)

        self.last_call_time = time.time()
        self.call_count += 1


def find_latest_timestamp_for_ticker(collection, ticker: str) -> Optional[datetime]:
    """
    Find the latest timestamp for a specific ticker in the database

    Args:
        collection: MongoDB collection
        ticker: Stock ticker symbol

    Returns:
        Latest timestamp as datetime, or None if no data exists
    """
    try:
        # Find all documents for this ticker
        pipeline = [
            {'$match': {'ticker': ticker, 'time_increments': 1}},
            {'$sort': {'year': -1, 'month': -1}}
        ]

        docs = list(collection.aggregate(pipeline))
        if not docs:
            logger.warning(f"No existing data found for {ticker}")
            return None

        latest_timestamp = None

        # Look through documents starting from most recent
        for doc in docs:
            year = doc['year']
            month = doc['month']
            data = doc.get('data', {})

            # Find the latest day and time in this document
            for day_str in sorted(data.keys(), key=int, reverse=True):
                day_data = data[day_str]

                # Find the latest time_seconds for this day
                for time_seconds_str in sorted(day_data.keys(), key=int, reverse=True):
                    time_seconds = int(time_seconds_str)

                    # Convert back to datetime
                    # Create base date for this day
                    day = int(day_str)
                    try:
                        base_date = datetime(year, month, day)
                    except ValueError:
                        continue  # Skip invalid dates

                    # Add the seconds from midnight
                    timestamp = base_date + timedelta(seconds=time_seconds)

                    if latest_timestamp is None or timestamp > latest_timestamp:
                        latest_timestamp = timestamp

        if latest_timestamp:
            logger.info(f"Latest data for {ticker}: {latest_timestamp}")
        else:
            logger.warning(f"No valid timestamps found for {ticker}")

        return latest_timestamp

    except Exception as e:
        logger.error(f"Error finding latest timestamp for {ticker}: {e}")
        return None


def fetch_incremental_data(client: RESTClient, ticker: str, start_datetime: datetime,
                           rate_limiter: RateLimiter) -> List[Any]:
    """
    Fetch data from start_datetime + 1 minute to now to avoid duplicates

    Args:
        client: Polygon REST client
        ticker: Stock ticker symbol
        start_datetime: Last timestamp we have data for
        rate_limiter: Rate limiter instance

    Returns:
        List of aggregation data
    """
    # Start from 1 minute after the last timestamp to avoid duplicates
    actual_start = start_datetime + timedelta(minutes=1)
    end_date = datetime.now()

    # If start is after end, no new data needed
    if actual_start >= end_date:
        logger.info(f"No new data needed for {ticker} (already up to date)")
        return []

    from_date = actual_start.strftime("%Y-%m-%d")
    to_date = end_date.strftime("%Y-%m-%d")

    logger.info(f"📊 Fetching {ticker}: {from_date} to {to_date}")

    # For incremental updates, we likely won't need chunking
    # but keep it for safety with longer gaps
    for attempt in range(MAX_RETRIES):
        rate_limiter.wait_if_needed()

        try:
            aggs = []

            # Calculate if we need chunking (more than 30 days)
            days_diff = (end_date - actual_start).days

            if days_diff <= 30:
                # Single request for small date ranges
                try:
                    for agg in client.list_aggs(
                            ticker=ticker,
                            multiplier=1,
                            timespan="minute",
                            from_=from_date,
                            to=to_date,
                            limit=50000,
                    ):
                        aggs.append(agg)

                    logger.info(f"✅ Retrieved {len(aggs):,} data points for {ticker}")
                    return aggs

                except Exception as e:
                    if "429" in str(e) or "too many" in str(e).lower():
                        if attempt < MAX_RETRIES - 1:
                            logger.warning(
                                f"⚠️ Rate limit hit (attempt {attempt + 1}/{MAX_RETRIES}). Waiting {RETRY_DELAY}s...")
                            time.sleep(RETRY_DELAY)
                            rate_limiter.minute_start = time.time()
                            rate_limiter.call_count = 0
                            continue
                        else:
                            logger.error(f"❌ Max retries reached for {ticker}: {e}")
                            return []
                    else:
                        raise e
            else:
                # Use chunking for larger date ranges (shouldn't happen often in weekly updates)
                logger.info(f"Large date range detected ({days_diff} days), using chunking")
                current_start = actual_start

                while current_start < end_date:
                    current_end = min(current_start + timedelta(days=30), end_date)

                    from_chunk = current_start.strftime("%Y-%m-%d")
                    to_chunk = current_end.strftime("%Y-%m-%d")

                    logger.info(f"   📅 Fetching chunk: {from_chunk} to {to_chunk}")

                    if current_start != actual_start:
                        rate_limiter.wait_if_needed()

                    try:
                        chunk_aggs = []
                        for agg in client.list_aggs(
                                ticker=ticker,
                                multiplier=1,
                                timespan="minute",
                                from_=from_chunk,
                                to=to_chunk,
                                limit=50000,
                        ):
                            chunk_aggs.append(agg)

                        aggs.extend(chunk_aggs)
                        logger.info(f"   ✓ Got {len(chunk_aggs):,} data points")

                    except Exception as chunk_error:
                        if "429" in str(chunk_error) or "too many" in str(chunk_error).lower():
                            logger.warning(f"   ⚠️ Rate limit hit on chunk, waiting {RETRY_DELAY}s...")
                            time.sleep(RETRY_DELAY)
                            rate_limiter.minute_start = time.time()
                            rate_limiter.call_count = 0
                            continue
                        else:
                            raise chunk_error

                    current_start = current_end + timedelta(days=1)

                logger.info(f"✅ Retrieved {len(aggs):,} total data points for {ticker}")
                return aggs

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "too many" in error_str.lower():
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"⚠️ Rate limit error (attempt {attempt + 1}/{MAX_RETRIES}). Waiting {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                    rate_limiter.minute_start = time.time()
                    rate_limiter.call_count = 0
                    continue
                else:
                    logger.error(f"❌ Max retries reached for {ticker}: {e}")
                    return []
            else:
                logger.error(f"❌ Error fetching {ticker}: {e}")
                return []

    return []


def update_mongodb_data(collection, ticker: str, aggs: List[Any]) -> int:
    """
    Add new aggregation data to existing MongoDB documents
    Same structure as original script but merges with existing data

    Args:
        collection: MongoDB collection
        ticker: Stock ticker symbol
        aggs: List of new aggregation data

    Returns:
        Number of documents updated/created
    """
    if not aggs:
        return 0

    # Organize new data by year/month/day structure
    organized_data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

    for agg in aggs:
        # Convert from milliseconds to datetime
        dt = datetime.fromtimestamp(agg.timestamp / 1000)

        year = dt.year
        month = dt.month
        day = dt.day

        # Convert time to seconds from midnight
        time_seconds = dt.hour * 3600 + dt.minute * 60 + dt.second
        time_key = str(time_seconds)

        # Store OHLCV data
        organized_data[year][month][day][time_key] = {
            'open': float(agg.open),
            'high': float(agg.high),
            'low': float(agg.low),
            'close': float(agg.close),
            'volume': int(agg.volume)
        }

    # Update MongoDB documents
    documents_updated = 0
    for year, year_data in organized_data.items():
        for month, month_data in year_data.items():
            # Check if document already exists
            existing_doc = collection.find_one({
                'ticker': ticker,
                'year': year,
                'month': month,
                'time_increments': 1
            })

            if existing_doc:
                # Merge with existing data
                existing_data = existing_doc.get('data', {})

                # Add new days or merge with existing days
                for day, day_data in month_data.items():
                    day_str = str(day)
                    if day_str in existing_data:
                        # Merge with existing day data (add new time entries)
                        existing_data[day_str].update(dict(day_data))
                        logger.info(
                            f"   📝 Merged {len(day_data)} new entries for {ticker} {year}-{month:02d}-{day:02d}")
                    else:
                        # Add completely new day
                        existing_data[day_str] = dict(day_data)
                        logger.info(
                            f"   📅 Added new day {ticker} {year}-{month:02d}-{day:02d} with {len(day_data)} entries")

                # Update the document
                collection.update_one(
                    {'_id': existing_doc['_id']},
                    {'$set': {'data': existing_data}}
                )
                logger.info(f"   ✅ Updated {ticker} {year}-{month:02d}")

            else:
                # Create new document (shouldn't happen often in weekly updates)
                doc = {
                    'ticker': ticker,
                    'year': year,
                    'month': month,
                    'time_increments': 1,
                    'data': {}
                }

                for day, day_data in month_data.items():
                    doc['data'][str(day)] = dict(day_data)

                collection.insert_one(doc)
                logger.info(f"   ✨ Created new document {ticker} {year}-{month:02d}")

            documents_updated += 1

    return documents_updated


def send_error_notification(subject: str, error_message: str, traceback_str: str = ""):
    """
    Send email notification on error using simple email format

    Args:
        subject: Email subject
        error_message: Error description
        traceback_str: Full traceback if available
    """
    try:
        # Get email password from environment variable
        email_password = 'vbqzaatwlhmtxysm'
        if not email_password:
            logger.warning("EMAIL_PASSWORD environment variable not set - skipping email notification")
            logger.warning(f"Would have sent email: {subject} - {error_message}")
            return

        # Create simple email message
        message = f"""Subject: {subject}
From: {EMAIL_ADDRESS}
To: {EMAIL_ADDRESS}

Stock Data Update Script Error

Time: {datetime.now()}
Error: {error_message}

Traceback:
{traceback_str}

Please check the console output for more details.
"""

        # Send email using basic SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, email_password)
        server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, message)
        server.quit()

        logger.info("Error notification email sent successfully")

    except Exception as e:
        logger.error(f"Failed to send error notification email: {e}")
        logger.error(f"Original error was: {subject} - {error_message}")


def run_weekly_update():
    """
    Main function to run weekly stock data updates
    """
    start_time = time.time()

    try:
        logger.info("=" * 60)
        logger.info("🔄 STARTING WEEKLY STOCK DATA UPDATE")
        logger.info("=" * 60)

        # Initialize MongoDB connection
        try:
            mongo_client = MongoClient('localhost', 27017, serverSelectionTimeoutMS=5000)
            db = mongo_client['MTA_devel']
            collection = db['tick_history_polygon']
            logger.info("✅ Connected to MongoDB")
        except Exception as e:
            error_msg = f"Failed to connect to MongoDB: {e}"
            logger.error(f"❌ {error_msg}")
            send_error_notification("Stock Update - MongoDB Connection Failed", error_msg, traceback.format_exc())
            return False

        # Initialize Polygon client
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            api_key = "38pLH5oteMbZD7M19rLIryj_Khrc_Bfx"
            logger.warning("⚠️  Using hardcoded API key (consider setting POLYGON_API_KEY env variable)")

        client = RESTClient(api_key)
        rate_limiter = RateLimiter(API_CALLS_PER_MINUTE)

        # Track statistics
        total_tickers = len(MAJOR_STOCKS)
        successful_updates = []
        failed_updates = []
        skipped_updates = []  # Tickers with no new data
        total_new_data_points = 0
        total_documents_updated = 0

        logger.info(f"🎯 Processing {total_tickers} tickers for incremental updates")
        logger.info(f"⏰ Rate limit: {API_CALLS_PER_MINUTE} calls/minute")

        # Process each ticker
        for idx, ticker in enumerate(MAJOR_STOCKS, 1):
            logger.info(f"\n{'=' * 50}")
            logger.info(f"Processing {idx}/{total_tickers}: {ticker}")
            logger.info(f"{'=' * 50}")

            try:
                # Find latest timestamp for this ticker
                latest_timestamp = find_latest_timestamp_for_ticker(collection, ticker)

                if latest_timestamp is None:
                    logger.warning(f"⚠️  No existing data for {ticker} - consider running initial fetch first")
                    failed_updates.append(f"{ticker} (no existing data)")
                    continue

                # Fetch incremental data
                new_aggs = fetch_incremental_data(client, ticker, latest_timestamp, rate_limiter)

                if not new_aggs:
                    logger.info(f"✨ No new data for {ticker} (already up to date)")
                    skipped_updates.append(ticker)
                    continue

                # Update MongoDB
                docs_updated = update_mongodb_data(collection, ticker, new_aggs)

                successful_updates.append(ticker)
                total_new_data_points += len(new_aggs)
                total_documents_updated += docs_updated

                logger.info(f"✅ {ticker}: {len(new_aggs):,} new data points, {docs_updated} documents updated")

                # Show progress
                elapsed = time.time() - start_time
                avg_time_per_ticker = elapsed / idx
                remaining_tickers = total_tickers - idx
                eta = remaining_tickers * avg_time_per_ticker

                logger.info(f"📈 Progress: {idx}/{total_tickers} ({idx / total_tickers * 100:.1f}%)")
                logger.info(f"⏱️  Elapsed: {elapsed / 60:.1f} min | ETA: {eta / 60:.1f} min")

            except Exception as e:
                error_msg = f"Error processing {ticker}: {e}"
                logger.error(f"❌ {error_msg}")
                logger.error(traceback.format_exc())
                failed_updates.append(f"{ticker} ({str(e)[:50]}...)")

        # Final summary
        elapsed_total = time.time() - start_time
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ WEEKLY UPDATE COMPLETE")
        logger.info(f"{'=' * 60}")
        logger.info(f"📊 Successful updates: {len(successful_updates)}/{total_tickers}")
        logger.info(f"⚠️  Skipped (no new data): {len(skipped_updates)}")
        logger.info(f"❌ Failed updates: {len(failed_updates)}")

        if successful_updates:
            logger.info(
                f"Updated tickers: {', '.join(successful_updates[:10])}{', ...' if len(successful_updates) > 10 else ''}")

        if failed_updates:
            logger.info(f"Failed tickers: {', '.join(failed_updates)}")
            # Send notification for failures
            failure_msg = f"{len(failed_updates)} tickers failed to update: {', '.join(failed_updates)}"
            send_error_notification("Stock Update - Some Tickers Failed", failure_msg)

        logger.info(f"\n📈 Total new data points: {total_new_data_points:,}")
        logger.info(f"📁 Total documents updated: {total_documents_updated:,}")
        logger.info(f"⏱️  Total time: {elapsed_total / 60:.1f} minutes")

        mongo_client.close()

        # Send success notification if significant updates
        if successful_updates:
            success_msg = f"Weekly update completed successfully. Updated {len(successful_updates)} tickers with {total_new_data_points:,} new data points."
            logger.info(f"📧 Sending success notification...")

        return True

    except Exception as e:
        error_msg = f"Critical error in weekly update: {e}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        send_error_notification("Stock Update - Critical Error", error_msg, traceback.format_exc())
        return False


if __name__ == "__main__":
    logger.info("Stock Data Weekly Updater Started")

    # Check if this is a test run
    if len(os.sys.argv) > 1 and os.sys.argv[1] == "--test":
        logger.info("🧪 Running in test mode")
        # You can add test-specific logic here

    success = run_weekly_update()

    if success:
        logger.info("✅ Weekly update completed successfully!")
        os.sys.exit(0)
    else:
        logger.error("❌ Weekly update failed!")
        os.sys.exit(1)