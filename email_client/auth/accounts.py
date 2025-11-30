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
            auth_type TEXT DEFAULT 'oauth',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_default INTEGER DEFAULT 0
        )
    """)
    # Add missing columns if they don't exist (for existing databases)
    # SQLite doesn't support checking if a column exists directly,
    # so we use try/except on ALTER TABLE
    
    # Check and add encrypted_token_bundle column
    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN encrypted_token_bundle TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Check and add auth_type column
    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN auth_type TEXT DEFAULT 'oauth'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Check and add imap_host column (if missing)
    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN imap_host TEXT")
        # Update existing rows with empty string if needed
        cursor.execute("UPDATE accounts SET imap_host = '' WHERE imap_host IS NULL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Check and add smtp_host column (if missing)
    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN smtp_host TEXT")
        # Update existing rows with empty string if needed
        cursor.execute("UPDATE accounts SET smtp_host = '' WHERE smtp_host IS NULL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Check and add created_at column (if missing)
    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Check and add is_default column (if missing)
    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN is_default INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
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
    if "created_at" in row.keys() and row["created_at"]:
        try:
            if isinstance(row["created_at"], str):
                created_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            else:
                created_at = datetime.fromisoformat(str(row["created_at"]))
        except (ValueError, AttributeError):
            pass
    
    # Handle auth_type - use 'oauth' as default if column doesn't exist
    auth_type = "oauth"
    if "auth_type" in row.keys():
        auth_type = row["auth_type"] or "oauth"
    
    # Strip whitespace from email address when loading from database
    # This prevents XOAUTH2 authentication failures from hidden whitespace
    email_address = (row["email_address"] or "").strip()
    
    return EmailAccount(
        id=row["id"],
        display_name=row["display_name"] or "",
        email_address=email_address,
        provider=row["provider"],
        imap_host=row["imap_host"] if "imap_host" in row.keys() else "",
        smtp_host=row["smtp_host"] if "smtp_host" in row.keys() else "",
        auth_type=auth_type,
        created_at=created_at,
        is_default=bool(row["is_default"]) if "is_default" in row.keys() else False,
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
    Get the token bundle for an OAuth account.
    
    Args:
        account_id: The account ID.
        
    Returns:
        The TokenBundle if found, None otherwise.
        
    Raises:
        AccountNotFoundError: If the account doesn't exist.
        AccountError: If decryption fails or account is not OAuth-based.
    """
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT encrypted_token_bundle, auth_type FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if not row:
            raise AccountNotFoundError(f"Account with ID {account_id} not found")
        
        # Check auth_type - default to 'oauth' if column doesn't exist
        auth_type = "oauth"
        if "auth_type" in row.keys():
            auth_type = row["auth_type"] or "oauth"
        
        if auth_type != "oauth":
            raise AccountError(f"Account {account_id} is not an OAuth account")
        
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


def update_token_bundle(account_id: int, token_bundle: TokenBundle) -> None:
    """
    Update the token bundle for an OAuth account.
    
    Args:
        account_id: The account ID.
        token_bundle: The new TokenBundle to save.
        
    Raises:
        AccountNotFoundError: If the account doesn't exist.
        AccountError: If encryption or update fails.
    """
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Verify account exists
        cursor.execute("SELECT id FROM accounts WHERE id = ?", (account_id,))
        if not cursor.fetchone():
            raise AccountNotFoundError(f"Account with ID {account_id} not found")
        
        # Encrypt and update token bundle
        encrypted_data = _encrypt_token_bundle(token_bundle)
        cursor.execute(
            "UPDATE accounts SET encrypted_token_bundle = ? WHERE id = ?",
            (encrypted_data, account_id)
        )
        conn.commit()
    except AccountNotFoundError:
        raise
    except Exception as e:
        conn.rollback()
        raise AccountError(f"Failed to update token bundle: {str(e)}")
    finally:
        conn.close()


