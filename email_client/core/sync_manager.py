"""
Synchronization manager for email client.

This module orchestrates synchronization between remote mailboxes (via IMAP)
and the local cache (via repository functions).
"""
import threading
from typing import Callable, List, Optional, Set
from email_client.models import EmailAccount, Folder, EmailMessage
from email_client.network.imap_client import ImapClient
from email_client.storage import cache_repo


class SyncManager:
    """
    Manages synchronization between remote mailboxes and local cache.
    
    Thread-safe design but does not create threads internally.
    The UI layer is responsible for threading decisions.
    """
    
    def __init__(
        self,
        account: EmailAccount,
        imap_client: ImapClient,
        token_bundle=None
    ):
        """
        Initialize the sync manager.
        
        Args:
            account: The email account to sync.
            imap_client: The IMAP client instance (should be initialized with account and token).
            token_bundle: Optional token bundle (if not already set in imap_client).
        """
        self.account = account
        self.imap_client = imap_client
        self._lock = threading.Lock()  # For thread-safety
        self._sync_in_progress = False
    
    def initial_sync(
        self, 
        inbox_limit: int = 100,
        folder_limit: int = 50,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Folder]:
        """
        Perform initial synchronization.
        
        Fetches all folders from the server and syncs messages for each folder.
        
        Args:
            inbox_limit: Maximum number of messages to fetch for Inbox.
            folder_limit: Maximum number of messages to fetch for other folders.
            progress_callback: Optional callback for progress updates.
                             Signature: callback(folder_name: str, synced_count: int, total_folders: int) -> None
            
        Returns:
            List of Folder objects that were synced.
            
        Raises:
            ImapError: If IMAP operations fail.
        """
        with self._lock:
            if self._sync_in_progress:
                raise RuntimeError("Sync already in progress")
            self._sync_in_progress = True
        
        try:
            # Fetch all folders from server
            with self.imap_client:
                remote_folders = self.imap_client.list_folders()
            
            # Upsert folders into cache
            synced_folders = []
            for folder in remote_folders:
                folder.account_id = self.account.id or 0
                cached_folder = cache_repo.upsert_folder(folder)
                synced_folders.append(cached_folder)
            
            total_folders = len(synced_folders)
            
            # Sync all folders (prioritize Inbox first)
            # Sort folders: Inbox first, then system folders, then others
            def folder_priority(folder):
                if folder.server_path.upper() == 'INBOX' or folder.name.upper() == 'INBOX':
                    return 0
                elif folder.is_system_folder:
                    return 1
                else:
                    return 2
            
            synced_folders.sort(key=folder_priority)
            
            # Sync each folder
            for idx, folder in enumerate(synced_folders):
                try:
                    # Determine limit based on folder type
                    limit = inbox_limit if (
                        folder.server_path.upper() == 'INBOX' or 
                        folder.name.upper() == 'INBOX'
                    ) else folder_limit
                    
                    # Sync the folder
                    synced_count = self._sync_folder_internal(folder, limit=limit)
                    
                    # Report progress
                    if progress_callback:
                        progress_callback(folder.name, synced_count, total_folders)
                except Exception as e:
                    # Log error but continue with other folders
                    print(f"Error syncing folder {folder.name}: {e}")
                    if progress_callback:
                        progress_callback(folder.name, 0, total_folders)
                    continue
            
            return synced_folders
        finally:
            with self._lock:
                self._sync_in_progress = False
    
    def sync_folder(self, folder: Folder, limit: int = 100) -> int:
        """
        Synchronize a folder with the remote server.
        
        Fetches remote headers and upserts into cache:
        - Inserts new messages
        - Updates changed messages
        - Marks deleted messages (messages in cache but not on server)
        
        Args:
            folder: The folder to sync.
            limit: Maximum number of messages to fetch from server.
            
        Returns:
            Number of messages synced.
            
        Raises:
            ImapError: If IMAP operations fail.
            RuntimeError: If sync is already in progress.
        """
        with self._lock:
            if self._sync_in_progress:
                raise RuntimeError("Sync already in progress")
            self._sync_in_progress = True
        
        try:
            return self._sync_folder_internal(folder, limit)
        finally:
            with self._lock:
                self._sync_in_progress = False
    
    def _sync_folder_internal(self, folder: Folder, limit: int = 100) -> int:
        """
        Internal folder sync implementation (without lock management).
        
        Args:
            folder: The folder to sync.
            limit: Maximum number of messages to fetch from server.
            
        Returns:
            Number of messages synced.
        """
        # Fetch remote headers
        with self.imap_client:
            remote_messages = self.imap_client.fetch_headers(folder, limit=limit)
        
        # Get cached messages for this folder
        folder_id = folder.id or 0
        if not folder_id:
            # Folder not yet cached, need to upsert it first
            folder.account_id = self.account.id or 0
            folder = cache_repo.upsert_folder(folder)
            folder_id = folder.id or 0
        
        cached_messages = cache_repo.list_emails(folder_id, limit=1000, offset=0)
        
        # Create sets of UIDs for comparison
        remote_uids: Set[int] = {msg.uid_on_server for msg in remote_messages}
        cached_uids: Set[int] = {msg.uid_on_server for msg in cached_messages}
        
        # Create a map of cached messages by UID
        cached_by_uid = {msg.uid_on_server: msg for msg in cached_messages}
        
        # Upsert remote messages (insert new, update existing)
        # Batch process: prepare all messages first, then upsert in a single transaction
        synced_count = 0
        messages_to_upsert = []
        
        for remote_msg in remote_messages:
            # Set account and folder IDs
            remote_msg.account_id = self.account.id or 0
            remote_msg.folder_id = folder_id
            
            # Check if message exists in cache
            if remote_msg.uid_on_server in cached_by_uid:
                # Update existing message
                cached_msg = cached_by_uid[remote_msg.uid_on_server]
                remote_msg.id = cached_msg.id
            
            messages_to_upsert.append(remote_msg)
        
        # Upsert all messages (database will handle transaction)
        for msg in messages_to_upsert:
            cache_repo.upsert_email_header(msg)
            synced_count += 1
        
        # Mark deleted messages (in cache but not on server)
        deleted_uids = cached_uids - remote_uids
        # Note: We don't actually delete from cache, just mark as deleted
        # The UI can decide whether to show deleted messages or not
        for deleted_uid in deleted_uids:
            deleted_msg = cached_by_uid[deleted_uid]
            if deleted_msg.id:
                # Mark as deleted by adding \Deleted flag
                deleted_msg.flags.add('\\Deleted')
                cache_repo.upsert_email_header(deleted_msg)
        
        # Update folder unread count
        unread_count = sum(1 for msg in remote_messages if not msg.is_read)
        folder.unread_count = unread_count
        cache_repo.upsert_folder(folder)
        
        return synced_count
    
    def fetch_and_cache_body(
        self,
        folder: Folder,
        message: EmailMessage
    ) -> EmailMessage:
        """
        Fetch email body from server if not cached, and save to cache.
        
        Args:
            folder: The folder containing the message.
            message: The email message (must have id and uid_on_server set).
            
        Returns:
            The message with body content populated.
            
        Raises:
            ImapError: If IMAP operations fail.
            ValueError: If message ID or UID is not set.
        """
        if not message.id:
            raise ValueError("Message ID must be set to fetch body")
        
        if not message.uid_on_server:
            raise ValueError("Message UID must be set to fetch body")
        
        # Check if body is already cached
        cached_message = cache_repo.get_email_by_id(message.id)
        if cached_message and (cached_message.body_plain or cached_message.body_html):
            # Body already cached (at least one format exists)
            return cached_message
        
        # Fetch body from server
        with self.imap_client:
            body_plain, body_html = self.imap_client.fetch_body(
                folder,
                str(message.uid_on_server)
            )
        
        # Update cache with body content
        cache_repo.update_email_body(
            message.id,
            body_plain or "",
            body_html or ""
        )
        
        # Return updated message
        updated_message = cache_repo.get_email_by_id(message.id)
        return updated_message or message
    
    def run_periodic_sync(
        self,
        callback: Optional[Callable[[Folder], None]] = None
    ) -> List[Folder]:
        """
        Run periodic synchronization.
        
        This method is designed to be called by a timer or periodic task.
        It syncs all folders and optionally calls a callback for each synced folder.
        
        Args:
            callback: Optional callback function called for each synced folder.
                     Signature: callback(folder: Folder) -> None
        
        Returns:
            List of folders that were synced.
            
        Raises:
            ImapError: If IMAP operations fail.
            RuntimeError: If sync is already in progress.
        """
        with self._lock:
            if self._sync_in_progress:
                raise RuntimeError("Sync already in progress")
            self._sync_in_progress = True
        
        try:
            # Get all cached folders for this account
            cached_folders = cache_repo.list_folders(self.account.id or 0)
            
            # If no folders cached, do initial sync
            if not cached_folders:
                return self.initial_sync()
            
            # Sync each folder (use internal method to avoid double lock)
            synced_folders = []
            for folder in cached_folders:
                try:
                    self._sync_folder_internal(folder, limit=100)
                    synced_folders.append(folder)
                    
                    # Call callback if provided
                    if callback:
                        callback(folder)
                except Exception as e:
                    # Log error but continue with other folders
                    # Note: In a real implementation, you might want to use logging
                    print(f"Error syncing folder {folder.name}: {e}")
                    continue
            
            return synced_folders
        finally:
            with self._lock:
                self._sync_in_progress = False
    
    def is_syncing(self) -> bool:
        """
        Check if a sync operation is currently in progress.
        
        Returns:
            True if sync is in progress, False otherwise.
        """
        with self._lock:
            return self._sync_in_progress

