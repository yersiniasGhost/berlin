# MLF Utils - Utility Library Documentation

Common utilities for the BerlinProject MLF (Machine Learning Framework) applications.

## Overview

This package provides shared utilities for data sanitization, file handling, configuration management, error handling, and caching across all MLF applications.

---

## Modules

### data_sanitization.py

Utilities for sanitizing data structures for JSON serialization.

#### Functions

**sanitize_nan_values(obj)**
```python
from mlf_utils import sanitize_nan_values

# Sanitize data for JSON response
data = {'value': float('nan'), 'price': 100.0}
clean_data = sanitize_nan_values(data)
# Returns: {'value': None, 'price': 100.0}

# Works with nested structures
nested = {
    'stats': {'avg': float('inf'), 'count': 10},
    'values': [1.0, float('nan'), 3.0]
}
clean_nested = sanitize_nan_values(nested)
# Returns: {'stats': {'avg': None, 'count': 10}, 'values': [1.0, None, 3.0]}
```

---

### file_handlers.py

Centralized file upload handling with validation and security.

#### FileUploadHandler Class

**Basic Usage**
```python
from mlf_utils import FileUploadHandler
from flask import request, jsonify

# Create handler instance
upload_handler = FileUploadHandler(
    upload_dir='uploads',
    allowed_extensions={'.json', '.csv'},
    max_file_size=16 * 1024 * 1024  # 16MB
)

# In Flask route
@app.route('/api/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    result = upload_handler.save_file(file, prefix='config')

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400
```

**Advanced Usage**
```python
# Validate without saving
is_valid, error = upload_handler.validate_file(file)
if not is_valid:
    return jsonify({'error': error}), 400

# List uploaded files
json_files = upload_handler.list_files(extension='.json')

# Delete file
success, error = upload_handler.delete_file('old_config.json')
```

---

### config_loader.py

Configuration file loading and management with consistent error handling.

#### ConfigLoader Class

**Basic Usage**
```python
from mlf_utils import ConfigLoader

# Create loader instance
config_loader = ConfigLoader(config_dir='inputs')

# Load configuration
success, config, error = config_loader.load_config('monitor_config.json')
if success:
    print(f"Loaded config: {config}")
else:
    print(f"Error: {error}")
```

**Saving Configurations**
```python
# Save configuration
config_data = {
    'name': 'My Strategy',
    'parameters': {'period': 20}
}

success, error = config_loader.save_config(
    'my_strategy.json',
    config_data,
    overwrite=True
)
```

**Utility Methods**
```python
# List all configs
configs = config_loader.list_configs(extension='.json')

# Check if config exists
exists = config_loader.config_exists('my_config.json')

# Delete config
success, error = config_loader.delete_config('old_config.json')

# Load from absolute path
success, config, error = config_loader.load_config_from_path('/tmp/test.json')
```

---

### error_handlers.py

Standardized error handling for Flask API responses.

#### Exception Classes

**Basic Error Handling**
```python
from mlf_utils import (
    ValidationError,
    NotFoundError,
    create_error_response,
    create_success_response
)

@app.route('/api/data', methods=['GET'])
def get_data():
    try:
        # Your logic here
        if not data_id:
            raise ValidationError(
                'Invalid request',
                validation_errors=['data_id is required']
            )

        data = load_data(data_id)
        if not data:
            raise NotFoundError(
                f'Data not found: {data_id}',
                resource_type='data'
            )

        return create_success_response({'data': data})

    except Exception as e:
        return create_error_response(e)
```

**Error Response Format**
```json
{
  "success": false,
  "error": {
    "message": "Validation failed",
    "code": "VALIDATION_ERROR",
    "validation_errors": ["parameter 'ticker' is required"]
  }
}
```

**Available Error Classes**
- `APIError` - Base error (HTTP 500)
- `ValidationError` - Validation errors (HTTP 400)
- `NotFoundError` - Resource not found (HTTP 404)
- `ConfigurationError` - Config errors (HTTP 400)
- `ProcessingError` - Processing errors (HTTP 500)

**Helper Functions**
```python
# Handle validation errors
return handle_validation_error(['ticker is required', 'invalid date format'])

# Handle not found
return handle_not_found('Configuration', identifier='my_config.json')

# Handle missing parameter
return handle_missing_parameter('ticker')
```

---

### cache_manager.py

Time-based caching with TTL (Time To Live) support.

#### CacheManager Class

**Basic Usage**
```python
from mlf_utils import CacheManager

# Create cache instance
cache = CacheManager(ttl=300, name='my_cache')  # 5 minutes TTL

# Set value
cache.set('user_data', {'name': 'John', 'role': 'admin'})

# Get value (returns None if expired)
data = cache.get('user_data')

# Clear cache
cache.clear()

# Get statistics
stats = cache.get_stats()
# Returns: {'hits': 10, 'misses': 3, 'hit_rate_percent': 76.92, ...}
```

**Function Caching Decorator**
```python
from mlf_utils import cached

@cached(ttl=600)  # Cache for 10 minutes
def expensive_function(param1, param2):
    # ... expensive computation ...
    return result

# First call: executes function
result = expensive_function('a', 'b')

# Second call within 10 minutes: returns cached result
result = expensive_function('a', 'b')  # Instant!
```

