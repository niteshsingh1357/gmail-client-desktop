"""
Account management for email client.

This module provides functions to manage email accounts, including creating,
listing, retrieving, and deleting accounts. It handles OAuth token storage
with encryption and manages default account settings.
"""
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple
from email_client.models import EmailAccount
from email_client.auth.oauth import TokenBundle
from email_client.config import SQLITE_DB_PATH, DEFAULT_IMAP_PORT, DEFAULT_SMTP_PORT


# Local exceptions (if utils.errors doesn't exist)
class AccountError(Exception):
    """Base exception for account-related errors."""
    pass


class AccountNotFoundError(AccountError):
    """Raised when an account is not found."""
    pass


class AccountCreationError(AccountError):
    """Raised when account creation fails."""
    pass


# Provider configuration mapping
_PROVIDER_CONFIGS = {
    "gmail": {
        "imap_host": "imap.gmail.com",
        "smtp_host": "smtp.gmail.com",
    },
    "outlook": {
        "imap_host": "outlook.office365.com",
        "smtp_host": "smtp.office365.com",
    },
    "yahoo": {
        "imap_host": "imap.mail.yahoo.com",
        "smtp_host": "smtp.mail.yahoo.com",
    },
    "custom": {
        "imap_host": "",
        "smtp_host": "",
    },
}


def _get_db_connection() -> sqlite3.Connection:
    """
    Get a database connection.
    
    This assumes storage.db provides a connection factory. For now, we'll
    create a direct connection, but this can be replaced with storage.db.get_connection()
    when that module is available.
    """
    # Ensure the database directory exists before connecting
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # TODO: Replace with storage.db.get_connection() when available
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure the accounts table schema exists."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            email_address TEXT NOT NULL UNIQUE,
            provider TEXT NOT NULL,
            imap_host TEXT NOT NULL,
            smtp_host TEXT NOT NULL,
            encrypted_token_bundle TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_default INTEGER DEFAULT 0
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_email ON accounts(email_address)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_default ON accounts(is_default)")
    conn.commit()


def _get_encryption_manager():
    """
    Get the encryption manager.
    
    This assumes storage.encryption provides an encryption manager. For now,
    we'll use a placeholder that can be replaced.
    """
    # TODO: Replace with storage.encryption.get_encryption_manager() when available
    try:
        from encryption.crypto import get_encryption_manager
        return get_encryption_manager()
    except ImportError:
        # Fallback: create a simple encryption manager for development
        # In production, this should use storage.encryption
        raise ImportError(
            "Encryption module not available. "
            "Please ensure storage.encryption is properly configured."
        )


def _encrypt_token_bundle(token_bundle: TokenBundle) -> str:
    """Encrypt a token bundle for storage."""
    # Serialize token bundle to JSON
    token_data = {
        "access_token": token_bundle.access_token,
        "refresh_token": token_bundle.refresh_token,
        "expires_at": token_bundle.expires_at.isoformat() if token_bundle.expires_at else None,
    }
    json_data = json.dumps(token_data)
    
    # Encrypt using encryption manager
    encryption_manager = _get_encryption_manager()
    return encryption_manager.encrypt(json_data)


def _decrypt_token_bundle(encrypted_data: str) -> TokenBundle:
    """Decrypt a stored token bundle."""
    if not encrypted_data:
        raise ValueError("No encrypted token data provided")
    
    encryption_manager = _get_encryption_manager()
    json_data = encryption_manager.decrypt(encrypted_data)
    token_data = json.loads(json_data)
    
    expires_at = None
    if token_data.get("expires_at"):
        expires_at = datetime.fromisoformat(token_data["expires_at"])
    
    return TokenBundle(
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        expires_at=expires_at,
    )


def _get_provider_hosts(provider_name: str) -> Tuple[str, str]:
    """
    Get IMAP and SMTP hosts for a provider.
    
    Args:
        provider_name: The provider name (e.g., 'gmail', 'outlook', 'yahoo', 'custom').
        
    Returns:
        A tuple of (imap_host, smtp_host).
        
    Raises:
        AccountCreationError: If provider is not recognized.
    """
    provider_lower = provider_name.lower()
    config = _PROVIDER_CONFIGS.get(provider_lower)
    
    if not config:
        raise AccountCreationError(f"Unknown provider: {provider_name}")
    
    return config["imap_host"], config["smtp_host"]


def _row_to_email_account(row: sqlite3.Row) -> EmailAccount:
    """Convert a database row to an EmailAccount model."""
    created_at = None
    if row["created_at"]:
        try:
            if isinstance(row["created_at"], str):
                created_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            else:
                created_at = datetime.fromisoformat(str(row["created_at"]))
        except (ValueError, AttributeError):
            pass
    
    return EmailAccount(
        id=row["id"],
        display_name=row["display_name"] or "",
        email_address=row["email_address"],
        provider=row["provider"],
        imap_host=row["imap_host"],
        smtp_host=row["smtp_host"],
        created_at=created_at,
        is_default=bool(row["is_default"]),
    )


