"""
Replay Routes for Stock Analysis UI
Handles replay mode setup, configuration, and control APIs
"""

import os
import re
from pathlib import Path
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app, session, redirect

from mlf_utils.log_manager import LogManager
from mlf_utils.env_vars import EnvVars

logger = LogManager().get_logger("ReplayRoutes")

replay_bp = Blueprint('replay', __name__, url_prefix='/replay')


@replay_bp.route('/')
def replay_setup():
    """Render the replay setup page"""
    return render_template('replay.html')


@replay_bp.route('/api/list_pip_files', methods=['GET'])
def list_pip_files():
    """
    List available PIP data files from the PIP_DATA_PATH directory.
    Attempts to extract ticker symbol from filename.
    """
    try:
        env = EnvVars()
        pip_path = env.pip_data_path

        if not pip_path:
            return jsonify({
                'success': False,
                'error': 'PIP_DATA_PATH not configured in environment',
                'files': []
            })

        pip_dir = Path(pip_path).expanduser()
        if not pip_dir.exists():
            return jsonify({
                'success': False,
                'error': f'PIP data directory not found: {pip_path}',
                'files': []
            })

        files = []
        # Look for common PIP file extensions
        for pattern in ['*.txt', '*.json', '*.pip', '*.csv']:
            for file_path in pip_dir.glob(pattern):
                if file_path.is_file():
                    # Try to extract ticker from filename
                    ticker = extract_ticker_from_filename(file_path.name)

                    # Get file size and modification time
                    stat = file_path.stat()

                    files.append({
                        'filename': file_path.name,
                        'path': str(file_path),
                        'ticker': ticker,
                        'size': stat.st_size,
                        'size_formatted': format_file_size(stat.st_size),
                        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                    })

        # Sort by filename
        files.sort(key=lambda x: x['filename'].lower())

        return jsonify({
            'success': True,
            'files': files,
            'directory': str(pip_dir)
        })

    except Exception as e:
        logger.error(f"Error listing PIP files: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'files': []
        })


@replay_bp.route('/api/list_monitor_configs', methods=['GET'])
def list_monitor_configs():
    """List available monitor configuration files from the monitors/ directory"""
    try:
        # Find monitors directory relative to project root
        # stock_analysis_ui is in src/, monitors is at project root
        current_dir = Path(__file__).parent.parent.parent.parent
        monitors_dir = current_dir / 'monitors'

        if not monitors_dir.exists():
            return jsonify({
                'success': False,
                'error': f'Monitors directory not found: {monitors_dir}',
                'configs': []
            })

        configs = []
        for file_path in monitors_dir.glob('*.json'):
            if file_path.is_file():
                stat = file_path.stat()
                configs.append({
                    'filename': file_path.name,
                    'path': str(file_path),
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                })

        # Sort by modification time (newest first)
        configs.sort(key=lambda x: x['modified'], reverse=True)

        return jsonify({
            'success': True,
            'configs': configs,
            'directory': str(monitors_dir)
        })

    except Exception as e:
        logger.error(f"Error listing monitor configs: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'configs': []
        })


