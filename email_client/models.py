"""
Core domain models for the email client.

This module contains pure domain models (dataclasses) without any database
or UI dependencies. These models represent the core business entities.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Set


@dataclass(slots=True)
class EmailAccount:
    """Represents an email account configuration."""
    id: Optional[int] = None
    display_name: str = ""
    email_address: str = ""
    provider: str = ""  # e.g., 'gmail', 'outlook', 'yahoo', 'custom'
    imap_host: str = ""
    smtp_host: str = ""
    created_at: Optional[datetime] = None
    is_default: bool = False


@dataclass(slots=True)
class Folder:
    """Represents an email folder (mailbox)."""
    id: Optional[int] = None
    account_id: int = 0
    name: str = ""
    server_path: str = ""  # Server-side path (e.g., "INBOX", "INBOX/Sent")
    unread_count: int = 0
    is_system_folder: bool = False  # True for Inbox/Sent/Drafts/Trash
    
    def increment_unread(self) -> None:
        """Increment the unread count by 1."""
        self.unread_count += 1
    
    def decrement_unread(self) -> None:
        """Decrement the unread count by 1, but not below 0."""
        if self.unread_count > 0:
            self.unread_count -= 1
    
    def reset_unread(self) -> None:
        """Reset the unread count to 0."""
        self.unread_count = 0


@dataclass(slots=True)
class EmailMessage:
    """Represents an email message."""
    id: Optional[int] = None
    account_id: int = 0
    folder_id: int = 0
    uid_on_server: int = 0  # IMAP UID
    sender: str = ""
    recipients: List[str] = field(default_factory=list)  # List of email addresses (To recipients)
    cc_recipients: List[str] = field(default_factory=list)  # CC recipients
    bcc_recipients: List[str] = field(default_factory=list)  # BCC recipients
    subject: str = ""
    preview_text: str = ""  # First few lines of the message
    sent_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    is_read: bool = False
    has_attachments: bool = False
    flags: Set[str] = field(default_factory=set)  # e.g., {'\\Seen', '\\Flagged', '\\Deleted'}
    body_plain: str = ""
    body_html: str = ""
    
    def mark_read(self) -> None:
        """Mark this email as read."""
        self.is_read = True
        self.flags.add('\\Seen')
    
    def mark_unread(self) -> None:
        """Mark this email as unread."""
        self.is_read = False
        self.flags.discard('\\Seen')
    
    def toggle_starred(self) -> None:
        """Toggle the starred/flagged status."""
        if '\\Flagged' in self.flags:
            self.flags.discard('\\Flagged')
        else:
            self.flags.add('\\Flagged')
    
    def is_starred(self) -> bool:
        """Check if this email is starred/flagged."""
        return '\\Flagged' in self.flags


@dataclass(slots=True)
class Attachment:
    """Represents an email attachment."""
    id: Optional[int] = None
    email_id: int = 0
    filename: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    local_path: Optional[str] = None  # Path to local cached file
    is_encrypted: bool = False

