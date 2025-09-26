"""
API layer for indicator configuration management.
Provides endpoints and utilities for UI integration.
"""

from typing import Dict, List, Any, Optional
from flask import Blueprint, jsonify, request
import json
from pathlib import Path

from indicator_triggers.indicator_base import IndicatorConfiguration, IndicatorRegistry
from indicator_triggers.refactored_indicators import *  # Import to register indicators


class IndicatorConfigManager:
    """Manages indicator configurations with persistence."""
    
    def __init__(self, config_dir: str = "indicator_configs"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self._active_configs: Dict[str, IndicatorConfiguration] = {}
    
    def save_configuration(self, config: IndicatorConfiguration, config_id: str = None) -> str:
        """Save indicator configuration to file."""
        if config_id is None:
            config_id = f"{config.indicator_name}_{len(self._active_configs)}"
        
        config_file = self.config_dir / f"{config_id}.json"
        
        with open(config_file, 'w') as f:
            f.write(config.to_json())
        
        self._active_configs[config_id] = config
        return config_id
    
    def load_configuration(self, config_id: str) -> Optional[IndicatorConfiguration]:
        """Load indicator configuration from file."""
        config_file = self.config_dir / f"{config_id}.json"
        
        if not config_file.exists():
            return None
        
        with open(config_file, 'r') as f:
            config = IndicatorConfiguration.from_json(f.read())
        
        self._active_configs[config_id] = config
        return config
    
    def list_configurations(self) -> List[Dict[str, Any]]:
        """List all saved configurations."""
        configs = []
        
        for config_file in self.config_dir.glob("*.json"):
            config_id = config_file.stem
            
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                
                configs.append({
                    'id': config_id,
                    'indicator_name': config_data['indicator_name'],
                    'display_name': config_data['display_name'],
                    'enabled': config_data.get('enabled', True),
                    'parameter_count': len(config_data.get('parameters', {}))
                })
            except Exception as e:
                print(f"Error loading config {config_id}: {e}")
                continue
        
        return configs
    
    def delete_configuration(self, config_id: str) -> bool:
        """Delete a configuration."""
        config_file = self.config_dir / f"{config_id}.json"
        
        if config_file.exists():
            config_file.unlink()
            self._active_configs.pop(config_id, None)
            return True
        
        return False
    
    def create_indicator_instance(self, config_id: str) -> Optional[BaseIndicator]:
        """Create indicator instance from saved configuration."""
        config = self.load_configuration(config_id)
        if config is None:
            return None
        
        return IndicatorRegistry().create_indicator(config)
    
    def export_configuration_set(self, config_ids: List[str]) -> Dict[str, Any]:
        """Export multiple configurations as a set."""
        export_data = {
            'version': '1.0',
            'configurations': {}
        }
        
        for config_id in config_ids:
            config = self.load_configuration(config_id)
            if config:
                export_data['configurations'][config_id] = config.to_dict()
        
        return export_data
    
    def import_configuration_set(self, import_data: Dict[str, Any]) -> List[str]:
        """Import multiple configurations from export data."""
        imported_ids = []
        
        configurations = import_data.get('configurations', {})
        for config_id, config_data in configurations.items():
            try:
                config = IndicatorConfiguration.from_dict(config_data)
                new_id = self.save_configuration(config, config_id)
                imported_ids.append(new_id)
            except Exception as e:
                print(f"Error importing config {config_id}: {e}")
                continue
        
        return imported_ids


# Global config manager
config_manager = IndicatorConfigManager()

# Flask Blueprint for API endpoints
indicator_api = Blueprint('indicator_api', __name__, url_prefix='/api/indicators')


@indicator_api.route('/available', methods=['GET'])
def get_available_indicators():
    """Get list of all available indicator types."""
    indicators = IndicatorRegistry().get_available_indicators()
    return jsonify({
        'success': True,
        'indicators': indicators
    })


@indicator_api.route('/schema/<indicator_name>', methods=['GET'])
def get_indicator_schema(indicator_name: str):
    """Get UI schema for a specific indicator type."""
    try:
        indicator_class = IndicatorRegistry().get_indicator_class(indicator_name)
        temp_instance = indicator_class()
        schema = temp_instance.get_ui_schema()
        
        return jsonify({
            'success': True,
            'schema': schema
        })
    
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404


@indicator_api.route('/schemas', methods=['GET'])
def get_all_schemas():
    """Get UI schemas for all indicator types."""
    schemas = IndicatorRegistry().get_ui_schemas()
    return jsonify({
        'success': True,
        'schemas': schemas
    })


@indicator_api.route('/configurations', methods=['GET'])
def list_configurations():
    """List all saved indicator configurations."""
    configs = config_manager.list_configurations()
    return jsonify({
        'success': True,
        'configurations': configs
    })


@indicator_api.route('/configurations', methods=['POST'])
def create_configuration():
    """Create a new indicator configuration."""
    try:
        data = request.get_json()
        
        config = IndicatorConfiguration(
            indicator_name=data['indicator_name'],
            display_name=data.get('display_name', data['indicator_name']),
            parameters=data.get('parameters', {}),
            enabled=data.get('enabled', True)
        )
        
        # Validate by creating temporary instance
        IndicatorRegistry().create_indicator(config)
        
        config_id = config_manager.save_configuration(config, data.get('config_id'))
        
        return jsonify({
            'success': True,
            'config_id': config_id,
            'message': 'Configuration created successfully'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@indicator_api.route('/configurations/<config_id>', methods=['GET'])
def get_configuration(config_id: str):
    """Get a specific indicator configuration."""
    config = config_manager.load_configuration(config_id)
    
    if config is None:
        return jsonify({
            'success': False,
            'error': 'Configuration not found'
        }), 404
    
    return jsonify({
        'success': True,
        'configuration': config.to_dict()
    })


@indicator_api.route('/configurations/<config_id>', methods=['PUT'])
def update_configuration(config_id: str):
    """Update an existing indicator configuration."""
    try:
        data = request.get_json()
        
        config = IndicatorConfiguration(
            indicator_name=data['indicator_name'],
            display_name=data.get('display_name', data['indicator_name']),
            parameters=data.get('parameters', {}),
            enabled=data.get('enabled', True)
        )
        
        # Validate by creating temporary instance
        IndicatorRegistry().create_indicator(config)
        
        config_manager.save_configuration(config, config_id)
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated successfully'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@indicator_api.route('/configurations/<config_id>', methods=['DELETE'])
def delete_configuration(config_id: str):
    """Delete an indicator configuration."""
    if config_manager.delete_configuration(config_id):
        return jsonify({
            'success': True,
            'message': 'Configuration deleted successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Configuration not found'
        }), 404


@indicator_api.route('/configurations/export', methods=['POST'])
def export_configurations():
    """Export multiple configurations."""
    data = request.get_json()
    config_ids = data.get('config_ids', [])
    
    export_data = config_manager.export_configuration_set(config_ids)
    
    return jsonify({
        'success': True,
        'export_data': export_data
    })


@indicator_api.route('/configurations/import', methods=['POST'])
def import_configurations():
    """Import multiple configurations."""
    try:
        data = request.get_json()
        import_data = data.get('import_data', {})
        
        imported_ids = config_manager.import_configuration_set(import_data)
        
        return jsonify({
            'success': True,
            'imported_ids': imported_ids,
            'message': f'Imported {len(imported_ids)} configurations'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@indicator_api.route('/test/<config_id>', methods=['POST'])
def test_indicator(config_id: str):
    """Test an indicator with sample data."""
    try:
        # This would need sample tick data for testing
        # For now, just validate the configuration
        indicator = config_manager.create_indicator_instance(config_id)
        
        if indicator is None:
            return jsonify({
                'success': False,
                'error': 'Configuration not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Indicator configuration is valid',
            'indicator_name': indicator.name,
            'parameters': indicator.config.parameters
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400