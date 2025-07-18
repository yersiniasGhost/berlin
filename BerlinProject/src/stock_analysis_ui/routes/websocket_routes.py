# Update your websocket_routes.py file

"""
WebSocket event handlers for real-time communication with simple ID routing
"""

import logging
from datetime import datetime
from flask import current_app
from flask_socketio import emit

logger = logging.getLogger('WebSocketRoutes')


def register_websocket_events(socketio, initial_app_service):
    """Register all WebSocket event handlers"""

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        logger.info('Client connected')

        # Send current status to newly connected client
        try:
            # Get app_service from current_app instead of closure variable
            app_service = current_app.app_service

            # Handle case where app_service might be None initially
            if app_service is None:
                # Send minimal initial data for unauthenticated state
                initial_data = {
                    'combinations': [],
                    'streaming': False,
                    'authenticated': False,
                    'message': 'Connected - authentication required',
                    'timestamp': datetime.now().isoformat()
                }
                emit('initial_data', initial_data)
                return

            # Get current combinations
            combinations_data = app_service.get_combinations() if hasattr(app_service, 'get_combinations') else {'combinations': [], 'total': 0}

            # Get streaming status
            is_streaming = getattr(app_service, 'is_streaming', False)

            # Get authentication status
            is_authenticated = True
            if hasattr(app_service, 'auth_manager') and app_service.auth_manager:
                is_authenticated = app_service.auth_manager.is_authenticated()

            # Send initial data
            initial_data = {
                'combinations': combinations_data.get('combinations', []),
                'streaming': is_streaming,
                'authenticated': is_authenticated,
                'message': 'Connected to trading dashboard',
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Sending initial data: {len(initial_data['combinations'])} combinations, streaming: {is_streaming}")

            emit('initial_data', initial_data)

        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
            import traceback
            traceback.print_exc()

            # Send minimal data on error
            emit('initial_data', {
                'combinations': [],
                'streaming': False,
                'authenticated': False,
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
            # Get app_service from current_app
            app_service = current_app.app_service
            if not app_service:
                emit('error', {'message': 'App service not available'})
                return

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
            # Get app_service from current_app
            app_service = current_app.app_service
            if not app_service:
                emit('error', {'message': 'App service not available'})
                return

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
            # Get app_service from current_app
            app_service = current_app.app_service
            if not app_service:
                emit('status_update', {
                    'streaming': False,
                    'authenticated': False,
                    'combinations': [],
                    'total_combinations': 0
                })
                return

            combinations_data = app_service.get_combinations()
            status = {
                'streaming': getattr(app_service, 'is_streaming', False),
                'authenticated': app_service.auth_manager.is_authenticated() if app_service.auth_manager else True,
                'combinations': combinations_data.get('combinations', []),
                'total_combinations': combinations_data.get('total', 0)
            }
            emit('status_update', status)

        except Exception as e:
            logger.error(f"Error handling status request: {e}")
            emit('error', {'message': str(e)})

    @socketio.on('debug_client_state')
    def handle_debug_client_state():
        """Handle debug request from client"""
        try:
            # Get app_service from current_app
            app_service = current_app.app_service
            if not app_service:
                emit('debug_server_state', {
                    'app_service': 'None',
                    'message': 'App service not initialized'
                })
                return

            debug_info = {
                'server_combinations': list(app_service.combinations.keys()) if hasattr(app_service, 'combinations') else [],
                'streaming_active': getattr(app_service, 'is_streaming', False),
                'ui_tool_available': hasattr(app_service, 'ui_tool')
            }

            emit('debug_server_state', debug_info)
            logger.info(f"Sent debug info: {debug_info}")

        except Exception as e:
            logger.error(f"Error handling debug request: {e}")
            emit('error', {'message': str(e)})

    logger.info("WebSocket events registered with dynamic app_service resolution")