import logging
import sys
from typing import Optional # Added for type hinting

# Define custom log levels if needed, or map to standard ones
LOG_LEVEL_QUIET = logging.CRITICAL + 10 # Effectively off for handlers
LOG_LEVEL_USER_INTERACTION = logging.INFO + 5 # Custom level between INFO and WARNING
LOG_LEVEL_NORMAL = logging.INFO # Key operational steps
LOG_LEVEL_VERBOSE = logging.DEBUG # Detailed internal steps

# Register the custom level name
logging.addLevelName(LOG_LEVEL_USER_INTERACTION, "USER")

DEFAULT_FORMAT = '%(asctime)s - %(levelname)-8s - %(name)-15s - %(filename)s:%(lineno)d - %(message)s'
# More user-friendly format for normal console output
NORMAL_CONSOLE_FORMAT = '%(asctime)s - %(levelname)-8s - %(message)s'
# Even simpler for user interaction level on console
USER_INTERACTION_CONSOLE_FORMAT = '%(message)s'

_is_initialized = False
_global_logging_enabled = True
_root_logger = logging.getLogger()

# Define specific loggers for different parts of the app
CONFIG_LOGGER = logging.getLogger("app.config")
SERVICE_LOGGER = logging.getLogger("app.service")
ENGINE_LOGGER = logging.getLogger("app.engine")
CLI_LOGGER = logging.getLogger("app.cli")

# Add known noisy third-party loggers
GOOGLE_API_LOGGER_NAME = "google.generativeai"
HTTPX_LOGGER_NAME = "httpx" # google-generativeai uses httpx

def setup_logging(level: int = LOG_LEVEL_NORMAL,
                  console_level_override: Optional[int] = None,
                  log_file: Optional[str] = 'app_client.log',
                  enable_global: bool = True):
    """
    Initializes or reconfigures the logging system.

    Args:
        level: The base filtering level for the application's own loggers.
               Messages below this level from app loggers won't be processed further.
        console_level_override: Specific level for the console handler. If None, uses 'level'.
        log_file: Path to the log file. If None, file logging is disabled.
        enable_global: Master switch for application logging.
    """
    global _is_initialized, _global_logging_enabled
    _global_logging_enabled = enable_global

    # --- Root Logger and Global Disabling ---
    if not _global_logging_enabled:
        _root_logger.setLevel(LOG_LEVEL_QUIET + 1) # Set very high to silence everything
        # Remove existing handlers
        for handler in _root_logger.handlers[:]:
            _root_logger.removeHandler(handler)
            if hasattr(handler, 'close'): # Ensure handler is closed
                handler.close()
        _root_logger.addHandler(logging.NullHandler())
        _is_initialized = True
        # Also silence noisy third-party loggers when globally disabled
        logging.getLogger(GOOGLE_API_LOGGER_NAME).setLevel(LOG_LEVEL_QUIET + 1)
        logging.getLogger(HTTPX_LOGGER_NAME).setLevel(LOG_LEVEL_QUIET + 1)
        # No "Logging initialized" message if globally disabled
        return

    # --- Clear Existing Handlers ---
    # This is crucial to prevent adding multiple handlers if setup_logging is called again.
    for handler in _root_logger.handlers[:]:
        _root_logger.removeHandler(handler)
        if hasattr(handler, 'close'):
            handler.close()

    # --- Set Root Logger Level ---
    # The root logger's level should be the *lowest* (most verbose) of all desired outputs.
    # For instance, if file logs at DEBUG and console at INFO, root should be DEBUG.
    min_effective_level = level # Start with the app's base level
    if console_level_override is not None:
        min_effective_level = min(min_effective_level, console_level_override)
    if log_file: # File handler always logs at VERBOSE (DEBUG) from our app
        min_effective_level = min(min_effective_level, LOG_LEVEL_VERBOSE)

    _root_logger.setLevel(min_effective_level)


    # --- Console Handler ---
    actual_console_level = console_level_override if console_level_override is not None else level

    if actual_console_level < LOG_LEVEL_QUIET: # Only add console handler if not completely quieted
        console_formatter = logging.Formatter(DEFAULT_FORMAT) # Default for verbose
        if actual_console_level == LOG_LEVEL_USER_INTERACTION:
            console_formatter = logging.Formatter(USER_INTERACTION_CONSOLE_FORMAT)
        elif actual_console_level == LOG_LEVEL_NORMAL : # Normal
            console_formatter = logging.Formatter(NORMAL_CONSOLE_FORMAT)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(actual_console_level)
        _root_logger.addHandler(console_handler)

    # --- File Handler ---
    if log_file:
        file_formatter = logging.Formatter(DEFAULT_FORMAT) # File always gets detailed format
        try:
            file_handler = logging.FileHandler(log_file, mode='w')
            file_handler.setFormatter(file_formatter)
            # File handler for app logs everything from VERBOSE (DEBUG) up,
            # respecting the root logger's filter.
            file_handler.setLevel(LOG_LEVEL_VERBOSE)
            _root_logger.addHandler(file_handler)
        except Exception as e:
            # Fallback if file handler can't be created (e.g., permissions)
            # Log to console if possible, or just print.
            if _root_logger.hasHandlers(): # Check if console handler was added
                CLI_LOGGER.error(f"Could not create file handler for '{log_file}': {e}")
            else:
                print(f"ERROR: Could not create file handler for '{log_file}': {e}", file=sys.stderr)
            log_file = None # Indicate file logging is effectively disabled


    # --- Control Third-Party Logger Verbosity ---
    # If our app's effective console level is verbose, let third-party loggers be more verbose.
    # Otherwise, make them quieter (e.g., WARNING or higher).
    third_party_log_level_setting = logging.WARNING # Default for third-party
    if actual_console_level <= LOG_LEVEL_VERBOSE: # If our console is verbose
        third_party_log_level_setting = LOG_LEVEL_NORMAL # Let them show INFO too

    logging.getLogger(GOOGLE_API_LOGGER_NAME).setLevel(third_party_log_level_setting)
    logging.getLogger(HTTPX_LOGGER_NAME).setLevel(third_party_log_level_setting)

    _is_initialized = True

    # Log initialization status (respects console handler's level)
    init_msg = f"Logging initialized. Effective console level: {logging.getLevelName(actual_console_level)}."
    if log_file:
        init_msg += f" File logging ({logging.getLevelName(LOG_LEVEL_VERBOSE)}+) to: {log_file}"
    else:
        init_msg += " File logging disabled."

    # This message itself will be filtered by the console handler's level.
    # If actual_console_level is USER_INTERACTION, this INFO message won't show on console.
    CLI_LOGGER.info(init_msg)
    # If console is very quiet, a direct print might be needed for this one-time setup message.
    if actual_console_level >= LOG_LEVEL_QUIET and _root_logger.handlers and not any(isinstance(h, logging.StreamHandler) and h.stream == sys.stdout for h in _root_logger.handlers):
         pass # No console handler, or it's super quiet
    elif actual_console_level > LOG_LEVEL_NORMAL: # If console won't show INFO  <- FIXED HERE
         if any(isinstance(h, logging.StreamHandler) and h.stream == sys.stdout for h in _root_logger.handlers):
             # A direct print can be used if the CLI_LOGGER.info won't make it to console
             # but this can be tricky. Better to rely on the levels.
             # For simplicity, let the CLI_LOGGER.info be the source. If console level is too high, it won't show.
             pass



