"""
Logging configuration for the email client.

This module sets up logging with rotating file handlers and console output,
providing a centralized way to configure logging throughout the application.
"""
import logging
import logging.handlers
from pathlib import Path
from typing import Optional


# Default log directory
LOG_DIR = Path.home() / ".email_client" / "logs"
LOG_FILE = LOG_DIR / "app.log"

# Maximum log file size (10 MB)
MAX_LOG_SIZE = 10 * 1024 * 1024

# Number of backup log files to keep
BACKUP_COUNT = 5


def setup_logging(debug: bool = False) -> None:
    """
    Configure logging for the email client application.
    
    Sets up:
    - Rotating file handler for ~/.email_client/logs/app.log
    - Console handler for immediate feedback
    - Appropriate log levels based on debug mode
    
    Args:
        debug: If True, sets log level to DEBUG. Otherwise, uses INFO.
    """
    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determine log level
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(levelname)s - %(message)s'
    )
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler (only show WARNING and above unless debug)
    console_handler = logging.StreamHandler()
    console_level = logging.DEBUG if debug else logging.WARNING
    console_handler.setLevel(console_level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Email Client Application Started")
    logger.info(f"Log level: {logging.getLevelName(log_level)}")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info("=" * 60)
    
    # Suppress noisy third-party loggers
    _suppress_noisy_loggers()


def _suppress_noisy_loggers() -> None:
    """
    Suppress verbose logging from third-party libraries.
    
    This reduces noise in the logs from libraries that are overly verbose
    at DEBUG/INFO levels.
    """
    # Suppress urllib3 (used by requests)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Suppress requests
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    # Suppress imaplib (can be very verbose)
    logging.getLogger("imaplib").setLevel(logging.WARNING)
    
    # Suppress smtplib
    logging.getLogger("smtplib").setLevel(logging.WARNING)
    
    # Suppress cryptography
    logging.getLogger("cryptography").setLevel(logging.WARNING)
    
    # Suppress PyQt5 (if used)
    logging.getLogger("PyQt5").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Logger name (usually __name__). If None, returns root logger.
        
    Returns:
        A Logger instance.
    """
    return logging.getLogger(name)


def set_log_level(level: int) -> None:
    """
    Change the log level for all handlers.
    
    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    for handler in root_logger.handlers:
        handler.setLevel(level)