@replay_bp.route('/api/get_available_tickers', methods=['GET'])
def get_available_tickers():
    """
    Get list of tickers with available MongoDB historical data.
    Reuses the same logic as visualization_apps replay routes.
    """
    try:
        from pymongo import MongoClient
        from mlf_utils.ticker_config import get_tracked_tickers, get_default_ticker

        env = EnvVars()
        client = MongoClient(env.mongo_host, env.mongo_port, serverSelectionTimeoutMS=5000)
        db = client[env.mongo_database]
        collection = db[env.mongo_collection]

        tracked_tickers = get_tracked_tickers()
        ticker_info = []

        for ticker in tracked_tickers:
            # Find all documents for this ticker and get min/max dates
            docs = list(collection.find({'ticker': ticker}, {'year': 1, 'month': 1, 'data': 1}))

            if docs:
                min_date = None
                max_date = None

                for doc in docs:
                    year = doc.get('year')
                    month = doc.get('month')
                    data = doc.get('data', {})

                    if not data:
                        continue

                    # Get actual days with data
                    days_with_data = [int(d) for d in data.keys() if data[d]]

                    if days_with_data:
                        min_day = min(days_with_data)
                        max_day = max(days_with_data)

                        doc_min = datetime(year, month, min_day)
                        doc_max = datetime(year, month, max_day)

                        if min_date is None or doc_min < min_date:
                            min_date = doc_min
                        if max_date is None or doc_max > max_date:
                            max_date = doc_max

                ticker_info.append({
                    'ticker': ticker,
                    'has_data': min_date is not None,
                    'start_date': min_date.strftime('%Y-%m-%d') if min_date else None,
                    'end_date': max_date.strftime('%Y-%m-%d') if max_date else None
                })
            else:
                ticker_info.append({
                    'ticker': ticker,
                    'has_data': False,
                    'start_date': None,
                    'end_date': None
                })

        # Sort by ticker name, putting tickers with data first
        ticker_info.sort(key=lambda x: (not x['has_data'], x['ticker']))

        return jsonify({
            'success': True,
            'tickers': ticker_info,
            'default_ticker': get_default_ticker()
        })

    except Exception as e:
        logger.error(f"Error getting available tickers: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'tickers': []
        })


@replay_bp.route('/api/start_replay', methods=['POST'])
def start_replay():
    """
    Initialize replay mode and redirect to dashboard.
    Handles both PIP file and MongoDB data sources.
    """
    try:
        data = request.get_json()

        source_type = data.get('source_type')  # 'pip' or 'mongodb'
        monitor_config = data.get('monitor_config')
        playback_speed = float(data.get('playback_speed', 1.0))

        if not monitor_config:
            return jsonify({'success': False, 'error': 'Monitor config is required'})

        # Validate monitor config exists
        if not Path(monitor_config).exists():
            return jsonify({'success': False, 'error': f'Monitor config not found: {monitor_config}'})

        if source_type == 'pip':
            # PIP file replay
            pip_file = data.get('pip_file')
            ticker = data.get('ticker')

            if not pip_file:
                return jsonify({'success': False, 'error': 'PIP file is required'})

            if not Path(pip_file).exists():
                return jsonify({'success': False, 'error': f'PIP file not found: {pip_file}'})

            # Store replay config in session for dashboard to pick up
            session['replay_mode'] = True
            session['replay_config'] = {
                'source_type': 'pip',
                'pip_file': pip_file,
                'ticker': ticker,
                'monitor_config': monitor_config,
                'playback_speed': playback_speed
            }

            return jsonify({'success': True, 'redirect': '/dashboard'})

        elif source_type == 'mongodb':
            # MongoDB historical data replay
            ticker = data.get('ticker')
            date_str = data.get('date')

            if not ticker:
                return jsonify({'success': False, 'error': 'Ticker is required'})

            if not date_str:
                return jsonify({'success': False, 'error': 'Date is required'})

            # Validate date format
            try:
                replay_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'})

            # Store replay config in session
            session['replay_mode'] = True
            session['replay_config'] = {
                'source_type': 'mongodb',
                'ticker': ticker.upper(),
                'date': date_str,
                'monitor_config': monitor_config,
                'playback_speed': playback_speed
            }

            return jsonify({'success': True, 'redirect': '/dashboard'})

        else:
            return jsonify({'success': False, 'error': f'Invalid source type: {source_type}'})

    except Exception as e:
        logger.error(f"Error starting replay: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


def extract_ticker_from_filename(filename: str) -> str:
    """
    Extract ticker symbol from filename.
    Common patterns: NVDA_pips.txt, nvda_data.json, AAPL-2024-01-15.txt
    """
    # Remove extension
    name = Path(filename).stem.upper()

    # Common patterns
    patterns = [
        r'^([A-Z]{1,5})[-_]',  # NVDA_pips, AAPL-data
        r'^([A-Z]{1,5})$',      # Just ticker: NVDA
        r'([A-Z]{1,5})[-_]PIPS?',  # nvda_pips
        r'([A-Z]{1,5})[-_]DATA',   # nvda_data
    ]

    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return 'UNKNOWN'


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
