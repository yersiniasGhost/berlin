"""
Configuration File Loading and Management Utilities
Provides centralized configuration file loading with validation and error handling.
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Union
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("ConfigLoader")


class ConfigLoader:
    """
    Centralized configuration file loader with validation and error handling.

    Provides consistent configuration file loading patterns across the application,
    with proper error handling and validation.
    """

    def __init__(self, config_dir: Union[str, Path] = 'inputs'):
        """
        Initialize configuration loader.

        Args:
            config_dir: Directory containing configuration files (relative or absolute)
        """
        self.config_dir = Path(config_dir)

        # Create directory if it doesn't exist
        if not self.config_dir.exists():
            logger.info(f"Creating config directory: {self.config_dir}")
            self.config_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self, filename: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Load and parse JSON configuration file.

        Args:
            filename: Name of configuration file to load

        Returns:
            Tuple of (success: bool, config: dict, error_message: str)
            - If successful: (True, config_dict, '')
            - If failed: (False, {}, error_message)
        """
        try:
            filepath = self.config_dir / filename

            if not filepath.exists():
                error_msg = f'Configuration file not found: {filename}'
                logger.error(error_msg)
                return False, {}, error_msg

            with open(filepath, 'r') as f:
                config = json.load(f)

            logger.info(f"Successfully loaded config: {filename}")
            return True, config, ''

        except json.JSONDecodeError as e:
            error_msg = f'Invalid JSON in {filename}: {str(e)}'
            logger.error(error_msg)
            return False, {}, error_msg

        except Exception as e:
            error_msg = f'Error loading {filename}: {str(e)}'
            logger.error(error_msg)
            return False, {}, error_msg

    def load_config_from_path(self, filepath: Union[str, Path]) -> Tuple[bool, Dict[str, Any], str]:
        """
        Load configuration from an absolute or relative path.

        Args:
            filepath: Path to configuration file

        Returns:
            Tuple of (success: bool, config: dict, error_message: str)
        """
        try:
            filepath = Path(filepath)

            if not filepath.exists():
                error_msg = f'Configuration file not found: {filepath}'
                logger.error(error_msg)
                return False, {}, error_msg

            with open(filepath, 'r') as f:
                config = json.load(f)

            logger.info(f"Successfully loaded config from: {filepath}")
            return True, config, ''

        except json.JSONDecodeError as e:
            error_msg = f'Invalid JSON in {filepath}: {str(e)}'
            logger.error(error_msg)
            return False, {}, error_msg

        except Exception as e:
            error_msg = f'Error loading {filepath}: {str(e)}'
            logger.error(error_msg)
            return False, {}, error_msg

    def save_config(
        self,
        filename: str,
        config: Dict[str, Any],
        indent: int = 2,
        overwrite: bool = True
    ) -> Tuple[bool, str]:
        """
        Save configuration to JSON file.

        Args:
            filename: Name of file to save
            config: Configuration dictionary to save
            indent: JSON indentation level
            overwrite: Whether to overwrite existing file

        Returns:
            Tuple of (success: bool, error_message: str)
            - If successful: (True, '')
            - If failed: (False, error_message)
        """
        try:
            filepath = self.config_dir / filename

            # Check if file exists and overwrite is False
            if filepath.exists() and not overwrite:
                error_msg = f'File already exists: {filename} (use overwrite=True to replace)'
                logger.warning(error_msg)
                return False, error_msg

            with open(filepath, 'w') as f:
                json.dump(config, f, indent=indent)

            logger.info(f"Successfully saved config: {filename}")
            return True, ''

        except Exception as e:
            error_msg = f'Error saving {filename}: {str(e)}'
            logger.error(error_msg)
            return False, error_msg

    def save_config_to_path(
        self,
        filepath: Union[str, Path],
        config: Dict[str, Any],
        indent: int = 2,
        overwrite: bool = True
    ) -> Tuple[bool, str]:
        """
        Save configuration to an absolute or relative path.

        Args:
            filepath: Path where to save configuration
            config: Configuration dictionary to save
            indent: JSON indentation level
            overwrite: Whether to overwrite existing file

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        try:
            filepath = Path(filepath)

            # Create parent directories if they don't exist
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Check if file exists and overwrite is False
            if filepath.exists() and not overwrite:
                error_msg = f'File already exists: {filepath} (use overwrite=True to replace)'
                logger.warning(error_msg)
                return False, error_msg

            with open(filepath, 'w') as f:
                json.dump(config, f, indent=indent)

            logger.info(f"Successfully saved config to: {filepath}")
            return True, ''

        except Exception as e:
            error_msg = f'Error saving {filepath}: {str(e)}'
            logger.error(error_msg)
            return False, error_msg

    def list_configs(self, extension: str = '.json') -> list:
        """
        List all configuration files in the config directory.

        Args:
            extension: File extension to filter by (default: '.json')

        Returns:
            List of configuration filenames
        """
        try:
            if not self.config_dir.exists():
                return []

            files = [
                f.name for f in self.config_dir.iterdir()
                if f.is_file() and f.suffix.lower() == extension.lower()
            ]

            return sorted(files)

        except Exception as e:
            logger.error(f"Error listing config files: {e}")
            return []

    def config_exists(self, filename: str) -> bool:
        """
        Check if a configuration file exists.

        Args:
            filename: Name of configuration file

        Returns:
            True if file exists, False otherwise
        """
        filepath = self.config_dir / filename
        return filepath.exists()

    def delete_config(self, filename: str) -> Tuple[bool, str]:
        """
        Delete a configuration file.

        Args:
            filename: Name of configuration file to delete

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        try:
            filepath = self.config_dir / filename

            if not filepath.exists():
                error_msg = f'Configuration file not found: {filename}'
                logger.error(error_msg)
                return False, error_msg

            # Security check: ensure file is within config directory
            if not str(filepath.resolve()).startswith(str(self.config_dir.resolve())):
                error_msg = 'Invalid file path (outside config directory)'
                logger.error(error_msg)
                return False, error_msg

            filepath.unlink()
            logger.info(f"Successfully deleted config: {filename}")
            return True, ''

        except Exception as e:
            error_msg = f'Error deleting {filename}: {str(e)}'
            logger.error(error_msg)
            return False, error_msg
