"""
Database models for the email client
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class Account:
    """Email account model"""
    account_id: Optional[int] = None
    email_address: str = ""
    display_name: str = ""
    provider: str = ""  # 'gmail', 'outlook', 'yahoo', 'custom'
    auth_type: str = ""  # 'oauth2' or 'password'
    encrypted_token: str = ""  # Encrypted OAuth token or password
    imap_server: str = ""
    imap_port: int = 993
    smtp_server: str = ""
    smtp_port: int = 587
    use_tls: bool = True
    created_at: Optional[datetime] = None
    last_sync: Optional[datetime] = None
    settings: str = "{}"  # JSON string for additional settings


@dataclass
class Folder:
    """Email folder model"""
    folder_id: Optional[int] = None
    account_id: int = 0
    name: str = ""
    full_path: str = ""  # e.g., "INBOX", "INBOX/Sent"
    folder_type: str = ""  # 'inbox', 'sent', 'drafts', 'trash', 'custom'
    sync_enabled: bool = True
    last_sync: Optional[datetime] = None


@dataclass
class Email:
    """Email message model"""
    email_id: Optional[int] = None
    account_id: int = 0
    folder_id: int = 0
    message_id: str = ""  # Unique message ID from server
    uid: int = 0  # IMAP UID
    sender: str = ""
    sender_name: str = ""
    recipients: str = ""  # Comma-separated
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    timestamp: Optional[datetime] = None
    is_read: bool = False
    is_starred: bool = False
    has_attachments: bool = False
    cached: bool = False  # Whether body is cached locally
    created_at: Optional[datetime] = None


@dataclass
class Attachment:
    """Email attachment model"""
    attachment_id: Optional[int] = None
    email_id: int = 0
    filename: str = ""
    file_path: str = ""  # Local file path
    file_size: int = 0
    mime_type: str = ""
    content_id: Optional[str] = None  # For inline attachments
    encrypted: bool = False

