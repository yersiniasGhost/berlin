import os
import sys
import logging
import argparse
import uuid
from flask import Flask
from flask_socketio import SocketIO

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..'))

from services.schwab_auth import SchwabAuthManager
from services.app_service import AppService
from data_streamer.cs_replay_data_link import CSReplayDataLink

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TradingApp')

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# CHANGED: Session-based app services instead of global
session_app_services = {}  # session_id -> app_service
app_service = None  # Keep for replay mode compatibility


def parse_symbol_files(symbol_file_args):
    """Parse symbol:file pairs from command line arguments"""
    symbol_files = {}

    for arg in symbol_file_args:
        if ':' not in arg:
            logger.error(f"Invalid format: {arg}. Use SYMBOL:filepath format")
            continue

        symbol, file_path = arg.split(':', 1)
        symbol = symbol.upper().strip()
        file_path = file_path.strip()

        if not symbol or not file_path:
            logger.error(f"Empty symbol or file path in: {arg}")
            continue

        symbol_files[symbol] = file_path

    return symbol_files


def validate_files(file_paths):
    """Validate that all files exist and are readable"""
    if isinstance(file_paths, dict):
        # Multiple files case
        for symbol, file_path in file_paths.items():
            if not os.path.exists(file_path):
                logger.error(f"File not found for {symbol}: {file_path}")
                return False
            logger.info(f"✓ {symbol}: {file_path}")
    else:
        # Single file case
        if not os.path.exists(file_paths):
            logger.error(f"File not found: {file_paths}")
            return False
        logger.info(f"✓ File: {file_paths}")

    return True


def setup_cs_replay_mode_single(file_path: str, symbol: str, speed: float = 1.0) -> bool:
    """Set up CS Replay mode with single symbol file"""
    global app_service

    print(f"\n=== CS REPLAY MODE (Single Symbol) ===")
    print(f"File: {file_path}")
    print(f"Symbol: {symbol}")
    print(f"Speed: {speed}x")

    if not validate_files(file_path):
        return False

    # Create app service without auth manager (replay mode)
    app_service = AppService(socketio, auth_manager=None)

    # Create CSReplayDataLink
    cs_replay_link = CSReplayDataLink(playback_speed=speed)

    # Load the symbol file
    if not cs_replay_link.add_symbol_file(symbol, file_path):
        logger.error(f"Failed to load data for {symbol}")
        return False

    # Set data_link on app_service BEFORE calling start_streaming
    app_service.data_link = cs_replay_link

    # Start streaming
    if not app_service.start_streaming():
        logger.error("Failed to start streaming")
        return False

    print("✅ CS Replay mode setup successful!")
    return True


def setup_cs_replay_mode_multi(symbol_files: dict, speed: float = 1.0) -> bool:
    """Set up CS Replay mode with multiple symbol files"""
    global app_service

    print(f"\n=== CS REPLAY MODE (Multi Symbol) ===")
    print(f"Speed: {speed}x")
    print("Symbol Files:")
    for symbol, file_path in symbol_files.items():
        print(f"  {symbol}: {file_path}")

    if not validate_files(symbol_files):
        return False

    # Create app service without auth manager (replay mode)
    app_service = AppService(socketio, auth_manager=None)

    # Create CSReplayDataLink
    cs_replay_link = CSReplayDataLink(playback_speed=speed)

    # Load each symbol file
    for symbol, file_path in symbol_files.items():
        if not cs_replay_link.add_symbol_file(symbol, file_path):
            logger.error(f"Failed to load data for {symbol}")
            return False

    # Set data_link on app_service
    app_service.data_link = cs_replay_link

    # Start streaming
    if not app_service.start_streaming():
        logger.error("Failed to start streaming")
        return False

    print("✅ CS Replay mode setup successful!")
    return True


def authenticate_before_startup() -> bool:
    """Force fresh Schwab authentication for live mode (unchanged from original)"""
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


