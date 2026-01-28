#!/usr/bin/env python3
"""
Migration Script: Fix Polygon Timezone Data

Problem:
    The tick_history_polygon collection has timestamps stored in Pacific Time (PT)
    instead of Eastern Time (ET). This occurred because the original data fetch code
    used datetime.fromtimestamp() which converts to server local time (Pacific),
    but the data should be stored in Eastern Time (market timezone).

Solution:
    Shift all seconds_from_midnight keys by +10800 seconds (3 hours) to convert
    from Pacific Time to Eastern Time.

Edge Cases Handled:
    - Day boundary crossings (times >= 86400 seconds roll to next day)
    - Month boundary crossings (day 31 -> day 1 of next month)
    - Leap years for February

Usage:
    # Dry run (preview changes without modifying database)
    python scripts/migrate_polygon_timezone_fix.py --dry-run

    # Execute migration
    python scripts/migrate_polygon_timezone_fix.py

    # Execute with verbose logging
    python scripts/migrate_polygon_timezone_fix.py --verbose

Author: Migration script for BerlinProject timezone fix
Date: 2024
"""

import argparse
import sys
from datetime import datetime
from calendar import monthrange
from collections import defaultdict
from typing import Dict, Any, Tuple, List

from pymongo import MongoClient
from pymongo.collection import Collection


# Constants
PT_TO_ET_OFFSET_SECONDS = 10800  # 3 hours = 10800 seconds
SECONDS_PER_DAY = 86400
COLLECTION_NAME = 'tick_history_polygon'
DATABASE_NAME = 'MTA_devel'


