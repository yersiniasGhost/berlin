import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
from typing import Dict
from mlf_utils.env_vars import EnvVars


# Inline Singleton to avoid circular import with mlf_utils/__init__.py
class _LogManagerSingleton(type):
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        class_key = cls.__name__
        if class_key not in cls._instances:
            with cls._lock:
                if class_key not in cls._instances:
                    cls._instances[class_key] = super(_LogManagerSingleton, cls).__call__(*args, **kwargs)
        return cls._instances[class_key]


class LogManager(metaclass=_LogManagerSingleton):

    def __init__(self, log_filename: str = "application.log"):
        self._loggers: Dict[str, logging.Logger] = {}
        self._file_handler: logging.Handler | None = None
        self._log_dir = Path(EnvVars().log_path or "/var/log/mlf")
        print(f"LOGMANAGER init: {self._log_dir}")
        self._setup_base_config(log_filename)


    def _setup_base_config(self, log_filename: str):
        """Initialize base logging configuration."""
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created log dir: {self._log_dir}")
        except PermissionError:
            print("Warning: Cannot create /var/log/raptor. Ensure proper permissions.")
            # Fallback to current directory
            self._log_dir = Path('.')

        if self._file_handler is None:
            try:
                self._file_handler = RotatingFileHandler(
                    self._log_dir / log_filename,
                    maxBytes=10485760,
                    backupCount=5
                )
            except Exception:
                self._file_handler = logging.StreamHandler()

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]'
            )
            self._file_handler.setFormatter(formatter)
        # # Create formatters
        # self.detailed_formatter = logging.Formatter(
        #     '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]'
        # )
        # self.simple_formatter = logging.Formatter(
        #     '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        # )



    def get_logger(self, name: str) -> logging.Logger:
        print(f"Get logger: {name}")
        if name not in self._loggers:
            logger = logging.getLogger(name)
            level = EnvVars().log_level
            if isinstance(level, str):
                level = logging._nameToLevel.get(level.upper(), logging.INFO)
            if not isinstance(level, int):
                level = logging.INFO
            logger.setLevel(level)

            # Remove any existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)

            # Add our single file handler
            if self._file_handler:
                logger.addHandler(self._file_handler)
            else:
                logger.addHandler(logging.StreamHandler())

            # Prevent propagation to root logger
            logger.propagate = False

            self._loggers[name] = logger

        return self._loggers[name]


    def update_all_log_levels(self, level: int):
        """Update log level for all managed loggers."""
        for logger in self._loggers.values():
            logger.setLevel(level)

    def get_all_loggers(self) -> Dict[str, logging.Logger]:
        """Get dictionary of all managed loggers."""
        return self._loggers.copy()


    def configure_library_loggers(self, level=None):
        """Configure third-party libraries to use the same file handler"""
        if level is None:
            level = EnvVars().log_level
        if isinstance(level, str):
            level = logging._nameToLevel.get(level.upper(), logging.INFO)
        if not isinstance(level, int):
            level = logging.INFO

        # Configure FastAPI and related libraries
        for logger_name in [
            "fastapi",
            "uvicorn",
            "uvicorn.access",
            "uvicorn.error",
            "aiomqtt",
        ]:
            lib_logger = logging.getLogger(logger_name)
            lib_logger.setLevel(level)

            # Add our file handler if not already there
            if self._file_handler and not any(isinstance(h, type(self._file_handler)) for h in lib_logger.handlers):
                lib_logger.addHandler(self._file_handler)
            elif not self._file_handler and not lib_logger.handlers:
                lib_logger.addHandler(logging.StreamHandler())

            # Prevent propagation to root logger to avoid duplicate logs
            lib_logger.propagate = False
