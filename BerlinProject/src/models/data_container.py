import json
from typing import Dict, Any, List, Union, Optional
from datetime import datetime, timedelta


class DataContainer:

    def __init__(self, data_configs: List[Dict[str, Any]]):
        """
        Initialize DataContainer with a list of data configs.

        Args:
            data_configs: List of dicts, each with 'ticker', 'start_date', 'end_date'
        """
        self.data_configs = data_configs
        self.split_configs: Optional[List] = None

    @classmethod
    def from_file(cls, file_path: str) -> 'DataContainer':
        """
        Create DataContainer from a JSON file.

        Args:
            file_path: Path to JSON file (can be dict or list of dicts)

        Returns:
            DataContainer instance
        """
        with open(file_path, 'r') as f:
            config = json.load(f)

        if isinstance(config, dict):
            data_configs = [config]
        elif isinstance(config, list):
            data_configs = config
        else:
            raise ValueError(f"Data config must be dict or list, got {type(config)}")

        return cls(data_configs)

    @classmethod
    def from_json(cls, config: Union[Dict[str, Any], List[Dict[str, Any]]]) -> 'DataContainer':
        """
        Create DataContainer from a dict or list of dicts.

        Args:
            config: Either a single dict or list of dicts

        Returns:
            DataContainer instance
        """
        if isinstance(config, dict):
            data_configs = [config]
        elif isinstance(config, list):
            data_configs = config
        else:
            raise ValueError(f"Data config must be dict or list, got {type(config)}")

        return cls(data_configs)

    def create_splits(self, num_splits: int, daily_splits: bool = False) -> 'DataContainer':
        """
        Create a new DataContainer with date ranges split.
        Splits each config in the list into multiple date ranges.

        Args:
            num_splits: Number of splits to create (e.g., 4 splits). Ignored if daily_splits=True.
            daily_splits: If True, create one split per calendar day (ignores num_splits).

        Returns:
            New DataContainer with split configs
        """
        self.split_configs = []

        for config in self.data_configs:
            ticker = config['ticker']
            start_date = datetime.strptime(config['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(config['end_date'], '%Y-%m-%d')

            if daily_splits:
                # Create one split per calendar day
                current_date = start_date
                while current_date <= end_date:
                    split_config = {
                        'ticker': ticker,
                        'start_date': current_date.strftime('%Y-%m-%d'),
                        'end_date': current_date.strftime('%Y-%m-%d')
                    }
                    self.split_configs.append(split_config)
                    current_date += timedelta(days=1)
            else:
                # Original behavior: divide date range into num_splits equal parts
                total_days = (end_date - start_date).days
                days_per_split = total_days // num_splits

                for i in range(num_splits):
                    split_start = start_date + timedelta(days=i * days_per_split)

                    if i == num_splits - 1:
                        split_end = end_date
                    else:
                        split_end = start_date + timedelta(days=(i + 1) * days_per_split - 1)

                    split_config = {
                        'ticker': ticker,
                        'start_date': split_start.strftime('%Y-%m-%d'),
                        'end_date': split_end.strftime('%Y-%m-%d')
                    }
                    self.split_configs.append(split_config)

    def __repr__(self):
        return f"DataContainer({len(self.data_configs)} configs)"