**Global Cache Instances**
```python
from mlf_utils import indicator_schema_cache, config_cache, data_cache

# Use pre-configured global caches
schemas = indicator_schema_cache.get('schemas')
if not schemas:
    schemas = load_schemas()
    indicator_schema_cache.set('schemas', schemas)
```

---

## Usage Examples

### Complete Flask Route Example

```python
from flask import Blueprint, request, jsonify
from mlf_utils import (
    FileUploadHandler,
    ConfigLoader,
    sanitize_nan_values,
    create_error_response,
    create_success_response,
    ValidationError,
    config_cache
)

# Initialize utilities
upload_handler = FileUploadHandler(upload_dir='uploads')
config_loader = ConfigLoader(config_dir='configs')

bp = Blueprint('api', __name__)

@bp.route('/upload', methods=['POST'])
def upload_config():
    """Upload configuration file"""
    try:
        file = request.files.get('file')
        result = upload_handler.save_file(file, prefix='config')

        if not result['success']:
            raise ValidationError(result['error'])

        return create_success_response(
            data={'filepath': result['filepath']},
            message='File uploaded successfully'
        )

    except Exception as e:
        return create_error_response(e)


@bp.route('/config/<filename>', methods=['GET'])
def get_config(filename):
    """Load configuration with caching"""
    try:
        # Check cache first
        config = config_cache.get(filename)
        if config:
            return create_success_response({'config': config})

        # Load from disk
        success, config, error = config_loader.load_config(filename)
        if not success:
            raise ValidationError(error)

        # Cache for 5 minutes
        config_cache.set(filename, config)

        # Sanitize before returning
        clean_config = sanitize_nan_values(config)

        return create_success_response({'config': clean_config})

    except Exception as e:
        return create_error_response(e)
```

---

## Best Practices

### Import Organization
```python
# Group imports by module
from mlf_utils import (
    # Data sanitization
    sanitize_nan_values,

    # File handling
    FileUploadHandler,

    # Config management
    ConfigLoader,

    # Error handling
    ValidationError,
    create_error_response,

    # Caching
    indicator_schema_cache
)
```

### Error Handling Pattern
```python
@app.route('/api/endpoint')
def endpoint():
    try:
        # Your business logic here
        ...

    except ValidationError as e:
        # Specific error handling
        return create_error_response(e)

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return create_error_response(e)
```

### Caching Strategy
```python
# Use decorator for pure functions
@cached(ttl=600)
def calculate_indicators(data):
    return process(data)

# Use instance for mutable data
cache = CacheManager(ttl=300)

def get_user_data(user_id):
    data = cache.get(f'user_{user_id}')
    if not data:
        data = fetch_from_db(user_id)
        cache.set(f'user_{user_id}', data)
    return data
```

---

## Testing

### Unit Tests
```python
import pytest
from mlf_utils import sanitize_nan_values, ConfigLoader

def test_sanitize_nan():
    data = {'value': float('nan')}
    result = sanitize_nan_values(data)
    assert result['value'] is None

def test_config_loader():
    loader = ConfigLoader(config_dir='test_configs')
    success, config, error = loader.load_config('test.json')
    assert success
    assert config is not None
```

### Integration Tests
```python
def test_upload_handler(client):
    """Test file upload endpoint"""
    data = {'file': (io.BytesIO(b'test'), 'test.json')}
    response = client.post('/api/upload', data=data)
    assert response.status_code == 200
    assert response.json['success']
```

---

## Performance Considerations

### Caching
- Use appropriate TTL values based on data volatility
- Monitor cache hit rates with `cache.get_stats()`
- Clear caches when underlying data changes
- Use global cache instances for shared data

### File Operations
- Use `FileUploadHandler` for consistent validation
- Set appropriate `max_file_size` limits
- Clean up old uploaded files periodically
- Use secure filenames to prevent path traversal

### Error Handling
- Create error responses early to avoid processing invalid requests
- Use specific error types for better client error handling
- Log errors appropriately (warnings for client errors, errors for server errors)

---

## Migration Guide

### From Inline Functions

**Before**:
```python
def sanitize_nan_values(obj):
    if isinstance(obj, dict):
        return {key: sanitize_nan_values(value) for key, value in obj.items()}
    # ... rest of implementation ...

data = sanitize_nan_values(my_data)
```

**After**:
```python
from mlf_utils import sanitize_nan_values

data = sanitize_nan_values(my_data)
```

### From Ad-Hoc File Handling

**Before**:
```python
if 'file' not in request.files:
    return jsonify({'error': 'No file'}), 400

file = request.files['file']
if not file.filename.endswith('.json'):
    return jsonify({'error': 'Invalid file type'}), 400

filepath = os.path.join('uploads', secure_filename(file.filename))
file.save(filepath)
```

**After**:
```python
from mlf_utils import FileUploadHandler

upload_handler = FileUploadHandler(upload_dir='uploads')
result = upload_handler.save_file(request.files.get('file'))
return jsonify(result), 200 if result['success'] else 400
```

---

## Changelog

### v1.0.0 (2025-11-29)
- Initial release with 5 utility modules
- Data sanitization for JSON serialization
- File upload handling with validation
- Configuration loading and management
- Standardized error handling
- Time-based caching with TTL

---

## Support

For issues or questions, see:
- Project documentation: `/claudedocs/`
- Implementation guide: `/claudedocs/20251129_1430_phase1_implementation_complete.md`
- Analysis report: `/claudedocs/20251128_1400_visualization_apps_analysis.md`
