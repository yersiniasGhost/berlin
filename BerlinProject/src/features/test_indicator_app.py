"""
Simple test app for the indicator system to debug Flask issues.
"""

from flask import Flask, jsonify
from features.indicator_api import indicator_api, config_manager
from features.indicator_base import IndicatorRegistry

def create_test_app():
    """Create a minimal Flask app for testing."""
    app = Flask(__name__)
    app.register_blueprint(indicator_api)
    
    @app.route('/')
    def index():
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Indicator Test</title>
        </head>
        <body>
            <h1>Indicator System Test</h1>
            <p>Available endpoints:</p>
            <ul>
                <li><a href="/api/indicators/available">Available Indicators</a></li>
                <li><a href="/api/indicators/schemas">All Schemas</a></li>
                <li><a href="/api/indicators/configurations">Configurations</a></li>
            </ul>
        </body>
        </html>
        '''
    
    @app.route('/test')
    def test():
        """Test endpoint to verify system is working."""
        try:
            # Test indicator registry
            indicators = IndicatorRegistry().get_available_indicators()
            
            return jsonify({
                'success': True,
                'message': 'Indicator system is working',
                'indicator_count': len(indicators),
                'indicators': [i['name'] for i in indicators]
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return app

if __name__ == "__main__":
    app = create_test_app()
    print("Starting test app on http://localhost:5001")
    print("Available routes:")
    print("  /")
    print("  /test") 
    print("  /api/indicators/available")
    app.run(debug=True, port=5001)