from pymongo import MongoClient
import json

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
collection = client['MTA_devel']['tick_history']

# Find NVDA data for July 2025
query = {
    'ticker': 'NVDA',
    'year': 2025,
    'month': 7
}

doc = collection.find_one(query)

if doc:
    print("NVDA JULY 2025 RAW DATA")
    print("=" * 50)
    print(f"Ticker: {doc['ticker']}")
    print(f"Year: {doc['year']}")
    print(f"Month: {doc['month']}")
    print(f"Interval: {doc['time_increments']} minutes")
    print()

    data = doc.get('data', {})

    # Check if day 21 exists
    if '21' in data:
        print("JULY 21ST DATA:")
        print("-" * 30)

        day_21_data = data['21']
        print(f"Total data points: {len(day_21_data)}")
        print()

        # Sort by timestamp (seconds from midnight)
        sorted_times = sorted(day_21_data.keys(), key=int)

        for timestamp in sorted_times:
            price_data = day_21_data[timestamp]

            # Convert seconds to time
            seconds = int(timestamp)
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            time_str = f"{hours:02d}:{minutes:02d}"

            print(f"{time_str} - O: ${price_data['open']:.2f}, H: ${price_data['high']:.2f}, "
                  f"L: ${price_data['low']:.2f}, C: ${price_data['close']:.2f}, "
                  f"Vol: {price_data['volume']:,}")
    else:
        print("NO DATA FOUND FOR JULY 21ST")
        available_days = sorted([int(day) for day in data.keys()])
        print(f"Available days: {available_days}")

else:
    print("NO NVDA DATA FOUND FOR JULY 2025")