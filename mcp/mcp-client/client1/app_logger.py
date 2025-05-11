import logging
import sys

# Define custom log levels if needed, or map to standard ones
# For simplicity, we'll use standard levels and control verbosity by setting the logger's effective level.
LOG_LEVEL_QUIET = logging.CRITICAL + 10 # Effectively off
LOG_LEVEL_NORMAL = logging.INFO
LOG_LEVEL_VERBOSE = logging.DEBUG

DEFAULT_FORMAT = '%(asctime)s - %(levelname)-8s - %(name)-15s - %(filename)s:%(lineno)d - %(message)s'
SIMPLE_FORMAT = '%(asctime)s - %(levelname)-8s - %(message)s' # For less noisy normal output

_is_initialized = False
_global_logging_enabled = True # Master switch
_root_logger = logging.getLogger() # Get the root logger

# We'll have specific loggers for different parts of the app
# to allow finer-grained control if desired in the future.
# For now, they all inherit from the root logger's level.
CONFIG_LOGGER = logging.getLogger("app.config")
SERVICE_LOGGER = logging.getLogger("app.service")
ENGINE_LOGGER = logging.getLogger("app.engine")
CLI_LOGGER = logging.getLogger("app.cli")


def setup_logging(level: int = LOG_LEVEL_NORMAL, log_file: str = 'app_client.log', enable_global: bool = True):
    """
    Initializes or reconfigures the logging system.
    """
    global _is_initialized, _global_logging_enabled
    _global_logging_enabled = enable_global

    if not _global_logging_enabled:
        _root_logger.setLevel(LOG_LEVEL_QUIET)
        for handler in _root_logger.handlers[:]: # Iterate over a copy
            _root_logger.removeHandler(handler)
            handler.close()
        _root_logger.addHandler(logging.NullHandler()) # Prevent "No handlers could be found"
        _is_initialized = True
        return

    # Clear existing handlers to avoid duplication if called multiple times
    for handler in _root_logger.handlers[:]:
        _root_logger.removeHandler(handler)
        handler.close() # Important to close file handlers

    _root_logger.setLevel(level)

    formatter = logging.Formatter(DEFAULT_FORMAT if level == LOG_LEVEL_VERBOSE else SIMPLE_FORMAT)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level) # Console shows messages at the set level
    _root_logger.addHandler(console_handler)

    # File Handler (always logs at least DEBUG if enabled, or the passed level)
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT)) # File always gets detailed format
        file_handler.setLevel(LOG_LEVEL_VERBOSE if level == LOG_LEVEL_VERBOSE else LOG_LEVEL_NORMAL) # Log more to file
        _root_logger.addHandler(file_handler)
    
    _is_initialized = True
    CLI_LOGGER.info(f"Logging initialized. Level: {logging.getLevelName(level)}. Global enabled: {_global_logging_enabled}")

def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance. If logging is globally disabled,
    operations on this logger will be no-ops or go to NullHandler.
    """
    if not _is_initialized:
        # Default setup if not explicitly called, though cli.py should call it.
        setup_logging()
    
    # The individual loggers (CONFIG_LOGGER, etc.) will inherit the root logger's level
    # unless explicitly set otherwise.
    return logging.getLogger(name) # Use standard `getLogger`

def disable_logging():
    """Globally disables all logging."""
    global _global_logging_enabled
    _global_logging_enabled = False
    setup_logging(enable_global=False) # Reconfigure with global off

def enable_logging(level: int = LOG_LEVEL_NORMAL):
    """Globally enables logging with the specified level."""
    global _global_logging_enabled
    _global_logging_enabled = True
    setup_logging(level=level, enable_global=True)

# --- Convenience functions for different loggers ---
# These directly use the predefined logger instances.

# For Config
def config_log_debug(msg, *args, **kwargs):
    if _global_logging_enabled: CONFIG_LOGGER.debug(msg, *args, **kwargs)
def config_log_info(msg, *args, **kwargs):
    if _global_logging_enabled: CONFIG_LOGGER.info(msg, *args, **kwargs)
def config_log_warning(msg, *args, **kwargs):
    if _global_logging_enabled: CONFIG_LOGGER.warning(msg, *args, **kwargs)
def config_log_error(msg, *args, **kwargs):
    if _global_logging_enabled: CONFIG_LOGGER.error(msg, *args, **kwargs)

# For Services
def service_log_debug(msg, *args, **kwargs):
    if _global_logging_enabled: SERVICE_LOGGER.debug(msg, *args, **kwargs)
def service_log_info(msg, *args, **kwargs):
    if _global_logging_enabled: SERVICE_LOGGER.info(msg, *args, **kwargs)
def service_log_warning(msg, *args, **kwargs):
    if _global_logging_enabled: SERVICE_LOGGER.warning(msg, *args, **kwargs)
def service_log_error(msg, *args, **kwargs):
    if _global_logging_enabled: SERVICE_LOGGER.error(msg, *args, **kwargs)

# For Engine
def engine_log_debug(msg, *args, **kwargs):
    if _global_logging_enabled: ENGINE_LOGGER.debug(msg, *args, **kwargs)
def engine_log_info(msg, *args, **kwargs):
    if _global_logging_enabled: ENGINE_LOGGER.info(msg, *args, **kwargs)
def engine_log_warning(msg, *args, **kwargs):
    if _global_logging_enabled: ENGINE_LOGGER.warning(msg, *args, **kwargs)
def engine_log_error(msg, *args, **kwargs):
    if _global_logging_enabled: ENGINE_LOGGER.error(msg, *args, **kwargs)
def engine_log_critical(msg, *args, **kwargs): # Critical for engine might be useful
    if _global_logging_enabled: ENGINE_LOGGER.critical(msg, *args, **kwargs)


# For CLI / Main App
def cli_log_debug(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.debug(msg, *args, **kwargs)
def cli_log_info(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.info(msg, *args, **kwargs)
def cli_log_warning(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.warning(msg, *args, **kwargs)
def cli_log_error(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.error(msg, *args, **kwargs)
def cli_log_critical(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.critical(msg, *args, **kwargs)

# Example usage in other modules:
# from app_logger import service_log_info, engine_log_debug
# service_log_info("Service started")
# engine_log_debug("Detailed step in engine")
