import logging
import os

import coloredlogs
from six import integer_types, string_types, text_type

# import PKG_NAME
PKG_NAME = os.path.basename(os.path.dirname(__file__))

ROOT_LOGGER = logging.getLogger()
ROOT_LOGGER.setLevel(logging.DEBUG)
PKG_LOGGER = logging.getLogger(PKG_NAME)
PKG_STREAM_HANDLER = None
PKG_FILE_HANDLER = None

def setup_logging(stream_log_level=None, log_path=None, file_log_level=None, **kwargs):
    global PKG_FILE_HANDLER, PKG_STREAM_HANDLER

    if log_path:
        if PKG_FILE_HANDLER:
            PKG_LOGGER.removeHandler(PKG_FILE_HANDLER)
        PKG_FILE_HANDLER = logging.FileHandler(log_path)
        ROOT_LOGGER.addHandler(PKG_FILE_HANDLER)
    if file_log_level:
        PKG_FILE_HANDLER.setLevel(file_log_level)
    if stream_log_level:
        if not PKG_STREAM_HANDLER:
            PKG_STREAM_HANDLER = logging.StreamHandler()
            if os.name != 'nt':
                PKG_STREAM_HANDLER.setFormatter(coloredlogs.ColoredFormatter())
            PKG_STREAM_HANDLER.addFilter(coloredlogs.HostNameFilter())
            PKG_STREAM_HANDLER.addFilter(coloredlogs.ProgramNameFilter())
            ROOT_LOGGER.addHandler(PKG_STREAM_HANDLER)
        PKG_STREAM_HANDLER.setLevel(stream_log_level)

    # TODO: maybe process quiet differently so that it does not add a stream handler
    if PKG_STREAM_HANDLER:
        logging.info("stream log level: %s", PKG_STREAM_HANDLER.level)
    if PKG_FILE_HANDLER:
        logging.info("file log level: %s", PKG_FILE_HANDLER.level)

def log_level_value(log_level):
    if isinstance(log_level, integer_types):
        return log_level
    if isinstance(log_level, string_types) and hasattr(logging, log_level):
        return getattr(logging, log_level)

def log_level_quiet(log_level):
    return log_level_value(log_level) > logging.WARNING

def log_stream_quiet():
    if PKG_STREAM_HANDLER:
        return log_level_quiet(PKG_STREAM_HANDLER.level)


setup_logging()
