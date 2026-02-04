"""
Dashboard routes for the main UI pages
"""

import uuid
from datetime import datetime
from flask import Blueprint, render_template, current_app, redirect, session
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("DashboardRoutes")

dashboard_bp = Blueprint('dashboard', __name__)


def get_session_app_service():
    """Get the app_service for the current session"""
    session_id = session.get('session_id')
    if not session_id:
        return None

    return current_app.session_app_services.get(session_id)


def initialize_replay_session(replay_config):
    """Initialize a replay session with the given configuration"""
    from services.app_service import AppService

    session_id = str(uuid.uuid4())
    session['session_id'] = session_id
    session['authenticated'] = True

    # Create app service without auth manager (replay mode)
    app_service = AppService(current_app.socketio, auth_manager=None)

    source_type = replay_config.get('source_type')
    playback_speed = replay_config.get('playback_speed', 1.0)

    if source_type == 'pip':
        # Use existing CSReplayDataLink
        from data_streamer.cs_replay_data_link import CSReplayDataLink

        pip_file = replay_config.get('pip_file')
        ticker = replay_config.get('ticker', 'UNKNOWN')

        cs_replay_link = CSReplayDataLink(playback_speed=playback_speed)

        if not cs_replay_link.add_symbol_file(ticker, pip_file):
            logger.error(f"Failed to load PIP data for {ticker}")
            return None

        app_service.data_link = cs_replay_link
        logger.info(f"Initialized PIP replay: {ticker} from {pip_file}")

    elif source_type == 'mongodb':
        # Use new MongoReplayDataLink
        from data_streamer.mongo_replay_data_link import MongoReplayDataLink

        ticker = replay_config.get('ticker')
        date_str = replay_config.get('date')
        replay_date = datetime.strptime(date_str, '%Y-%m-%d')

        mongo_replay_link = MongoReplayDataLink(playback_speed=playback_speed)

        if not mongo_replay_link.load_data(ticker, replay_date):
            logger.error(f"Failed to load MongoDB data for {ticker} on {date_str}")
            return None

        # Set up callbacks for WebSocket events
        # IMPORTANT: Capture socketio reference now since callbacks run in background thread
        # where current_app context is not available
        socketio = current_app.socketio
        room = f"session_{session_id}"

        def on_progress(current, total, progress):
            try:
                socketio.emit('replay_progress', {
                    'current': current,
                    'total': total,
                    'progress': progress
                }, room=room)
            except Exception as e:
                logger.error(f"Error emitting replay_progress: {e}")

        def on_complete():
            try:
                socketio.emit('replay_complete', room=room)
            except Exception as e:
                logger.error(f"Error emitting replay_complete: {e}")

        mongo_replay_link.on_tick_processed = on_progress
        mongo_replay_link.on_replay_complete = on_complete

        app_service.data_link = mongo_replay_link
        logger.info(f"Initialized MongoDB replay: {ticker} on {date_str}")

    else:
        logger.error(f"Unknown replay source type: {source_type}")
        return None

    # Register app service for this session
    current_app.session_app_services[session_id] = app_service

    # Add the trading card with the monitor config
    monitor_config = replay_config.get('monitor_config')
    ticker = replay_config.get('ticker')

    if monitor_config and ticker:
        result = app_service.add_combination(ticker, monitor_config)
        if result.get('success'):
            logger.info(f"Added trading card: {result.get('card_id')} for {ticker}")
        else:
            logger.error(f"Failed to add trading card: {result.get('error')}")

    # Start streaming
    if not app_service.start_streaming():
        logger.error("Failed to start replay streaming")
        return None

    logger.info(f"Replay session initialized: {session_id}")
    return session_id


@dashboard_bp.route('/')
def home():
    """Home page - always show this first"""
    return render_template('home.html')


@dashboard_bp.route('/dashboard')
def dashboard():
    """Main dashboard page - requires session-based authentication"""
    # Check if this is a new replay session
    replay_config = session.get('replay_config')
    is_replay_mode = session.get('replay_mode', False)

    if is_replay_mode and replay_config and not session.get('session_id'):
        # Initialize new replay session
        session_id = initialize_replay_session(replay_config)
        if not session_id:
            # Failed to initialize replay
            session.clear()
            return redirect('/replay?error=initialization_failed')

    # Check if we're in replay mode with a global app_service (CLI mode)
    global_app_service = current_app.app_service

    # If in CLI replay mode (global app_service exists) and no session, create one
    if global_app_service is not None and (not session.get('authenticated') or not session.get('session_id')):
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        session['authenticated'] = True

        # Register the global app_service for this session
        current_app.session_app_services[session_id] = global_app_service
        logger.info(f"CLI Replay mode: Auto-created session {session_id}")

    # Check if user has valid session
    if not session.get('authenticated') or not session.get('session_id'):
        return redirect('/')

    # Get session-specific app_service
    app_service = get_session_app_service()
    if not app_service:
        # Session expired or invalid
        session.clear()
        return redirect('/')

    # Check if auth manager exists and is authenticated
    if app_service.auth_manager and not app_service.auth_manager.is_authenticated():
        return redirect('/')

    # Get available configuration files
    available_configs = app_service.get_available_configs()

    return render_template('dashboard.html',
                           available_configs=available_configs,
                           session_id=session.get('session_id'))


@dashboard_bp.route('/combination/<combination_id>')
def combination_detail(combination_id: str):
    """Detailed view for a specific combination"""
    # Same session-based authentication check
    if not session.get('authenticated') or not session.get('session_id'):
        return redirect('/')

    app_service = get_session_app_service()
    if not app_service:
        session.clear()
        return redirect('/')

    if app_service.auth_manager and not app_service.auth_manager.is_authenticated():
        return redirect('/')

    # Get combination data
    combination_data = app_service.ui_tool.get_combination_data(combination_id)

    if not combination_data:
        return render_template('error.html',
                               error=f"Combination {combination_id} not found"), 404

    return render_template('combination_detail.html',
                           combination_data=combination_data)


@dashboard_bp.route('/card-details.html')
def card_details():
    """Serve the card details page"""
    # Check if we're in replay mode with a global app_service
    global_app_service = current_app.app_service

    # If in replay mode (global app_service exists) and no session, create one
    if global_app_service is not None and (not session.get('authenticated') or not session.get('session_id')):
        import uuid
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        session['authenticated'] = True

        # Register the global app_service for this session
        current_app.session_app_services[session_id] = global_app_service
        logger.info(f"Replay mode: Auto-created session {session_id} for card details")

    # Same session-based authentication check
    if not session.get('authenticated') or not session.get('session_id'):
        return redirect('/')

    app_service = get_session_app_service()
    if not app_service:
        session.clear()
        return redirect('/')

    if app_service.auth_manager and not app_service.auth_manager.is_authenticated():
        return redirect('/')

    return render_template('card_details.html')


@dashboard_bp.route('/logout')
def logout():
    """Logout and cleanup session"""
    session_id = session.get('session_id')
    if session_id and session_id in current_app.session_app_services:
        # Cleanup the app_service
        app_service = current_app.session_app_services[session_id]
        try:
            app_service.cleanup()
        except:
            pass
        del current_app.session_app_services[session_id]

    session.clear()
    return redirect('/')