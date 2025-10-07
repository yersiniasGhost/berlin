"""
Monitor Configuration Editor Routes
Provides UI for creating and editing monitor configurations
"""

from flask import Blueprint, render_template, request, jsonify
import os
import json
import logging

logger = logging.getLogger('MonitorConfigRoutes')

monitor_config_bp = Blueprint('monitor_config', __name__, url_prefix='/monitor_config')


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

        inputs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'inputs')
        file_path = os.path.join(inputs_dir, filename)

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'File not found'})

        with open(file_path, 'r') as f:
            config = json.load(f)

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

        inputs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'inputs')
        file_path = os.path.join(inputs_dir, filename)

        with open(file_path, 'w') as f:
            json.dump(config, f, indent=2)

        return jsonify({
            'success': True,
            'message': f'Configuration saved to {filename}'
        })

    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return jsonify({'success': False, 'error': str(e)})


@monitor_config_bp.route('/api/get_indicator_classes', methods=['GET'])
def get_indicator_classes():
    """Get available indicator classes from the registry"""
    try:
        # Import refactored_indicators to ensure registration happens
        import indicator_triggers.refactored_indicators
        from indicator_triggers.indicator_base import IndicatorRegistry

        registry = IndicatorRegistry()
        schemas = registry.get_ui_schemas()

        logger.info(f"Retrieved {len(schemas)} indicator classes")

        return jsonify({
            'success': True,
            'indicators': schemas
        })

    except Exception as e:
        logger.error(f"Error getting indicator classes: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
