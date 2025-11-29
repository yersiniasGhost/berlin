"""
File Upload and Validation Utilities
Provides centralized file upload handling with validation for Flask applications.
"""

import os
from pathlib import Path
from typing import Tuple, Dict, Any, Set, Optional
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage


class FileUploadHandler:
    """
    Centralized file upload handler with validation and security features.

    Provides consistent file validation, secure filename handling, and
    organized file storage for uploaded configuration files.
    """

    # Default allowed file extensions
    DEFAULT_ALLOWED_EXTENSIONS: Set[str] = {'.json', '.csv'}

    # Default maximum file size (16MB)
    DEFAULT_MAX_FILE_SIZE: int = 16 * 1024 * 1024

    def __init__(
        self,
        upload_dir: str = 'uploads',
        allowed_extensions: Optional[Set[str]] = None,
        max_file_size: Optional[int] = None
    ):
        """
        Initialize file upload handler.

        Args:
            upload_dir: Directory to store uploaded files (relative or absolute)
            allowed_extensions: Set of allowed file extensions (e.g., {'.json', '.csv'})
            max_file_size: Maximum file size in bytes
        """
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        self.allowed_extensions = allowed_extensions or self.DEFAULT_ALLOWED_EXTENSIONS
        self.max_file_size = max_file_size or self.DEFAULT_MAX_FILE_SIZE

    def validate_file(self, file: Optional[FileStorage]) -> Tuple[bool, str]:
        """
        Validate uploaded file for security and format compliance.

        Args:
            file: Werkzeug FileStorage object from Flask request.files

        Returns:
            Tuple of (is_valid: bool, error_message: str)
            If valid, error_message is empty string
        """
        if not file or not file.filename:
            return False, 'No file selected'

        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            allowed_ext_str = ', '.join(self.allowed_extensions)
            return False, f'Only {allowed_ext_str} files are allowed'

        # Check file size if possible
        # Note: This requires the file to be seekable, which may not always work
        # with streaming uploads. Consider adding size validation in route handler.
        try:
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset to beginning

            if file_size > self.max_file_size:
                max_mb = self.max_file_size / (1024 * 1024)
                return False, f'File size exceeds maximum allowed size of {max_mb:.1f}MB'
        except (AttributeError, IOError):
            # If we can't check size, proceed (size will be validated during read)
            pass

        return True, ''

    def save_file(
        self,
        file: Optional[FileStorage],
        prefix: str = '',
        custom_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save uploaded file to disk with validation and secure filename handling.

        Args:
            file: Werkzeug FileStorage object from Flask request.files
            prefix: Optional prefix for filename (e.g., 'config_type')
            custom_filename: Optional custom filename to use instead of uploaded name

        Returns:
            Dict with keys:
                - success: bool indicating if save was successful
                - filename: str final filename used
                - filepath: str absolute path to saved file
                - error: str error message (only present if success=False)
        """
        # Validate file
        is_valid, error = self.validate_file(file)
        if not is_valid:
            return {'success': False, 'error': error}

        # Generate secure filename
        if custom_filename:
            base_filename = secure_filename(custom_filename)
        else:
            base_filename = secure_filename(file.filename)

        # Add prefix if provided
        if prefix:
            filename = f"{prefix}_{base_filename}"
        else:
            filename = base_filename

        # Ensure unique filename if file already exists
        filepath = self.upload_dir / filename
        if filepath.exists():
            # Add timestamp to make unique
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) == 2:
                filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
            else:
                filename = f"{filename}_{timestamp}"
            filepath = self.upload_dir / filename

        try:
            # Save file
            file.save(str(filepath))

            return {
                'success': True,
                'filename': filename,
                'filepath': str(filepath.absolute())
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Error saving file: {str(e)}'
            }

    def delete_file(self, filename: str) -> Tuple[bool, str]:
        """
        Delete a file from the upload directory.

        Args:
            filename: Name of file to delete

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        try:
            filepath = self.upload_dir / filename

            if not filepath.exists():
                return False, f'File not found: {filename}'

            # Security check: ensure file is within upload directory
            if not str(filepath.resolve()).startswith(str(self.upload_dir.resolve())):
                return False, 'Invalid file path'

            filepath.unlink()
            return True, ''

        except Exception as e:
            return False, f'Error deleting file: {str(e)}'

    def list_files(self, extension: Optional[str] = None) -> list:
        """
        List all files in the upload directory.

        Args:
            extension: Optional file extension filter (e.g., '.json')

        Returns:
            List of filenames in the upload directory
        """
        try:
            if extension:
                files = [
                    f.name for f in self.upload_dir.iterdir()
                    if f.is_file() and f.suffix.lower() == extension.lower()
                ]
            else:
                files = [f.name for f in self.upload_dir.iterdir() if f.is_file()]

            return sorted(files)

        except Exception:
            return []


def allowed_file(filename: str, allowed_extensions: Set[str]) -> bool:
    """
    Check if a filename has an allowed extension.

    Legacy helper function for backward compatibility.

    Args:
        filename: Filename to check
        allowed_extensions: Set of allowed extensions (e.g., {'json', 'csv'})

    Returns:
        True if filename has an allowed extension
    """
    if not filename or '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions
