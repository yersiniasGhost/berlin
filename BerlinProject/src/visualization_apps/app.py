from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import os
import sys
import json
import logging
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict
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

# Optimizer utility functions
def balance_fronts(front: List[IndividualStats]) -> List[IndividualStats]:
    ideal_point = np.min([ind.fitness_values for ind in front], axis=0)
    balanced_front = sorted(front, key=lambda ind: np.linalg.norm(ind.fitness_values - ideal_point))
    return balanced_front

def select_winning_population(number_of_elites: int, fronts: Dict[int, List]) -> [List[IndividualStats]]:
    elitists: List[IndividualStats] = []
    for front in fronts.values():
        sorted_front = balance_fronts(front)
        for stat in sorted_front:
            if len(elitists) < number_of_elites:
                elitists.append(stat)
    return elitists

# Import optimizer WebSocket functions
from routes.optimizer_routes import (
    run_genetic_algorithm_threaded_with_new_indicators, 
    optimization_state,
    save_optimization_results_with_new_indicators
)

@app.route('/')
def index():
    return render_template('home.html')

# ===== WEBSOCKET HANDLERS FOR OPTIMIZER =====

@socketio.on('start_optimization')
def handle_start_optimization(data):
    """Start the genetic algorithm optimization with NEW indicator system"""
    global optimization_state
    
    if optimization_state['running']:
        emit('optimization_error', {'error': 'Optimization already running'})
        return

    # Try to get paths from data, or use temp paths from HTTP call
    ga_config_path = data.get('ga_config_path') or optimization_state.get('ga_config_path_temp')
    data_config_path = data.get('data_config_path') or optimization_state.get('data_config_path_temp')

    if not ga_config_path or not data_config_path:
        emit('optimization_error', {'error': 'Config paths not provided. Make sure to call /api/start_optimization first.'})
        return

    # Reset state and clear cached instances
    optimization_state['running'] = True
    optimization_state['paused'] = False
    optimization_state['current_generation'] = 0
    optimization_state['best_individuals_log'] = []
    optimization_state['ga_instance'] = None  # Clear cached GA instance
    optimization_state['io_instance'] = None  # Clear cached IO instance

    # Start optimization thread with NEW indicator system
    import threading
    optimization_state['thread'] = threading.Thread(
        target=run_genetic_algorithm_threaded_with_new_indicators,
        args=(ga_config_path, data_config_path, socketio)
    )
    optimization_state['thread'].start()

@socketio.on('pause_optimization')
def handle_pause_optimization():
    """Pause the optimization"""
    global optimization_state

    if optimization_state['running']:
        optimization_state['paused'] = True
        emit('optimization_paused', {
            'generation': optimization_state['current_generation'],
            'total_generations': optimization_state['total_generations']
        })
        logger.info("Optimization paused by user")

@socketio.on('resume_optimization')
def handle_resume_optimization():
    """Resume the optimization"""
    global optimization_state

    if optimization_state['running'] and optimization_state['paused']:
        optimization_state['paused'] = False
        emit('optimization_resumed', {
            'generation': optimization_state['current_generation'],
            'total_generations': optimization_state['total_generations']
        })
        logger.info("Optimization resumed by user")

@socketio.on('stop_optimization')
def handle_stop_optimization():
    """Stop the optimization"""
    global optimization_state

    optimization_state['running'] = False
    optimization_state['paused'] = False

    if optimization_state['thread'] and optimization_state['thread'].is_alive():
        optimization_state['thread'].join(timeout=2)

    emit('optimization_stopped', {
        'generation': optimization_state['current_generation'],
        'total_generations': optimization_state['total_generations']
    })
    logger.info("Optimization stopped by user")

@socketio.on('save_current_best')
def handle_save_current_best():
    """Save the current best results without stopping the optimization"""
    global optimization_state
    
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
        
        # Get the current GA config path and test name
        ga_config_path = optimization_state.get('ga_config_path', 'unknown_config.json')
        test_name = optimization_state.get('test_name', 'unknown_test')
        
        # Save current results with timestamp indicating it's a partial save
        test_name_with_partial = f"{test_name}_partial_gen_{optimization_state.get('current_generation', 0)}"
        
        results_info = save_optimization_results_with_new_indicators(
            optimization_state['best_individuals_log'],
            optimization_state['last_best_individual'],
            optimization_state.get('elites', []),
            ga_config_path,
            test_name_with_partial,
            save_timestamp,
            optimization_state.get('processed_indicators', [])
        )
        
        emit('save_current_success', {
            'generation': optimization_state.get('current_generation', 0),
            'total_generations': optimization_state.get('total_generations', 0),
            'results_info': results_info
        })
        
        logger.info(f"✅ Successfully saved current best results at generation {optimization_state.get('current_generation', 0)}")
        
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
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)