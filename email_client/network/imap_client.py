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
    
    def __init__(self, account: EmailAccount, token_bundle: Optional[TokenBundle] = None, password: Optional[str] = None):
        """
        Initialize the IMAP client.
        
        Args:
            account: The email account configuration.
            token_bundle: Optional OAuth token bundle for XOAUTH2 authentication.
            password: Optional password for password-based authentication.
        """
        self.account = account
        self.token_bundle = token_bundle
        self.password = password
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self._authenticated = False
    
    def _refresh_token_if_needed(self) -> None:
        """
        Automatically refresh the access token if it's expired or about to expire.
        
        Raises:
            ImapAuthenticationError: If token refresh fails.
        """
        if not self.token_bundle or not self.account.id:
            return
        
        # Check if token is expired or about to expire (within 5 minutes)
        if self.token_bundle.expires_at:
            from datetime import datetime
            now = datetime.now()
            time_until_expiry = (self.token_bundle.expires_at - now).total_seconds()
            
            # Only refresh if expired or expiring soon (within 5 minutes)
            if time_until_expiry <= 300:  # 5 minutes or less remaining
                try:
                    from email_client.auth.accounts import refresh_token_bundle
                    refreshed_bundle = refresh_token_bundle(self.account.id)
                    if refreshed_bundle:
                        self.token_bundle = refreshed_bundle
                    else:
                        raise ImapAuthenticationError(
                            "Failed to refresh expired access token: refresh returned no token bundle. "
                            "Please remove and re-add your account to re-authenticate."
                        )
                except Exception as e:
                    # If refresh fails, provide clear error message
                    error_msg = str(e)
                    if "refresh token" in error_msg.lower() or "invalid" in error_msg.lower():
                        raise ImapAuthenticationError(
                            f"Token refresh failed: {error_msg}. "
                            "The refresh token may be invalid or revoked. "
                            "Please remove and re-add your account to re-authenticate."
                        )
                    else:
                        raise ImapAuthenticationError(
                            f"Failed to refresh expired access token: {error_msg}. "
                            "Please remove and re-add your account to re-authenticate."
                        )
    
    def _build_xoauth2_bytes(self) -> bytes:
        """
        Build the XOAUTH2 authentication string as raw bytes (for IMAP responder).
        
        Format: user=email\x01auth=Bearer access_token\x01\x01
        
        Returns:
            Raw bytes of the XOAUTH2 string (NOT base64-encoded).
            imaplib.authenticate() will automatically base64-encode this.
        """
        if not self.token_bundle or not self.token_bundle.access_token:
            raise ImapAuthenticationError("No access token available for XOAUTH2")
        
        # Automatically refresh token if expired or about to expire
        self._refresh_token_if_needed()
        
        # Strip whitespace from email to prevent XOAUTH2 authentication failures
        email = self.account.email_address.strip()
        
        # Build XOAUTH2 string - Format: user=email\x01auth=Bearer token\x01\x01
        auth_string = f"user={email}\x01auth=Bearer {self.token_bundle.access_token}\x01\x01"
        
        # Return raw bytes - imaplib will base64-encode it automatically
        return auth_string.encode('utf-8')
    
    def _build_xoauth2_string(self) -> str:
        """
        Build the XOAUTH2 authentication string (base64-encoded, for SMTP compatibility).
        
        This method returns a base64-encoded string for SMTP usage.
        For IMAP, use _build_xoauth2_bytes() instead, as imaplib handles base64 encoding.
        
        Returns:
            Base64-encoded XOAUTH2 string.
        """
        # Get raw bytes and base64-encode them for SMTP usage
        auth_bytes = self._build_xoauth2_bytes()
        return base64.b64encode(auth_bytes).decode('utf-8')
    
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
                # Validate token bundle before using
                if not self.token_bundle.access_token:
                    raise ImapAuthenticationError(
                        "Token bundle exists but access_token is missing or empty. "
                        "The token may not have been saved correctly."
                    )
                
                # Use XOAUTH2 authentication for OAuth accounts
                xoauth2_bytes = self._build_xoauth2_bytes()
                
                # Build responder function that returns raw bytes (imaplib handles base64 encoding)
                challenge_error_info = {'scope': None, 'status': None, 'schemes': None}
                
                def xoauth2_responder(challenge):
                    """Responder function for XOAUTH2 authentication."""
                    if challenge:
                        try:
                            challenge_str = challenge.decode('utf-8')
                            # Parse JSON error responses from Google
                            import json
                            try:
                                challenge_data = json.loads(challenge_str)
                                if isinstance(challenge_data, dict):
                                    challenge_error_info['status'] = challenge_data.get('status')
                                    challenge_error_info['scope'] = challenge_data.get('scope', '')
                                    challenge_error_info['schemes'] = challenge_data.get('schemes', '')
                                    
                                    # Abort on error responses
                                    if challenge_data.get('status') in ('400', '401'):
                                        return None
                            except json.JSONDecodeError:
                                pass
                        except Exception:
                            pass
                    
                    return xoauth2_bytes
                
                try:
                    result, data = self.connection.authenticate('XOAUTH2', xoauth2_responder)
                    if result != 'OK':
                        error_msg = data[0].decode('utf-8') if data and data[0] else 'Unknown error'
                        raise ImapAuthenticationError(f"XOAUTH2 authentication failed: {error_msg}")
                except imaplib.IMAP4.error as imap_error:
                    error_msg = str(imap_error)
                    
                    # Enhance error message with challenge details if available
                    enhanced_error = error_msg
                    if "Invalid SASL argument" in error_msg or "BAD" in error_msg:
                        scope = challenge_error_info.get('scope')
                        status = challenge_error_info.get('status')
                        
                        if scope:
                            enhanced_error = (
                                f"IMAP authentication failed.\n"
                                f"Server requested scope: {scope}\n"
                                f"Original error: {error_msg}\n\n"
                                "Please remove and re-add your account to get a fresh token with the correct scopes."
                            )
                        else:
                            enhanced_error = (
                                f"{error_msg}\n\n"
                                "The OAuth token may be missing the required scope for IMAP access. "
                                "Please remove and re-add your account."
                            )
                    
                    raise ImapAuthenticationError(f"IMAP authentication error: {enhanced_error}")
            elif self.password:
                # Use password-based authentication
                result, data = self.connection.login(self.account.email_address, self.password)
                if result != 'OK':
                    error_msg = data[0].decode('utf-8') if data and data[0] else 'Unknown error'
                    raise ImapAuthenticationError(
                        f"Password authentication failed: {error_msg}"
                    )
            else:
                # No authentication method provided
                raise ImapAuthenticationError(
                    "No authentication method provided. Either token_bundle (for OAuth) or password (for password-based) is required."
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
        elif self.connection:
            # Check if connection is still alive by trying a NOOP command
            try:
                self.connection.noop()
            except Exception:
                # Connection is dead, reconnect
                self.connection = None
                self._authenticated = False
                self._connect()
    
    def _quote_folder_name(self, folder_path: str) -> str:
        """
        Quote IMAP folder name if it contains spaces or special characters.
        
        IMAP requires folder names with spaces or special characters to be quoted.
        For example: "Sent Mail" -> '"Sent Mail"', "[Gmail]/All Mail" -> '"[Gmail]/All Mail"'
        
        Args:
            folder_path: The folder path to quote.
            
        Returns:
            The quoted folder path if needed, or the original path.
        """
        if not folder_path:
            return folder_path
        
        # If already quoted, return as is
        if folder_path.startswith('"') and folder_path.endswith('"'):
            return folder_path
        
        # Check if folder name needs quoting (contains spaces or special characters)
        # Simple folders like "INBOX" don't need quoting
        needs_quoting = (
            ' ' in folder_path or
            '[' in folder_path or
            ']' in folder_path or
            '/' in folder_path and not folder_path.startswith('"')
        )
        
        if needs_quoting:
            # Escape any existing quotes and wrap in quotes
            escaped = folder_path.replace('"', '\\"')
            return f'"{escaped}"'
        
        return folder_path
    
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
            
            # Map Gmail folder names to display names
            name = self._map_gmail_folder_name(server_path, name)
            
            # Determine if it's a system folder
            path_upper = server_path.upper()
            is_system = (
                path_upper == 'INBOX' or
                path_upper.endswith('/INBOX') or
                '[GMAIL]/ALL MAIL' in path_upper or
                '[GMAIL]/SENT MAIL' in path_upper or
                '[GMAIL]/DRAFTS' in path_upper or
                '[GMAIL]/TRASH' in path_upper or
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
    
    def _map_gmail_folder_name(self, server_path: str, name: str) -> str:
        """
        Map Gmail IMAP folder paths to user-friendly display names.
        
        Args:
            server_path: The full IMAP folder path (e.g., "INBOX", "[Gmail]/All Mail").
            name: The extracted folder name.
            
        Returns:
            User-friendly display name.
        """
        path_upper = server_path.upper()
        
        # Map common Gmail folders
        if path_upper == 'INBOX' or path_upper.endswith('/INBOX'):
            return 'Inbox'
        elif '[GMAIL]/ALL MAIL' in path_upper or 'ALL MAIL' in path_upper:
            return 'All Mail'
        elif '[GMAIL]/SENT MAIL' in path_upper or path_upper.endswith('/SENT') or path_upper.endswith('/SENT MAIL'):
            return 'Sent'
        elif '[GMAIL]/DRAFTS' in path_upper or path_upper.endswith('/DRAFTS'):
            return 'Drafts'
        elif '[GMAIL]/TRASH' in path_upper or path_upper.endswith('/TRASH'):
            return 'Trash'
        elif '[GMAIL]/SPAM' in path_upper or path_upper.endswith('/SPAM'):
            return 'Spam'
        elif '[GMAIL]/STARRED' in path_upper or path_upper.endswith('/STARRED'):
            return 'Starred'
        elif '[GMAIL]/IMPORTANT' in path_upper or path_upper.endswith('/IMPORTANT'):
            return 'Important'
        else:
            # For custom labels/folders, remove [Gmail]/ prefix if present
            if name.startswith('[Gmail]/'):
                return name.replace('[Gmail]/', '')
            return name
    
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
            # Select the folder (quote folder name if it contains spaces or special characters)
            folder_path = self._quote_folder_name(folder.server_path)
            result, data = self.connection.select(folder_path)
            if result != 'OK':
                raise ImapOperationError(f"Failed to select folder '{folder.server_path}': {result}")
            
            # Try to get latest emails using date-based search first
            # Search for emails from the last 90 days (to ensure we get recent emails)
            from datetime import timedelta
            since_date = datetime.now() - timedelta(days=90)
            date_str = since_date.strftime('%d-%b-%Y')
            
            # Try searching for recent emails first
            uid_list = []
            try:
                result, message_ids = self.connection.uid('search', None, f'SINCE {date_str}')
                if result == 'OK' and message_ids and message_ids[0]:
                    uid_list = message_ids[0].decode('utf-8').split()
            except Exception:
                # If date search fails, fall back to ALL
                pass
            
            # If date search returned too few results or failed, search ALL messages
            if len(uid_list) < limit:
                result, message_ids = self.connection.uid('search', None, 'ALL')
                if result != 'OK':
                    raise ImapOperationError(f"Failed to search folder '{folder.server_path}': {result}")
                
                if not message_ids or not message_ids[0]:
                    return []
                
                # Parse message IDs
                all_uids = message_ids[0].decode('utf-8').split()
                if all_uids:
                    # Combine recent UIDs with latest UIDs from all (take highest UIDs as they're usually newer)
                    if uid_list:
                        # Merge and deduplicate, prioritizing recent UIDs
                        uid_set = set(uid_list)
                        # Add the highest UIDs (last N from the full list) to ensure we cover latest
                        sample_size = max(limit * 10, 500)
                        latest_uids = all_uids[-sample_size:] if len(all_uids) > sample_size else all_uids
                        uid_set.update(latest_uids)
                        uid_list = list(uid_set)
                    else:
                        # Take highest UIDs (most recent)
                        sample_size = max(limit * 10, 500)
                        uid_list = all_uids[-sample_size:] if len(all_uids) > sample_size else all_uids
            
            if not uid_list:
                return []
            
            # Convert to integers and sort to get highest UIDs first (usually newest)
            # Then fetch a reasonable sample for date sorting
            try:
                uid_ints = sorted([int(uid) for uid in uid_list], reverse=True)
                # Take top N UIDs (highest = newest typically)
                sample_size = max(limit * 10, 500)
                top_uids = uid_ints[:sample_size]
                uid_list = [str(uid) for uid in top_uids]
            except (ValueError, TypeError):
                # If conversion fails, just use the list as-is
                pass
            
            # Fetch headers and flags in batch (much faster than individual requests)
            # IMAP supports fetching multiple messages at once
            messages = self._fetch_message_headers_batch(uid_list, folder)
            
            # Sort by date descending (newest first)
            # Use received_at if available, otherwise sent_at
            def get_sort_key(msg: EmailMessage):
                # Primary sort: received_at (or sent_at if received_at is None)
                date_value = msg.received_at if msg.received_at else msg.sent_at
                if date_value:
                    return date_value
                # Fallback to a very old date if no date
                return datetime.min
            
            messages.sort(key=get_sort_key, reverse=True)
            
            # Return only the requested limit, now properly sorted by date (newest first)
            return messages[:limit]
        except ImapOperationError:
            raise
        except Exception as e:
            raise ImapOperationError(f"Error fetching headers: {str(e)}")
    
    def _fetch_message_headers_batch(self, uid_list: List[str], folder: Folder) -> List[EmailMessage]:
        """
        Fetch headers and flags for multiple messages in a single IMAP request.
        
        This is much faster than fetching messages one by one.
        
        Args:
            uid_list: List of UID strings to fetch.
            folder: The folder containing the messages.
            
        Returns:
            List of EmailMessage objects.
        """
        messages = []
        
        if not uid_list:
            return messages
        
        try:
            # Build UID range string for batch fetch
            # Format: "1,2,3" or "1:100" for ranges
            # For simplicity, we'll use comma-separated list
            uid_range = ','.join(uid_list)
            
            # Fetch headers and flags for all UIDs in one request
            result, data = self.connection.uid('fetch', uid_range, '(RFC822.HEADER FLAGS)')
            
            if result != 'OK':
                # If batch fetch fails, fall back to individual fetches
                print(f"Batch fetch failed with result: {result}, falling back to individual fetches")
                return self._fallback_individual_fetch(uid_list, folder)
            
            if not data:
                return messages
            
            # Parse all responses
            # IMAP can return data in different formats:
            # - List of tuples: [(b'1 (UID 123 FLAGS (\\Seen) RFC822.HEADER {1234}', b'headers...'), ...]
            # - List of bytes: [b'1 (UID 123 ...', b'headers...', b'2 (UID 124 ...', ...]
            # - Mixed format
            
            # Handle case where data is a list of tuples
            response_items = []
            if data and isinstance(data[0], tuple):
                response_items = data
            elif data:
                # Try to parse as alternating format
                # Sometimes IMAP returns: [b'1 (UID ...', b'headers', b'2 (UID ...', b'headers', ...]
                i = 0
                while i < len(data) - 1:
                    if isinstance(data[i], bytes) and isinstance(data[i+1], bytes):
                        response_items.append((data[i], data[i+1]))
                        i += 2
                    else:
                        i += 1
            
            for response_item in response_items:
                if not isinstance(response_item, tuple) or len(response_item) < 2:
                    continue
                
                try:
                    # Extract UID from first part (e.g., "1 (UID 123 FLAGS (\\Seen) RFC822.HEADER {1234}")
                    flags_str = str(response_item[0])
                    
                    # Extract UID from the response
                    uid_match = re.search(r'UID\s+(\d+)', flags_str)
                    if not uid_match:
                        continue
                    
                    uid = int(uid_match.group(1))
                    
                    # Extract flags
                    flags = self._parse_flags(flags_str)
                    
                    # Extract headers from second part
                    headers_bytes = response_item[1]
                    if not isinstance(headers_bytes, bytes):
                        continue
                    
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
                    received_at = sent_at
                    
                    # Extract preview text (first line of body, but we only have headers)
                    preview_text = ""
                    
                    # Check for attachments
                    has_attachments = 'Content-Disposition' in msg or 'attachment' in str(msg.get('Content-Type', '')).lower()
                    
                    # Determine if read
                    is_read = '\\Seen' in flags
                    
                    message = EmailMessage(
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
                    messages.append(message)
                except Exception as e:
                    # Skip messages that can't be parsed
                    continue
            
            return messages
        except Exception as e:
            # If batch fetch fails, fall back to individual fetches
            print(f"Batch fetch exception: {e}, falling back to individual fetches")
            return self._fallback_individual_fetch(uid_list, folder)
    
    def _fallback_individual_fetch(self, uid_list: List[str], folder: Folder) -> List[EmailMessage]:
        """Fallback to individual fetches if batch fetch fails"""
        messages = []
        for uid_str in uid_list:
            try:
                uid = int(uid_str)
                message = self._fetch_message_headers(uid, folder)
                if message:
                    messages.append(message)
            except Exception:
                continue
        return messages
    
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
            # Select the folder (quote folder name if it contains spaces or special characters)
            folder_path = self._quote_folder_name(folder.server_path)
            result, data = self.connection.select(folder_path)
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
            # Select the folder (quote folder name if it contains spaces or special characters)
            folder_path = self._quote_folder_name(folder.server_path)
            result, data = self.connection.select(folder_path)
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
            # Select the source folder (quote folder name if it contains spaces or special characters)
            src_path = self._quote_folder_name(src.server_path)
            result, data = self.connection.select(src_path)
            if result != 'OK':
                raise ImapOperationError(f"Failed to select source folder '{src.server_path}': {result}")
            
            # Copy the message to destination (quote destination folder name too)
            dest_path = self._quote_folder_name(dest.server_path)
            result, data = self.connection.uid('copy', message_uid, dest_path)
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
    
    def delete_message(self, folder: Folder, message_uid: str) -> None:
        """
        Delete a message from the server.
        
        This marks the message with the \\Deleted flag and expunges it.
        For Gmail and most providers, this moves the message to Trash.
        
        Args:
            folder: The folder containing the message.
            message_uid: The message UID as a string.
            
        Raises:
            ImapOperationError: If the operation fails.
        """
        self._ensure_connected()
        
        try:
            # Select the folder (quote folder name if it contains spaces or special characters)
            folder_path = self._quote_folder_name(folder.server_path)
            result, data = self.connection.select(folder_path)
            if result != 'OK':
                raise ImapOperationError(f"Failed to select folder '{folder.server_path}': {result}")
            
            # Mark message as deleted
            result, data = self.connection.uid('store', message_uid, '+FLAGS', '(\\Deleted)')
            if result != 'OK':
                raise ImapOperationError(f"Failed to mark message {message_uid} as deleted: {result}")
            
            # Expunge to actually delete (or move to Trash for Gmail)
            result, data = self.connection.expunge()
            if result != 'OK':
                raise ImapOperationError(f"Failed to expunge deleted messages: {result}")
        except ImapOperationError:
            raise
        except Exception as e:
            raise ImapOperationError(f"Error deleting message: {str(e)}")
    
    def create_folder(self, folder_path: str) -> None:
        """
        Create a folder on the IMAP server.
        
        Args:
            folder_path: The folder path/name to create (e.g., "test", "My Folder").
            
        Raises:
            ImapOperationError: If the operation fails.
        """
        self._ensure_connected()
        
        try:
            # imaplib's create() method should handle string quoting automatically
            # However, we need to ensure the folder name is properly encoded
            # For IMAP, folder names should be passed as strings and imaplib will handle quoting
            result, data = self.connection.create(folder_path)
            if result != 'OK':
                error_msg = data[0].decode('utf-8', errors='ignore') if data and data[0] else 'Unknown error'
                raise ImapOperationError(f"CREATE command error: {error_msg}")
        except imaplib.IMAP4.error as imap_error:
            # Convert imaplib error to our custom exception
            error_msg = str(imap_error)
            raise ImapOperationError(f"CREATE command error: {error_msg}")
        except ImapOperationError:
            raise
        except Exception as e:
            if isinstance(e, ImapOperationError):
                raise
            raise ImapOperationError(f"Error creating folder: {str(e)}")
    
    def rename_folder(self, old_path: str, new_path: str) -> None:
        """
        Rename a folder on the IMAP server.
        
        Args:
            old_path: The current folder path/name.
            new_path: The new folder path/name.
            
        Raises:
            ImapOperationError: If the operation fails.
        """
        self._ensure_connected()
        
        try:
            # Let imaplib handle quoting internally
            result, data = self.connection.rename(old_path, new_path)
            if result != 'OK':
                error_msg = data[0].decode('utf-8') if data and data[0] else 'Unknown error'
                raise ImapOperationError(f"RENAME command error: {error_msg}")
        except ImapOperationError:
            raise
        except Exception as e:
            if isinstance(e, ImapOperationError):
                raise
            raise ImapOperationError(f"Error renaming folder: {str(e)}")
    
    def delete_folder(self, folder_path: str) -> None:
        """
        Delete a folder from the IMAP server.
        
        Args:
            folder_path: The folder path/name to delete.
            
        Raises:
            ImapOperationError: If the operation fails.
        """
        self._ensure_connected()
        
        try:
            # Let imaplib handle quoting internally
            result, data = self.connection.delete(folder_path)
            if result != 'OK':
                error_msg = data[0].decode('utf-8') if data and data[0] else 'Unknown error'
                raise ImapOperationError(f"DELETE command error: {error_msg}")
        except ImapOperationError:
            raise
        except Exception as e:
            if isinstance(e, ImapOperationError):
                raise
            raise ImapOperationError(f"Error deleting folder: {str(e)}")

