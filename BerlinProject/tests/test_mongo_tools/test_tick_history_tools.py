import unittest

from mongo_tools.tick_history_tools import TickHistoryTools, STREAMING_MODE, RANDOM_MODE
from datetime import datetime


class TestTickHistory(unittest.TestCase):
    # Create tools instance
    def test_number_of_days(self):
        """Test that a single trading day returns exactly 390 ticks (6.5 hours of trading)"""
        # Create tools instance for a single day (April 2, 2024)
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 10, 22),
            end_date=datetime(2024, 10, 24),
            time_increments=1
        )

        check = tools.books
        # Assert we get exactly 390 ticks (one trading day)
        self.assertEqual(len(check), 3,
                         f"Expected 3 trading days got {len(check)}")

    def test_ticks_in_day(self):
        """Test that we can get tick data across multiple days"""
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 6, 20),
            end_date=datetime(2024, 6, 20),
            time_increments=5
        )

        ticks = list(tools.serve_next_tick())
        self.assertTrue(ticks, 78)

    def test_multi_months(self):
        """Test getting NVDA tick data from the database"""
        # Create tools instance
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 3, 20),
            end_date=datetime(2024, 7, 12),
            time_increments=1
        )

        check = tools.books

        self.assertEqual(len(check), 60,
                         f"Expected 60 trading days got {len(check)}")

    def test_serve_next(self):
        """Test getting NVDA tick data from the database"""
        # Create tools instance
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 9, 20),
            end_date=datetime(2024, 9, 25),
            time_increments=1
        )


class TestNewTickHistory(unittest.TestCase):

    def test_new_method(self):
        data_config = [{
            'ticker': 'NVDA',
            'start_date': '2024-05-22',
            'end_date': '2024-05-24',
            'time_increments': '1'
        }
        ]

        tools = TickHistoryTools.get_tools2(data_config)

        check = tools.books

        lengths = [len(data_dict) for outer_list in check for data_dict in outer_list]

        self.assertEqual(len(lengths), 3,
                         f"Expected 3 trading days got {len(check)}")

    def test_new_method2(self):
        data_config = [{
            'ticker': 'NVDA',
            'start_date': '2024-05-22',
            'end_date': '2024-05-24',
            'time_increments': '5'
        },
            {
                'ticker': 'META',
                'start_date': '2024-05-22',
                'end_date': '2024-05-24',
                'time_increments': '5'
            }
        ]

        tools = TickHistoryTools.get_tools2(data_config)
        check = tools.books
        indexed_data = TickHistoryTools.index_days(check)

        self.assertEqual(len(indexed_data), 6,
                         f"Expected 6 indexed tickdatas got {len(check)}")

    def test_get_history_random_stream(self):
        data_config = [{
            'ticker': 'NVDA',
            'start_date': '2024-05-22',
            'end_date': '2024-05-24',
            'time_increments': '5'
        },
            {
                'ticker': 'META',
                'start_date': '2024-05-22',
                'end_date': '2024-05-24',
                'time_increments': '5'
            }
        ]

        tools = TickHistoryTools.get_tools2(data_config)

        # WRITE TESTS FOR THIS STUFF vvv^^^
        tools.set_iteration_mode(RANDOM_MODE, 2)
        history_random = tools.get_history()

        tools.set_iteration_mode(STREAMING_MODE, 2)
        history_stream = tools.get_history()

    def test_serve_next_tick(self):
        data_config = [{
            'ticker': 'NVDA',
            'start_date': '2024-05-22',
            'end_date': '2024-05-24',
            'time_increments': '5'
        },
            {
                'ticker': 'META',
                'start_date': '2024-05-22',
                'end_date': '2024-05-24',
                'time_increments': '5'
            }]

        tools = TickHistoryTools.get_tools2(data_config)
        tools.set_iteration_mode(RANDOM_MODE, 2)
        tick_generator = tools.serve_next_tick()
        first_tick = next(tick_generator)

        # Get first 5 items (ticks or separators)
        for _ in range(100):
            tick, tick_idx, day_idx = next(tick_generator)
            if tick is None:
                print(f"End of day {day_idx}")
            else:
                print(f"Day {day_idx}, Tick {tick_idx}: Close = {tick.close}")