def add_cards_from_args(args) -> None:
    """Add trading cards based on command line arguments"""
    if not args.config:
        logger.info("No configs specified - cards can be added via web interface")
        return

    # Determine symbols based on mode
    symbols = []
    if args.replay_file and args.symbol:
        # Single symbol mode
        symbols = [args.symbol.upper()]
    elif args.replay_files:
        # Multi symbol mode
        symbol_files = parse_symbol_files(args.replay_files)
        symbols = list(symbol_files.keys())
    else:
        logger.info("No symbols specified - cards can be added via web interface")
        return

    configs = args.config if isinstance(args.config, list) else [args.config]

    print(f"\nAdding Trading Cards:")

    # Handle config assignment
    if len(configs) == 1:
        # One config for all symbols
        config_file = configs[0]
        for symbol in symbols:
            result = app_service.add_combination(symbol, config_file)
            if result['success']:
                print(f"✓ Added card: {result['card_id']} ({symbol})")
            else:
                print(f"✗ Failed to add {symbol}: {result['error']}")

    elif len(symbols) == len(configs):
        # One-to-one mapping
        for symbol, config_file in zip(symbols, configs):
            result = app_service.add_combination(symbol, config_file)
            if result['success']:
                print(f"✓ Added card: {result['card_id']} ({symbol})")
            else:
                print(f"✗ Failed to add {symbol}: {result['error']}")

    else:
        logger.error(f"Mismatch: {len(symbols)} symbols but {len(configs)} configs")
        logger.error("Provide either 1 config for all symbols, or 1 config per symbol")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Trading Dashboard - Live Schwab or CS Replay Mode',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Live mode (original - unchanged)
  python app.py

  # CS Replay mode - single symbol
  python app.py --replay-file pltr_pips.txt --symbol PLTR --config monitor_config.json

  # CS Replay mode - multiple symbols
  python app.py --replay-files PLTR:pltr_pips.txt NVDA:nvda_pips.txt --config config.json

  # CS Replay with custom speed
  python app.py --replay-file pltr_pips.txt --symbol PLTR --speed 2.0 --config config.json
        '''
    )

    # CS Replay arguments
    parser.add_argument(
        '--replay-file',
        help='Path to single PIP data file for replay mode'
    )

    parser.add_argument(
        '--symbol',
        help='Symbol for single file replay mode (e.g., PLTR)'
    )

    parser.add_argument(
        '--replay-files',
        nargs='+',
        help='Multiple symbol:file pairs (e.g., PLTR:pltr_pips.txt NVDA:nvda_pips.txt)'
    )

    parser.add_argument(
        '--speed', '-s',
        type=float,
        default=1.0,
        help='Playback speed multiplier (default: 1.0 = real-time)'
    )

    parser.add_argument(
        '--config',
        nargs='+',
        help='Path(s) to monitor configuration JSON file(s)'
    )

    # Server arguments
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=5050,
        help='Port to run the web server on (default: 5050)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind the web server to (default: 0.0.0.0)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    return parser.parse_args()


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

    # Store socketio reference on app for routes to access
    app.socketio = socketio

    # Store session manager on app
    app.session_app_services = session_app_services

    # Make app_service available to routes (might be None for live mode)
    app.app_service = app_service

    return app


# Update the main execution block
if __name__ == '__main__':
    # Parse command line arguments
    args = parse_arguments()

    # Determine mode and setup accordingly
    if args.replay_file and args.symbol:
        # Single symbol CS Replay mode - use global app_service
        if not setup_cs_replay_mode_single(args.replay_file, args.symbol.upper(), args.speed):
            print("Failed to set up CS Replay mode.")
            sys.exit(1)

    elif args.replay_files:
        # Multi symbol CS Replay mode - use global app_service
        symbol_files = parse_symbol_files(args.replay_files)
        if not symbol_files:
            print("No valid symbol:file pairs provided.")
            sys.exit(1)

        if not setup_cs_replay_mode_multi(symbol_files, args.speed):
            print("Failed to set up CS Replay mode.")
            sys.exit(1)

    else:
        # Live mode - NO AUTOMATIC AUTHENTICATION
        # Authentication will happen through the UI per session
        print("Live mode - authentication will be handled through web interface")
        app_service = None

    # Add cards from command line arguments (only if app_service exists)
    if app_service is not None:
        add_cards_from_args(args)

    # Create Flask app
    create_app()

    # Determine mode for display
    if args.replay_file or args.replay_files:
        mode = "CS Replay"
        if args.replay_files:
            symbol_files = parse_symbol_files(args.replay_files)
            mode += f" ({len(symbol_files)} symbols)"
        else:
            mode += f" ({args.symbol})"
        mode += f" @ {args.speed}x speed"
    else:
        mode = "Live Schwab (Session-based Authentication)"

    print(f"\n🚀 Starting Trading Dashboard at http://localhost:{args.port}")
    print(f"Mode: {mode}")
    if app_service is None:
        print("🔐 Each browser session will authenticate separately")

    socketio.run(app, debug=args.debug, host=args.host, port=args.port)

