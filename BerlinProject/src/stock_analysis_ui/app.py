#!/usr/bin/env python3
"""
Main Flask application entry point - SIMPLIFIED VERSION with proper type hints
"""

import os
import sys
import logging
from flask import Flask
from flask_socketio import SocketIO

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..'))

from services.schwab_auth import SchwabAuthManager
from services.app_service import AppService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TradingApp')

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global app service
app_service: AppService = None


def authenticate_before_startup() -> bool:
    """Force fresh Schwab authentication before starting the web server"""
    global app_service

    print("\n=== TRADING DASHBOARD AUTHENTICATION ===")
    print("Charles Schwab API authentication required to start the application.")

    # Create auth manager and force fresh authentication
    auth_manager = SchwabAuthManager()
    print("Starting Schwab authentication...")

    if not auth_manager.authenticate():
        print("\nAuthentication failed. Cannot start application.")
        return False

    # Create app service with authenticated manager
    app_service = AppService(socketio, auth_manager)

    # Start streaming infrastructure immediately
    print("Starting streaming infrastructure...")
    if not app_service.start_streaming():
        print("Failed to start streaming infrastructure.")
        return False

    print("\nAuthentication and streaming setup successful! Starting web server...")
    return True


def register_routes() -> None:
    """Register all route blueprints"""
    from routes.dashboard_routes import dashboard_bp
    from routes.api_routes import api_bp
    from routes.file_routes import file_bp
    from routes.websocket_routes import register_websocket_events

    # Register blueprints
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(file_bp, url_prefix='/api/files')

    # Register WebSocket events
    register_websocket_events(socketio, app_service)


def create_app():
    """Create and configure the Flask application"""
    register_routes()

    # Make app_service available to routes with proper typing
    app.app_service = app_service

    # Add type annotation for IDE support (this fixes the yellow underline)
    if not hasattr(app, '__annotations__'):
        app.__annotations__ = {}
    app.__annotations__['app_service'] = AppService

    return app


if __name__ == '__main__':
    # Authenticate before starting the server
    if authenticate_before_startup():
        create_app()
        print("🚀 Starting Trading Dashboard at http://localhost:5050")
        socketio.run(app, debug=False, host='0.0.0.0', port=5050)
    else:
        print("Exiting due to authentication failure.")
        sys.exit(1)