"""
API routes for the trading application with simple ID-based routing
"""

import logging
from datetime import datetime
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
            'total_combinations': combinations['total'],
            'subscribed_symbols': list(getattr(app_service, 'subscribed_symbols', set()))
        })

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/combinations', methods=['POST'])
def add_combination():
    """Add a new symbol + monitor config combination"""
    try:
        data = request.json

        symbol = data.get('symbol', '').upper().strip()
        config_file = data.get('config_file', '').strip()
        card_id = data.get('card_id', '').strip() or None

        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol is required'}), 400

        if not config_file:
            return jsonify({'success': False, 'error': 'Config file is required'}), 400

        app_service = current_app.app_service
        result = app_service.add_combination(symbol, config_file, card_id)

        if result['success']:
            logger.info(f"Successfully added combination: {result['combination_id']}")
            return jsonify(result)
        else:
            logger.error(f"Failed to add combination: {result.get('error', 'Unknown error')}")
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error adding combination: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations/<combination_id>', methods=['DELETE'])
def remove_combination(combination_id: str):
    """Remove a combination by ID"""
    try:
        app_service = current_app.app_service
        result = app_service.remove_combination(combination_id)

        if result['success']:
            logger.info(f"Successfully removed combination: {combination_id}")
            return jsonify(result)
        else:
            logger.error(f"Failed to remove combination {combination_id}: {result.get('error', 'Unknown error')}")
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error removing combination {combination_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations/<combination_id>')
def get_combination(combination_id: str):
    """Get data for a specific combination"""
    try:
        app_service = current_app.app_service
        combination_data = app_service.get_combination_data(combination_id)

        if combination_data:
            return jsonify({
                'success': True,
                'combination_id': combination_id,
                'data': combination_data
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Combination {combination_id} not found'
            }), 404

    except Exception as e:
        logger.error(f"Error getting combination {combination_id}: {e}")
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


@api_bp.route('/debug/process', methods=['POST'])
def debug_process_indicators():
    """Debug endpoint to manually trigger indicator processing for all combinations"""
    try:
        app_service = current_app.app_service

        if not app_service.is_streaming:
            return jsonify({'success': False, 'error': 'Streaming not active'}), 400

        # Use the new debug method from AppService
        result = app_service.debug_process_all_combinations()

        if result['success']:
            logger.info(f"Debug processing completed: {result['processed_count']} combinations processed")
        else:
            logger.error(f"Debug processing failed: {result.get('error', 'Unknown error')}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in debug processing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/debug/live-data', methods=['POST'])
def debug_live_data():
    """Debug endpoint to check live data flow"""
    try:
        app_service = current_app.app_service
        app_service.debug_live_data_flow()

        return jsonify({
            'success': True,
            'message': 'Live data debug info logged to terminal',
            'total_combinations': len(app_service.combinations),
            'streaming_active': app_service.is_streaming
        })

    except Exception as e:
        logger.error(f"Error in live data debug: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/debug/combinations')
def debug_combinations():
    """Debug endpoint to get detailed combination information"""
    try:
        app_service = current_app.app_service

        detailed_combinations = {}
        for combination_id, trading_combination in app_service.combinations.items():
            detailed_combinations[combination_id] = {
                'combination_id': combination_id,
                'symbol': trading_combination.symbol,
                'card_id': trading_combination.card_id,
                'unique_aggregator_key': trading_combination.unique_aggregator_key,
                'timeframes': list(trading_combination.timeframes),
                'monitor_config_name': trading_combination.monitor_config.name,
                'has_data_streamer': trading_combination.data_streamer is not None,
                'has_aggregators': len(trading_combination.aggregators) > 0,
                'aggregator_status': {
                    timeframe: {
                        'history_size': len(aggregator.get_history()),
                        'has_current_candle': aggregator.get_current_candle() is not None,
                        'current_price': aggregator.get_current_candle().close if aggregator.get_current_candle() else 0
                    }
                    for timeframe, aggregator in trading_combination.aggregators.items()
                }
            }

        return jsonify({
            'success': True,
            'total_combinations': len(detailed_combinations),
            'combinations': detailed_combinations,
            'streaming_manager_aggregators': list(app_service.streaming_manager.aggregators.keys()) if app_service.streaming_manager else [],
            'subscribed_symbols': list(getattr(app_service, 'subscribed_symbols', set()))
        })

    except Exception as e:
        logger.error(f"Error in debug combinations: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/debug/master-ui-tool')
def debug_master_ui_tool():
    """Debug endpoint to check MasterUIExternalTool state"""
    try:
        app_service = current_app.app_service

        if not app_service.master_ui_tool:
            return jsonify({'success': False, 'error': 'MasterUIExternalTool not available'})

        master_ui_tool = app_service.master_ui_tool

        debug_info = {
            'total_combinations': len(master_ui_tool.combinations),
            'combination_details': {},
            'active_combinations': list(master_ui_tool.active_combinations)
        }

        # Get details for each combination in MasterUIExternalTool
        for combination_id, combination_data in master_ui_tool.combinations.items():
            debug_info['combination_details'][combination_id] = {
                'symbol': combination_data.combination_info.symbol,
                'monitor_config_name': combination_data.combination_info.monitor_config_name,
                'card_id': combination_data.combination_info.card_id,
                'has_current_data': bool(combination_data.current_data),
                'indicators_count': len(combination_data.indicators),
                'bar_scores_count': len(combination_data.bar_scores),
                'history_size': len(combination_data.history),
                'last_update': combination_data.last_update.isoformat() if combination_data.last_update else None
            }

        return jsonify({
            'success': True,
            'debug_info': debug_info
        })

    except Exception as e:
        logger.error(f"Error in debug master UI tool: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


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


@api_bp.route('/config/validate', methods=['POST'])
def validate_config():
    """Validate a configuration file"""
    try:
        data = request.json
        config_file = data.get('config_file', '').strip()

        if not config_file:
            return jsonify({'success': False, 'error': 'Config file path is required'}), 400

        app_service = current_app.app_service

        # Try to load the config to validate it
        monitor_config = app_service._load_monitor_config(config_file)

        if monitor_config:
            return jsonify({
                'success': True,
                'valid': True,
                'config_name': monitor_config.name,
                'indicators_count': len(monitor_config.indicators),
                'timeframes': list(monitor_config.get_time_increments()),
                'has_bars': hasattr(monitor_config, 'bars') and bool(monitor_config.bars)
            })
        else:
            return jsonify({
                'success': False,
                'valid': False,
                'error': 'Failed to load or parse configuration file'
            })

    except Exception as e:
        logger.error(f"Error validating config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/health')
def health_check():
    """Simple health check endpoint"""
    try:
        app_service = current_app.app_service

        return jsonify({
            'status': 'healthy',
            'streaming': app_service.is_streaming,
            'authenticated': app_service.auth_manager.is_authenticated() if app_service.auth_manager else False,
            'total_combinations': len(app_service.combinations),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500