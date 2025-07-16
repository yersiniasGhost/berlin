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