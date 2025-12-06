"""
Cache repository layer for SQLite persistence.

This module provides a repository pattern for managing cached email data,
converting between database rows and domain models.
"""
import base64
import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from email_client.models import Folder, EmailMessage, Attachment
from email_client.storage import db
from email_client.storage.encryption import encrypt_text, decrypt_text, DecryptionError


# ============================================================================
# Folders
# ============================================================================

def upsert_folder(folder: Folder) -> Folder:
    """
    Insert or update a folder.
    
    Args:
        folder: The folder to upsert.
        
    Returns:
        The folder with its ID populated.
    """
    # Check if folder exists
    existing = db.fetchone(
        "SELECT id FROM folders WHERE account_id = ? AND server_path = ?",
        (folder.account_id, folder.server_path)
    )
    
    if existing:
        # Update existing folder
        db.execute(
            """
            UPDATE folders 
            SET name = ?, unread_count = ?, is_system_folder = ?
            WHERE id = ?
            """,
            (
                folder.name,
                folder.unread_count,
                1 if folder.is_system_folder else 0,
                existing["id"]
            )
        )
        folder.id = existing["id"]
    else:
        # Insert new folder
        cursor = db.execute(
            """
            INSERT INTO folders (account_id, name, server_path, unread_count, is_system_folder)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                folder.account_id,
                folder.name,
                folder.server_path,
                folder.unread_count,
                1 if folder.is_system_folder else 0,
            )
        )
        folder.id = cursor.lastrowid
    
    return folder


def list_folders(account_id: int) -> List[Folder]:
    """
    List all folders for an account.
    
    Args:
        account_id: The account ID.
        
    Returns:
        A list of Folder objects.
    """
    rows = db.fetchall(
        "SELECT * FROM folders WHERE account_id = ? ORDER BY name",
        (account_id,)
    )
    
    return [_row_to_folder(row) for row in rows]


def get_folder(folder_id: int) -> Optional[Folder]:
    """
    Get a folder by ID.
    
    Args:
        folder_id: The folder ID.
        
    Returns:
        A Folder object or None if not found.
    """
    row = db.fetchone(
        "SELECT * FROM folders WHERE id = ?",
        (folder_id,)
    )
    
    if row:
        return _row_to_folder(row)
    return None


def delete_folder(folder_id: int) -> None:
    """
    Delete a folder by ID.
    
    Args:
        folder_id: The folder ID to delete.
    """
    db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))


# ============================================================================
# Emails
# ============================================================================

def upsert_email_header(email: EmailMessage) -> EmailMessage:
    """
    Insert or update an email header (metadata only, not body).
    
    Args:
        email: The email message with header information.
        
    Returns:
        The email with its ID populated.
    """
    # Serialize recipients list to JSON
    recipients_json = json.dumps(email.recipients) if email.recipients else "[]"
    
    # Serialize flags set to JSON
    flags_json = json.dumps(list(email.flags)) if email.flags else "[]"
    
    # If email.id is set, update by ID (this handles moved emails with new UIDs)
    if email.id:
        existing = db.fetchone(
            "SELECT id FROM emails WHERE id = ?",
            (email.id,)
        )
        if existing:
            # Update existing email header by ID (including updating uid_on_server)
            db.execute(
                """
                UPDATE emails 
                SET account_id = ?, folder_id = ?, uid_on_server = ?,
                    sender = ?, recipients = ?, subject = ?, preview_text = ?,
                    sent_at = ?, received_at = ?, is_read = ?, has_attachments = ?, flags = ?
                WHERE id = ?
                """,
                (
                    email.account_id,
                    email.folder_id,
                    email.uid_on_server,
                    email.sender,
                    recipients_json,
                    email.subject,
                    email.preview_text,
                    email.sent_at.isoformat() if email.sent_at else None,
                    email.received_at.isoformat() if email.received_at else None,
                    1 if email.is_read else 0,
                    1 if email.has_attachments else 0,
                    flags_json,
                    email.id
                )
            )
            return email
    
    # Check if email exists by unique key (account_id, folder_id, uid_on_server)
    existing = db.fetchone(
        """
        SELECT id FROM emails 
        WHERE account_id = ? AND folder_id = ? AND uid_on_server = ?
        """,
        (email.account_id, email.folder_id, email.uid_on_server)
    )
    
    if existing:
        # Update existing email header
        db.execute(
            """
            UPDATE emails 
            SET sender = ?, recipients = ?, subject = ?, preview_text = ?,
                sent_at = ?, received_at = ?, is_read = ?, has_attachments = ?, flags = ?
            WHERE id = ?
            """,
            (
                email.sender,
                recipients_json,
                email.subject,
                email.preview_text,
                email.sent_at.isoformat() if email.sent_at else None,
                email.received_at.isoformat() if email.received_at else None,
                1 if email.is_read else 0,
                1 if email.has_attachments else 0,
                flags_json,
                existing["id"]
            )
        )
        email.id = existing["id"]
    else:
        # Insert new email header
        cursor = db.execute(
            """
            INSERT INTO emails (
                account_id, folder_id, uid_on_server, sender, recipients,
                subject, preview_text, sent_at, received_at, is_read,
                has_attachments, flags
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email.account_id,
                email.folder_id,
                email.uid_on_server,
                email.sender,
                recipients_json,
                email.subject,
                email.preview_text,
                email.sent_at.isoformat() if email.sent_at else None,
                email.received_at.isoformat() if email.received_at else None,
                1 if email.is_read else 0,
                1 if email.has_attachments else 0,
                flags_json,
            )
        )
        email.id = cursor.lastrowid
    
    return email


