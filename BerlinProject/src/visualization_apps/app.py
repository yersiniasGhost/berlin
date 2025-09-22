from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import os
import sys
import json
import logging
import math
import threading
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from werkzeug.utils import secure_filename

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..'))

# Import the new indicator system
from indicator_triggers.indicator_api import indicator_api, config_manager
from indicator_triggers.indicator_base import IndicatorRegistry

# Import optimizer types
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('VisualizationApp')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'visualization-apps-secret-key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
socketio = SocketIO(app, cors_allowed_origins="*")

# Register the new indicator API blueprint
app.register_blueprint(indicator_api)

# Import and register route blueprints
from routes.replay_routes import replay_bp
from routes.optimizer_routes import optimizer_bp
from routes.indicator_routes import indicator_bp

app.register_blueprint(replay_bp)
app.register_blueprint(optimizer_bp) 
app.register_blueprint(indicator_bp)

# Create upload folders
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Utility functions from your existing apps
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'json'

def sanitize_nan_values(obj):
    """
    Recursively sanitize NaN values in a data structure for JSON compatibility.
    Converts NaN to None (null in JSON), and handles nested lists/dicts.
    """
    if isinstance(obj, dict):
        return {key: sanitize_nan_values(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_nan_values(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj):
            return None
        elif math.isinf(obj):
            return None  # Convert infinity to null as well
        else:
            return obj
    else:
        return obj

# Import optimizer utility functions from routes to avoid duplication
from routes.optimizer_routes import balance_fronts, select_winning_population

class OptimizationState:
    """Thread-safe optimization state management"""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._state = {
            'running': False,
            'paused': False,
            'current_generation': 0,
            'total_generations': 0,
            'best_individuals_log': [],
            'last_best_individual': None,
            'elites': [],
            'thread': None,
            'ga_instance': None,
            'io_instance': None,
            'test_name': None,
            'ga_config_path': None,
            'data_config_path_temp': None,
            'ga_config_path_temp': None,
            'timestamp': None,
            'processed_indicators': []
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Thread-safe get operation"""
        with self._lock:
            return self._state.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Thread-safe set operation"""
        with self._lock:
            self._state[key] = value
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Thread-safe bulk update operation"""
        with self._lock:
            self._state.update(updates)
    
    def reset_optimization_state(self) -> None:
        """Reset optimization-specific state while preserving config paths"""
        with self._lock:
            ga_config_path_temp = self._state.get('ga_config_path_temp')
            data_config_path_temp = self._state.get('data_config_path_temp')
            
            self._state.update({
                'running': False,
                'paused': False,
                'current_generation': 0,
                'total_generations': 0,
                'best_individuals_log': [],
                'last_best_individual': None,
                'elites': [],
                'thread': None,
                'ga_instance': None,
                'io_instance': None,
                'test_name': None,
                'ga_config_path': None,
                'timestamp': None,
                'processed_indicators': []
            })
            
            if ga_config_path_temp:
                self._state['ga_config_path_temp'] = ga_config_path_temp
            if data_config_path_temp:
                self._state['data_config_path_temp'] = data_config_path_temp
    
    def is_running(self) -> bool:
        """Thread-safe check if optimization is running"""
        with self._lock:
            return self._state.get('running', False)
    
    def is_paused(self) -> bool:
        """Thread-safe check if optimization is paused"""
        with self._lock:
            return self._state.get('paused', False)

optimization_state = OptimizationState()

# Import optimizer WebSocket functions
from routes.optimizer_routes import (
    run_genetic_algorithm_threaded_with_new_indicators, 
    save_optimization_results_with_new_indicators
)

@app.route('/')
def index():
    return render_template('home.html')

# ===== WEBSOCKET HANDLERS FOR OPTIMIZER =====

@socketio.on('start_optimization')
def handle_start_optimization(data):
    """Start the genetic algorithm optimization with NEW indicator system"""
    
    if optimization_state.is_running():
        emit('optimization_error', {'error': 'Optimization already running'})
        return

    # Try to get paths from data, or use temp paths from HTTP call
    ga_config_path = data.get('ga_config_path') or optimization_state.get('ga_config_path_temp')
    data_config_path = data.get('data_config_path') or optimization_state.get('data_config_path_temp')

    if not ga_config_path or not data_config_path:
        emit('optimization_error', {'error': 'Config paths not provided. Make sure to call /api/start_optimization first.'})
        return

    # Reset state and clear cached instances using thread-safe method
    optimization_state.update({
        'running': True,
        'paused': False,
        'current_generation': 0,
        'best_individuals_log': [],
        'ga_instance': None,  # Clear cached GA instance
        'io_instance': None   # Clear cached IO instance
    })

    # Start optimization thread with NEW indicator system
    thread = threading.Thread(
        target=run_genetic_algorithm_threaded_with_new_indicators,
        args=(ga_config_path, data_config_path, socketio, optimization_state)
    )
    optimization_state.set('thread', thread)
    thread.start()

@socketio.on('pause_optimization')
def handle_pause_optimization():
    """Pause the optimization"""

    if optimization_state.is_running():
        optimization_state.set('paused', True)
        emit('optimization_paused', {
            'generation': optimization_state.get('current_generation'),
            'total_generations': optimization_state.get('total_generations')
        })
        logger.info("Optimization paused by user")

@socketio.on('resume_optimization')
def handle_resume_optimization():
    """Resume the optimization"""

    if optimization_state.is_running() and optimization_state.is_paused():
        optimization_state.set('paused', False)
        emit('optimization_resumed', {
            'generation': optimization_state.get('current_generation'),
            'total_generations': optimization_state.get('total_generations')
        })
        logger.info("Optimization resumed by user")

@socketio.on('stop_optimization')
def handle_stop_optimization():
    """Stop the optimization"""

    optimization_state.update({
        'running': False,
        'paused': False
    })

    thread = optimization_state.get('thread')
    if thread and thread.is_alive():
        thread.join(timeout=10)  # Increased timeout for better cleanup
        if thread.is_alive():
            logger.warning("Optimization thread did not terminate gracefully within timeout")

    emit('optimization_stopped', {
        'generation': optimization_state.get('current_generation'),
        'total_generations': optimization_state.get('total_generations')
    })
    logger.info("Optimization stopped by user")

@socketio.on('save_current_best')
def handle_save_current_best():
    """Save the current best results without stopping the optimization"""
    
    logger.info("📁 Saving current best results with NEW indicator system...")
    
    # Check if we have current results to save
    if not optimization_state.get('last_best_individual') or not optimization_state.get('best_individuals_log'):
        emit('save_current_error', {
            'error': 'No optimization results available to save yet'
        })
        return
    
    try:
        # Generate timestamp for this save
        save_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        
        # Get the current GA config path and test name (thread-safe)
        ga_config_path = optimization_state.get('ga_config_path', 'unknown_config.json')
        test_name = optimization_state.get('test_name', 'unknown_test')
        current_gen = optimization_state.get('current_generation', 0)
        
        # Save current results with timestamp indicating it's a partial save
        test_name_with_partial = f"{test_name}_partial_gen_{current_gen}"
        
        results_info = save_optimization_results_with_new_indicators(
            optimization_state.get('best_individuals_log', []),
            optimization_state.get('last_best_individual'),
            optimization_state.get('elites', []),
            ga_config_path,
            test_name_with_partial,
            save_timestamp,
            optimization_state.get('processed_indicators', [])
        )
        
        emit('save_current_success', {
            'generation': current_gen,
            'total_generations': optimization_state.get('total_generations', 0),
            'results_info': results_info
        })
        
        logger.info(f"✅ Successfully saved current best results at generation {current_gen}")
        
    except Exception as e:
        logger.error(f"❌ Error saving current best: {e}")
        emit('save_current_error', {
            'error': str(e)
        })

@app.errorhandler(404)
def not_found(error):
    return render_template('base.html'), 404

@app.errorhandler(500)  
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    uploads_dir = Path('uploads')
    uploads_dir.mkdir(exist_ok=True)
    logger.info(f"Created uploads directory: {uploads_dir.absolute()}")
    
    logger.info("🚀 Starting Visualization Apps with NEW Indicator System")
    logger.info("   - Replay Visualization: /replay")
    logger.info("   - Optimizer Visualization: /optimizer") 
    logger.info("   - Indicator Visualization: /indicator")
    logger.info("   - Indicator API: /api/indicators/*")
    
    # Start the Flask-SocketIO application
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False, log_output=True)
