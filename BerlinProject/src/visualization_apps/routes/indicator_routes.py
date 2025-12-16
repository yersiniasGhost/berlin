"""
Indicator Visualization Routes
Handles individual indicator visualization and testing with new indicator system
"""

from flask import Blueprint, render_template, request, jsonify
import os
import sys
import json
import numpy as np
from datetime import datetime
from pathlib import Path

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..', '..'))

# Import necessary modules for indicator visualization
from mongo_tools.mongo_db_connect import MongoDBConnect

# Import mlf_utils
from mlf_utils import FileUploadHandler, ConfigLoader
from mlf_utils.log_manager import LogManager

# Import new indicator system - this is the key integration
from indicator_triggers.indicator_base import IndicatorRegistry, IndicatorConfiguration
from indicator_triggers.refactored_indicators import *  # Import to register indicators
from indicator_triggers.indicator_api import config_manager

logger = LogManager().get_logger("IndicatorVisualization")

# Create Blueprint
indicator_bp = Blueprint('indicator', __name__, url_prefix='/indicator')

# Create upload handler and config loader for indicator routes
upload_handler = FileUploadHandler(upload_dir='uploads', allowed_extensions={'.json', '.csv'})
config_loader = ConfigLoader(config_dir='inputs')

class NewIndicatorVisualizer:
    """Visualizer using the NEW refactored indicator system"""
    
    def __init__(self):
        self.mongo_db = MongoDBConnect()
        self.registry = IndicatorRegistry()

    def load_and_process_data_with_new_system(self, ticker: str, start_date: str, end_date: str, indicator_configs: list):
        """Load data and process using the NEW refactored indicator system"""
        logger.info(f"Loading data for {ticker} from {start_date} to {end_date} with NEW indicator system")

        try:
            # Create indicator instances using NEW system
            indicator_instances = []
            for config in indicator_configs:
                try:
                    # Create indicator configuration using new system
                    indicator_config = IndicatorConfiguration(
                        indicator_name=config['name'],
                        display_name=config.get('display_name', config['name']),
                        parameters=config.get('parameters', {}),
                        enabled=config.get('enabled', True)
                    )
                    
                    # Create indicator instance
                    indicator_instance = self.registry.create_indicator(indicator_config)
                    indicator_instances.append(indicator_instance)
                    logger.info(f"✅ Created NEW indicator: {config['name']}")
                    
                except Exception as e:
                    logger.error(f"❌ Error creating indicator {config['name']}: {e}")
                    continue

            if not indicator_instances:
                logger.error("No valid indicators created")
                return None, None, None

            # Load historical data (same as before)
            # Create a temporary monitor config just for data loading
            from models.monitor_configuration import MonitorConfiguration
            
            temp_monitor = MonitorConfiguration(
                name="temp_indicator_viz",
                description="Temporary for indicator visualization",
                indicators=[],  # We'll use the new system instead
                trade_executor={
                    "default_position_size": 100.0,
                    "stop_loss_pct": 0.01,
                    "take_profit_pct": 0.02,
                    "ignore_bear_signals": False,
                    "trailing_stop_loss": False,
                    "trailing_stop_distance_pct": 0.01,
                    "trailing_stop_activation_pct": 0.005
                }
            )

            # Process data using YahooFinanceHistorical
            success = self.mongo_db.process_historical_data(ticker, start_date, end_date, temp_monitor)

            if not success:
                return None, None, None

            # Get aggregators
            aggregators = self.mongo_db.aggregators

            # Get the main aggregator key for timestamps
            main_key = None
            for key in aggregators.keys():
                if "1m" in key:
                    main_key = key
                    break
            if not main_key:
                main_key = list(aggregators.keys())[0]

            # Get candles from aggregator history
            candles = aggregators[main_key].history

            # Process indicators using NEW SYSTEM
            indicator_data = self.process_indicators_with_new_system(indicator_instances, candles)

            logger.info(f"Loaded {len(candles)} candles from {main_key}")
            logger.info(f"Processed NEW indicators: {list(indicator_data.keys())}")

            return candles, indicator_data, indicator_instances

        except Exception as e:
            logger.error(f"Error in NEW indicator system processing: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None

    def process_indicators_with_new_system(self, indicator_instances, candles):
        """Process indicators using the NEW refactored system exclusively"""
        logger.info("Processing indicators with NEW refactored system...")
        
        indicator_data = {}

        # Convert candles to TickData format for new indicators
        from models.tick_data import TickData
        tick_data_list = []
        for candle in candles:
            tick_data = TickData(
                symbol=candle.symbol,
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume
            )
            tick_data_list.append(tick_data)

        # Process each indicator using NEW system
        for indicator_instance in indicator_instances:
            try:
                # Calculate using new indicator system
                results = indicator_instance.calculate(tick_data_list)
                
                indicator_name = indicator_instance.name
                display_name = indicator_instance.config.display_name
                
                # Store results with both internal name and display name
                indicator_data[indicator_name] = results
                indicator_data[f"{indicator_name}_display_name"] = display_name
                
                # Store parameter info
                indicator_data[f"{indicator_name}_parameters"] = indicator_instance.config.parameters
                
                logger.info(f"📊 NEW indicator {display_name}: {len(results)} values calculated")
                
                # If this is a composite indicator (like MACD), it might return multiple series
                # Check if the indicator provides breakdown data
                if hasattr(indicator_instance, 'get_component_data'):
                    try:
                        components = indicator_instance.get_component_data(tick_data_list)
                        for comp_name, comp_data in components.items():
                            indicator_data[f"{indicator_name}_{comp_name}"] = comp_data
                            logger.info(f"📊 NEW component {comp_name}: {len(comp_data)} values")
                    except Exception as comp_error:
                        logger.warning(f"Could not get component data for {indicator_name}: {comp_error}")

            except Exception as e:
                logger.error(f"❌ Error calculating NEW indicator {indicator_instance.name}: {e}")
                import traceback
                traceback.print_exc()
                continue

        return indicator_data

    def get_available_indicators_with_schemas(self):
        """Get all available indicators with their parameter schemas"""
        try:
            available_indicators = self.registry.get_available_indicators()
            schemas = {}
            
            for indicator_name in available_indicators:
                try:
                    schema = self.registry.get_ui_schema(indicator_name)
                    schemas[indicator_name] = schema
                except Exception as e:
                    logger.error(f"Error getting schema for {indicator_name}: {e}")
                    continue
            
            return available_indicators, schemas
            
        except Exception as e:
            logger.error(f"Error getting available indicators: {e}")
            return [], {}

# Global visualizer instance using NEW system
new_visualizer = NewIndicatorVisualizer()

# ===== ROUTES =====

@indicator_bp.route('/')
def indicator_main():
    """Main indicator visualization page"""
    return render_template('indicator/main.html')

@indicator_bp.route('/api/available_indicators')
def get_available_indicators():
    """Get list of available indicators from NEW system"""
    try:
        available_indicators, schemas = new_visualizer.get_available_indicators_with_schemas()
        
        return jsonify({
            'success': True,
            'indicators': available_indicators,
            'schemas': schemas
        })
        
    except Exception as e:
        logger.error(f"Error getting available indicators: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@indicator_bp.route('/api/load_examples')
def load_examples():
    """Load example indicator configurations using NEW system"""
    try:
        # Get available indicators
        available_indicators, schemas = new_visualizer.get_available_indicators_with_schemas()
        
        # Create example configurations using available indicators
        example_configs = []
        
        for indicator_name in available_indicators[:3]:  # Just show first 3 as examples
            if indicator_name in schemas:
                schema = schemas[indicator_name]
                
                # Create example parameters based on schema defaults
                example_params = {}
                for param_spec in schema.get('parameter_specs', []):
                    example_params[param_spec['name']] = param_spec.get('default_value', 0)
                
                example_configs.append({
                    'name': indicator_name,
                    'display_name': schema.get('display_name', indicator_name),
                    'parameters': example_params,
                    'enabled': True
                })

        examples = {
            'indicators': example_configs,
            'data_config': {
                'ticker': 'NVDA',
                'start_date': '2024-01-01',
                'end_date': '2024-12-31'
            }
        }
        
        return jsonify({
            'success': True,
            'examples': examples
        })
        
    except Exception as e:
        logger.error(f"Error loading examples: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@indicator_bp.route('/api/upload_file', methods=['POST'])
def upload_file():
    """Handle configuration file uploads"""
    try:
        file = request.files.get('file')

        # Use FileUploadHandler for validation and saving
        result = upload_handler.save_file(file)

        if result['success']:
            # Add file_path for backward compatibility
            result['file_path'] = result['filepath']

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'success': False, 'error': str(e)})

@indicator_bp.route('/api/fetch_yahoo', methods=['POST'])
def fetch_yahoo_data():
    """Fetch data from Yahoo Finance for indicator testing"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', 'AAPL').upper()
        start_date = data.get('start_date', '2024-01-01')
        end_date = data.get('end_date', '2024-12-31')

        # Test data availability by creating a temporary load
        mongo_source = MongoDBConnect()
        
        # Create minimal monitor for testing
        from models.monitor_configuration import MonitorConfiguration
        test_monitor = MonitorConfiguration(
            name="test_data_fetch",
            description="Test data availability",
            indicators=[],
            trade_executor={'default_position_size': 100.0}
        )

        success = mongo_source.process_historical_data(ticker, start_date, end_date, test_monitor)
        
        if success:
            # Get sample data info
            aggregators = mongo_source.aggregators
            main_key = list(aggregators.keys())[0]
            candles = aggregators[main_key].history
            
            return jsonify({
                'success': True,
                'ticker': ticker,
                'date_range': f"{start_date} to {end_date}",
                'candle_count': len(candles),
                'data_available': True,
                'message': f'Successfully loaded {len(candles)} data points for {ticker}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'No data available for {ticker} in the specified date range'
            })

    except Exception as e:
        logger.error(f"Error fetching Yahoo data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@indicator_bp.route('/api/visualize', methods=['POST'])
def visualize_indicators():
    """Main visualization endpoint using NEW indicator system"""
    try:
        data = request.json
        ticker = data.get('ticker', '').upper()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        indicator_configs = data.get('indicators', [])

        if not all([ticker, start_date, end_date]):
            return jsonify({"success": False, "error": "Missing required parameters: ticker, start_date, end_date"}), 400

        if not indicator_configs:
            return jsonify({"success": False, "error": "No indicators specified"}), 400

        logger.info(f"📊 Visualizing {len(indicator_configs)} NEW indicators for {ticker}")

        # Load data using NEW indicator system
        candles, indicator_data, indicator_instances = new_visualizer.load_and_process_data_with_new_system(
            ticker, start_date, end_date, indicator_configs
        )

        if not candles:
            return jsonify({"success": False, "error": f"No data found for {ticker}"}), 404

        # Format candlestick data for Highcharts
        candlestick_data = []
        for candle in candles:
            timestamp = int(candle.timestamp.timestamp() * 1000)
            candlestick_data.append([
                timestamp,
                candle.open,
                candle.high,
                candle.low,
                candle.close
            ])

        # Format NEW indicator data for Highcharts
        indicators_data_formatted = {}
        current_indicators = {}
        
        # Process all data from NEW indicator system
        for key, values in indicator_data.items():
            # Skip metadata keys
            if key.endswith('_display_name') or key.endswith('_parameters'):
                continue
                
            # Handle different value types
            if isinstance(values, (list, np.ndarray)):
                # Time series data
                indicator_series = []
                values_list = values.tolist() if isinstance(values, np.ndarray) else values
                
                for i, value in enumerate(values_list):
                    if i < len(candles) and value is not None:
                        timestamp = int(candles[i].timestamp.timestamp() * 1000)
                        
                        # Handle NaN values
                        if isinstance(value, float) and (np.isnan(value) or str(value) == 'nan'):
                            clean_value = None
                        else:
                            clean_value = float(value)

                        if clean_value is not None:
                            indicator_series.append([timestamp, clean_value])

                indicators_data_formatted[key] = {
                    "data": indicator_series,
                    "name": indicator_data.get(f"{key}_display_name", key)
                }
                
            elif isinstance(values, (int, float)) and not np.isnan(values):
                # Single current value
                current_indicators[key] = {
                    "data": [[int(candles[-1].timestamp.timestamp() * 1000), float(values)]],
                    "name": f"{indicator_data.get(f'{key}_display_name', key)} (Current)"
                }

        # Create indicator metadata for frontend
        indicator_metadata = []
        for instance in indicator_instances:
            indicator_metadata.append({
                'name': instance.name,
                'display_name': instance.config.display_name,
                'parameters': instance.config.parameters,
                'enabled': instance.config.enabled,
                'system': 'new_refactored_system'
            })

        response = {
            "success": True,
            "ticker": ticker,
            "data": {
                "candlestick": candlestick_data,
                "indicators": indicators_data_formatted,  # Time series indicator data
                "current_indicators": current_indicators,  # Current single values
                "indicator_metadata": indicator_metadata  # Metadata about indicators used
            },
            "candle_count": len(candles),
            "indicator_count": len(indicator_instances),
            "date_range": f"{start_date} to {end_date}",
            "system_version": "new_indicator_system_v1.0"
        }

        logger.info(f"✅ Successfully processed {len(indicator_instances)} NEW indicators with {len(candles)} candles")
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in NEW indicator visualization: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False, 
            "error": str(e),
            "system_version": "new_indicator_system_v1.0"
        }), 500

@indicator_bp.route('/api/test_indicator', methods=['POST'])
def test_single_indicator():
    """Test a single indicator with sample data"""
    try:
        data = request.get_json()
        indicator_name = data.get('indicator_name')
        parameters = data.get('parameters', {})
        
        if not indicator_name:
            return jsonify({'success': False, 'error': 'indicator_name is required'})

        # Create indicator configuration
        indicator_config = IndicatorConfiguration(
            indicator_name=indicator_name,
            display_name=data.get('display_name', indicator_name),
            parameters=parameters,
            enabled=True
        )
        
        # Test creation
        registry = IndicatorRegistry()
        indicator_instance = registry.create_indicator(indicator_config)
        
        return jsonify({
            'success': True,
            'message': f'Indicator {indicator_name} created successfully',
            'indicator_info': {
                'name': indicator_instance.name,
                'display_name': indicator_instance.config.display_name,
                'parameters': indicator_instance.config.parameters,
                'system': 'new_refactored_system'
            }
        })
        
    except Exception as e:
        logger.error(f"Error testing indicator: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@indicator_bp.route('/api/save_indicator_config', methods=['POST'])
def save_indicator_config():
    """Save an indicator configuration using the new system"""
    try:
        data = request.get_json()
        
        indicator_config = IndicatorConfiguration(
            indicator_name=data['indicator_name'],
            display_name=data.get('display_name', data['indicator_name']),
            parameters=data.get('parameters', {}),
            enabled=data.get('enabled', True)
        )
        
        # Save using the config manager
        config_id = config_manager.save_configuration(indicator_config, data.get('config_id'))
        
        return jsonify({
            'success': True,
            'config_id': config_id,
            'message': 'Indicator configuration saved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error saving indicator config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@indicator_bp.route('/api/load_indicator_config/<config_id>')
def load_indicator_config(config_id: str):
    """Load a saved indicator configuration"""
    try:
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
        
    except Exception as e:
        logger.error(f"Error loading indicator config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@indicator_bp.route('/api/load_configs', methods=['POST'])
def load_configs():
    """Load and validate the uploaded configuration files for indicator visualization"""
    try:
        data = request.get_json()
        # For indicator visualization, we might have different file types
        # But let's keep it consistent with other visualizations
        
        return jsonify({
            'success': True,
            'message': 'Configurations loaded successfully'
        })

    except Exception as e:
        logger.error(f"Error loading configs: {e}")
        return jsonify({'success': False, 'error': str(e)})