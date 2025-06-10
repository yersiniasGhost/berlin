# File: BerlinProject/src/stock_analysis_ui/routes/api_routes.py
# FIXED VERSION for simplified architecture

"""
Simplified API routes for AppService
"""

import logging
from datetime import datetime

import numpy as np
from flask import Blueprint, request, jsonify, current_app

from data_streamer.indicator_processor import IndicatorProcessor
from environments.tick_data import TickData

logger = logging.getLogger('APIRoutes')
api_bp = Blueprint('api', __name__)


@api_bp.route('/status')
def get_status():
    """Get current application status"""
    try:
        app_service = current_app.app_service
        combinations = app_service.get_combinations()

        return jsonify({
            'authenticated': app_service.auth_manager.is_authenticated(),
            'streaming': app_service.is_streaming,
            'combinations': combinations['combinations'],
            'total_combinations': combinations['total']
        })

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/combinations', methods=['POST'])
def add_combination():
    """Add a new combination - auto-generate card ID"""
    try:
        data = request.json

        symbol = data.get('symbol', '').upper().strip()
        config_file = data.get('config_file', '').strip()

        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol is required'}), 400

        if not config_file:
            return jsonify({'success': False, 'error': 'Config file is required'}), 400

        app_service = current_app.app_service
        result = app_service.add_combination(symbol, config_file)

        if result['success']:
            logger.info(f"Successfully added combination: {result['card_id']}")
            return jsonify(result)
        else:
            logger.error(f"Failed to add combination: {result.get('error', 'Unknown error')}")
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error adding combination: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations/<card_id>', methods=['DELETE'])
def remove_combination(card_id: str):
    """Remove a combination by card ID"""
    try:
        app_service = current_app.app_service
        result = app_service.remove_combination(card_id)

        if result['success']:
            logger.info(f"Successfully removed combination: {card_id}")
            return jsonify(result)
        else:
            logger.error(f"Failed to remove combination {card_id}: {result.get('error', 'Unknown error')}")
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error removing combination {card_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations')
def get_combinations():
    """Get all active combinations"""
    try:
        app_service = current_app.app_service
        combinations = app_service.get_combinations()
        return jsonify(combinations)

    except Exception as e:
        logger.error(f"Error getting combinations: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/configs')
def get_available_configs():
    """Get list of available configuration files"""
    try:
        app_service = current_app.app_service
        configs = app_service.get_available_configs()

        return jsonify({
            'success': True,
            'configs': configs,
            'total': len(configs)
        })

    except Exception as e:
        logger.error(f"Error getting available configs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/streaming/start', methods=['POST'])
def start_streaming():
    """Start streaming infrastructure"""
    try:
        app_service = current_app.app_service

        if app_service.start_streaming():
            logger.info("Streaming started via API")
            return jsonify({'success': True, 'message': 'Streaming started'})
        else:
            logger.error("Failed to start streaming via API")
            return jsonify({'success': False, 'error': 'Failed to start streaming'}), 500

    except Exception as e:
        logger.error(f"Error starting streaming: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/streaming/stop', methods=['POST'])
def stop_streaming():
    """Stop streaming"""
    try:
        app_service = current_app.app_service

        if app_service.stop_streaming():
            logger.info("Streaming stopped via API")
            return jsonify({'success': True, 'message': 'Streaming stopped'})
        else:
            logger.error("Failed to stop streaming via API")
            return jsonify({'success': False, 'error': 'Failed to stop streaming'}), 500

    except Exception as e:
        logger.error(f"Error stopping streaming: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/debug/<card_id>')
def debug_card(card_id: str):
    """Debug endpoint to see what's happening with a specific card"""
    try:
        app_service = current_app.app_service

        if card_id not in app_service.combinations:
            return jsonify({'error': f'Card {card_id} not found'}), 404

        combination = app_service.combinations[card_id]
        data_streamer = combination['data_streamer']

        # Get debug status
        debug_info = data_streamer.debug_status()

        # Get current indicator calculations (force a calculation)
        all_candle_data = data_streamer._get_all_candle_data()
        current_indicators, current_raw, current_bars = data_streamer.indicator_processor.calculate_indicators(
            all_candle_data, None  # No specific completed timeframe
        )

        debug_info['current_calculation'] = {
            'indicators': current_indicators,
            'raw_indicators': current_raw,
            'bar_scores': current_bars,
            'calculation_time': datetime.now().isoformat()
        }

        # Test individual indicators
        debug_info['indicator_tests'] = {}
        for indicator_def in data_streamer.monitor_config.indicators:
            timeframe = getattr(indicator_def, 'time_increment', '1m')
            if timeframe in all_candle_data:
                candles = all_candle_data[timeframe]
                try:
                    result = data_streamer.indicator_processor._calculate_single_indicator(candles, indicator_def)
                    recent_results = result[-10:] if len(result) > 10 else result
                    debug_info['indicator_tests'][indicator_def.name] = {
                        'success': True,
                        'result_length': len(result),
                        'recent_values': recent_results.tolist() if hasattr(recent_results, 'tolist') else list(
                            recent_results),
                        'trigger_count': int(np.sum(result > 0)) if hasattr(result, '__len__') else 0,
                        'max_value': float(np.max(result)) if hasattr(result, '__len__') and len(result) > 0 else 0
                    }
                except Exception as e:
                    debug_info['indicator_tests'][indicator_def.name] = {
                        'success': False,
                        'error': str(e)
                    }

        return jsonify({
            'success': True,
            'debug_info': debug_info
        })

    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/debug/trigger-test/<card_id>')
def trigger_test(card_id: str):
    """Force trigger test for debugging"""
    try:
        app_service = current_app.app_service

        if card_id not in app_service.combinations:
            return jsonify({'error': f'Card {card_id} not found'}), 404

        combination = app_service.combinations[card_id]
        data_streamer = combination['data_streamer']

        # Force set a trigger for testing
        data_streamer.indicator_processor.stored_values['test_trigger'] = {
            'value': 1.0,
            'raw_value': 1.0,
            'timestamp': datetime.now(),
            'timeframe': '1m'
        }

        # Force send to UI
        for tool in data_streamer.external_tools:
            tool.indicator_vector(
                card_id=card_id,
                symbol=data_streamer.symbol,
                tick=TickData(
                    symbol=data_streamer.symbol,
                    timestamp=datetime.now(),
                    open=100.0, high=100.0, low=100.0, close=100.0,
                    volume=1000, time_increment="1m"
                ),
                indicators={'test_trigger': 1.0},
                bar_scores={'test_bar': 1.0},
                raw_indicators={'test_trigger': 1.0}
            )

        return jsonify({
            'success': True,
            'message': 'Test trigger sent'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations/<card_id>/details')
def get_card_details(card_id: str):
    """Get detailed indicator history and current values for a specific card"""
    try:
        app_service = current_app.app_service

        # Check if card exists
        if card_id not in app_service.combinations:
            return jsonify({'success': False, 'error': f'Card {card_id} not found'}), 404

        combination = app_service.combinations[card_id]
        symbol = combination['symbol']
        monitor_config = combination['monitor_config']
        data_streamer = combination['data_streamer']

        # Get timeframes from the monitor config
        timeframes = monitor_config.get_time_increments()

        # Get all candle data from the DataStreamer's aggregators
        all_candle_data = data_streamer._get_all_candle_data()

        # Build aggregator info
        aggregator_info = {}
        for timeframe in timeframes:
            if timeframe in all_candle_data:
                candles = all_candle_data[timeframe]
                aggregator_info[timeframe] = {
                    'history_count': len(candles),
                    'current_price': candles[-1].close if candles else 0,
                    'latest_timestamp': candles[-1].timestamp.isoformat() if candles else None
                }

        # Calculate current indicator values
        current_indicators, current_raw, current_bars = data_streamer.indicator_processor.calculate_indicators(
            all_candle_data, None  # No specific timeframe completed
        )

        # Calculate indicator history over time (simplified version)
        indicator_history = _calculate_simple_indicator_history(all_candle_data, monitor_config)

        # Build response
        response_data = {
            'success': True,
            'card_info': {
                'card_id': card_id,
                'symbol': symbol,
                'config_name': monitor_config.name,
                'timeframes': list(timeframes),
                'total_indicators': len(monitor_config.indicators)
            },
            'aggregator_info': aggregator_info,
            'current_values': {
                'indicators': current_indicators,
                'raw_indicators': current_raw,
                'bar_scores': current_bars,
                'timestamp': datetime.now().isoformat()
            },
            'indicator_history': indicator_history,
            'indicator_definitions': [
                {
                    'name': ind.name,
                    'function': ind.function,
                    'timeframe': getattr(ind, 'time_increment', '1m'),
                    'parameters': ind.parameters
                }
                for ind in monitor_config.indicators
            ]
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error getting card details for {card_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def _calculate_simple_indicator_history(all_candle_data: dict, monitor_config, lookback_periods: int = 60) -> dict:
    """
    Calculate indicator history showing trigger events properly
    """
    try:
        # Use 1m data if available, otherwise use the smallest timeframe
        timeframes = sorted(all_candle_data.keys())
        if not timeframes:
            return {'timestamps': [], 'indicators': {}, 'bar_scores': {}, 'periods': 0}

        # Prefer 1m data for history, fall back to smallest timeframe
        history_timeframe = "1m" if "1m" in all_candle_data else timeframes[0]
        historical_data = all_candle_data[history_timeframe]

        if len(historical_data) < 30:
            return {'timestamps': [], 'indicators': {}, 'bar_scores': {}, 'periods': 0}

        indicator_history = {
            'timestamps': [],
            'indicators': {},
            'bar_scores': {},
            'periods': 0
        }

        # Initialize indicator arrays
        for indicator in monitor_config.indicators:
            indicator_history['indicators'][indicator.name] = []

        # Initialize bar arrays
        if hasattr(monitor_config, 'bars'):
            for bar_name in monitor_config.bars.keys():
                indicator_history['bar_scores'][bar_name] = []

        # Take the last N data points for sampling
        recent_data_size = min(lookback_periods, len(historical_data) - 20)
        start_index = len(historical_data) - recent_data_size

        # Sample every few data points to avoid too much computation
        sample_interval = max(1, recent_data_size // 50)  # Aim for ~50 data points

        logger.info(f"Calculating history: {recent_data_size} points, sampling every {sample_interval}")

        # CALCULATE INDICATORS ONLY ONCE for each timeframe
        timeframe_results = {}

        for tf in all_candle_data.keys():
            tf_data = all_candle_data[tf]
            if len(tf_data) >= 20:
                print(f"🔧 HISTORY: Calculating {tf} indicators with {len(tf_data)} candles")

                # Get indicators that match this timeframe
                tf_indicators = [ind for ind in monitor_config.indicators
                                 if getattr(ind, 'time_increment', '1m') == tf]

                if tf_indicators:
                    # Calculate each indicator for this timeframe
                    tf_results = {}

                    for indicator_def in tf_indicators:
                        try:
                            from data_streamer.indicator_processor import IndicatorProcessor
                            processor = IndicatorProcessor(monitor_config)
                            result = processor._calculate_single_indicator(tf_data, indicator_def)

                            if result is not None and isinstance(result, np.ndarray):
                                tf_results[indicator_def.name] = result
                                print(f"🔧 HISTORY: {indicator_def.name} calculated, max value: {np.max(result)}")

                        except Exception as e:
                            logger.error(f"Error calculating history for {indicator_def.name}: {e}")
                            tf_results[indicator_def.name] = np.zeros(len(tf_data))

                    timeframe_results[tf] = tf_results

        # Now sample the results at specific time points
        for i in range(start_index, len(historical_data), sample_interval):
            try:
                # Get timestamp from the main timeframe
                timestamp = historical_data[i].timestamp
                indicator_history['timestamps'].append(timestamp.isoformat())

                # Sample indicator values at this time point
                current_indicators = {}

                for tf, tf_results in timeframe_results.items():
                    tf_data = all_candle_data[tf]

                    # Find the corresponding index in this timeframe
                    tf_index = min(i // (len(historical_data) // len(tf_data)), len(tf_data) - 1)
                    tf_index = max(0, tf_index)

                    for indicator_name, result_array in tf_results.items():
                        if tf_index < len(result_array):
                            # FIXED: Look for recent triggers, not just current value
                            current_value = float(result_array[tf_index])

                            # Look back up to 10 periods for triggers
                            lookback_start = max(0, tf_index - 10)
                            recent_values = result_array[lookback_start:tf_index + 1]

                            # Find most recent trigger
                            trigger_strength = 0.0
                            for j, val in enumerate(reversed(recent_values)):
                                if val > 0:
                                    periods_since = j
                                    # Apply decay: 1.0 - (periods * 0.1)
                                    trigger_strength = max(0.0, 1.0 - (periods_since * 0.1))
                                    break

                            current_indicators[indicator_name] = trigger_strength

                # Store indicator values for this time point
                for indicator_name in indicator_history['indicators'].keys():
                    value = current_indicators.get(indicator_name, 0.0)
                    indicator_history['indicators'][indicator_name].append(value)

                # Calculate bar scores from current indicator values
                current_bars = {}
                if hasattr(monitor_config, 'bars') and monitor_config.bars:
                    for bar_name, bar_weights in monitor_config.bars.items():
                        weighted_sum = 0.0
                        total_weight = 0.0
                        for indicator_name, weight in bar_weights.items():
                            if indicator_name in current_indicators:
                                weighted_sum += current_indicators[indicator_name] * weight
                                total_weight += weight
                        current_bars[bar_name] = weighted_sum / total_weight if total_weight > 0 else 0.0

                # Store bar scores
                for bar_name in indicator_history['bar_scores'].keys():
                    value = current_bars.get(bar_name, 0.0)
                    indicator_history['bar_scores'][bar_name].append(value)

            except Exception as e:
                logger.error(f"Error calculating indicators for history point {i}: {e}")

        indicator_history['periods'] = len(indicator_history['timestamps'])

        # Debug output
        for indicator_name, values in indicator_history['indicators'].items():
            max_val = max(values) if values else 0
            trigger_count = sum(1 for v in values if v > 0.1)
            print(f"🔧 HISTORY RESULT: {indicator_name} - max: {max_val:.3f}, triggers: {trigger_count}")

        logger.info(f"Generated {indicator_history['periods']} history points with trigger awareness")

        return indicator_history

    except Exception as e:
        logger.error(f"Error calculating indicator history: {e}")
        import traceback
        traceback.print_exc()
        return {'timestamps': [], 'indicators': {}, 'bar_scores': {}, 'periods': 0}

