import logging
import os
import sys
from pathlib import Path

# The root config logging level  is configured to logging.WARNING
# Do not change this since lot of third party packages use root config to log messages
rootLogger = logging.getLogger()
# defaultFormat = "%(asctime)s - %(name)s - %(levelname)s -- %(message)s"
defaultFormat = "%(name)s - %(levelname)s -- %(message)s"
logging.basicConfig(format=defaultFormat)


def prepare_logger(process_name: str, use_stdout: bool = True, short_hand: bool = True,
                   super_short_hand: bool = True):
    logfile_path = os.getenv("LOGFILE_PATH")
    log_level = os.getenv("LOGLEVEL")
    if not log_level:
        log_level = "DEBUG"
    handlers = []
    if use_stdout:
        handlers.append(logging.StreamHandler(stream=sys.stdout))

    elif logfile_path:
        log_file = process_name+"-"+str(os.getpid())
        path = Path(logfile_path)
        path.mkdir(parents=True, exist_ok=True)
        # if not os.path.isdir(logfile_path):
        #     print("Cannot create LOG FILE in path: " + logfile_path)
        #     raise Exception("Cannot create LOG FILE in path: " + logfile_path)
        log_path = logfile_path + "/" + log_file
        handlers.append(logging.FileHandler(log_path))
    else:
        # Default log handler to stdout
        handlers.append(logging.StreamHandler(stream=sys.stdout))

    log_format = defaultFormat
    if super_short_hand:
        log_format = "%(message)s"
    elif short_hand:
        log_format = "%(name)s - %(levelname)s -- %(message)s"
        log_format = "%(message)s"

    logging.basicConfig(handlers=handlers,  level=log_level, format=log_format)
    logging.info("Configured Logger.  Level " + log_level)

    return logging.getLogger()


def log(name, log_level=None):
    the_logger = logging.getLogger()
    if log_level is None:
        log_level = "DEBUG"
    the_logger.setLevel(log_level)
    return the_logger
