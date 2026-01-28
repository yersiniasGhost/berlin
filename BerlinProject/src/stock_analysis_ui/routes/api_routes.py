# File: routes/api_routes.py
"""
API routes for AppService with session-based support - ENHANCED WITH CANDLESTICK ENDPOINTS
"""

import json
import time
import uuid
from datetime import datetime
from functools import wraps

import numpy as np
from flask import Blueprint, request, jsonify, current_app, session

# Import the services we need
from stock_analysis_ui.services.app_service import AppService
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
from mlf_utils.log_manager import LogManager
from mlf_utils.timezone_utils import now_utc, isoformat_et

logger = LogManager().get_logger("APIRoutes")
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
        # Debug logging for auth issues
        session_id = session.get('session_id')
        authenticated = session.get('authenticated')
        logger.debug(f"Auth check: session_id={session_id}, authenticated={authenticated}")

        if not authenticated or not session_id:
            logger.warning(f"Auth failed: authenticated={authenticated}, session_id={session_id}")
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        app_service = get_session_app_service()
        if not app_service:
            logger.warning(f"Invalid session: session_id={session_id} not found in session_app_services")
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

        # Get full candle history from the data streamer
        candlestick_data = []
        current_price = None

        if card_id in app_service.combinations:
            try:
                combination = app_service.combinations[card_id]
                if 'data_streamer' in combination:
                    data_streamer = combination['data_streamer']
                    all_candle_data = data_streamer._get_all_candle_data()

                    if aggregator_key in all_candle_data and all_candle_data[aggregator_key]:
                        candle_history = all_candle_data[aggregator_key]

                        # Convert TickData objects to [timestamp_ms, open, high, low, close] format
                        for candle in candle_history:
                            timestamp_ms = int(candle.timestamp.timestamp() * 1000)
                            candlestick_data.append([
                                timestamp_ms,
                                float(candle.open),
                                float(candle.high),
                                float(candle.low),
                                float(candle.close)
                            ])

                        # Get current price from last candle
                        if candle_history:
                            current_price = float(candle_history[-1].close)

                        logger.info(f"Returning {len(candlestick_data)} candles for {card_id} ({aggregator_key})")
            except Exception as e:
                logger.warning(f"Could not get candle history: {e}")

        if not candlestick_data:
            logger.info(f"No candle history available for {card_id}, starting with empty chart")

        # Debug info
        debug_info = {
            'initial_candles': len(candlestick_data),
            'current_price': current_price,
            'data_source': 'aggregator_history',
            'message': f'Loaded {len(candlestick_data)} candles from aggregator history'
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
            'timestamp': isoformat_et(now_utc())
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
            'timestamp': isoformat_et(now_utc()),
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


@api_bp.route('/combinations/<card_id>/chart-data')
@require_session_auth
def get_chart_data(card_id: str):
    """
    Get comprehensive chart data for card details visualization.
    Returns data compatible with replay visualization charts (indicator charts, trigger charts, P&L).
    """
    try:
        app_service = get_session_app_service()

        # Check if card exists
        if card_id not in app_service.combinations:
            return jsonify({'success': False, 'error': f'Card {card_id} not found'}), 404

        combination = app_service.combinations[card_id]
        symbol = combination['symbol']
        monitor_config = combination['monitor_config']
        data_streamer = combination['data_streamer']
        test_name = combination.get('test_name', monitor_config.name)

        # Get all candle data from all aggregators
        all_candle_data = data_streamer._get_all_candle_data()

        # Build per-aggregator candlestick data (same format as replay tool)
        per_aggregator_candles = {}
        for agg_key, candles in all_candle_data.items():
            candlestick_series = []
            for candle in candles:
                timestamp_ms = int(candle.timestamp.timestamp() * 1000)
                candlestick_series.append([
                    timestamp_ms,
                    float(candle.open),
                    float(candle.high),
                    float(candle.low),
                    float(candle.close)
                ])
            per_aggregator_candles[agg_key] = candlestick_series
            logger.debug(f"Prepared {len(candlestick_series)} candles for {agg_key}")

        # Get primary candlestick data (first available aggregator for trade overlay)
        candlestick_data = []
        primary_agg_key = list(all_candle_data.keys())[0] if all_candle_data else None
        if primary_agg_key:
            candlestick_data = per_aggregator_candles.get(primary_agg_key, [])

        # Get indicator processor data
        indicator_processor = data_streamer.indicator_processor

        # Build indicator history in chart-compatible format [[timestamp_ms, value], ...]
        indicator_history_formatted = {}
        raw_indicator_history_formatted = {}
        component_history_formatted = {}

        # Get timestamps from aggregators for each indicator
        indicator_agg_mapping = {}
        for indicator_def in monitor_config.indicators:
            timeframe = indicator_def.get_timeframe()
            agg_type = indicator_def.get_aggregator_type()
            agg_key = f"{timeframe}-{agg_type}"
            indicator_agg_mapping[indicator_def.name] = agg_key

        # Build indicator history from processor's trigger history
        for ind_name, history in indicator_processor.indicator_trigger_history.items():
            # Extract actual indicator name from internal key (e.g., "1m-heiken_macd5m" -> "macd5m")
            actual_name = ind_name.split('_', 1)[-1] if '_' in ind_name else ind_name

            # Get aggregator key for timestamps
            agg_key = indicator_agg_mapping.get(actual_name)
            if not agg_key and '_' in ind_name:
                agg_key = ind_name.rsplit('_', 1)[0]

            # Get timestamps from aggregator
            timestamps = []
            if agg_key and agg_key in all_candle_data:
                candles = all_candle_data[agg_key]
                # Use last N timestamps to match history length
                timestamps = [int(c.timestamp.timestamp() * 1000) for c in candles[-len(history):]]

            # Pad timestamps if needed
            while len(timestamps) < len(history):
                # Generate synthetic timestamps
                base_ts = timestamps[0] if timestamps else int(now_utc().timestamp() * 1000)
                timestamps.insert(0, base_ts - (len(history) - len(timestamps)) * 60000)

            # Format raw indicator values (trigger values 0/1)
            series = []
            for i, value in enumerate(history):
                if i < len(timestamps) and value is not None:
                    series.append([timestamps[i], float(value)])
            if series:
                raw_indicator_history_formatted[actual_name] = series

        # Build time-decayed indicator history
        for ind_name, value in indicator_processor.indicators.items():
            # For live data, we only have current values, not full history
            # Create a single-point "history" for current state
            agg_key = indicator_agg_mapping.get(ind_name)
            if agg_key and agg_key in all_candle_data:
                candles = all_candle_data[agg_key]
                if candles:
                    timestamp = int(candles[-1].timestamp.timestamp() * 1000)
                    indicator_history_formatted[ind_name] = [[timestamp, float(value)]]

        # Build component history from processor's component data
        for comp_name, comp_value in indicator_processor.component_data.items():
            # Extract indicator name from component (e.g., "macd5m_macd" -> "macd5m")
            indicator_name = comp_name.rsplit('_', 1)[0] if '_' in comp_name else comp_name
            agg_key = indicator_agg_mapping.get(indicator_name)

            if agg_key and agg_key in all_candle_data:
                candles = all_candle_data[agg_key]
                if candles:
                    timestamp = int(candles[-1].timestamp.timestamp() * 1000)
                    component_history_formatted[comp_name] = [[timestamp, float(comp_value)]]

        # Build class_to_layout mapping (indicator class -> layout type)
        class_to_layout = {}
        try:
            import indicator_triggers.refactored_indicators
            from indicator_triggers.indicator_base import IndicatorRegistry
            registry = IndicatorRegistry()

            for indicator_def in monitor_config.indicators:
                indicator_class_name = indicator_def.indicator_class
                if indicator_class_name and indicator_class_name not in class_to_layout:
                    try:
                        indicator_cls = registry.get_indicator_class(indicator_class_name)
                        layout_type = indicator_cls.get_layout_type()
                        class_to_layout[indicator_class_name] = layout_type
                    except (ValueError, AttributeError):
                        # Default based on name
                        layout_type = 'stacked' if 'macd' in indicator_class_name.lower() else 'overlay'
                        class_to_layout[indicator_class_name] = layout_type
        except Exception as e:
            logger.warning(f"Could not build class_to_layout mapping: {e}")

        # Get trade details from trade executor
        trade_details = {}
        trades_with_pnl = []
        pnl_data = []

        trade_executor = data_streamer.trade_executor
        if hasattr(trade_executor, 'trade_details_history'):
            trade_details = trade_executor.trade_details_history

        # Get portfolio trade history
        portfolio = trade_executor.portfolio
        if hasattr(portfolio, 'trade_history'):
            cumulative_pnl = 0
            for trade in portfolio.trade_history:
                trade_entry = {
                    'timestamp': trade.get('timestamp', 0),
                    'action': trade.get('action', ''),
                    'price': trade.get('price', 0),
                    'quantity': trade.get('quantity', 0),
                    'pnl': trade.get('pnl', 0)
                }
                trades_with_pnl.append(trade_entry)

                # Build cumulative P&L data
                if trade.get('pnl'):
                    cumulative_pnl += trade['pnl']
                    pnl_data.append([trade['timestamp'], cumulative_pnl])

        # Get portfolio metrics
        portfolio_metrics = {}
        if hasattr(data_streamer, 'get_portfolio_metrics'):
            portfolio_metrics = data_streamer.get_portfolio_metrics()

        # Build indicators list for frontend
        indicators_list = []
        for indicator_def in monitor_config.indicators:
            indicators_list.append({
                'name': indicator_def.name,
                'indicator_class': indicator_def.indicator_class,
                'type': indicator_def.type,
                'agg_config': {
                    'timeframe': indicator_def.get_timeframe(),
                    'aggregator_type': indicator_def.get_aggregator_type()
                },
                'parameters': indicator_def.parameters
            })

        # Get threshold config for bar charts
        threshold_config = {
            'enter_long': monitor_config.enter_long,
            'exit_long': monitor_config.exit_long
        }

        # Build bar score history
        bar_score_history = {}
        if hasattr(indicator_processor, 'bar_history'):
            bar_score_history = indicator_processor.bar_history

        chart_data = {
            'success': True,
            'ticker': symbol,
            'test_name': test_name,
            'card_id': card_id,
            'candlestick_data': candlestick_data,
            'per_aggregator_candles': per_aggregator_candles,
            'indicator_agg_mapping': indicator_agg_mapping,
            'indicator_history': indicator_history_formatted,
            'raw_indicator_history': raw_indicator_history_formatted,
            'component_history': component_history_formatted,
            'class_to_layout': class_to_layout,
            'indicators': indicators_list,
            'trades': trades_with_pnl,
            'trade_details': trade_details,
            'pnl_data': pnl_data,
            'pnl_history': pnl_data,  # Alias for compatibility
            'portfolio_metrics': portfolio_metrics,
            'bar_score_history': bar_score_history,
            'threshold_config': threshold_config,
            'current_values': {
                'indicators': indicator_processor.indicators,
                'raw_indicators': indicator_processor.raw_indicators,
                'bar_scores': data_streamer.bar_scores
            },
            'total_candles': len(candlestick_data),
            'total_trades': len(trades_with_pnl),
            'data_status': indicator_processor.get_data_status()
        }

        # Sanitize NaN values for JSON compatibility
        chart_data = _sanitize_chart_data(chart_data)

        logger.info(f"Chart data for {card_id}: {len(candlestick_data)} candles, "
                    f"{len(indicators_list)} indicators, {len(trades_with_pnl)} trades")

        return jsonify(chart_data)

    except Exception as e:
        logger.error(f"Error getting chart data for {card_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def _sanitize_chart_data(data):
    """Recursively sanitize data for JSON serialization (handle NaN, Infinity)"""
    import math

    if isinstance(data, dict):
        return {k: _sanitize_chart_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_chart_data(item) for item in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    elif isinstance(data, np.floating):
        if np.isnan(data) or np.isinf(data):
            return None
        return float(data)
    elif isinstance(data, np.integer):
        return int(data)
    elif isinstance(data, np.ndarray):
        return _sanitize_chart_data(data.tolist())
    return data