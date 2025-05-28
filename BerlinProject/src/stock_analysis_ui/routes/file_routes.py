"""
File browser and config file handling routes
"""

import os
import json
import logging
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

logger = logging.getLogger('FileRoutes')
file_bp = Blueprint('files', __name__)

ALLOWED_EXTENSIONS = {'json'}


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@file_bp.route('/browse')
def browse_files():
    """Simple file browser for JSON config files"""
    try:
        path = request.args.get('path', '')

        # Security: Default to safe directories
        if not path:
            safe_dirs = [
                os.getcwd(),
                os.path.expanduser('~'),
                os.path.dirname(os.path.abspath(__file__))
            ]
            return jsonify({
                'directories': [{'name': os.path.basename(d) or d, 'path': d} for d in safe_dirs if os.path.exists(d)],
                'files': [],
                'current_path': 'Select a directory:'
            })

        if not os.path.exists(path) or not os.path.isdir(path):
            return jsonify({'error': 'Invalid directory'}), 400

        directories = []
        files = []

        try:
            for item in sorted(os.listdir(path)):
                if item.startswith('.'):
                    continue

                item_path = os.path.join(path, item)

                if os.path.isdir(item_path):
                    directories.append({'name': item, 'path': item_path})
                elif item.lower().endswith('.json'):
                    is_config = 'config' in item.lower()
                    files.append({
                        'name': item,
                        'path': item_path,
                        'is_config': is_config,
                        'size': os.path.getsize(item_path)
                    })
        except PermissionError:
            return jsonify({'error': 'Permission denied'}), 403

        parent = os.path.dirname(path) if path != os.path.dirname(path) else None

        return jsonify({
            'current_path': path,
            'parent_path': parent,
            'directories': directories,
            'files': files
        })

    except Exception as e:
        logger.error(f"Error browsing files: {e}")
        return jsonify({'error': str(e)}), 500


@file_bp.route('/validate', methods=['POST'])
def validate_config():
    """Validate a monitor configuration file"""
    try:
        data = request.json
        file_path = data.get('file_path', '')

        if not os.path.exists(file_path):
            return jsonify({'valid': False, 'error': 'File not found'})

        with open(file_path, 'r') as f:
            config_data = json.load(f)

        errors = []

        # Basic validation
        if 'monitor' not in config_data:
            errors.append("Missing 'monitor' section")
        if 'indicators' not in config_data:
            errors.append("Missing 'indicators' section")

        # Get summary info
        summary = {
            'name': config_data.get('monitor', {}).get('name', 'Unnamed'),
            'indicators': len(config_data.get('indicators', [])),
            'bars': list(config_data.get('monitor', {}).get('bars', {}).keys())
        }

        return jsonify({
            'valid': len(errors) == 0,
            'errors': errors,
            'summary': summary,
            'file_name': os.path.basename(file_path)
        })

    except json.JSONDecodeError:
        return jsonify({'valid': False, 'error': 'Invalid JSON format'})
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)})


@file_bp.route('/upload', methods=['POST'])
def upload_config():
    """Upload a configuration file"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']

        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file'}), 400

        filename = secure_filename(file.filename)

        # Save to uploads directory
        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)

        # Quick validation
        try:
            with open(file_path, 'r') as f:
                json.load(f)
        except json.JSONDecodeError:
            os.remove(file_path)
            return jsonify({'success': False, 'error': 'Invalid JSON file'}), 400

        return jsonify({
            'success': True,
            'file_path': file_path,
            'file_name': filename
        })

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500