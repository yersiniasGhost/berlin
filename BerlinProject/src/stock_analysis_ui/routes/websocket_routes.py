"""
WebSocket event handlers for real-time communication
"""

import logging
from flask_socketio import emit

logger = logging.getLogger('WebSocketRoutes')


def register_websocket_events(socketio, app_service):
    """Register all WebSocket event handlers"""

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        logger.info('Client connected')

        # Send current status to newly connected client
        try:
            # Get current combinations
            combinations_data = app_service.get_combinations() if hasattr(app_service, 'get_combinations') else {'combinations': [], 'total': 0}

            # Get streaming status - check multiple attributes
            is_streaming = False
            if hasattr(app_service, 'is_streaming'):
                is_streaming = app_service.is_streaming
            elif hasattr(app_service, 'streaming_manager') and app_service.streaming_manager:
                is_streaming = True

            # Get authentication status
            is_authenticated = True
            if hasattr(app_service, 'auth_manager') and app_service.auth_manager:
                is_authenticated = app_service.auth_manager.is_authenticated()

            # Send initial data
            initial_data = {
                'combinations': combinations_data.get('combinations', []),
                'streaming': is_streaming,
                'authenticated': is_authenticated,
                'message': 'Connected to trading dashboard'
            }

            logger.info(f"Sending initial data: {len(initial_data['combinations'])} combinations, streaming: {is_streaming}")

            emit('initial_data', initial_data)

            # Send individual combination data for each existing combination
            if hasattr(app_service, 'ui_tool') and app_service.ui_tool:
                for combo in initial_data['combinations']:
                    combination_id = combo.get('combination_id')
                    if combination_id:
                        try:
                            combo_data = app_service.ui_tool.get_combination_data(combination_id)
                            if combo_data:
                                emit('combination_data_response', {
                                    'combination_id': combination_id,
                                    'data': combo_data
                                })
                                logger.info(f"Sent data for existing combination: {combination_id}")
                        except Exception as e:
                            logger.error(f"Error sending data for combination {combination_id}: {e}")

        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
            import traceback
            traceback.print_exc()

            # Send minimal data on error
            emit('initial_data', {
                'combinations': [],
                'streaming': False,
                'authenticated': True,
                'message': 'Connected (error loading data)'
            })

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        logger.info('Client disconnected')

    @socketio.on('request_combination_data')
    def handle_combination_data_request(data):
        """Handle request for specific combination data"""
        try:
            combination_id = data.get('combination_id')
            if not combination_id:
                emit('error', {'message': 'combination_id is required'})
                return

            if not hasattr(app_service, 'ui_tool'):
                emit('error', {'message': 'UI tool not available'})
                return

            combination_data = app_service.ui_tool.get_combination_data(combination_id)

            if combination_data:
                emit('combination_data_response', {
                    'combination_id': combination_id,
                    'data': combination_data
                })
                logger.debug(f"Sent combination data for {combination_id}")
            else:
                emit('error', {'message': f'Combination {combination_id} not found'})

        except Exception as e:
            logger.error(f"Error handling combination data request: {e}")
            emit('error', {'message': str(e)})

    @socketio.on('request_all_data')
    def handle_all_data_request():
        """Handle request for all combinations data"""
        try:
            if not hasattr(app_service, 'ui_tool'):
                emit('error', {'message': 'UI tool not available'})
                return

            all_data = app_service.ui_tool.get_all_combinations_data()
            emit('all_data_response', all_data)

        except Exception as e:
            logger.error(f"Error handling all data request: {e}")
            emit('error', {'message': str(e)})

    @socketio.on('ping')
    def handle_ping():
        """Handle ping for connection testing"""
        emit('pong', {'message': 'Connection is active'})

    @socketio.on('request_status')
    def handle_status_request():
        """Handle request for current status"""
        try:
            combinations_data = app_service.get_combinations()
            status = {
                'streaming': app_service.is_streaming if hasattr(app_service, 'is_streaming') else False,
                'authenticated': app_service.auth_manager.is_authenticated() if app_service.auth_manager else True,
                'combinations': combinations_data.get('combinations', []),
                'total_combinations': combinations_data.get('total', 0)
            }
            emit('status_update', status)

        except Exception as e:
            logger.error(f"Error handling status request: {e}")
            emit('error', {'message': str(e)})

    logger.info("WebSocket events registered")