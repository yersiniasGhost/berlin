"""
Dashboard routes for the main UI pages
"""

from flask import Blueprint, render_template, current_app

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    """Main dashboard page"""
    app_service = current_app.app_service

    # Get available configuration files
    available_configs = app_service.get_available_configs()

    return render_template('dashboard.html',
                           available_configs=available_configs)


@dashboard_bp.route('/combination/<combination_id>')
def combination_detail(combination_id: str):
    """Detailed view for a specific combination"""
    app_service = current_app.app_service

    # Get combination data
    combination_data = app_service.ui_tool.get_combination_data(combination_id)

    if not combination_data:
        return render_template('error.html',
                               error=f"Combination {combination_id} not found"), 404

    return render_template('combination_detail.html',
                           combination_data=combination_data)