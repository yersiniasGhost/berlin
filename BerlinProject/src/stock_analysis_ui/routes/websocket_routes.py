"""
WebSocket event handlers for real-time communication with session-based routing
"""

from datetime import datetime
from flask import current_app
from flask_socketio import emit, join_room, leave_room
from mlf_utils.log_manager import LogManager
from mlf_utils.timezone_utils import now_utc, isoformat_et

logger = LogManager().get_logger("WebSocketRoutes")


def get_session_from_websocket():
    """Get session info from WebSocket connection"""
    # Get session from the HTTP session that established the WebSocket
    from flask import session
    return session.get('session_id'), session.get('authenticated')


def get_session_app_service(session_id):
    """Get app_service for a specific session"""
    if not session_id:
        return None
    return current_app.session_app_services.get(session_id)


def register_websocket_events(socketio, initial_app_service):
    """Register all WebSocket event handlers with session-based routing"""

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        logger.info('Client connected')

        try:
            # Get session info from WebSocket connection
            session_id, authenticated = get_session_from_websocket()

            if not authenticated or not session_id:
                # Send unauthenticated state
                initial_data = {
                    'combinations': [],
                    'streaming': False,
                    'authenticated': False,
                    'message': 'Connected - authentication required',
                    'timestamp': isoformat_et(now_utc())
                }
                emit('initial_data', initial_data)
                return

            # Join user to their own room for targeted updates
            join_room(f"session_{session_id}")
            logger.info(f"Client joined room: session_{session_id}")

            # Get session-specific app_service
            app_service = get_session_app_service(session_id)
            if not app_service:
                # Session expired
                initial_data = {
                    'combinations': [],
                    'streaming': False,
                    'authenticated': False,
                    'message': 'Session expired - please re-authenticate',
                    'timestamp': isoformat_et(now_utc())
                }
                emit('initial_data', initial_data)
                return

            # Get current combinations for this session
            combinations_data = app_service.get_combinations()
            is_streaming = getattr(app_service, 'is_streaming', False)
            is_authenticated = app_service.auth_manager.is_authenticated() if app_service.auth_manager else True

            # Send session-specific initial data
            initial_data = {
                'combinations': combinations_data.get('combinations', []),
                'streaming': is_streaming,
                'authenticated': is_authenticated,
                'message': 'Connected to your trading dashboard',
                'session_id': session_id,
                'timestamp': isoformat_et(now_utc())
            }

            logger.info(
                f"Sending initial data to session {session_id}: {len(initial_data['combinations'])} combinations, streaming: {is_streaming}")
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
        session_id, _ = get_session_from_websocket()
        if session_id:
            leave_room(f"session_{session_id}")
            logger.info(f"Client disconnected from session: {session_id}")
        else:
            logger.info('Client disconnected')

    @socketio.on('request_combination_data')
    def handle_combination_data_request(data):
        """Handle request for specific combination data"""
        try:
            session_id, authenticated = get_session_from_websocket()

            if not authenticated or not session_id:
                emit('error', {'message': 'Authentication required'})
                return

            app_service = get_session_app_service(session_id)
            if not app_service:
                emit('error', {'message': 'Invalid session'})
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
                logger.debug(f"Sent combination data for {combination_id} to session {session_id}")
            else:
                emit('error', {'message': f'Combination {combination_id} not found'})

        except Exception as e:
            logger.error(f"Error handling combination data request: {e}")
            emit('error', {'message': str(e)})

    @socketio.on('request_all_data')
    def handle_all_data_request():
        """Handle request for all combinations data"""
        try:
            session_id, authenticated = get_session_from_websocket()

            if not authenticated or not session_id:
                emit('error', {'message': 'Authentication required'})
                return

            app_service = get_session_app_service(session_id)
            if not app_service:
                emit('error', {'message': 'Invalid session'})
                return

            if not hasattr(app_service, 'ui_tool'):
                emit('error', {'message': 'UI tool not available'})
                return

            all_data = app_service.ui_tool.get_all_combinations_data()
            emit('all_data_response', all_data)

        except Exception as e:
            logger.error(f"Error handling all data request: {e}")
            emit('error', {'message': str(e)})

    @socketio.on('request_status')
    def handle_status_request():
        """Handle request for current status"""
        try:
            session_id, authenticated = get_session_from_websocket()

            if not authenticated or not session_id:
                emit('status_update', {
                    'streaming': False,
                    'authenticated': False,
                    'combinations': [],
                    'total_combinations': 0
                })
                return

            app_service = get_session_app_service(session_id)
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
                'total_combinations': combinations_data.get('total', 0),
                'session_id': session_id
            }
            emit('status_update', status)

        except Exception as e:
            logger.error(f"Error handling status request: {e}")
            emit('error', {'message': str(e)})

    @socketio.on('debug_client_state')
    def handle_debug_client_state():
        """Handle debug request from client"""
        try:
            session_id, authenticated = get_session_from_websocket()

            if not authenticated or not session_id:
                emit('debug_server_state', {
                    'session_id': 'None',
                    'app_service': 'None',
                    'message': 'Not authenticated'
                })
                return

            app_service = get_session_app_service(session_id)
            if not app_service:
                emit('debug_server_state', {
                    'session_id': session_id,
                    'app_service': 'None',
                    'message': 'Session expired'
                })
                return

            debug_info = {
                'session_id': session_id,
                'server_combinations': list(app_service.combinations.keys()) if hasattr(app_service,
                                                                                        'combinations') else [],
                'streaming_active': getattr(app_service, 'is_streaming', False),
                'ui_tool_available': hasattr(app_service, 'ui_tool'),
                'total_sessions': len(current_app.session_app_services)
            }

            emit('debug_server_state', debug_info)
            logger.info(f"Sent debug info for session {session_id}: {debug_info}")

        except Exception as e:
            logger.error(f"Error handling debug request: {e}")
            emit('error', {'message': str(e)})

    @socketio.on('ping')
    def handle_ping():
        """Handle ping for connection testing"""
        emit('pong', {'message': 'Connection is active'})

    logger.info("WebSocket events registered with session-based routing")