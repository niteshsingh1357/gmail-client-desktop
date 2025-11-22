"""
Global settings and constants for the email client.

This module provides configuration constants and helpers for the email client.
It is framework-agnostic and designed to be easily unit-testable.
"""
import os
from pathlib import Path
from typing import Optional


# Default port constants
DEFAULT_IMAP_PORT: int = 993
DEFAULT_SMTP_PORT: int = 587

# OAuth configuration (read from environment)
OAUTH_CLIENT_ID: Optional[str] = None
OAUTH_CLIENT_SECRET: Optional[str] = None

# Database configuration
SQLITE_DB_PATH: Path = Path.home() / ".email_client" / "email_client.db"

# Sync and caching configuration
DEFAULT_REFRESH_INTERVAL_SECONDS: int = 60
MAX_CACHED_EMAILS_PER_FOLDER: int = 500


def load_env() -> None:
    """
    Load environment variables and apply sensible defaults.
    
    This function reads OAuth credentials from environment variables
    and sets up default paths. It should be called at application startup.
    """
    global OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, SQLITE_DB_PATH
    
    # Load OAuth credentials from environment
    OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
    OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
    
    # Allow override of database path via environment variable
    db_path_env = os.environ.get("SQLITE_DB_PATH")
    if db_path_env:
        SQLITE_DB_PATH = Path(db_path_env)
    
    # Ensure the database directory exists
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_database_url() -> str:
    """
    Get the SQLite database URL for database connections.
    
    Returns:
        A SQLite database URL string in the format 'sqlite:///path/to/database.db'
    
    Example:
        >>> get_database_url()
        'sqlite:///Users/username/.email_client/email_client.db'
    """
    # Convert Windows paths to forward slashes for SQLite URL
    db_path_str = str(SQLITE_DB_PATH).replace("\\", "/")
    return f"sqlite:///{db_path_str}"

