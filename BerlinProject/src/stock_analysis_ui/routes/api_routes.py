# File: BerlinProject/src/stock_analysis_ui/routes/api_routes.py
# FIXED VERSION - No mock data, clean real indicator history

"""
Simplified API routes for AppService
"""
import json
import logging
from datetime import datetime

import numpy as np
from flask import Blueprint, request, jsonify, current_app

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
    """Add a new combination - now handles file content directly"""
    try:
        data = request.json

        symbol = data.get('symbol', '').upper().strip()
        config_content = data.get('config_content', '')
        config_name = data.get('config_name', '')

        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol is required'}), 400

        if not config_content:
            return jsonify({'success': False, 'error': 'Config content is required'}), 400

        # Validate JSON content
        try:
            config_data = json.loads(config_content)
        except json.JSONDecodeError as e:
            return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}'}), 400

        # Create temporary file to work with existing load_monitor_config function
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file.write(config_content)
            temp_config_path = temp_file.name

        try:
            # Load monitor configuration from temporary file
            from models.monitor_configuration import load_monitor_config
            monitor_config = load_monitor_config(temp_config_path)

            if not monitor_config:
                return jsonify({'success': False, 'error': 'Failed to parse monitor configuration'}), 400

            app_service = current_app.app_service
            result = app_service.add_combination(symbol, temp_config_path)

            if result['success']:
                logger.info(f"Successfully added combination: {result['card_id']} with uploaded config: {config_name}")
                return jsonify(result)
            else:
                logger.error(f"Failed to add combination: {result.get('error', 'Unknown error')}")
                return jsonify(result), 400

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_config_path)
            except:
                pass  # Ignore cleanup errors

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

        # Get all candle data
        all_candle_data = data_streamer._get_all_candle_data()

        # Get current indicators
        current_indicators, current_raw, current_bars = data_streamer.indicator_processor.calculate_indicators(
            all_candle_data, None
        )

        # Build debug info
        debug_info = {
            'card_id': card_id,
            'symbol': data_streamer.symbol,
            'timeframes': list(all_candle_data.keys()),
            'candle_counts': {tf: len(candles) for tf, candles in all_candle_data.items()},
            'current_indicators': current_indicators,
            'current_raw': current_raw,
            'current_bars': current_bars,
            'stored_values': data_streamer.indicator_processor.stored_values
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
            all_candle_data, None
        )

        # Get REAL indicator history from processor
        indicator_history = data_streamer.indicator_processor.get_history_data()

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

# Remove the old _get_real_indicator_history function since we're using the processor's method now