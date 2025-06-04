# File: BerlinProject/src/stock_analysis_ui/routes/api_routes.py
# FIXED VERSION for simplified architecture

"""
Simplified API routes for AppService
"""

import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app

from data_streamer.indicator_processor import IndicatorProcessor

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
    Calculate a simple indicator history using available candle data
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

        # Create a simple processor for history calculation
        processor = IndicatorProcessor(monitor_config)

        # Take the last N data points for sampling
        recent_data_size = min(lookback_periods, len(historical_data) - 20)
        start_index = len(historical_data) - recent_data_size

        # Sample every few data points to avoid too much computation
        sample_interval = max(1, recent_data_size // 50)  # Aim for ~50 data points

        logger.info(f"Calculating history: {recent_data_size} points, sampling every {sample_interval}")

        for i in range(start_index, len(historical_data), sample_interval):
            # Create a data slice up to this point for each timeframe
            data_slice = {}
            for tf, tf_data in all_candle_data.items():
                # Get proportional slice for this timeframe
                tf_index = min(i, len(tf_data) - 1)
                data_slice[tf] = tf_data[:tf_index + 1]

            if any(len(tf_data) >= 20 for tf_data in data_slice.values()):
                try:
                    # Calculate indicators for this point in time
                    indicators, raw_indicators, bar_scores = processor.calculate_indicators(data_slice, None)

                    # Store timestamp
                    timestamp = historical_data[i].timestamp
                    indicator_history['timestamps'].append(timestamp.isoformat())

                    # Store indicator values
                    for indicator_name in indicator_history['indicators'].keys():
                        value = indicators.get(indicator_name, 0.0)
                        indicator_history['indicators'][indicator_name].append(value)

                    # Store bar scores
                    for bar_name in indicator_history['bar_scores'].keys():
                        value = bar_scores.get(bar_name, 0.0)
                        indicator_history['bar_scores'][bar_name].append(value)

                except Exception as e:
                    logger.error(f"Error calculating indicators for history point {i}: {e}")

        indicator_history['periods'] = len(indicator_history['timestamps'])
        logger.info(f"Generated {indicator_history['periods']} history points")

        return indicator_history

    except Exception as e:
        logger.error(f"Error calculating indicator history: {e}")
        return {'timestamps': [], 'indicators': {}, 'bar_scores': {}, 'periods': 0}