# Update your dashboard_routes.py file

"""
Dashboard routes for the main UI pages
"""

from flask import Blueprint, render_template, current_app, redirect

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def home():
    """Home page - always show this first"""
    return render_template('home.html')


@dashboard_bp.route('/dashboard')
def dashboard():
    """Main dashboard page - requires authentication"""
    # Check if app_service is available and authenticated
    if not hasattr(current_app, 'app_service') or current_app.app_service is None:
        # Redirect back to home if not authenticated
        return redirect('/')

    app_service = current_app.app_service

    # Check if auth manager exists and is authenticated
    if app_service.auth_manager and not app_service.auth_manager.is_authenticated():
        return redirect('/')

    # Get available configuration files
    available_configs = app_service.get_available_configs()

    return render_template('dashboard.html',
                           available_configs=available_configs)


@dashboard_bp.route('/combination/<combination_id>')
def combination_detail(combination_id: str):
    """Detailed view for a specific combination"""
    # Same authentication check
    if not hasattr(current_app, 'app_service') or current_app.app_service is None:
        return redirect('/')

    app_service = current_app.app_service

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
    # Same authentication check
    if not hasattr(current_app, 'app_service') or current_app.app_service is None:
        return redirect('/')

    app_service = current_app.app_service

    if app_service.auth_manager and not app_service.auth_manager.is_authenticated():
        return redirect('/')

    return render_template('card_details.html')