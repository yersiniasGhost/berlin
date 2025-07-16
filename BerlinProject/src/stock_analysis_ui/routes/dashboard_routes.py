"""
Dashboard routes for the main UI pages
"""

import logging
from flask import Blueprint, render_template, current_app, redirect, session

logger = logging.getLogger('DashboardRoutes')

dashboard_bp = Blueprint('dashboard', __name__)


def get_session_app_service():
    """Get the app_service for the current session"""
    session_id = session.get('session_id')
    if not session_id:
        return None

    return current_app.session_app_services.get(session_id)


@dashboard_bp.route('/')
def home():
    """Home page - always show this first"""
    return render_template('home.html')


@dashboard_bp.route('/dashboard')
def dashboard():
    """Main dashboard page - requires session-based authentication"""
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


@dashboard_bp.route('/monitor-creation')
def monitor_creation():
    """Monitor creation page - requires session-based authentication"""
    # [existing auth code...]

    # Define available indicator functions with their parameter schemas
    available_indicators = {
        'sma_crossover': {
            'name': 'SMA Crossover',
            'parameters': {
                'period': {'type': 'number', 'default': 20, 'min': 1, 'max': 200},
                'trend': {'type': 'select', 'options': ['bullish', 'bearish'], 'default': 'bullish'},
                'crossover_value': {'type': 'number', 'default': 0.001, 'min': 0, 'max': 1, 'step': 0.0001},
                'lookback': {'type': 'number', 'default': 10, 'min': 1, 'max': 100}
            }
        },
        'macd_histogram_crossover': {
            'name': 'MACD Histogram Crossover',
            'parameters': {
                'slow': {'type': 'number', 'default': 26, 'min': 1, 'max': 100},
                'fast': {'type': 'number', 'default': 12, 'min': 1, 'max': 100},
                'signal': {'type': 'number', 'default': 9, 'min': 1, 'max': 50},
                'histogram_threshold': {'type': 'number', 'default': 0.001, 'min': 0, 'max': 1, 'step': 0.0001},
                'lookback': {'type': 'number', 'default': 10, 'min': 1, 'max': 100},
                'trend': {'type': 'select', 'options': ['bullish', 'bearish'], 'default': 'bullish'}
            }
        },
        'bol_bands_lower_band_bounce': {
            'name': 'Bollinger Bands Lower Band Bounce',
            'parameters': {
                'period': {'type': 'number', 'default': 20, 'min': 1, 'max': 100},
                'sd': {'type': 'number', 'default': 2.0, 'min': 0.1, 'max': 5.0, 'step': 0.1},
                'candle_bounce_number': {'type': 'number', 'default': 1, 'min': 1, 'max': 10},
                'bounce_trigger': {'type': 'number', 'default': 0.05, 'min': 0, 'max': 1, 'step': 0.01},
                'lookback': {'type': 'number', 'default': 10, 'min': 1, 'max': 100},
                'trend': {'type': 'select', 'options': ['bullish', 'bearish'], 'default': 'bullish'}
            }
        }
    }

    # Available aggregation configs
    aggregation_configs = [
        {'value': '1m-normal', 'label': '1m Normal'},
        {'value': '1m-Heiken', 'label': '1m Heiken Ashi'},
        {'value': '5m-normal', 'label': '5m Normal'},
        {'value': '5m-Heiken', 'label': '5m Heiken Ashi'},
        {'value': '15m-normal', 'label': '15m Normal'},
        {'value': '15m-Heiken', 'label': '15m Heiken Ashi'},
        {'value': '30m-normal', 'label': '30m Normal'},
        {'value': '30m-Heiken', 'label': '30m Heiken Ashi'},
        {'value': '1h-normal', 'label': '1h Normal'},
        {'value': '1h-Heiken', 'label': '1h Heiken Ashi'}
    ]

    return render_template('monitor_creation.html',
                           available_indicators=available_indicators,
                           aggregation_configs=aggregation_configs,
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