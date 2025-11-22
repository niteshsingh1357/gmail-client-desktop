"""
Search and filtering for cached emails.

This module provides search functionality over cached email data
using SQL LIKE queries for text matching.
"""
import json
import sqlite3
from datetime import datetime
from typing import List, Optional
from email_client.models import EmailMessage
from email_client.storage import db


def search_emails(
    account_id: Optional[int] = None,
    query: str = "",
    folder_id: Optional[int] = None,
    read_state: Optional[str] = None,
    limit: int = 50
) -> List[EmailMessage]:
    """
    Search emails in the cache.
    
    Searches in subject, sender, and preview_text fields using SQL LIKE queries.
    Body text is not searched directly (it's encrypted), but preview_text
    contains a preview of the body content.
    
    Args:
        account_id: Optional account ID to filter by. If None, searches all accounts.
        query: Search query string. If empty, returns all emails matching filters.
        folder_id: Optional folder ID to filter by. If None, searches all folders.
        read_state: Optional read state filter. Values: 'read', 'unread', or None for all.
        limit: Maximum number of results to return (default: 50).
        
    Returns:
        A list of EmailMessage objects sorted by received_at DESC.
        
    Example:
        >>> # Search for emails containing "meeting" in any account
        >>> results = search_emails(query="meeting")
        
        >>> # Search unread emails in a specific folder
        >>> results = search_emails(folder_id=1, read_state="unread", query="urgent")
        
        >>> # Get all unread emails for an account
        >>> results = search_emails(account_id=1, read_state="unread")
    """
    # Build WHERE clause conditions
    conditions = []
    params = []
    
    # Account filter
    if account_id is not None:
        conditions.append("account_id = ?")
        params.append(account_id)
    
    # Folder filter
    if folder_id is not None:
        conditions.append("folder_id = ?")
        params.append(folder_id)
    
    # Read state filter
    if read_state is not None:
        if read_state.lower() == "read":
            conditions.append("is_read = 1")
        elif read_state.lower() == "unread":
            conditions.append("is_read = 0")
        # If read_state is something else, ignore it
    
    # Search query filter
    if query and query.strip():
        search_term = f"%{query.strip()}%"
        # Search in subject, sender, and preview_text
        conditions.append(
            "(subject LIKE ? OR sender LIKE ? OR preview_text LIKE ?)"
        )
        params.extend([search_term, search_term, search_term])
    
    # Build the SQL query
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
    
    sql_query = f"""
        SELECT * FROM emails
        {where_clause}
        ORDER BY received_at DESC, sent_at DESC
        LIMIT ?
    """
    params.append(limit)
    
    # Execute query
    rows = db.fetchall(sql_query, tuple(params))
    
    # Convert rows to EmailMessage objects (headers only, no body)
    return [_row_to_email_header(row) for row in rows]


def _row_to_email_header(row: sqlite3.Row) -> EmailMessage:
    """
    Convert a database row to an EmailMessage object (headers only, no body).
    
    This is a simplified version for search results that doesn't load
    or decrypt body content.
    """
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
        body_plain="",  # Not loaded for search results
        body_html="",   # Not loaded for search results
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