def seconds_to_time_str(seconds: int) -> str:
    """Convert seconds from midnight to HH:MM format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def get_days_in_month(year: int, month: int) -> int:
    """Get the number of days in a given month"""
    return monthrange(year, month)[1]


def get_next_month(year: int, month: int) -> Tuple[int, int]:
    """Get the next month, handling year boundary"""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def migrate_document(doc: Dict[str, Any], dry_run: bool = False, verbose: bool = False) -> Dict[str, Any]:
    """
    Migrate a single document by shifting all time keys by 3 hours.

    Args:
        doc: MongoDB document to migrate
        dry_run: If True, don't modify the document
        verbose: If True, print detailed changes

    Returns:
        Dictionary with migration statistics
    """
    ticker = doc['ticker']
    year = doc['year']
    month = doc['month']
    data = doc.get('data', {})

    stats = {
        'ticker': ticker,
        'year': year,
        'month': month,
        'entries_migrated': 0,
        'entries_rolled_to_next_day': 0,
        'entries_rolled_to_next_month': 0,
        'days_affected': 0,
    }

    # New data structure with corrected times
    new_data = defaultdict(dict)
    days_in_month = get_days_in_month(year, month)

    # Track entries that need to go to next month
    next_month_data = defaultdict(dict)

    for day_str, day_data in data.items():
        day = int(day_str)
        stats['days_affected'] += 1

        for time_seconds_str, tick_data in day_data.items():
            old_seconds = int(time_seconds_str)
            new_seconds = old_seconds + PT_TO_ET_OFFSET_SECONDS

            stats['entries_migrated'] += 1

            # Handle day boundary crossing
            if new_seconds >= SECONDS_PER_DAY:
                new_seconds -= SECONDS_PER_DAY
                new_day = day + 1
                stats['entries_rolled_to_next_day'] += 1

                # Handle month boundary crossing
                if new_day > days_in_month:
                    # This entry belongs to day 1 of next month
                    next_month_data[str(1)][str(new_seconds)] = tick_data
                    stats['entries_rolled_to_next_month'] += 1

                    if verbose:
                        print(f"    {ticker} {year}/{month}/{day} {seconds_to_time_str(old_seconds)} -> "
                              f"NEXT MONTH day 1 {seconds_to_time_str(new_seconds)}")
                    continue
                else:
                    new_data[str(new_day)][str(new_seconds)] = tick_data

                    if verbose:
                        print(f"    {ticker} {year}/{month}/{day} {seconds_to_time_str(old_seconds)} -> "
                              f"day {new_day} {seconds_to_time_str(new_seconds)}")
            else:
                new_data[str(day)][str(new_seconds)] = tick_data

    if not dry_run:
        doc['data'] = dict(new_data)

    stats['next_month_data'] = dict(next_month_data) if next_month_data else None

    return stats


def run_migration(dry_run: bool = False, verbose: bool = False, limit: int = None):
    """
    Run the migration on all documents in tick_history_polygon.

    Args:
        dry_run: If True, preview changes without modifying database
        verbose: If True, print detailed changes
        limit: If set, only process this many documents (for testing)
    """
    print("=" * 60)
    print("Polygon Timezone Migration Script")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE MIGRATION'}")
    print(f"Offset: +{PT_TO_ET_OFFSET_SECONDS} seconds ({PT_TO_ET_OFFSET_SECONDS // 3600} hours)")
    print(f"Collection: {DATABASE_NAME}.{COLLECTION_NAME}")
    print("=" * 60)

    # Connect to MongoDB
    try:
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]

        # Test connection
        client.server_info()
        print("Connected to MongoDB")
    except Exception as e:
        print(f"ERROR: Failed to connect to MongoDB: {e}")
        sys.exit(1)

    # Get document count
    total_docs = collection.count_documents({})
    print(f"Total documents to process: {total_docs}")

    if limit:
        print(f"Limiting to {limit} documents (testing mode)")

    print("-" * 60)

    # Track overall statistics
    total_stats = {
        'documents_processed': 0,
        'documents_updated': 0,
        'entries_migrated': 0,
        'entries_rolled_to_next_day': 0,
        'entries_rolled_to_next_month': 0,
        'errors': 0,
    }

    # Track data that needs to go to next month documents
    next_month_updates = defaultdict(lambda: defaultdict(dict))

    # Process documents
    cursor = collection.find({})
    if limit:
        cursor = cursor.limit(limit)

    for i, doc in enumerate(cursor):
        doc_id = doc['_id']
        ticker = doc['ticker']
        year = doc['year']
        month = doc['month']

        try:
            # Migrate the document
            stats = migrate_document(doc, dry_run=dry_run, verbose=verbose)

            total_stats['documents_processed'] += 1
            total_stats['entries_migrated'] += stats['entries_migrated']
            total_stats['entries_rolled_to_next_day'] += stats['entries_rolled_to_next_day']
            total_stats['entries_rolled_to_next_month'] += stats['entries_rolled_to_next_month']

            # Store next month data for later
            if stats['next_month_data']:
                next_year, next_month = get_next_month(year, month)
                key = (ticker, next_year, next_month)
                for day_str, day_data in stats['next_month_data'].items():
                    next_month_updates[key][day_str].update(day_data)

            # Update the document in MongoDB
            if not dry_run and stats['entries_migrated'] > 0:
                collection.update_one(
                    {'_id': doc_id},
                    {'$set': {'data': doc['data']}}
                )
                total_stats['documents_updated'] += 1

            # Progress update
            if (i + 1) % 100 == 0 or (i + 1) == total_docs:
                print(f"Processed {i + 1}/{total_docs} documents...")

        except Exception as e:
            print(f"ERROR processing {ticker} {year}/{month}: {e}")
            total_stats['errors'] += 1

    # Handle next month data (merge into existing documents or create new ones)
    if next_month_updates and not dry_run:
        print("-" * 60)
        print(f"Processing {len(next_month_updates)} cross-month data transfers...")

        for (ticker, year, month), data in next_month_updates.items():
            # Find or create the target document
            target_doc = collection.find_one({
                'ticker': ticker,
                'year': year,
                'month': month,
                'time_increments': 1
            })

            if target_doc:
                # Merge with existing data
                existing_data = target_doc.get('data', {})
                for day_str, day_data in data.items():
                    if day_str in existing_data:
                        existing_data[day_str].update(day_data)
                    else:
                        existing_data[day_str] = day_data

                collection.update_one(
                    {'_id': target_doc['_id']},
                    {'$set': {'data': existing_data}}
                )
                print(f"  Merged cross-month data into {ticker} {year}/{month}")
            else:
                # Create new document
                new_doc = {
                    'ticker': ticker,
                    'year': year,
                    'month': month,
                    'time_increments': 1,
                    'data': dict(data)
                }
                collection.insert_one(new_doc)
                print(f"  Created new document for {ticker} {year}/{month}")

    # Print summary
    print("=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    print(f"Documents processed:        {total_stats['documents_processed']}")
    print(f"Documents updated:          {total_stats['documents_updated']}")
    print(f"Total entries migrated:     {total_stats['entries_migrated']}")
    print(f"Entries rolled to next day: {total_stats['entries_rolled_to_next_day']}")
    print(f"Entries rolled to next month: {total_stats['entries_rolled_to_next_month']}")
    print(f"Errors:                     {total_stats['errors']}")
    print("=" * 60)

    if dry_run:
        print("\nThis was a DRY RUN. No changes were made to the database.")
        print("Run without --dry-run to apply changes.")
    else:
        print("\nMigration complete!")

    client.close()

    return total_stats


def verify_migration(sample_count: int = 3):
    """
    Verify the migration by checking sample documents.
    """
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    client = MongoClient('mongodb://localhost:27017/')
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    # Get sample documents
    samples = list(collection.find({}).limit(sample_count))

    for doc in samples:
        ticker = doc['ticker']
        year = doc['year']
        month = doc['month']
        data = doc.get('data', {})

        all_times = []
        for day_data in data.values():
            all_times.extend([int(k) for k in day_data.keys()])

        if all_times:
            min_time = min(all_times)
            max_time = max(all_times)
            print(f"\n{ticker} {year}/{month}:")
            print(f"  Time range: {seconds_to_time_str(min_time)} - {seconds_to_time_str(max_time)}")
            print(f"  Market open (9:30/34200): {'Present' if 34200 in all_times else 'Missing'}")
            print(f"  Pre-market (4:00/14400): {'Present' if 14400 in all_times else 'Missing'}")

            # Check for incorrect times
            incorrect_times = [t for t in all_times if t < 14400]  # Before 4 AM ET
            if incorrect_times:
                print(f"  WARNING: {len(incorrect_times)} entries before 4:00 AM ET!")
            else:
                print(f"  All times are valid (>= 4:00 AM ET)")

    client.close()


def main():
    parser = argparse.ArgumentParser(
        description='Migrate tick_history_polygon timestamps from Pacific Time to Eastern Time',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/migrate_polygon_timezone_fix.py --dry-run    # Preview changes
  python scripts/migrate_polygon_timezone_fix.py              # Execute migration
  python scripts/migrate_polygon_timezone_fix.py --verify     # Verify after migration
        """
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying the database')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print detailed changes for each entry')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of documents to process (for testing)')
    parser.add_argument('--verify', action='store_true',
                        help='Verify migration results (run after migration)')

    args = parser.parse_args()

    if args.verify:
        verify_migration()
    else:
        run_migration(dry_run=args.dry_run, verbose=args.verbose, limit=args.limit)

        if not args.dry_run:
            verify_migration()


if __name__ == '__main__':
    main()
