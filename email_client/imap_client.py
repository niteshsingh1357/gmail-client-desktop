"""
IMAP client for email retrieval
"""
import imaplib
import email
import re
import codecs
from email.header import decode_header
from email.utils import parseaddr
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import config
from database.models import Email, Folder
from utils.helpers import parse_email_address


class IMAPClient:
    """IMAP client for retrieving emails"""
    
    def __init__(self, server: str, port: int, use_tls: bool = True):
        self.server = server
        self.port = port
        self.use_tls = use_tls
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.authenticated = False
    
    def connect(self, username: str, password: str) -> bool:
        """Connect and authenticate to IMAP server"""
        try:
            if self.use_tls:
                self.connection = imaplib.IMAP4_SSL(self.server, self.port, timeout=config.IMAP_TIMEOUT)
            else:
                self.connection = imaplib.IMAP4(self.server, self.port, timeout=config.IMAP_TIMEOUT)
                self.connection.starttls()
            
            result, data = self.connection.login(username, password)
            if result == 'OK':
                self.authenticated = True
                return True
            return False
        except Exception as e:
            print(f"IMAP connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.connection and self.authenticated:
            try:
                self.connection.logout()
            except:
                pass
            self.authenticated = False
            self.connection = None
    
    def list_folders(self) -> List[Folder]:
        """List all folders on the server"""
        if not self.authenticated:
            return []
        
        folders = []
        try:
            result, data = self.connection.list()
            if result == 'OK':
                for folder_data in data:
                    try:
                        # Parse folder information
                        if isinstance(folder_data, bytes):
                            folder_str = folder_data.decode('utf-8', errors='ignore')
                        else:
                            folder_str = str(folder_data)
                        
                        # IMAP LIST response format: (flags) "hierarchy" "folder name"
                        # Example: (\HasNoChildren) "/" "INBOX"
                        # Or: (\HasNoChildren) "/" "Cloud Masters"
                        
                        # Extract folder path - it's usually in quotes at the end
                        # Find the last quoted string
                        quoted_strings = re.findall(r'"([^"]*)"', folder_str)
                        if quoted_strings:
                            folder_path_raw = quoted_strings[-1]  # Last quoted string is the folder path
                            # Keep original path for IMAP operations (may be encoded)
                            folder_path_original = folder_path_raw
                            # Decode folder path for display (may be encoded as =?UTF-8?Q?...)
                            folder_path_decoded = self._decode_header(folder_path_raw)
                            folder_name = folder_path_decoded.split('/')[-1] if '/' in folder_path_decoded else folder_path_decoded
                            # Use decoded path for full_path (IMAP can handle both, but decoded is cleaner)
                            folder_path = folder_path_decoded
                        else:
                            # Fallback: try splitting by ' "/" '
                            parts = folder_str.split(' "/" ')
                            if len(parts) == 2:
                                folder_path_raw = parts[1].strip('"')
                                folder_path_original = folder_path_raw
                                folder_path_decoded = self._decode_header(folder_path_raw)
                                folder_name = folder_path_decoded.split('/')[-1]
                                folder_path = folder_path_decoded
                            else:
                                continue
                        
                        # Determine folder type
                        folder_type = 'custom'
                        folder_lower = folder_path.upper()
                        if folder_path.upper() == 'INBOX' or folder_path.upper().endswith('/INBOX'):
                            folder_type = 'inbox'
                        elif 'SENT' in folder_lower or folder_lower.endswith('/SENT'):
                            folder_type = 'sent'
                        elif 'DRAFT' in folder_lower or folder_lower.endswith('/DRAFTS'):
                            folder_type = 'drafts'
                        elif 'TRASH' in folder_lower or 'DELETED' in folder_lower or folder_lower.endswith('/TRASH'):
                            folder_type = 'trash'
                        
                        folders.append(Folder(
                            name=folder_name,
                            full_path=folder_path,
                            folder_type=folder_type,
                            sync_enabled=True
                        ))
                    except Exception as e:
                        print(f"Error parsing folder data: {e}")
                        continue
        except Exception as e:
            print(f"Error listing folders: {e}")
        
        return folders
    
    def _encode_folder_name(self, folder_name: str) -> str:
        """Encode folder name to UTF-7 for IMAP (Gmail requirement)"""
        try:
            # Gmail requires UTF-7 encoding for folder names with spaces or special chars
            # imaplib handles this internally, but we need to ensure proper encoding
            # Use Python's codecs module for UTF-7 encoding
            if not folder_name:
                return folder_name
            
            # Check if folder name needs encoding (has spaces or special characters)
            needs_encoding = ' ' in folder_name or any(ord(c) > 127 for c in folder_name)
            
            if needs_encoding:
                # Encode to UTF-7
                # UTF-7: ASCII chars pass through, others encoded as +base64-
                encoded_bytes = codecs.encode(folder_name, 'utf-7')
                # UTF-7 output is ASCII, so decode to string
                encoded = encoded_bytes.decode('ascii')
                return encoded
            else:
                return folder_name
        except Exception as e:
            # If encoding fails, return original
            print(f"Warning: Failed to encode folder name '{folder_name}': {e}")
            return folder_name
    
    def select_folder(self, folder_path: str) -> bool:
        """Select a folder"""
        if not self.authenticated:
            return False
        if not folder_path:
            return False
        
        # List of folder paths to try (in order of preference)
        paths_to_try = [folder_path]
        
        # For Gmail, try different variations
        # Gmail uses "[Gmail]/Sent Mail" format
        if 'Sent Mail' in folder_path or folder_path == 'Sent Mail':
            # Try Gmail-specific paths
            paths_to_try.extend([
                '[Gmail]/Sent Mail',
                '"[Gmail]/Sent Mail"',
                '[Gmail].Sent Mail',
            ])
        elif 'Drafts' in folder_path or folder_path == 'Drafts':
            paths_to_try.extend([
                '[Gmail]/Drafts',
                '"[Gmail]/Drafts"',
                '[Gmail].Drafts',
            ])
        elif 'Trash' in folder_path or folder_path == 'Trash':
            paths_to_try.extend([
                '[Gmail]/Trash',
                '"[Gmail]/Trash"',
                '[Gmail].Trash',
            ])
        
        # If folder has spaces, also try UTF-7 encoding
        if ' ' in folder_path:
            try:
                encoded_path = self._encode_folder_name(folder_path)
                if encoded_path not in paths_to_try:
                    paths_to_try.append(encoded_path)
            except:
                pass
        
        # Try each path
        for path in paths_to_try:
            try:
                result, data = self.connection.select(path)
                if result == 'OK':
                    return True
            except Exception as e:
                error_msg = str(e)
                # Only log if it's not a BAD command error (which is expected for wrong paths)
                if "BAD" not in error_msg and "Could not parse" not in error_msg:
                    print(f"Error selecting folder '{path}': {e}")
                continue
        
        # If all attempts failed, print a warning
        print(f"Warning: Failed to select folder '{folder_path}'. Tried paths: {paths_to_try}")
        return False
    
    def fetch_emails(self, folder_path: str, limit: int = 100, since_date: Optional[datetime] = None) -> List[Email]:
        """Fetch emails from a folder"""
        if not self.authenticated:
            print("Not authenticated, cannot fetch emails")
            return []
        
        if not self.select_folder(folder_path):
            print(f"Failed to select folder: {folder_path}")
            return []
        
        emails = []
        try:
            # Build search criteria
            search_criteria = 'ALL'
            if since_date:
                date_str = since_date.strftime('%d-%b-%Y')
                search_criteria = f'(SINCE {date_str})'
            
            # Search for emails
            result, message_ids = self.connection.search(None, search_criteria)
            if result != 'OK':
                print(f"Search failed for folder {folder_path}: {result}")
                return []
            
            if not message_ids or len(message_ids) == 0:
                print(f"No message IDs returned for folder {folder_path}")
                return []
            
            # Handle case where message_ids[0] might be empty
            if isinstance(message_ids[0], bytes):
                message_id_str = message_ids[0].decode('utf-8', errors='ignore')
            else:
                message_id_str = str(message_ids[0])
            
            if not message_id_str.strip():
                print(f"Folder {folder_path} is empty (no emails)")
                return []
            
            message_id_list = message_id_str.split()
            if not message_id_list:
                print(f"Folder {folder_path} is empty (no message IDs)")
                return []
            
            print(f"Found {len(message_id_list)} emails in folder {folder_path}")
            
            # Get the most recent emails (limit)
            message_id_list = message_id_list[-limit:] if len(message_id_list) > limit else message_id_list
            
            for msg_id in reversed(message_id_list):  # Most recent first
                try:
                    # First, get the UID for this message
                    uid_result, uid_data = self.connection.fetch(msg_id, '(UID)')
                    uid = None
                    if uid_result == 'OK' and uid_data and len(uid_data) > 0:
                        try:
                            # uid_data[0] might be a tuple or bytes/string
                            uid_item = uid_data[0]
                            if isinstance(uid_item, tuple) and len(uid_item) > 0:
                                uid_item = uid_item[0]
                            
                            # Extract UID from response like: b'1 (UID 123)' or '1 (UID 123)'
                            if isinstance(uid_item, bytes):
                                uid_str = uid_item.decode('utf-8', errors='ignore')
                            else:
                                uid_str = str(uid_item)
                            
                            # Find UID number in the string - try different patterns
                            uid_match = re.search(r'UID\s+(\d+)', uid_str)
                            if not uid_match:
                                # Try pattern like "1 (UID 123)" where 1 is seq num and 123 is UID
                                uid_match = re.search(r'\(UID\s+(\d+)\)', uid_str)
                            if not uid_match:
                                # Try to find any number that might be the UID
                                numbers = re.findall(r'\d+', uid_str)
                                if numbers and len(numbers) > 1:
                                    # Usually the last number is the UID
                                    uid = int(numbers[-1])
                            else:
                                uid = int(uid_match.group(1))
                        except Exception as e:
                            # If UID extraction fails, continue without it
                            pass
                    
                    # Fetch the email content
                    result, msg_data = self.connection.fetch(msg_id, '(RFC822)')
                    if result == 'OK' and msg_data and len(msg_data) > 0:
                        # msg_data is a list of tuples, get the first one
                        email_obj = self._parse_email(msg_data[0], folder_path, uid=uid)
                        if email_obj:
                            emails.append(email_obj)
                except Exception as e:
                    print(f"Error fetching email {msg_id}: {e}")
                    continue
        except Exception as e:
            print(f"Error fetching emails: {e}")
        
        return emails
    
    def _parse_email(self, msg_data: Tuple, folder_path: str, uid: Optional[int] = None) -> Optional[Email]:
        """Parse email message data into Email object"""
        try:
            # Extract raw email from IMAP fetch response
            # msg_data is a tuple from IMAP fetch, typically:
            # (b'1 (RFC822 {size}', b'email content...')
            
            raw_email = None
            
            if not isinstance(msg_data, tuple) or len(msg_data) < 2:
                return None
            
            # The structure is: (header_bytes, email_bytes)
            header_part = msg_data[0]
            raw_email = msg_data[1]
            
            # Validate raw_email is bytes before proceeding
            if not isinstance(raw_email, bytes):
                return None
            
            if not raw_email or len(raw_email) == 0:
                return None
            
            # Parse email message
            msg = email.message_from_bytes(raw_email)
            
            # Extract headers
            subject = self._decode_header(msg.get('Subject', ''))
            sender = msg.get('From', '')
            sender_name, sender_email = parse_email_address(sender)
            recipients = msg.get('To', '')
            message_id = msg.get('Message-ID', '')
            date_str = msg.get('Date', '')
            
            # Parse date
            timestamp = None
            try:
                date_tuple = email.utils.parsedate_tz(date_str)
                if date_tuple:
                    timestamp = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
            except:
                pass
            
            if not timestamp:
                timestamp = datetime.now()
            
            # Extract body
            body_text = ""
            body_html = ""
            has_attachments = False
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    if "attachment" in content_disposition:
                        has_attachments = True
                    elif content_type == "text/plain":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload is not None:
                                if isinstance(payload, bytes):
                                    body_text = payload.decode('utf-8', errors='ignore')
                                else:
                                    body_text = str(payload)
                        except:
                            pass
                    elif content_type == "text/html":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload is not None:
                                if isinstance(payload, bytes):
                                    body_html = payload.decode('utf-8', errors='ignore')
                                else:
                                    body_html = str(payload)
                        except:
                            pass
            else:
                content_type = msg.get_content_type()
                if content_type == "text/plain":
                    try:
                        payload = msg.get_payload(decode=True)
                        if payload is not None:
                            if isinstance(payload, bytes):
                                body_text = payload.decode('utf-8', errors='ignore')
                            else:
                                body_text = str(payload)
                    except:
                        pass
                elif content_type == "text/html":
                    try:
                        payload = msg.get_payload(decode=True)
                        if payload is not None:
                            if isinstance(payload, bytes):
                                body_html = payload.decode('utf-8', errors='ignore')
                            else:
                                body_html = str(payload)
                    except:
                        pass
            
            return Email(
                message_id=message_id,
                uid=uid if uid is not None else 0,
                sender=sender_email,
                sender_name=sender_name,
                recipients=recipients,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                timestamp=timestamp,
                is_read=False,
                has_attachments=has_attachments,
                cached=False
            )
        except Exception as e:
            print(f"Error parsing email: {e}")
            return None
    
    def _decode_header(self, header: str) -> str:
        """Decode email header"""
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
        except:
            return header
    
    def mark_as_read(self, uid: int) -> bool:
        """Mark an email as read"""
        if not self.authenticated:
            return False
        try:
            result, data = self.connection.store(str(uid), '+FLAGS', '\\Seen')
            return result == 'OK'
        except Exception as e:
            print(f"Error marking email as read: {e}")
            return False
    
    def move_email(self, uid: int, destination_folder: str) -> bool:
        """Move an email to another folder"""
        if not self.authenticated:
            return False
        try:
            result, data = self.connection.copy(str(uid), destination_folder)
            if result == 'OK':
                result, data = self.connection.store(str(uid), '+FLAGS', '\\Deleted')
                if result == 'OK':
                    self.connection.expunge()
                    return True
            return False
        except Exception as e:
            print(f"Error moving email: {e}")
            return False

