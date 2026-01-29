"""
Tests for replay route extended hours parameter handling.

Tests verify that the include_extended_hours setting from the UI
is correctly passed through to the MongoDB data loading layer.

Run with: python tests/visualization_apps/test_replay_extended_hours.py
"""
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from unittest.mock import patch, MagicMock


class TestReplayExtendedHoursParameter:
    """Test that include_extended_hours is correctly passed through the replay route."""

    def test_run_monitor_backtest_passes_extended_hours_true(self):
        """Test that include_extended_hours=True is passed to process_historical_data."""
        from visualization_apps.routes.replay_routes import run_monitor_backtest
        import tempfile
        import json

        # Create minimal configs
        monitor_config = {
            "name": "Test Monitor",
            "indicators": [],
            "bars": {},
            "enter_long": [],
            "exit_long": [],
            "trade_executor": {}
        }

        data_config = {
            "ticker": "TEST",
            "start_date": "2026-01-20",
            "end_date": "2026-01-27",
            "include_extended_hours": True
        }

        # Create temp files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(monitor_config, f)
            monitor_path = f.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data_config, f)
            data_path = f.name

        try:
            # Mock MongoDBConnect to capture the call (imported at module level)
            with patch('visualization_apps.routes.replay_routes.MongoDBConnect') as MockMongo:
                mock_instance = MagicMock()
                mock_instance.process_historical_data.return_value = True
                mock_instance.get_all_aggregators.return_value = {}
                MockMongo.return_value = mock_instance

                # Mock BacktestDataStreamer (late import - patch at source)
                with patch('optimization.calculators.bt_data_streamer.BacktestDataStreamer') as MockStreamer:
                    mock_streamer = MagicMock()
                    mock_streamer.aggregators = {}
                    mock_streamer.run.return_value = MagicMock(closed_trades=[], open_positions=[])
                    MockStreamer.return_value = mock_streamer

                    # Mock IndicatorProcessorHistoricalNew (late import - patch at source)
                    with patch('optimization.calculators.indicator_processor_historical_new.IndicatorProcessorHistoricalNew') as MockIndicator:
                        mock_ind = MagicMock()
                        mock_ind.calculate_indicators.return_value = ({}, {}, {}, {}, {})
                        MockIndicator.return_value = mock_ind

                        try:
                            run_monitor_backtest(monitor_path, data_path)
                        except Exception:
                            pass  # We just want to verify the call was made correctly

                        # Verify process_historical_data was called with include_extended_hours=True
                        mock_instance.process_historical_data.assert_called_once()
                        call_args = mock_instance.process_historical_data.call_args
                        # Check positional or keyword argument
                        if len(call_args[0]) >= 5:
                            assert call_args[0][4] is True, "include_extended_hours should be True"
                        else:
                            assert call_args[1].get('include_extended_hours', True) is True
        finally:
            os.unlink(monitor_path)
            os.unlink(data_path)

    def test_run_monitor_backtest_passes_extended_hours_false(self):
        """Test that include_extended_hours=False is passed to process_historical_data."""
        from visualization_apps.routes.replay_routes import run_monitor_backtest
        import tempfile
        import json

        # Create minimal configs
        monitor_config = {
            "name": "Test Monitor",
            "indicators": [],
            "bars": {},
            "enter_long": [],
            "exit_long": [],
            "trade_executor": {}
        }

        data_config = {
            "ticker": "TEST",
            "start_date": "2026-01-20",
            "end_date": "2026-01-27",
            "include_extended_hours": False  # Explicitly set to False
        }

        # Create temp files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(monitor_config, f)
            monitor_path = f.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data_config, f)
            data_path = f.name

        try:
            # Mock MongoDBConnect to capture the call (imported at module level)
            with patch('visualization_apps.routes.replay_routes.MongoDBConnect') as MockMongo:
                mock_instance = MagicMock()
                mock_instance.process_historical_data.return_value = True
                mock_instance.get_all_aggregators.return_value = {}
                MockMongo.return_value = mock_instance

                # Mock BacktestDataStreamer (late import - patch at source)
                with patch('optimization.calculators.bt_data_streamer.BacktestDataStreamer') as MockStreamer:
                    mock_streamer = MagicMock()
                    mock_streamer.aggregators = {}
                    mock_streamer.run.return_value = MagicMock(closed_trades=[], open_positions=[])
                    MockStreamer.return_value = mock_streamer

                    # Mock IndicatorProcessorHistoricalNew (late import - patch at source)
                    with patch('optimization.calculators.indicator_processor_historical_new.IndicatorProcessorHistoricalNew') as MockIndicator:
                        mock_ind = MagicMock()
                        mock_ind.calculate_indicators.return_value = ({}, {}, {}, {}, {})
                        MockIndicator.return_value = mock_ind

                        try:
                            run_monitor_backtest(monitor_path, data_path)
                        except Exception:
                            pass

                        # Verify process_historical_data was called with include_extended_hours=False
                        mock_instance.process_historical_data.assert_called_once()
                        call_args = mock_instance.process_historical_data.call_args
                        # Check positional or keyword argument
                        if len(call_args[0]) >= 5:
                            assert call_args[0][4] is False, "include_extended_hours should be False"
                        else:
                            assert call_args[1].get('include_extended_hours', True) is False
        finally:
            os.unlink(monitor_path)
            os.unlink(data_path)

    def test_run_monitor_backtest_defaults_to_true(self):
        """Test that missing include_extended_hours defaults to True."""
        from visualization_apps.routes.replay_routes import run_monitor_backtest
        import tempfile
        import json

        # Create minimal configs - WITHOUT include_extended_hours
        monitor_config = {
            "name": "Test Monitor",
            "indicators": [],
            "bars": {},
            "enter_long": [],
            "exit_long": [],
            "trade_executor": {}
        }

        data_config = {
            "ticker": "TEST",
            "start_date": "2026-01-20",
            "end_date": "2026-01-27"
            # No include_extended_hours - should default to True
        }

        # Create temp files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(monitor_config, f)
            monitor_path = f.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data_config, f)
            data_path = f.name

        try:
            # Mock MongoDBConnect to capture the call (imported at module level)
            with patch('visualization_apps.routes.replay_routes.MongoDBConnect') as MockMongo:
                mock_instance = MagicMock()
                mock_instance.process_historical_data.return_value = True
                mock_instance.get_all_aggregators.return_value = {}
                MockMongo.return_value = mock_instance

                # Mock BacktestDataStreamer (late import - patch at source)
                with patch('optimization.calculators.bt_data_streamer.BacktestDataStreamer') as MockStreamer:
                    mock_streamer = MagicMock()
                    mock_streamer.aggregators = {}
                    mock_streamer.run.return_value = MagicMock(closed_trades=[], open_positions=[])
                    MockStreamer.return_value = mock_streamer

                    # Mock IndicatorProcessorHistoricalNew (late import - patch at source)
                    with patch('optimization.calculators.indicator_processor_historical_new.IndicatorProcessorHistoricalNew') as MockIndicator:
                        mock_ind = MagicMock()
                        mock_ind.calculate_indicators.return_value = ({}, {}, {}, {}, {})
                        MockIndicator.return_value = mock_ind

                        try:
                            run_monitor_backtest(monitor_path, data_path)
                        except Exception:
                            pass

                        # Verify process_historical_data was called with include_extended_hours=True (default)
                        mock_instance.process_historical_data.assert_called_once()
                        call_args = mock_instance.process_historical_data.call_args
                        if len(call_args[0]) >= 5:
                            assert call_args[0][4] is True, "include_extended_hours should default to True"
                        else:
                            assert call_args[1].get('include_extended_hours', True) is True
        finally:
            os.unlink(monitor_path)
            os.unlink(data_path)


def run_tests():
    """Run all tests without pytest."""
    import traceback

    test_classes = [TestReplayExtendedHoursParameter]
    passed = 0
    failed = 0

    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                try:
                    print(f"Running {test_class.__name__}.{method_name}...", end=" ")
                    getattr(instance, method_name)()
                    print("PASSED")
                    passed += 1
                except AssertionError as e:
                    print(f"FAILED: {e}")
                    failed += 1
                except Exception as e:
                    print(f"ERROR: {e}")
                    traceback.print_exc()
                    failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
