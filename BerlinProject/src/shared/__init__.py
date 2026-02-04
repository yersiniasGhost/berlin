"""
Shared module for common resources across Flask applications.

Provides:
- Static files (CSS, JS) accessible via url_for('shared.static', filename='...')
- Template components accessible via {% include 'shared/components/_xyz.html' %}

Used by:
- stock_analysis_ui (Card Details page)
- visualization_apps (Replay tool)
"""

import os
from flask import Blueprint

# Get the directory where this file is located
SHARED_DIR = os.path.dirname(os.path.abspath(__file__))

# Create blueprint for shared static files
# This allows both apps to access /shared/static/js/...
shared_bp = Blueprint(
    'shared',
    __name__,
    static_folder='static',
    static_url_path='/shared/static'
)


def configure_shared_templates(app):
    """
    Configure Flask app to find shared templates.

    This allows templates to use {% include 'shared/components/_xyz.html' %}
    where templates are actually stored in src/shared/templates/components/

    Args:
        app: Flask application instance
    """
    from jinja2 import ChoiceLoader, FileSystemLoader, PrefixLoader

    # Path to shared templates directory
    shared_templates_dir = os.path.join(SHARED_DIR, 'templates')

    # Create a PrefixLoader that maps 'shared' prefix to the shared templates
    # This allows {% include 'shared/components/_xyz.html' %} to resolve to
    # src/shared/templates/components/_xyz.html
    shared_loader = PrefixLoader({
        'shared': FileSystemLoader(shared_templates_dir)
    })

    # Combine with the app's default loader
    app.jinja_loader = ChoiceLoader([
        app.jinja_loader,  # App's default templates (e.g., stock_analysis_ui/templates)
        shared_loader      # Shared templates with 'shared/' prefix
    ])
