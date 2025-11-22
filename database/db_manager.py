"""
Database manager for SQLite operations
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import config
from database.models import Account, Folder, Email, Attachment


class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or config.DB_PATH
        self.conn = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database schema"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL")
        cursor = self.conn.cursor()
        
        # Accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_address TEXT NOT NULL UNIQUE,
                display_name TEXT,
                provider TEXT NOT NULL,
                auth_type TEXT NOT NULL,
                encrypted_token TEXT,
                imap_server TEXT,
                imap_port INTEGER DEFAULT 993,
                smtp_server TEXT,
                smtp_port INTEGER DEFAULT 587,
                use_tls INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_sync TIMESTAMP,
                settings TEXT DEFAULT '{}'
            )
        """)
        
        # Folders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                folder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                full_path TEXT NOT NULL,
                folder_type TEXT,
                sync_enabled INTEGER DEFAULT 1,
                last_sync TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
                UNIQUE(account_id, full_path)
            )
        """)
        
        # Emails table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                email_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                folder_id INTEGER NOT NULL,
                message_id TEXT,
                uid INTEGER,
                sender TEXT,
                sender_name TEXT,
                recipients TEXT,
                subject TEXT,
                body_text TEXT,
                body_html TEXT,
                timestamp TIMESTAMP,
                is_read INTEGER DEFAULT 0,
                is_starred INTEGER DEFAULT 0,
                has_attachments INTEGER DEFAULT 0,
                cached INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
                FOREIGN KEY (folder_id) REFERENCES folders(folder_id) ON DELETE CASCADE,
                UNIQUE(account_id, folder_id, uid)
            )
        """)
        
        # Attachments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT,
                file_size INTEGER,
                mime_type TEXT,
                content_id TEXT,
                encrypted INTEGER DEFAULT 0,
                FOREIGN KEY (email_id) REFERENCES emails(email_id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_account ON emails(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_folder ON emails(folder_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_timestamp ON emails(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folders_account ON folders(account_id)")
        
        self.conn.commit()
    
    # Account operations
    def add_account(self, account: Account) -> int:
        """Add a new account and return account_id"""
        # Check if account already exists
        cursor = self.conn.cursor()
        cursor.execute("SELECT account_id FROM accounts WHERE email_address = ?", (account.email_address,))
        existing = cursor.fetchone()
        if existing:
            raise ValueError(f"Account with email '{account.email_address}' already exists (ID: {existing['account_id']})")
        
        cursor.execute("""
            INSERT INTO accounts (email_address, display_name, provider, auth_type,
                                encrypted_token, imap_server, imap_port, smtp_server,
                                smtp_port, use_tls, settings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (account.email_address, account.display_name, account.provider,
              account.auth_type, account.encrypted_token, account.imap_server,
              account.imap_port, account.smtp_server, account.smtp_port,
              1 if account.use_tls else 0, account.settings))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_account(self, account_id: int) -> Optional[Account]:
        """Get account by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_account(row)
        return None
    
    def get_all_accounts(self) -> List[Account]:
        """Get all accounts"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM accounts ORDER BY email_address")
        return [self._row_to_account(row) for row in cursor.fetchall()]
    
    def update_account(self, account: Account):
        """Update account"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE accounts SET
                display_name = ?, encrypted_token = ?, last_sync = ?, settings = ?
            WHERE account_id = ?
        """, (account.display_name, account.encrypted_token, account.last_sync,
              account.settings, account.account_id))
        self.conn.commit()
    
    def delete_account(self, account_id: int):
        """Delete account and all associated data"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE account_id = ?", (account_id,))
        self.conn.commit()
    
    # Folder operations
    def add_folder(self, folder: Folder) -> int:
        """Add a folder and return folder_id"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO folders (account_id, name, full_path, folder_type, sync_enabled)
            VALUES (?, ?, ?, ?, ?)
        """, (folder.account_id, folder.name, folder.full_path, folder.folder_type,
              1 if folder.sync_enabled else 0))
        self.conn.commit()
        cursor.execute("SELECT folder_id FROM folders WHERE account_id = ? AND full_path = ?",
                      (folder.account_id, folder.full_path))
        row = cursor.fetchone()
        return row['folder_id'] if row else None
    
    def get_folders(self, account_id: int) -> List[Folder]:
        """Get all folders for an account"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM folders WHERE account_id = ? ORDER BY full_path", (account_id,))
        return [self._row_to_folder(row) for row in cursor.fetchall()]
    
    def get_folder(self, folder_id: int) -> Optional[Folder]:
        """Get folder by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM folders WHERE folder_id = ?", (folder_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_folder(row)
        return None
    
    def get_folder_by_type(self, account_id: int, folder_type: str) -> Optional[Folder]:
        """Get folder by account and type (e.g., 'drafts', 'inbox')"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM folders WHERE account_id = ? AND folder_type = ?", (account_id, folder_type))
        row = cursor.fetchone()
        if row:
            return self._row_to_folder(row)
        return None
    
    # Email operations
    def add_email(self, email: Email) -> int:
        """Add an email and return email_id"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO emails (account_id, folder_id, message_id, uid,
                sender, sender_name, recipients, subject, body_text, body_html,
                timestamp, is_read, is_starred, has_attachments, cached)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (email.account_id, email.folder_id, email.message_id, email.uid,
              email.sender, email.sender_name, email.recipients, email.subject,
              email.body_text, email.body_html, email.timestamp, 1 if email.is_read else 0,
              1 if email.is_starred else 0, 1 if email.has_attachments else 0,
              1 if email.cached else 0))
        self.conn.commit()
        cursor.execute("SELECT email_id FROM emails WHERE account_id = ? AND folder_id = ? AND uid = ?",
                      (email.account_id, email.folder_id, email.uid))
        row = cursor.fetchone()
        return row['email_id'] if row else None
    
    def get_emails(self, folder_id: int, limit: int = 100, offset: int = 0,
                   unread_only: bool = False) -> List[Email]:
        """Get emails for a folder"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM emails WHERE folder_id = ?"
        params = [folder_id]
        
        if unread_only:
            query += " AND is_read = 0"
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        return [self._row_to_email(row) for row in cursor.fetchall()]
    
    def get_email(self, email_id: int) -> Optional[Email]:
        """Get email by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM emails WHERE email_id = ?", (email_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_email(row)
        return None
    
    def search_emails(self, account_id: Optional[int], query: str, limit: int = 100) -> List[Email]:
        """Search emails by content, sender, or subject"""
        cursor = self.conn.cursor()
        search_term = f"%{query}%"
        
        if account_id:
            cursor.execute("""
                SELECT * FROM emails
                WHERE account_id = ? AND (
                    subject LIKE ? OR sender LIKE ? OR sender_name LIKE ? OR body_text LIKE ?
                )
                ORDER BY timestamp DESC LIMIT ?
            """, (account_id, search_term, search_term, search_term, search_term, limit))
        else:
            cursor.execute("""
                SELECT * FROM emails
                WHERE subject LIKE ? OR sender LIKE ? OR sender_name LIKE ? OR body_text LIKE ?
                ORDER BY timestamp DESC LIMIT ?
            """, (search_term, search_term, search_term, search_term, limit))
        
        return [self._row_to_email(row) for row in cursor.fetchall()]
    
    def mark_email_read(self, email_id: int, is_read: bool = True):
        """Mark email as read/unread"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE emails SET is_read = ? WHERE email_id = ?",
                      (1 if is_read else 0, email_id))
        self.conn.commit()
    
    def delete_email(self, email_id: int):
        """Delete an email"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM emails WHERE email_id = ?", (email_id,))
        self.conn.commit()
    
    # Attachment operations
    def add_attachment(self, attachment: Attachment) -> int:
        """Add an attachment and return attachment_id"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO attachments (email_id, filename, file_path, file_size,
                mime_type, content_id, encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (attachment.email_id, attachment.filename, attachment.file_path,
              attachment.file_size, attachment.mime_type, attachment.content_id,
              1 if attachment.encrypted else 0))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_attachments(self, email_id: int) -> List[Attachment]:
        """Get all attachments for an email"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM attachments WHERE email_id = ?", (email_id,))
        return [self._row_to_attachment(row) for row in cursor.fetchall()]
    
    # Helper methods
    def _row_to_account(self, row) -> Account:
        """Convert database row to Account object"""
        return Account(
            account_id=row['account_id'],
            email_address=row['email_address'],
            display_name=row['display_name'] or "",
            provider=row['provider'],
            auth_type=row['auth_type'],
            encrypted_token=row['encrypted_token'] or "",
            imap_server=row['imap_server'] or "",
            imap_port=row['imap_port'],
            smtp_server=row['smtp_server'] or "",
            smtp_port=row['smtp_port'],
            use_tls=bool(row['use_tls']),
            created_at=self._parse_timestamp(row['created_at']),
            last_sync=self._parse_timestamp(row['last_sync']),
            settings=row['settings'] or "{}"
        )
    
    def _row_to_folder(self, row) -> Folder:
        """Convert database row to Folder object"""
        return Folder(
            folder_id=row['folder_id'],
            account_id=row['account_id'],
            name=row['name'],
            full_path=row['full_path'],
            folder_type=row['folder_type'] or "",
            sync_enabled=bool(row['sync_enabled']),
            last_sync=self._parse_timestamp(row['last_sync'])
        )
    
    def _row_to_email(self, row) -> Email:
        """Convert database row to Email object"""
        return Email(
            email_id=row['email_id'],
            account_id=row['account_id'],
            folder_id=row['folder_id'],
            message_id=row['message_id'] or "",
            uid=row['uid'],
            sender=row['sender'] or "",
            sender_name=row['sender_name'] or "",
            recipients=row['recipients'] or "",
            subject=row['subject'] or "",
            body_text=row['body_text'] or "",
            body_html=row['body_html'] or "",
            timestamp=self._parse_timestamp(row['timestamp']),
            is_read=bool(row['is_read']),
            is_starred=bool(row['is_starred']),
            has_attachments=bool(row['has_attachments']),
            cached=bool(row['cached']),
            created_at=self._parse_timestamp(row['created_at'])
        )
    
    def _row_to_attachment(self, row) -> Attachment:
        """Convert database row to Attachment object"""
        return Attachment(
            attachment_id=row['attachment_id'],
            email_id=row['email_id'],
            filename=row['filename'],
            file_path=row['file_path'] or "",
            file_size=row['file_size'] or 0,
            mime_type=row['mime_type'] or "",
            content_id=row['content_id'],
            encrypted=bool(row['encrypted'])
        )
    
    def _parse_timestamp(self, timestamp_str) -> Optional[datetime]:
        """Parse timestamp string to datetime"""
        if not timestamp_str:
            return None
        try:
            if isinstance(timestamp_str, str):
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return timestamp_str
        except:
            return None
    
    def close(self):
        """Close database connection"""
        if self.conn:
            try:
                # Commit any pending changes
                self.conn.commit()
                # Close the connection
                self.conn.close()
            except sqlite3.Error:
                pass  # Ignore errors on close
            finally:
                self.conn = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False