def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance. If logging is globally disabled,
    operations on this logger will be no-ops or go to NullHandler.
    """
    if not _is_initialized:
        # Fallback: Basic setup if not explicitly called.
        # This usually means cli.py didn't call setup_logging first.
        print("Warning: app_logger.setup_logging() not called explicitly. Using default setup.", file=sys.stderr)
        setup_logging()

    return logging.getLogger(name)

def disable_logging():
    """Globally disables all logging output from the application's loggers."""
    setup_logging(enable_global=False)

def enable_logging(level: int = LOG_LEVEL_NORMAL, console_level: Optional[int] = None):
    """Globally enables logging with the specified levels."""
    setup_logging(level=level, console_level_override=console_level, enable_global=True)

# --- Convenience functions for different loggers ---

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
def engine_log_info(msg, *args, **kwargs): # For operational info
    if _global_logging_enabled: ENGINE_LOGGER.info(msg, *args, **kwargs)
def engine_log_user(msg, *args, **kwargs): # For console user interaction level
    if _global_logging_enabled: ENGINE_LOGGER.log(LOG_LEVEL_USER_INTERACTION, msg, *args, **kwargs)
def engine_log_warning(msg, *args, **kwargs):
    if _global_logging_enabled: ENGINE_LOGGER.warning(msg, *args, **kwargs)
def engine_log_error(msg, *args, **kwargs):
    if _global_logging_enabled: ENGINE_LOGGER.error(msg, *args, **kwargs)
def engine_log_critical(msg, *args, **kwargs):
    if _global_logging_enabled: ENGINE_LOGGER.critical(msg, *args, **kwargs)

# For CLI / Main App
def cli_log_debug(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.debug(msg, *args, **kwargs)
def cli_log_info(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.info(msg, *args, **kwargs)
def cli_log_user(msg, *args, **kwargs): # CLI might also have user-level messages
    if _global_logging_enabled: CLI_LOGGER.log(LOG_LEVEL_USER_INTERACTION, msg, *args, **kwargs)
def cli_log_warning(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.warning(msg, *args, **kwargs)
def cli_log_error(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.error(msg, *args, **kwargs)
def cli_log_critical(msg, *args, **kwargs):
    if _global_logging_enabled: CLI_LOGGER.critical(msg, *args, **kwargs)