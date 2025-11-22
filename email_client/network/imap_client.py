"""
High-level IMAP client wrapper.

This module provides a clean, high-level interface for IMAP operations,
hiding the complexity of imaplib and providing better error handling.
"""
import imaplib
import email
import re
import base64
from email.header import decode_header
from email.utils import parseaddr, parsedate_tz, mktime_tz
from typing import List, Optional, Tuple
from datetime import datetime
from email_client.models import EmailAccount, Folder, EmailMessage
from email_client.auth.oauth import TokenBundle
from email_client.config import DEFAULT_IMAP_PORT


class ImapError(Exception):
    """Base exception for IMAP-related errors."""
    pass


class ImapConnectionError(ImapError):
    """Raised when IMAP connection fails."""
    pass


class ImapAuthenticationError(ImapError):
    """Raised when IMAP authentication fails."""
    pass


class ImapOperationError(ImapError):
    """Raised when an IMAP operation fails."""
    pass


class ImapClient:
    """
    High-level IMAP client wrapper.
    
    Supports XOAUTH2 authentication and provides a clean interface
    for common IMAP operations.
    """
    
    def __init__(self, account: EmailAccount, token_bundle: Optional[TokenBundle] = None):
        """
        Initialize the IMAP client.
        
        Args:
            account: The email account configuration.
            token_bundle: Optional OAuth token bundle for XOAUTH2 authentication.
        """
        self.account = account
        self.token_bundle = token_bundle
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self._authenticated = False
    
    def _build_xoauth2_string(self) -> str:
        """
        Build the XOAUTH2 authentication string.
        
        Format: user=email\1auth=Bearer access_token\1\1
        
        Returns:
            Base64-encoded XOAUTH2 string.
        """
        if not self.token_bundle or not self.token_bundle.access_token:
            raise ImapAuthenticationError("No access token available for XOAUTH2")
        
        auth_string = f"user={self.account.email_address}\x01auth=Bearer {self.token_bundle.access_token}\x01\x01"
        return base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    
    def _connect(self) -> None:
        """Establish connection to IMAP server."""
        if self.connection and self._authenticated:
            return
        
        try:
            host = self.account.imap_host
            port = DEFAULT_IMAP_PORT
            
            # Connect with SSL
            self.connection = imaplib.IMAP4_SSL(host, port)
            
            # Authenticate
            if self.token_bundle:
                # Use XOAUTH2 authentication
                xoauth2_string = self._build_xoauth2_string()
                result, data = self.connection.authenticate('XOAUTH2', lambda x: xoauth2_string)
                if result != 'OK':
                    raise ImapAuthenticationError(
                        f"XOAUTH2 authentication failed: {data[0].decode('utf-8') if data else 'Unknown error'}"
                    )
            else:
                # Fallback: password-based authentication (not recommended for OAuth accounts)
                raise ImapAuthenticationError(
                    "No token bundle provided. XOAUTH2 authentication required."
                )
            
            self._authenticated = True
        except imaplib.IMAP4.error as e:
            raise ImapConnectionError(f"IMAP connection failed: {str(e)}")
        except Exception as e:
            if isinstance(e, (ImapError, ImapConnectionError, ImapAuthenticationError)):
                raise
            raise ImapConnectionError(f"Failed to connect to IMAP server: {str(e)}")
    
    def _ensure_connected(self) -> None:
        """Ensure connection is established."""
        if not self._authenticated or not self.connection:
            self._connect()
    
    def __enter__(self):
        """Context manager entry."""
        self._connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
    
    def close(self) -> None:
        """Close the IMAP connection."""
        if self.connection and self._authenticated:
            try:
                self.connection.logout()
            except Exception:
                pass
            finally:
                self.connection = None
                self._authenticated = False
    
    def list_folders(self) -> List[Folder]:
        """
        List all folders on the server.
        
        Returns:
            A list of Folder objects with name and server_path populated.
            
        Raises:
            ImapOperationError: If the operation fails.
        """
        self._ensure_connected()
        
        try:
            result, data = self.connection.list()
            if result != 'OK':
                raise ImapOperationError(f"Failed to list folders: {result}")
            
            folders = []
            for folder_data in data:
                try:
                    folder = self._parse_folder_list_item(folder_data)
                    if folder:
                        folders.append(folder)
                except Exception as e:
                    # Skip folders that can't be parsed
                    continue
            
            return folders
        except ImapOperationError:
            raise
        except Exception as e:
            raise ImapOperationError(f"Error listing folders: {str(e)}")
    
    def _parse_folder_list_item(self, folder_data: bytes) -> Optional[Folder]:
        """
        Parse an IMAP LIST response item into a Folder object.
        
        Args:
            folder_data: Raw folder data from IMAP LIST command.
            
        Returns:
            A Folder object or None if parsing fails.
        """
        try:
            if isinstance(folder_data, bytes):
                folder_str = folder_data.decode('utf-8', errors='ignore')
            else:
                folder_str = str(folder_data)
            
            # IMAP LIST format: (flags) "hierarchy" "folder name"
            # Example: (\HasNoChildren) "/" "INBOX"
            
            # Extract folder path (last quoted string)
            quoted_strings = re.findall(r'"([^"]*)"', folder_str)
            if not quoted_strings:
                return None
            
            server_path = quoted_strings[-1]
            
            # Decode folder name if it's encoded
            try:
                decoded_parts = decode_header(server_path)
                decoded_path = ""
                for part, encoding in decoded_parts:
                    if isinstance(part, bytes):
                        if encoding:
                            decoded_path += part.decode(encoding)
                        else:
                            decoded_path += part.decode('utf-8', errors='ignore')
                    else:
                        decoded_path += part
                server_path = decoded_path
            except Exception:
                pass  # Use original if decoding fails
            
            # Extract folder name (last part of path)
            name = server_path.split('/')[-1] if '/' in server_path else server_path
            
            # Determine if it's a system folder
            path_upper = server_path.upper()
            is_system = (
                path_upper == 'INBOX' or
                'SENT' in path_upper or
                'DRAFT' in path_upper or
                'TRASH' in path_upper or
                'DELETED' in path_upper
            )
            
            return Folder(
                account_id=self.account.id or 0,
                name=name,
                server_path=server_path,
                is_system_folder=is_system,
                unread_count=0,  # Will be updated when fetching headers
            )
        except Exception:
            return None
    
    def fetch_headers(
        self,
        folder: Folder,
        limit: int = 100
    ) -> List[EmailMessage]:
        """
        Fetch email headers from a folder.
        
        Args:
            folder: The folder to fetch from.
            limit: Maximum number of emails to fetch.
            
        Returns:
            A list of EmailMessage objects with metadata and flags populated,
            but not body content.
            
        Raises:
            ImapOperationError: If the operation fails.
        """
        self._ensure_connected()
        
        try:
            # Select the folder
            result, data = self.connection.select(folder.server_path)
            if result != 'OK':
                raise ImapOperationError(f"Failed to select folder '{folder.server_path}': {result}")
            
            # Search for all messages
            result, message_ids = self.connection.search(None, 'ALL')
            if result != 'OK':
                raise ImapOperationError(f"Failed to search folder '{folder.server_path}': {result}")
            
            if not message_ids or not message_ids[0]:
                return []
            
            # Parse message IDs
            uid_list = message_ids[0].decode('utf-8').split()
            if not uid_list:
                return []
            
            # Get the most recent messages (limit)
            uid_list = uid_list[-limit:] if len(uid_list) > limit else uid_list
            
            # Fetch headers and flags for these UIDs
            messages = []
            for uid_str in reversed(uid_list):  # Most recent first
                try:
                    uid = int(uid_str)
                    message = self._fetch_message_headers(uid, folder)
                    if message:
                        messages.append(message)
                except (ValueError, Exception) as e:
                    continue  # Skip invalid UIDs
            
            return messages
        except ImapOperationError:
            raise
        except Exception as e:
            raise ImapOperationError(f"Error fetching headers: {str(e)}")
    
    def _fetch_message_headers(self, uid: int, folder: Folder) -> Optional[EmailMessage]:
        """
        Fetch headers and flags for a single message.
        
        Args:
            uid: The message UID.
            folder: The folder containing the message.
            
        Returns:
            An EmailMessage object with headers and flags populated.
        """
        try:
            # Fetch headers and flags
            result, data = self.connection.uid('fetch', str(uid), '(RFC822.HEADER FLAGS)')
            if result != 'OK' or not data or not data[0]:
                return None
            
            # Parse the response
            # data[0] is typically: (b'1 (UID 123 FLAGS (\\Seen \\Flagged) RFC822.HEADER {size}', b'headers...')
            response_item = data[0]
            if not isinstance(response_item, tuple) or len(response_item) < 2:
                return None
            
            # Extract flags from the first part
            flags_str = str(response_item[0])
            flags = self._parse_flags(flags_str)
            
            # Extract headers from the second part
            headers_bytes = response_item[1]
            if not isinstance(headers_bytes, bytes):
                return None
            
            # Parse email headers
            msg = email.message_from_bytes(headers_bytes)
            
            # Extract metadata
            subject = self._decode_header(msg.get('Subject', ''))
            sender = self._decode_header(msg.get('From', ''))
            recipients_str = self._decode_header(msg.get('To', ''))
            
            # Parse sender
            sender_name, sender_email = parseaddr(sender)
            if not sender_email:
                sender_email = sender
            
            # Parse recipients
            recipients = []
            if recipients_str:
                for addr in recipients_str.split(','):
                    _, email_addr = parseaddr(addr.strip())
                    if email_addr:
                        recipients.append(email_addr)
            
            # Parse dates
            sent_at = self._parse_date(msg.get('Date'))
            received_at = sent_at  # IMAP doesn't provide received_at separately
            
            # Extract preview text (first line of body, but we only have headers)
            preview_text = ""
            
            # Check for attachments
            has_attachments = 'Content-Disposition' in msg or 'attachment' in str(msg.get('Content-Type', '')).lower()
            
            # Determine if read
            is_read = '\\Seen' in flags
            
            return EmailMessage(
                account_id=self.account.id or 0,
                folder_id=folder.id or 0,
                uid_on_server=uid,
                sender=sender_email,
                recipients=recipients,
                subject=subject,
                preview_text=preview_text,
                sent_at=sent_at,
                received_at=received_at,
                is_read=is_read,
                has_attachments=has_attachments,
                flags=flags,
            )
        except Exception:
            return None
    
    def _parse_flags(self, flags_str: str) -> set:
        """Parse IMAP flags from a response string."""
        flags = set()
        # Look for flags like \Seen, \Flagged, etc.
        flag_pattern = r'\\([A-Za-z]+)'
        matches = re.findall(flag_pattern, flags_str)
        for match in matches:
            flags.add(f'\\{match}')
        return flags
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse an email date string to datetime."""
        if not date_str:
            return None
        try:
            date_tuple = parsedate_tz(date_str)
            if date_tuple:
                return datetime.fromtimestamp(mktime_tz(date_tuple))
        except Exception:
            pass
        return None
    
    def _decode_header(self, header: str) -> str:
        """Decode an email header."""
        try:
            decoded_parts = decode_header(header)
            decoded_str = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_str += part.decode(encoding)
                    else:
                        decoded_str += part.decode('utf-8', errors='ignore')
                else:
                    decoded_str += part
            return decoded_str
        except Exception:
            return header
    
    def fetch_body(
        self,
        folder: Folder,
        message_uid: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch the body of an email message.
        
        Args:
            folder: The folder containing the message.
            message_uid: The message UID as a string.
            
        Returns:
            A tuple of (plain_text, html_text). Either or both may be None.
            
        Raises:
            ImapOperationError: If the operation fails.
        """
        self._ensure_connected()
        
        try:
            # Select the folder
            result, data = self.connection.select(folder.server_path)
            if result != 'OK':
                raise ImapOperationError(f"Failed to select folder '{folder.server_path}': {result}")
            
            # Fetch the message body
            result, data = self.connection.uid('fetch', message_uid, '(RFC822)')
            if result != 'OK' or not data or not data[0]:
                raise ImapOperationError(f"Failed to fetch message {message_uid}")
            
            # Parse the email
            response_item = data[0]
            if not isinstance(response_item, tuple) or len(response_item) < 2:
                raise ImapOperationError(f"Invalid response format for message {message_uid}")
            
            email_bytes = response_item[1]
            if not isinstance(email_bytes, bytes):
                raise ImapOperationError(f"Invalid email data for message {message_uid}")
            
            msg = email.message_from_bytes(email_bytes)
            
            # Extract body parts
            plain_text = None
            html_text = None
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    
                    # Skip attachments
                    if "attachment" in content_disposition.lower():
                        continue
                    
                    if content_type == "text/plain" and plain_text is None:
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                plain_text = payload.decode('utf-8', errors='ignore')
                        except Exception:
                            pass
                    elif content_type == "text/html" and html_text is None:
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                html_text = payload.decode('utf-8', errors='ignore')
                        except Exception:
                            pass
            else:
                content_type = msg.get_content_type()
                try:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        if content_type == "text/plain":
                            plain_text = payload.decode('utf-8', errors='ignore')
                        elif content_type == "text/html":
                            html_text = payload.decode('utf-8', errors='ignore')
                except Exception:
                    pass
            
            return (plain_text, html_text)
        except ImapOperationError:
            raise
        except Exception as e:
            raise ImapOperationError(f"Error fetching body: {str(e)}")
    
    def mark_read(self, folder: Folder, message_uid: str) -> None:
        """
        Mark a message as read.
        
        Args:
            folder: The folder containing the message.
            message_uid: The message UID as a string.
            
        Raises:
            ImapOperationError: If the operation fails.
        """
        self._ensure_connected()
        
        try:
            # Select the folder
            result, data = self.connection.select(folder.server_path)
            if result != 'OK':
                raise ImapOperationError(f"Failed to select folder '{folder.server_path}': {result}")
            
            # Add \Seen flag
            result, data = self.connection.uid('store', message_uid, '+FLAGS', '(\\Seen)')
            if result != 'OK':
                raise ImapOperationError(f"Failed to mark message {message_uid} as read: {result}")
        except ImapOperationError:
            raise
        except Exception as e:
            raise ImapOperationError(f"Error marking message as read: {str(e)}")
    
    def move_message(
        self,
        src: Folder,
        dest: Folder,
        message_uid: str
    ) -> None:
        """
        Move a message from one folder to another.
        
        Args:
            src: The source folder.
            dest: The destination folder.
            message_uid: The message UID as a string.
            
        Raises:
            ImapOperationError: If the operation fails.
        """
        self._ensure_connected()
        
        try:
            # Select the source folder
            result, data = self.connection.select(src.server_path)
            if result != 'OK':
                raise ImapOperationError(f"Failed to select source folder '{src.server_path}': {result}")
            
            # Copy the message to destination
            result, data = self.connection.uid('copy', message_uid, dest.server_path)
            if result != 'OK':
                raise ImapOperationError(
                    f"Failed to copy message {message_uid} to '{dest.server_path}': {result}"
                )
            
            # Mark as deleted in source folder
            result, data = self.connection.uid('store', message_uid, '+FLAGS', '(\\Deleted)')
            if result != 'OK':
                raise ImapOperationError(f"Failed to mark message {message_uid} as deleted: {result}")
            
            # Expunge to actually delete
            result, data = self.connection.expunge()
            if result != 'OK':
                raise ImapOperationError(f"Failed to expunge deleted messages: {result}")
        except ImapOperationError:
            raise
        except Exception as e:
            raise ImapOperationError(f"Error moving message: {str(e)}")

