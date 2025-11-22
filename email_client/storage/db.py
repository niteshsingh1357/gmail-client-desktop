"""
SQLite database connection and migration management.

This module provides a simple, synchronous interface for SQLite database
operations with connection management and schema initialization.
"""
import sqlite3
from pathlib import Path
from typing import List, Tuple, Any, Optional
from email_client.config import SQLITE_DB_PATH


def _ensure_db_directory() -> None:
    """Ensure the database directory exists."""
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """
    Get a SQLite database connection.
    
    Returns:
        A sqlite3.Connection with row_factory set to sqlite3.Row.
        
    Note:
        The connection should be closed by the caller when done.
        Consider using a context manager or try/finally block.
    """
    _ensure_db_directory()
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency (allows multiple readers)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """
    Initialize the database schema.
    
    Creates all required tables if they don't exist. This function
    should be called on first run or when setting up a new database.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                email_address TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                imap_host TEXT NOT NULL,
                smtp_host TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_default INTEGER DEFAULT 0
            )
        """)
        
        # Folders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                server_path TEXT NOT NULL,
                unread_count INTEGER DEFAULT 0,
                is_system_folder INTEGER DEFAULT 0,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                UNIQUE(account_id, server_path)
            )
        """)
        
        # Emails table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                folder_id INTEGER NOT NULL,
                uid_on_server INTEGER NOT NULL,
                sender TEXT NOT NULL,
                recipients TEXT NOT NULL,
                subject TEXT,
                preview_text TEXT,
                sent_at TIMESTAMP,
                received_at TIMESTAMP,
                is_read INTEGER DEFAULT 0,
                has_attachments INTEGER DEFAULT 0,
                flags TEXT,
                body_plain TEXT,
                body_html TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE,
                UNIQUE(account_id, folder_id, uid_on_server)
            )
        """)
        
        # Attachments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                mime_type TEXT,
                size_bytes INTEGER DEFAULT 0,
                local_path TEXT,
                is_encrypted INTEGER DEFAULT 0,
                FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
            )
        """)
        
        # Settings table (key-value store for application settings)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tokens table (for storing OAuth token bundles, encrypted)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                account_id INTEGER PRIMARY KEY,
                encrypted_token_bundle TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_email 
            ON accounts(email_address)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_default 
            ON accounts(is_default)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_folders_account 
            ON folders(account_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_account 
            ON emails(account_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_folder 
            ON emails(folder_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_uid 
            ON emails(account_id, folder_id, uid_on_server)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_timestamp 
            ON emails(received_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_attachments_email 
            ON attachments(email_id)
        """)
        
        # Search indexes for better search performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_subject 
            ON emails(subject)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_sender 
            ON emails(sender)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_preview 
            ON emails(preview_text)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_account_read 
            ON emails(account_id, is_read)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_folder_read 
            ON emails(folder_id, is_read)
        """)
        
        conn.commit()
    finally:
        conn.close()


def execute(query: str, params: Tuple[Any, ...] = ()) -> sqlite3.Cursor:
    """
    Execute a SQL query and return the cursor.
    
    Args:
        query: SQL query string.
        params: Query parameters (tuple or list).
        
    Returns:
        The cursor object (useful for getting lastrowid, rowcount, etc.).
        
    Example:
        >>> cursor = execute("INSERT INTO accounts (email_address) VALUES (?)", ("test@example.com",))
        >>> account_id = cursor.lastrowid
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetchall(query: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
    """
    Execute a SELECT query and return all rows.
    
    Args:
        query: SQL SELECT query string.
        params: Query parameters (tuple or list).
        
    Returns:
        A list of Row objects (sqlite3.Row instances).
        
    Example:
        >>> rows = fetchall("SELECT * FROM accounts WHERE provider = ?", ("gmail",))
        >>> for row in rows:
        ...     print(row["email_address"])
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()


def fetchone(query: str, params: Tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
    """
    Execute a SELECT query and return the first row.
    
    Args:
        query: SQL SELECT query string.
        params: Query parameters (tuple or list).
        
    Returns:
        A Row object (sqlite3.Row) or None if no rows found.
        
    Example:
        >>> row = fetchone("SELECT * FROM accounts WHERE id = ?", (1,))
        >>> if row:
        ...     print(row["email_address"])
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    finally:
        conn.close()


def execute_many(query: str, params_list: List[Tuple[Any, ...]]) -> None:
    """
    Execute a query multiple times with different parameters.
    
    Args:
        query: SQL query string.
        params_list: List of parameter tuples.
        
    Example:
        >>> execute_many(
        ...     "INSERT INTO folders (account_id, name) VALUES (?, ?)",
        ...     [(1, "INBOX"), (1, "Sent")]
        ... )
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

