"""
Monitor Configuration Editor Routes
Provides UI for creating and editing monitor configurations
"""

from flask import Blueprint, render_template, request, jsonify
import os
import json

# Import mlf_utils
from mlf_utils import ConfigLoader, indicator_schema_cache
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("MonitorConfigRoutes")

monitor_config_bp = Blueprint('monitor_config', __name__, url_prefix='/monitor_config')

# Create config loader for monitor config routes
config_loader = ConfigLoader(config_dir='inputs')


@monitor_config_bp.route('/')
def monitor_config_main():
    """Main monitor configuration page"""
    return render_template('monitor_config/main.html')


@monitor_config_bp.route('/api/list_files', methods=['GET'])
def list_monitor_files():
    """List available monitor configuration files"""
    try:
        inputs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'inputs')

        if not os.path.exists(inputs_dir):
            return jsonify({'success': False, 'error': 'Inputs directory not found'})

        # Get all JSON files
        files = [f for f in os.listdir(inputs_dir) if f.endswith('.json')]

        return jsonify({
            'success': True,
            'files': sorted(files)
        })

    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({'success': False, 'error': str(e)})


@monitor_config_bp.route('/api/load_config', methods=['POST'])
def load_monitor_config():
    """Load a monitor configuration file"""
    try:
        data = request.get_json()
        filename = data.get('filename')

        if not filename:
            return jsonify({'success': False, 'error': 'No filename provided'})

        # Use ConfigLoader for consistent config loading
        success, config, error = config_loader.load_config(filename)

        if not success:
            return jsonify({'success': False, 'error': error})

        return jsonify({
            'success': True,
            'config': config
        })

    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return jsonify({'success': False, 'error': str(e)})


@monitor_config_bp.route('/api/save_config', methods=['POST'])
def save_monitor_config():
    """Save a monitor configuration file"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        config = data.get('config')

        if not filename or not config:
            return jsonify({'success': False, 'error': 'Missing filename or config'})

        # Use ConfigLoader for consistent config saving
        success, error = config_loader.save_config(filename, config)

        if not success:
            return jsonify({'success': False, 'error': error})

        return jsonify({
            'success': True,
            'message': f'Configuration saved to {filename}'
        })

    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return jsonify({'success': False, 'error': str(e)})


@monitor_config_bp.route('/api/get_indicator_classes', methods=['GET'])
def get_indicator_classes():
    """Get available indicator classes from the registry with caching"""
    try:
        # Check cache first
        cached_schemas = indicator_schema_cache.get('indicator_schemas')
        if cached_schemas:
            logger.info(f"Retrieved {len(cached_schemas)} indicator classes from cache")
            return jsonify({
                'success': True,
                'indicators': cached_schemas
            })

        # Import refactored_indicators to ensure registration happens
        import indicator_triggers.refactored_indicators
        from indicator_triggers.indicator_base import IndicatorRegistry

        registry = IndicatorRegistry()
        schemas = registry.get_ui_schemas()

        # Cache the schemas for 10 minutes
        indicator_schema_cache.set('indicator_schemas', schemas)

        logger.info(f"Retrieved {len(schemas)} indicator classes and cached them")

        return jsonify({
            'success': True,
            'indicators': schemas
        })

    except Exception as e:
        logger.error(f"Error getting indicator classes: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
