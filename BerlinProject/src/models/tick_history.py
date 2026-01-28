from typing import Dict, Optional
from datetime import datetime, timedelta

from bson import ObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator

from models.tick_data import TickData
from mlf_utils.timezone_utils import ET, to_utc, to_timestamp_ms


class TickHistory(BaseModel):
    """
    Represents historical tick data stored in MongoDB.

    Data Structure:
    - year, month: The calendar month this data covers
    - ticker: Stock symbol
    - time_increments: Candle size in minutes (1, 5, etc.)
    - data: Dict[day_of_month, Dict[seconds_from_midnight_ET, TickData]]

    IMPORTANT: The seconds_from_midnight keys represent Eastern Time (market timezone).
    When process_timestamps() is called, timestamps are converted to UTC-aware datetimes
    for consistency with the rest of the application.
    """
    id: Optional[ObjectId] = PydanticField(default_factory=ObjectId, alias="_id")
    month: int
    year: int
    ticker: str
    time_increments: int
    # Data is a dict of day of month to dict of number of seconds from midnight (ET) to tickdata
    data: Dict[str, Dict[str, TickData]]

    class Config:
        arbitrary_types_allowed = True  # Allows ObjectId
        json_encoders = {ObjectId: str}  # Serializes ObjectId to string for MongoDB

    @model_validator(mode='before')
    def validate_definition(cls, values):
        if 'data' in values and isinstance(values['data'], list):
            new_data = {}
            for item in values['data']:
                time = item.pop('time')  # Remove time from the dictionary
                new_data[time] = TickData(**item)  # Create TickData without time
            values['data'] = new_data
        return values

    def process_timestamps(self, as_utc: bool = True):
        """
        Process stored data to add proper timestamps to TickData objects.

        The stored data uses seconds_from_midnight as keys, representing Eastern Time
        (the market timezone). This method converts those to proper datetime objects.

        Args:
            as_utc: If True (default), store timestamps as UTC-aware datetimes.
                   If False, store as ET-aware datetimes.

        Note:
            After calling this method, each TickData.timestamp will be a
            timezone-aware datetime object, consistent with live data from
            SchwabDataLink.
        """
        for day, day_dict in self.data.items():
            # Create base date in Eastern Time (market timezone)
            # The seconds_from_midnight values represent ET times
            base_date_et = datetime(
                year=int(self.year),
                month=int(self.month),
                day=int(day),
                tzinfo=ET
            )
            for seconds_from_midnight, tick in day_dict.items():
                # Add seconds to get the full ET timestamp
                timestamp_et = base_date_et + timedelta(seconds=int(seconds_from_midnight))

                # Store as UTC (default) or ET based on preference
                if as_utc:
                    tick.timestamp = to_utc(timestamp_et)
                else:
                    tick.timestamp = timestamp_et

    def process_timestamps_as_ms(self):
        """
        Legacy method: Process timestamps and store as milliseconds since epoch.

        DEPRECATED: Use process_timestamps() instead, which stores proper
        timezone-aware datetime objects for consistency with the rest of
        the application.

        This method is kept for backward compatibility with code that expects
        timestamps as integers (milliseconds since epoch).
        """
        for day, day_dict in self.data.items():
            # Create base date in Eastern Time
            base_date_et = datetime(
                year=int(self.year),
                month=int(self.month),
                day=int(day),
                tzinfo=ET
            )
            for seconds_from_midnight, tick in day_dict.items():
                timestamp_et = base_date_et + timedelta(seconds=int(seconds_from_midnight))
                # Convert to milliseconds since epoch (UTC)
                tick.timestamp = to_timestamp_ms(timestamp_et)

#  TIck history tools, give it a interval date range and tickers and it should run through them.