def refresh_token_bundle(account_id: int) -> Optional[TokenBundle]:
    """
    Refresh an expired access token for an OAuth account.
    
    This function retrieves the current token bundle, checks if it's expired,
    and if so, refreshes it using the refresh token. The new token bundle
    is automatically saved back to the database.
    
    Args:
        account_id: The account ID.
        
    Returns:
        The refreshed TokenBundle if refresh was successful, None otherwise.
        
    Raises:
        AccountNotFoundError: If the account doesn't exist.
        AccountError: If refresh fails or account is not OAuth-based.
        TokenRefreshError: If token refresh fails (e.g., invalid refresh token).
    """
    from email_client.auth.oauth import GoogleOAuthProvider, TokenRefreshError
    
    # Get current token bundle
    token_bundle = get_token_bundle(account_id)
    if not token_bundle:
        return None
    
    # Check if token is expired or about to expire (within 5 minutes)
    if token_bundle.expires_at:
        from datetime import datetime, timedelta
        now = datetime.now()
        time_until_expiry = (token_bundle.expires_at - now).total_seconds()
        
        # Only refresh if expired or expiring soon (within 5 minutes)
        if time_until_expiry > 300:  # More than 5 minutes remaining
            return token_bundle  # Token is still valid
    
    # Token is expired or expiring soon - refresh it
    if not token_bundle.refresh_token:
        raise AccountError("Cannot refresh token: no refresh token available. Please re-authenticate.")
    
    # Get account to determine provider
    account = get_account(account_id)
    if not account:
        raise AccountNotFoundError(f"Account with ID {account_id} not found")
    
    provider_name = account.provider.lower()
    
    try:
        if provider_name == 'gmail':
            # Use GoogleOAuthProvider to refresh token
            oauth_provider = GoogleOAuthProvider()
            refreshed_bundle = oauth_provider.refresh_tokens(token_bundle.refresh_token)
            
            # Update token bundle in database
            update_token_bundle(account_id, refreshed_bundle)
            
            return refreshed_bundle
        else:
            raise AccountError(f"Token refresh not supported for provider: {provider_name}")
    except TokenRefreshError:
        raise
    except Exception as e:
        raise AccountError(f"Failed to refresh token: {str(e)}")


def get_password(account_id: int) -> Optional[str]:
    """
    Get the password for a password-based account.
    
    Args:
        account_id: The account ID.
        
    Returns:
        The decrypted password if found, None otherwise.
        
    Raises:
        AccountNotFoundError: If the account doesn't exist.
        AccountError: If decryption fails or account is not password-based.
    """
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT encrypted_token_bundle, auth_type FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if not row:
            raise AccountNotFoundError(f"Account with ID {account_id} not found")
        
        # Check auth_type - default to 'oauth' if column doesn't exist
        auth_type = "oauth"
        if "auth_type" in row.keys():
            auth_type = row["auth_type"] or "oauth"
        
        if auth_type != "password":
            raise AccountError(f"Account {account_id} is not a password-based account")
        
        encrypted_data = row["encrypted_token_bundle"]
        if not encrypted_data:
            return None
        
        encryption_manager = _get_encryption_manager()
        return encryption_manager.decrypt(encrypted_data)
    except AccountNotFoundError:
        raise
    except Exception as e:
        raise AccountError(f"Failed to retrieve password: {str(e)}")
    finally:
        conn.close()


def _encrypt_password(password: str) -> str:
    """Encrypt a password for storage."""
    encryption_manager = _get_encryption_manager()
    return encryption_manager.encrypt(password)


def create_password_account(
    provider_name: str,
    email: str,
    password: str,
    display_name: str,
    imap_host: str = None,
    smtp_host: str = None,
    imap_port: int = 993,
    smtp_port: int = 587,
    use_tls: bool = True
) -> EmailAccount:
    """
    Create a new password-based email account.
    
    Args:
        provider_name: The provider name (e.g., 'gmail', 'outlook', 'yahoo', 'custom').
        email: The email address.
        password: The password or app password.
        display_name: The display name for the account.
        imap_host: IMAP server host (defaults to provider default if None).
        smtp_host: SMTP server host (defaults to provider default if None).
        imap_port: IMAP server port.
        smtp_port: SMTP server port.
        use_tls: Whether to use TLS/SSL.
        
    Returns:
        The created EmailAccount.
        
    Raises:
        AccountCreationError: If account creation fails.
    """
    # Get provider-specific hosts if not provided
    if imap_host is None or smtp_host is None:
        default_imap, default_smtp = _get_provider_hosts(provider_name)
        imap_host = imap_host or default_imap
        smtp_host = smtp_host or default_smtp
    
    # Encrypt password
    try:
        encrypted_password = _encrypt_password(password)
    except Exception as e:
        raise AccountCreationError(f"Failed to encrypt password: {str(e)}")
    
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if account with this email already exists
        cursor.execute("SELECT id FROM accounts WHERE email_address = ?", (email,))
        if cursor.fetchone():
            raise AccountCreationError(f"Account with email {email} already exists")
        
        # If this is the first account, make it default
        cursor.execute("SELECT COUNT(*) as count FROM accounts")
        is_first_account = cursor.fetchone()["count"] == 0
        
        # Insert new account
        cursor.execute("""
            INSERT INTO accounts (
                display_name, email_address, provider, imap_host, smtp_host,
                encrypted_token_bundle, auth_type, is_default
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            display_name,
            email,
            provider_name.lower(),
            imap_host,
            smtp_host,
            encrypted_password,  # Store encrypted password in encrypted_token_bundle field
            'password',
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
    # Strip whitespace from email to prevent XOAUTH2 authentication failures
    profile_email = profile_email.strip()
    display_name = display_name.strip() if display_name else ''
    
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
                encrypted_token_bundle, auth_type, is_default
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            display_name,
            profile_email,
            provider_name.lower(),
            imap_host,
            smtp_host,
            encrypted_token,
            'oauth',
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