def update_email_body(email_id: int, body_plain: str, body_html: str) -> None:
    """
    Update the body content of an email (encrypted).
    
    Args:
        email_id: The email ID.
        body_plain: Plain text body content.
        body_html: HTML body content.
    """
    # Encrypt body content
    encrypted_plain = encrypt_text(body_plain) if body_plain else None
    encrypted_html = encrypt_text(body_html) if body_html else None
    
    # Store as base64-encoded strings for SQLite TEXT storage
    plain_str = base64.b64encode(encrypted_plain).decode('utf-8') if encrypted_plain else None
    html_str = base64.b64encode(encrypted_html).decode('utf-8') if encrypted_html else None
    
    db.execute(
        "UPDATE emails SET body_plain = ?, body_html = ? WHERE id = ?",
        (plain_str, html_str, email_id)
    )


def list_emails(folder_id: int, limit: int = 100, offset: int = 0) -> List[EmailMessage]:
    """
    List emails in a folder.
    
    Args:
        folder_id: The folder ID.
        limit: Maximum number of emails to return.
        offset: Number of emails to skip.
        
    Returns:
        A list of EmailMessage objects (headers only, bodies not loaded).
    """
    rows = db.fetchall(
        """
        SELECT * FROM emails 
        WHERE folder_id = ? 
        ORDER BY received_at DESC, sent_at DESC
        LIMIT ? OFFSET ?
        """,
        (folder_id, limit, offset)
    )
    
    return [_row_to_email(row, load_body=False) for row in rows]


def count_emails(folder_id: int) -> int:
    """
    Count total emails in a folder.
    
    Args:
        folder_id: The folder ID.
        
    Returns:
        Total number of emails in the folder.
    """
    row = db.fetchone(
        "SELECT COUNT(*) as count FROM emails WHERE folder_id = ?",
        (folder_id,)
    )
    return row['count'] if row else 0


def get_email_by_id(email_id: int) -> Optional[EmailMessage]:
    """
    Get an email by ID with body content.
    
    Args:
        email_id: The email ID.
        
    Returns:
        An EmailMessage object with body content loaded, or None if not found.
    """
    row = db.fetchone("SELECT * FROM emails WHERE id = ?", (email_id,))
    if not row:
        return None
    
    return _row_to_email(row, load_body=True)


def mark_email_read(email_id: int, is_read: bool) -> None:
    """
    Mark an email as read or unread.
    
    Args:
        email_id: The email ID.
        is_read: True to mark as read, False to mark as unread.
    """
    # Update is_read flag
    db.execute(
        "UPDATE emails SET is_read = ? WHERE id = ?",
        (1 if is_read else 0, email_id)
    )
    
    # Update flags JSON
    row = db.fetchone("SELECT flags FROM emails WHERE id = ?", (email_id,))
    if row and row["flags"]:
        try:
            flags = set(json.loads(row["flags"]))
            if is_read:
                flags.add('\\Seen')
            else:
                flags.discard('\\Seen')
            db.execute(
                "UPDATE emails SET flags = ? WHERE id = ?",
                (json.dumps(list(flags)), email_id)
            )
        except (json.JSONDecodeError, TypeError):
            # If flags can't be parsed, just update is_read
            pass


# ============================================================================
# Attachments
# ============================================================================

