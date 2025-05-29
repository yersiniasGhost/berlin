"""
API routes for the trading application with simple ID routing
"""

import logging
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
            logger.warning(f"Failed to add combination: {result['error']}")
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error adding combination: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations/<combination_id>', methods=['DELETE'])
def remove_combination(combination_id: str):
    """Remove a combination"""
    try:
        app_service = current_app.app_service
        result = app_service.remove_combination(combination_id)

        if result['success']:
            logger.info(f"Successfully removed combination: {combination_id}")
            return jsonify(result)
        else:
            logger.warning(f"Failed to remove combination: {result['error']}")
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error removing combination: {e}")
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


@api_bp.route('/combinations/<combination_id>')
def get_combination_data(combination_id: str):
    """Get data for a specific combination"""
    try:
        app_service = current_app.app_service

        if not hasattr(app_service, 'master_ui_tool'):
            return jsonify({'error': 'UI tool not available'}), 500

        combination_data = app_service.master_ui_tool.get_combination_data(combination_id)

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
        logger.error(f"Error getting combination data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/streaming/start', methods=['POST'])
def start_streaming():
    """Start streaming infrastructure"""
    try:
        app_service = current_app.app_service

        if app_service.start_streaming():
            return jsonify({'success': True, 'message': 'Streaming started'})
        else:
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
            return jsonify({'success': True, 'message': 'Streaming stopped'})
        else:
            return jsonify({'success': False, 'error': 'Failed to stop streaming'}), 500

    except Exception as e:
        logger.error(f"Error stopping streaming: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/debug/process', methods=['POST'])
def debug_process_indicators():
    """Debug endpoint to manually trigger indicator processing"""
    try:
        app_service = current_app.app_service

        if not app_service.is_streaming:
            return jsonify({'success': False, 'error': 'Streaming not active'}), 400

        processed_count = 0
        results = []

        logger.info(f"=== DEBUG PROCESS: Processing {len(app_service.combinations)} combinations ===")

        # Process each combination using its unique aggregators
        for combination_id, combination in app_service.combinations.items():
            symbol = combination.get_symbol()
            unique_key = combination.get_unique_aggregator_key()

            logger.info(f"DEBUG: Processing combination {combination_id} ({symbol}) with key {unique_key}")

            # Get aggregators for this combination
            if unique_key in app_service.streaming_manager.aggregators:
                aggregators = app_service.streaming_manager.aggregators[unique_key]

                # Log aggregator status
                for timeframe, aggregator in aggregators.items():
                    current_candle = aggregator.get_current_candle()
                    if current_candle:
                        logger.info(f"DEBUG: {timeframe} current candle: ${current_candle.close:.2f}")
                    else:
                        logger.info(f"DEBUG: {timeframe} no current candle")

                # Process indicators
                logger.info(f"DEBUG: Processing indicators for {combination_id}")
                try:
                    combination.process_indicators(aggregators)
                    processed_count += 1

                    results.append({
                        'combination_id': combination_id,
                        'symbol': symbol,
                        'unique_key': unique_key,
                        'processed': True
                    })
                except Exception as proc_error:
                    logger.error(f"DEBUG: Error processing {combination_id}: {proc_error}")
                    results.append({
                        'combination_id': combination_id,
                        'symbol': symbol,
                        'unique_key': unique_key,
                        'processed': False,
                        'error': str(proc_error)
                    })
            else:
                logger.warning(f"DEBUG: No aggregators found for {combination_id} (key: {unique_key})")
                results.append({
                    'combination_id': combination_id,
                    'symbol': symbol,
                    'unique_key': unique_key,
                    'processed': False,
                    'error': 'No aggregators found'
                })

        logger.info(f"=== DEBUG PROCESS COMPLETE: {processed_count} processed ===")

        return jsonify({
            'success': True,
            'processed_count': processed_count,
            'total_combinations': len(app_service.combinations),
            'results': results
        })

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