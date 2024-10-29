from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)


# This will handle the POST request from Rails
@app.route('/start', methods=['POST'])
def start_process():
    config = request.get_json()
    print(f"Received config: {config}")
    # You can trigger socket events or start any processing here

    # Emit an event to notify the Rails app about the process initiation
    socketio.emit('process_started', {'status': 'started', 'config': config})

    # Return a response to the Rails app
    return jsonify({'status': 'success', 'message': 'Python process started'})


# This is to run the Flask app
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
