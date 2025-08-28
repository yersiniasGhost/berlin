# File: routes/api_routes.py
"""
API routes for AppService with session-based support - ENHANCED WITH CANDLESTICK ENDPOINTS
"""

import json
import logging
import time
import uuid
from datetime import datetime
from functools import wraps

import numpy as np
from flask import Blueprint, request, jsonify, current_app, session

# Import the services we need
from stock_analysis_ui.services.app_service import AppService
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager

logger = logging.getLogger('APIRoutes')
api_bp = Blueprint('api', __name__)


def get_session_app_service():
    """Get the app_service for the current session"""
    session_id = session.get('session_id')
    if not session_id:
        return None

    return current_app.session_app_services.get(session_id)


def require_session_auth(f):
    """Decorator to require valid session authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated') or not session.get('session_id'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        app_service = get_session_app_service()
        if not app_service:
            return jsonify({'success': False, 'error': 'Invalid session'}), 401

        return f(*args, **kwargs)

    return decorated_function


# AUTHENTICATION ROUTE (no decorator needed)
@api_bp.route('/authenticate', methods=['POST'])
def authenticate():
    """Handle Schwab authentication from UI - Session-based"""
    try:
        data = request.json
        auth_url = data.get('auth_url', '').strip()

        if not auth_url:
            return jsonify({'success': False, 'error': 'Auth URL is required'}), 400

        if 'code=' not in auth_url:
            return jsonify({'success': False, 'error': 'Invalid auth URL - must contain authorization code'}), 400

        # Create unique session ID for this user
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        session['authenticated'] = True

        logger.info(f"Creating new session: {session_id}")

        # Create auth manager and process the URL
        auth_manager = SchwabAuthManager()

        # Extract code from URL
        from urllib.parse import urlparse, parse_qs
        try:
            parsed_url = urlparse(auth_url)
            query_params = parse_qs(parsed_url.query)

            if 'code' not in query_params:
                return jsonify({'success': False, 'error': 'Authorization code not found in URL'}), 400

            response_code = query_params['code'][0]

            # Process the authorization code
            import base64
            import requests

            credentials = f"{auth_manager.app_key}:{auth_manager.app_secret}"
            base64_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Authorization": f"Basic {base64_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            payload = {
                "grant_type": "authorization_code",
                "code": response_code,
                "redirect_uri": auth_manager.redirect_uri,
            }

            # Get tokens from Schwab
            token_response = requests.post(
                "https://api.schwabapi.com/v1/oauth/token",
                headers=headers,
                data=payload
            )

            token_data = token_response.json()

            if 'error' in token_data:
                logger.error(f"Token error: {token_data}")
                return jsonify({'success': False,
                                'error': f"Authentication failed: {token_data.get('error', 'Unknown error')}"}), 400

            auth_manager.access_token = token_data.get("access_token")
            auth_manager.refresh_token = token_data.get("refresh_token")

            if not auth_manager.access_token:
                return jsonify({'success': False, 'error': 'No access token received'}), 400

            # Get streamer info
            if not auth_manager._get_streamer_info():
                return jsonify({'success': False, 'error': 'Failed to get user preferences'}), 400

            # Create session-specific app_service
            socketio = current_app.socketio
            session_app_service = AppService(socketio, auth_manager, session_id=session_id)

            # Store in session manager
            current_app.session_app_services[session_id] = session_app_service

            # Start streaming infrastructure
            if not session_app_service.start_streaming():
                # Clean up on failure
                del current_app.session_app_services[session_id]
                return jsonify({'success': False, 'error': 'Failed to start streaming infrastructure'}), 500

            logger.info(f"Authentication successful for session: {session_id}")

            return jsonify({
                'success': True,
                'message': 'Authentication successful',
                'session_id': session_id,
                'redirect_url': '/dashboard'
            })

        except Exception as e:
            logger.error(f"Error processing auth URL: {e}")
            return jsonify({'success': False, 'error': f'Failed to process authorization: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error in authentication endpoint: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# SESSION-BASED ROUTES
@api_bp.route('/status')
@require_session_auth
def get_status():
    """Get current application status - session-based"""
    try:
        app_service = get_session_app_service()
        combinations = app_service.get_combinations()

        authenticated = True
        if app_service.auth_manager is not None:
            authenticated = app_service.auth_manager.is_authenticated()

        return jsonify({
            'authenticated': authenticated,
            'streaming': app_service.is_streaming,
            'combinations': combinations['combinations'],
            'total_combinations': combinations['total'],
            'session_id': session.get('session_id'),
            'mode': app_service.get_mode() if hasattr(app_service, 'get_mode') else 'Live Schwab'
        })

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/combinations', methods=['POST'])
@require_session_auth
def add_combination():
    """Add a new combination - session-based"""
    try:
        data = request.json
        app_service = get_session_app_service()

        symbol = data.get('symbol', '').upper().strip()
        config_content = data.get('config_content', '')
        config_name = data.get('config_name', '')

        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol is required'}), 400

        if not config_content:
            return jsonify({'success': False, 'error': 'Config content is required'}), 400

        # Validate JSON content
        try:
            config_data = json.loads(config_content)
        except json.JSONDecodeError as e:
            return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}'}), 400

        # Create temporary file to work with existing load_monitor_config function
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file.write(config_content)
            temp_file_path = temp_file.name

        try:
            # Add the combination - FIXED: Only pass symbol and config_file_path
            result = app_service.add_combination(symbol, temp_file_path)

            if result['success']:
                return jsonify({
                    'success': True,
                    'card_id': result['card_id'],
                    'message': f'Added {symbol} with configuration'
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 400

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass

    except Exception as e:
        logger.error(f"Error adding combination: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations/<card_id>', methods=['DELETE'])
@require_session_auth
def remove_combination(card_id: str):
    """Remove a combination - session-based"""
    try:
        app_service = get_session_app_service()

        result = app_service.remove_combination(card_id)

        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Removed combination {card_id}'
            })
        else:
            return jsonify({'success': False, 'error': result['error']}), 400

    except Exception as e:
        logger.error(f"Error removing combination {card_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations')
@require_session_auth
def get_combinations():
    """Get all combinations - session-based"""
    try:
        app_service = get_session_app_service()
        combinations = app_service.get_combinations()

        return jsonify({
            'success': True,
            'combinations': combinations['combinations'],
            'total': combinations['total']
        })

    except Exception as e:
        logger.error(f"Error getting combinations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations/<card_id>/details')
@require_session_auth
def get_card_details(card_id: str):
    """Get detailed indicator history and current values for a specific card - session-based"""
    try:
        app_service = get_session_app_service()

        # Check if card exists
        if card_id not in app_service.combinations:
            return jsonify({'success': False, 'error': f'Card {card_id} not found'}), 404

        combination = app_service.combinations[card_id]
        symbol = combination['symbol']
        monitor_config = combination['monitor_config']
        data_streamer = combination['data_streamer']

        # Get timeframes from the monitor config
        timeframes = monitor_config.get_time_increments()

        # Get all candle data from the DataStreamer's aggregators
        all_candle_data = data_streamer._get_all_candle_data()

        # Build aggregator info
        aggregator_info = {}
        for timeframe in timeframes:
            if timeframe in all_candle_data:
                candles = all_candle_data[timeframe]
                aggregator_info[timeframe] = {
                    'history_count': len(candles),
                    'current_price': candles[-1].close if candles else 0,
                    'latest_timestamp': candles[-1].timestamp.isoformat() if candles else None
                }

        # Calculate current indicator values
        current_indicators, current_raw, current_bars = data_streamer.indicator_processor.calculate_indicators(
            all_candle_data, None
        )

        # Get REAL indicator history from processor
        indicator_history = data_streamer.indicator_processor.get_history_data() if hasattr(
            data_streamer.indicator_processor, 'get_history_data') else {}

        # Convert monitor_config to dict format
        monitor_config_dict = {
            'name': monitor_config.name,
            'description': monitor_config.description,
            'enter_long': monitor_config.enter_long,
            'exit_long': monitor_config.exit_long,
            'bars': monitor_config.bars if hasattr(monitor_config, 'bars') else {}
        }

        # Get portfolio data if available
        portfolio_data = None
        if hasattr(data_streamer, 'get_portfolio_metrics'):
            portfolio_data = data_streamer.get_portfolio_metrics()

        response_data = {
            'success': True,
            'card_info': {
                'symbol': symbol,
                'card_id': card_id,
                'config_name': monitor_config.name if hasattr(monitor_config, 'name') else 'Configuration'
            },
            'monitor_config': monitor_config_dict,
            'aggregator_info': aggregator_info,
            'current_values': {
                'indicators': current_indicators,
                'raw_indicators': current_raw,
                'bar_scores': current_bars
            },
            'indicator_history': indicator_history,
            'portfolio_data': portfolio_data
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error getting card details for {card_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# NEW: Candlestick Data Endpoint
@api_bp.route('/combinations/<card_id>/candlestick')
@require_session_auth
def get_candlestick_data(card_id: str):
    """Get candlestick data for a specific card and timeframe - session-based"""
    try:
        app_service = get_session_app_service()

        # Check if card exists
        if card_id not in app_service.combinations:
            return jsonify({'success': False, 'error': f'Card {card_id} not found'}), 404

        combination = app_service.combinations[card_id]
        symbol = combination['symbol']
        data_streamer = combination['data_streamer']

        # Get timeframe from query parameter (default to 1m for intraday)
        timeframe = request.args.get('timeframe', '1m')

        # Map frontend timeframe to aggregator key
        timeframe_mapping = {
            '1m': '1m-normal',
            '5m': '5m-normal',
            '15m': '15m-normal',
            '1h': '1h-normal',
            '1d': '1d-normal'  # This might need special handling
        }

        aggregator_key = timeframe_mapping.get(timeframe, '1m-normal')

        # CREATE SINGLE CURRENT CANDLE from live data if available
        candlestick_data = []
        
        # Try to get the current price from the combination's latest data
        current_price = None
        if card_id in app_service.combinations:
            try:
                combination = app_service.combinations[card_id]
                if 'data_streamer' in combination:
                    data_streamer = combination['data_streamer']
                    # Try to get current price from aggregator if available
                    all_candle_data = data_streamer._get_all_candle_data()
                    if aggregator_key in all_candle_data and all_candle_data[aggregator_key]:
                        latest_candle = all_candle_data[aggregator_key][-1]
                        current_price = float(latest_candle.close)
            except Exception as e:
                logger.warning(f"Could not get current price: {e}")
        
        # If we have a current price, create an initial current candle
        if current_price:
            from datetime import datetime
            now = datetime.now()
            # Create timestamp for current minute
            current_minute = now.replace(second=0, microsecond=0)
            timestamp_ms = int(current_minute.timestamp() * 1000)
            
            # Create initial candle with current price as OHLC (will be updated by live data)
            initial_candle = [
                timestamp_ms,
                current_price,  # open
                current_price,  # high
                current_price,  # low
                current_price   # close
            ]
            candlestick_data = [initial_candle]
            
            logger.info(f"Created initial current candle for {card_id} at ${current_price}")
        else:
            logger.info(f"No current price available for {card_id}, starting with empty chart")

        # Simple debug info
        from datetime import datetime
        debug_info = {
            'initial_candles': len(candlestick_data),
            'current_price': current_price,
            'data_source': 'current_minute_only',
            'message': 'Starting with current minute candle, will build from live data'
        }

        return jsonify({
            'success': True,
            'candlestick_data': candlestick_data,
            'symbol': symbol,
            'timeframe': timeframe,
            'total_candles': len(candlestick_data),
            'aggregator_key': aggregator_key,
            'debug': debug_info
        })

    except Exception as e:
        logger.error(f"Error getting candlestick data for {card_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# NEW: Available Aggregators Endpoint
@api_bp.route('/combinations/<card_id>/aggregators')
@require_session_auth
def get_available_aggregators(card_id: str):
    """Get available aggregator timeframes for a specific card - session-based"""
    try:
        app_service = get_session_app_service()

        # Check if card exists
        if card_id not in app_service.combinations:
            return jsonify({'success': False, 'error': f'Card {card_id} not found'}), 404

        combination = app_service.combinations[card_id]
        data_streamer = combination['data_streamer']
        monitor_config = combination['monitor_config']

        # Get available timeframes from monitor config
        timeframes = monitor_config.get_time_increments() if monitor_config else []

        # Get all candle data to check what's actually available
        all_candle_data = data_streamer._get_all_candle_data()

        available_aggregators = {}
        for agg_key, candles in all_candle_data.items():
            # Extract timeframe from aggregator key (e.g., "1m-normal" -> "1m")
            timeframe = agg_key.split('-')[0] if '-' in agg_key else agg_key

            available_aggregators[timeframe] = {
                'aggregator_key': agg_key,
                'candle_count': len(candles),
                'latest_timestamp': candles[-1].timestamp.isoformat() if candles else None,
                'latest_price': float(candles[-1].close) if candles else None
            }

        return jsonify({
            'success': True,
            'available_aggregators': available_aggregators,
            'symbol': combination['symbol'],
            'card_id': card_id
        })

    except Exception as e:
        logger.error(f"Error getting available aggregators for {card_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/combinations/<card_id>/portfolio')
@require_session_auth
def get_portfolio_metrics(card_id: str):
    """Get portfolio metrics for a specific card - session-based"""
    try:
        app_service = get_session_app_service()

        # Check if card exists
        if card_id not in app_service.combinations:
            return jsonify({'success': False, 'error': f'Card {card_id} not found'}), 404

        combination = app_service.combinations[card_id]
        data_streamer = combination['data_streamer']

        portfolio_metrics = {}
        if hasattr(data_streamer, 'get_portfolio_metrics'):
            portfolio_metrics = data_streamer.get_portfolio_metrics()

        return jsonify({
            'success': True,
            'card_id': card_id,
            'portfolio_metrics': portfolio_metrics
        })

    except Exception as e:
        logger.error(f"Error getting portfolio for {card_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/portfolios')
@require_session_auth
def get_all_portfolios():
    """Get portfolio metrics for all active cards - session-based"""
    try:
        app_service = get_session_app_service()

        portfolios = {}
        for card_id, combination in app_service.combinations.items():
            data_streamer = combination['data_streamer']
            if hasattr(data_streamer, 'get_portfolio_metrics'):
                portfolios[card_id] = data_streamer.get_portfolio_metrics()

        return jsonify({
            'success': True,
            'portfolios': portfolios,
            'total_cards': len(portfolios)
        })

    except Exception as e:
        logger.error(f"Error getting all portfolios: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/streaming/start', methods=['POST'])
@require_session_auth
def start_streaming():
    """Start streaming infrastructure - session-based"""
    try:
        app_service = get_session_app_service()

        if app_service.start_streaming():
            logger.info("Streaming started via API")
            return jsonify({'success': True, 'message': 'Streaming started'})
        else:
            logger.error("Failed to start streaming via API")
            return jsonify({'success': False, 'error': 'Failed to start streaming'}), 500

    except Exception as e:
        logger.error(f"Error starting streaming: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/streaming/stop', methods=['POST'])
@require_session_auth
def stop_streaming():
    """Stop streaming - session-based"""
    try:
        app_service = get_session_app_service()

        if app_service.stop_streaming():
            logger.info("Streaming stopped via API")
            return jsonify({'success': True, 'message': 'Streaming stopped'})
        else:
            logger.error("Failed to stop streaming via API")
            return jsonify({'success': False, 'error': 'Failed to stop streaming'}), 500

    except Exception as e:
        logger.error(f"Error stopping streaming: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/available-configs')
@require_session_auth
def get_available_configs():
    """Get list of available configuration files - session-based"""
    try:
        app_service = get_session_app_service()
        configs = app_service.get_available_configs()

        return jsonify({
            'success': True,
            'configs': configs,
            'total': len(configs)
        })

    except Exception as e:
        logger.error(f"Error getting available configs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/generate-monitor-config', methods=['POST'])
@require_session_auth
def generate_monitor_config():
    """Generate monitor configuration JSON from wizard data"""
    try:
        data = request.json

        # Extract wizard data
        basic_info = data.get('basicInfo', {})
        indicators = data.get('indicators', [])
        bars = data.get('bars', {})
        trading_rules = data.get('tradingRules', {})

        # Generate the complete monitor configuration
        config = {
            "test_name": basic_info.get('testName', ''),
            "monitor": {
                "_id": "generated_monitor_id",
                "user_id": "user_id",
                "name": basic_info.get('monitorName', ''),
                "description": basic_info.get('description', ''),
                "enter_long": [],
                "exit_long": [],
                "bars": {}
            },
            "indicators": []
        }

        # Process bars into enter/exit conditions
        for bar_name, bar_data in bars.items():
            if bar_data.get('type') == 'bull':
                config["monitor"]["enter_long"].append({
                    "name": bar_name,
                    "threshold": trading_rules.get('entry', {}).get(bar_name, 0.5)
                })
            elif bar_data.get('type') == 'bear':
                config["monitor"]["exit_long"].append({
                    "name": bar_name,
                    "threshold": trading_rules.get('exit', {}).get(bar_name, 0.5)
                })

            # Add bar configuration
            config["monitor"]["bars"][bar_name] = {
                "type": bar_data.get('type'),
                "indicators": bar_data.get('indicators', {})
            }

        # Process indicators
        for indicator in indicators:
            config["indicators"].append({
                "name": indicator.get('name'),
                "type": "Indicator",
                "function": indicator.get('function'),
                "agg_config": indicator.get('aggConfig'),
                "calc_on_pip": False,
                "parameters": indicator.get('parameters', {})
            })

        return jsonify({
            'success': True,
            'config': config
        })

    except Exception as e:
        logger.error(f"Error generating monitor config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# DEBUG ENDPOINTS
@api_bp.route('/debug/streaming')
@require_session_auth
def debug_streaming():
    """Get detailed streaming debug information - session-based"""
    try:
        app_service = get_session_app_service()

        debug_info = {
            'app_service_streaming': app_service.is_streaming,
            'app_service_mode': app_service.get_mode() if hasattr(app_service, 'get_mode') else 'Unknown',
            'combinations_count': len(app_service.combinations),
            'data_link_type': type(app_service.data_link).__name__ if app_service.data_link else 'None',
            'session_id': session.get('session_id')
        }

        # Get CSReplayDataLink specific debug info
        if hasattr(app_service.data_link, 'get_debug_info'):
            debug_info['replay_debug'] = app_service.data_link.get_debug_info()

        # Get DataStreamer info
        debug_info['data_streamers'] = {}
        for card_id, combo in app_service.combinations.items():
            symbol = combo['symbol']
            data_streamer = combo['data_streamer']

            debug_info['data_streamers'][card_id] = {
                'symbol': symbol,
                'card_id': card_id,
                'aggregators_count': len(data_streamer.aggregators) if hasattr(data_streamer, 'aggregators') else 0,
                'external_tools_count': len(data_streamer.external_tools) if hasattr(data_streamer,
                                                                                     'external_tools') else 0
            }

        return jsonify({
            'success': True,
            'debug_info': debug_info,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting debug info: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/debug/websocket-health')
@require_session_auth
def websocket_health():
    """Get WebSocket health status - session-based"""
    try:
        app_service = get_session_app_service()

        health_data = {
            'timestamp': datetime.now().isoformat(),
            'ui_tool_health': app_service.ui_tool.get_health_status() if hasattr(app_service.ui_tool,
                                                                                 'get_health_status') else {},
            'active_combinations': len(app_service.combinations),
            'streaming_active': app_service.is_streaming,
            'session_id': session.get('session_id')
        }

        return jsonify({
            'success': True,
            'health': health_data
        })

    except Exception as e:
        logger.error(f"Error getting WebSocket health: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500