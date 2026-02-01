"""
Shared module for common resources across Flask applications.
Provides shared static files (JavaScript, CSS) that can be used by
visualization_apps and stock_analysis_ui.
"""

from flask import Blueprint
import os

# Create blueprint for shared static files
# This allows both apps to access /shared/static/js/...
shared_bp = Blueprint(
    'shared',
    __name__,
    static_folder='static',
    static_url_path='/shared/static'
)
