from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import os
import math
import threading
from datetime import datetime
from pathlib import Path

# Import and register route blueprints
from routes.optimization_state import OptimizationState
from routes.replay_routes import replay_bp
from routes.optimizer_routes import optimizer_bp
from routes.indicator_routes import indicator_bp
from routes.indicator_route import indicator_api
from routes.monitor_config_routes import monitor_config_bp

from mlf_utils.log_manager import LogManager
# Configure logging
lm = LogManager('mlf-app.log')
lm.configure_library_loggers()
logger = lm.get_logger("visualization-app")


app = Flask(__name__)
app.config['SECRET_KEY'] = 'visualization-apps-secret-key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
socketio = SocketIO(app, cors_allowed_origins="*")

# Register the new indicator API blueprint
app.register_blueprint(indicator_api)
app.register_blueprint(replay_bp)
app.register_blueprint(optimizer_bp)
app.register_blueprint(indicator_bp)
app.register_blueprint(monitor_config_bp)

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
    
    if OptimizationState().is_running():
        emit('optimization_error', {'error': 'Optimization already running'})
        return

    # Try to get paths from data, or use temp paths from HTTP call
    ga_config_path = data.get('ga_config_path') or OptimizationState().get('ga_config_path_temp')
    data_config_path = data.get('data_config_path') or OptimizationState().get('data_config_path_temp')

    if not ga_config_path or not data_config_path:
        emit('optimization_error', {'error': 'Config paths not provided. Make sure to call /api/start_optimization first.'})
        return

    # Reset state and clear cached instances using thread-safe method
    OptimizationState().update({
        'running': True,
        'paused': False,
        'current_generation': 0,
        'best_individuals_log': [],
        'elites': [],
        'ga_instance': None,  # Clear cached GA instance
        'io_instance': None   # Clear cached IO instance
    })

    # Start optimization thread with NEW indicator system
    thread = threading.Thread(
        target=run_genetic_algorithm_threaded_with_new_indicators,
        args=(ga_config_path, data_config_path, socketio, OptimizationState())
    )
    OptimizationState().set('thread', thread)
    thread.start()


@socketio.on('pause_optimization')
def handle_pause_optimization():
    """Pause the optimization"""

    if OptimizationState().is_running():
        OptimizationState().set('paused', True)
        emit('optimization_paused', {
            'generation': OptimizationState().get('current_generation'),
            'total_generations': OptimizationState().get('total_generations')
        })
        logger.info("Optimization paused by user")


@socketio.on('resume_optimization')
def handle_resume_optimization():
    """Resume the optimization"""

    if OptimizationState().is_running() and OptimizationState().is_paused():
        OptimizationState().set('paused', False)
        emit('optimization_resumed', {
            'generation': OptimizationState().get('current_generation'),
            'total_generations': OptimizationState().get('total_generations')
        })
        logger.info("Optimization resumed by user")

@socketio.on('stop_optimization')
def handle_stop_optimization():
    """Stop the optimization"""

    OptimizationState().update({
        'running': False,
        'paused': False
    })

    thread = OptimizationState().get('thread')
    if thread and thread.is_alive():
        thread.join(timeout=10)  # Increased timeout for better cleanup
        if thread.is_alive():
            logger.warning("Optimization thread did not terminate gracefully within timeout")

    emit('optimization_stopped', {
        'generation': OptimizationState().get('current_generation'),
        'total_generations': OptimizationState().get('total_generations')
    })
    logger.info("Optimization stopped by user")

@socketio.on('save_current_best')
def handle_save_current_best():
    """Save the current best results without stopping the optimization"""
    
    logger.info("📁 Saving current best results with NEW indicator system...")
    
    # Check if we have current results to save
    if not OptimizationState().get('last_best_individual') or not OptimizationState().get('best_individuals_log'):
        emit('save_current_error', {
            'error': 'No optimization results available to save yet'
        })
        return
    
    try:
        # Generate timestamp for this save
        save_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        
        # Get the current GA config path and test name (thread-safe)
        ga_config_path = OptimizationState().get('ga_config_path', 'unknown_config.json')
        test_name = OptimizationState().get('test_name', 'unknown_test')
        current_gen = OptimizationState().get('current_generation', 0)
        
        # Save current results with timestamp indicating it's a partial save
        test_name_with_partial = f"{test_name}_partial_gen_{current_gen}"
        
        results_info = save_optimization_results_with_new_indicators(
            OptimizationState().get('best_individuals_log', []),
            OptimizationState().get('last_best_individual'),
            OptimizationState().get('elites', []),
            ga_config_path,
            test_name_with_partial,
            save_timestamp,
            OptimizationState().get('processed_indicators', [])
        )
        
        emit('save_current_success', {
            'generation': current_gen,
            'total_generations': OptimizationState().get('total_generations', 0),
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
    socketio.run(app, debug=True, host='0.0.0.0', port=5003, use_reloader=False, log_output=True, allow_unsafe_werkzeug=True)