def list_accounts() -> List[EmailAccount]:
    """
    List all email accounts.
    
    Returns:
        A list of all EmailAccount objects, ordered by creation date.
    """
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM accounts
            ORDER BY created_at ASC
        """)
        rows = cursor.fetchall()
        return [_row_to_email_account(row) for row in rows]
    finally:
        conn.close()


def get_account(account_id: int) -> Optional[EmailAccount]:
    """
    Get an account by ID.
    
    Args:
        account_id: The account ID.
        
    Returns:
        The EmailAccount if found, None otherwise.
    """
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if row:
            return _row_to_email_account(row)
        return None
    finally:
        conn.close()


def get_token_bundle(account_id: int) -> Optional[TokenBundle]:
    """
    Get the token bundle for an account.
    
    Args:
        account_id: The account ID.
        
    Returns:
        The TokenBundle if found, None otherwise.
        
    Raises:
        AccountNotFoundError: If the account doesn't exist.
        AccountError: If decryption fails.
    """
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT encrypted_token_bundle FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if not row:
            raise AccountNotFoundError(f"Account with ID {account_id} not found")
        
        encrypted_data = row["encrypted_token_bundle"]
        if not encrypted_data:
            return None
        
        return _decrypt_token_bundle(encrypted_data)
    except AccountNotFoundError:
        raise
    except Exception as e:
        raise AccountError(f"Failed to retrieve token bundle: {str(e)}")
    finally:
        conn.close()


def create_oauth_account(
    provider_name: str,
    token_bundle: TokenBundle,
    profile_email: str,
    display_name: str
) -> EmailAccount:
    """
    Create a new OAuth-based email account.
    
    Args:
        provider_name: The provider name (e.g., 'gmail', 'outlook', 'yahoo').
        token_bundle: The OAuth token bundle.
        profile_email: The email address from the OAuth profile.
        display_name: The display name for the account.
        
    Returns:
        The created EmailAccount.
        
    Raises:
        AccountCreationError: If account creation fails.
    """
    # Get provider-specific hosts
    imap_host, smtp_host = _get_provider_hosts(provider_name)
    
    # Encrypt token bundle
    try:
        encrypted_token = _encrypt_token_bundle(token_bundle)
    except Exception as e:
        raise AccountCreationError(f"Failed to encrypt token bundle: {str(e)}")
    
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if account with this email already exists
        cursor.execute("SELECT id FROM accounts WHERE email_address = ?", (profile_email,))
        if cursor.fetchone():
            raise AccountCreationError(f"Account with email {profile_email} already exists")
        
        # If this is the first account, make it default
        cursor.execute("SELECT COUNT(*) as count FROM accounts")
        is_first_account = cursor.fetchone()["count"] == 0
        
        # Insert new account
        cursor.execute("""
            INSERT INTO accounts (
                display_name, email_address, provider, imap_host, smtp_host,
                encrypted_token_bundle, is_default
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            display_name,
            profile_email,
            provider_name.lower(),
            imap_host,
            smtp_host,
            encrypted_token,
            1 if is_first_account else 0,
        ))
        
        account_id = cursor.lastrowid
        conn.commit()
        
        # Return the created account
        return get_account(account_id)
    except AccountCreationError:
        raise
    except Exception as e:
        conn.rollback()
        raise AccountCreationError(f"Failed to create account: {str(e)}")
    finally:
        conn.close()


def delete_account(account_id: int) -> None:
    """
    Delete an account by ID.
    
    Args:
        account_id: The account ID to delete.
        
    Raises:
        AccountNotFoundError: If the account doesn't exist.
    """
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if account exists
        cursor.execute("SELECT is_default FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if not row:
            raise AccountNotFoundError(f"Account with ID {account_id} not found")
        
        was_default = bool(row["is_default"])
        
        # Delete the account
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
        
        # If we deleted the default account, set another account as default
        if was_default:
            cursor.execute("SELECT id FROM accounts ORDER BY created_at ASC LIMIT 1")
            new_default_row = cursor.fetchone()
            if new_default_row:
                cursor.execute(
                    "UPDATE accounts SET is_default = 1 WHERE id = ?",
                    (new_default_row["id"],)
                )
                conn.commit()
    except AccountNotFoundError:
        raise
    except Exception as e:
        conn.rollback()
        raise AccountError(f"Failed to delete account: {str(e)}")
    finally:
        conn.close()


def set_default_account(account_id: int) -> None:
    """
    Set an account as the default account.
    
    Args:
        account_id: The account ID to set as default.
        
    Raises:
        AccountNotFoundError: If the account doesn't exist.
    """
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if account exists
        cursor.execute("SELECT id FROM accounts WHERE id = ?", (account_id,))
        if not cursor.fetchone():
            raise AccountNotFoundError(f"Account with ID {account_id} not found")
        
        # Clear all default flags
        cursor.execute("UPDATE accounts SET is_default = 0")
        
        # Set the specified account as default
        cursor.execute("UPDATE accounts SET is_default = 1 WHERE id = ?", (account_id,))
        conn.commit()
    except AccountNotFoundError:
        raise
    except Exception as e:
        conn.rollback()
        raise AccountError(f"Failed to set default account: {str(e)}")
    finally:
        conn.close()


def get_default_account() -> Optional[EmailAccount]:
    """
    Get the default account.
    
    Returns:
        The default EmailAccount if one exists, None otherwise.
    """
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE is_default = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            return _row_to_email_account(row)
        return None
    finally:
        conn.close()