def add_attachment(attachment: Attachment) -> Attachment:
    """
    Add an attachment to an email.
    
    Args:
        attachment: The attachment to add.
        
    Returns:
        The attachment with its ID populated.
    """
    cursor = db.execute(
        """
        INSERT INTO attachments (email_id, filename, mime_type, size_bytes, local_path, is_encrypted)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            attachment.email_id,
            attachment.filename,
            attachment.mime_type,
            attachment.size_bytes,
            attachment.local_path,
            1 if attachment.is_encrypted else 0,
        )
    )
    attachment.id = cursor.lastrowid
    return attachment


def list_attachments(email_id: int) -> List[Attachment]:
    """
    List all attachments for an email.
    
    Args:
        email_id: The email ID.
        
    Returns:
        A list of Attachment objects.
    """
    rows = db.fetchall(
        "SELECT * FROM attachments WHERE email_id = ? ORDER BY filename",
        (email_id,)
    )
    
    return [_row_to_attachment(row) for row in rows]


# ============================================================================
# Settings
# ============================================================================

def get_settings() -> Dict[str, Any]:
    """
    Get all application settings.
    
    Returns:
        A dictionary of key-value settings.
    """
    rows = db.fetchall("SELECT key, value FROM settings")
    
    settings = {}
    for row in rows:
        key = row["key"]
        value_str = row["value"]
        
        # Try to parse as JSON, fallback to string
        try:
            settings[key] = json.loads(value_str)
        except (json.JSONDecodeError, TypeError):
            settings[key] = value_str
    
    return settings


def save_settings(key: str, value: Any) -> None:
    """
    Save a setting.
    
    Args:
        key: The setting key.
        value: The setting value (will be JSON-encoded if not a string).
    """
    # Serialize value to JSON if not a string
    if isinstance(value, str):
        value_str = value
    else:
        value_str = json.dumps(value, default=str)
    
    db.execute(
        """
        INSERT OR REPLACE INTO settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
        (key, value_str)
    )


# ============================================================================
# Helper functions for row conversion
# ============================================================================

def _row_to_folder(row: sqlite3.Row) -> Folder:
    """Convert a database row to a Folder model."""
    return Folder(
        id=row["id"],
        account_id=row["account_id"],
        name=row["name"],
        server_path=row["server_path"],
        unread_count=row["unread_count"] or 0,
        is_system_folder=bool(row["is_system_folder"]),
    )


def _row_to_email(row: sqlite3.Row, load_body: bool = False) -> EmailMessage:
    """Convert a database row to an EmailMessage model."""
    # Parse recipients from JSON
    recipients = []
    if row["recipients"]:
        try:
            recipients = json.loads(row["recipients"])
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Parse flags from JSON
    flags = set()
    if row["flags"]:
        try:
            flags = set(json.loads(row["flags"]))
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Parse dates
    sent_at = _parse_datetime(row["sent_at"])
    received_at = _parse_datetime(row["received_at"])
    
    # Load body content if requested
    body_plain = ""
    body_html = ""
    if load_body:
        if row["body_plain"]:
            try:
                encrypted_bytes = base64.b64decode(row["body_plain"].encode('utf-8'))
                body_plain = decrypt_text(encrypted_bytes)
            except (DecryptionError, ValueError):
                body_plain = ""  # Decryption failed, return empty
        
        if row["body_html"]:
            try:
                encrypted_bytes = base64.b64decode(row["body_html"].encode('utf-8'))
                body_html = decrypt_text(encrypted_bytes)
            except (DecryptionError, ValueError):
                body_html = ""  # Decryption failed, return empty
    
    return EmailMessage(
        id=row["id"],
        account_id=row["account_id"],
        folder_id=row["folder_id"],
        uid_on_server=row["uid_on_server"],
        sender=row["sender"] or "",
        recipients=recipients,
        subject=row["subject"] or "",
        preview_text=row["preview_text"] or "",
        sent_at=sent_at,
        received_at=received_at,
        is_read=bool(row["is_read"]),
        has_attachments=bool(row["has_attachments"]),
        flags=flags,
        body_plain=body_plain,
        body_html=body_html,
    )


def _row_to_attachment(row: sqlite3.Row) -> Attachment:
    """Convert a database row to an Attachment model."""
    return Attachment(
        id=row["id"],
        email_id=row["email_id"],
        filename=row["filename"],
        mime_type=row["mime_type"] or "",
        size_bytes=row["size_bytes"] or 0,
        local_path=row["local_path"],
        is_encrypted=bool(row["is_encrypted"]),
    )


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse a datetime string from the database."""
    if not dt_str:
        return None
    
    try:
        # Try ISO format first
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        try:
            # Try SQLite timestamp format
            return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        except (ValueError, AttributeError):
            return None

