"""
Folder management operations.

This module provides folder operations (create, rename, delete) and
email movement operations with transactional guarantees.
"""
from typing import Optional
from email_client.models import EmailAccount, Folder, EmailMessage
from email_client.network.imap_client import ImapClient, ImapError, ImapOperationError
from email_client.storage import cache_repo


class FolderError(Exception):
    """Base exception for folder-related errors."""
    pass


class FolderCreationError(FolderError):
    """Raised when folder creation fails."""
    pass


class FolderRenameError(FolderError):
    """Raised when folder renaming fails."""
    pass


class FolderDeletionError(FolderError):
    """Raised when folder deletion fails."""
    pass


class EmailMoveError(FolderError):
    """Raised when email movement fails."""
    pass


class FolderManager:
    """
    Manages folder operations with transactional guarantees.
    
    Ensures that if IMAP operations fail, the cache is not updated.
    """
    
    def __init__(
        self,
        account: EmailAccount,
        imap_client: ImapClient
    ):
        """
        Initialize the folder manager.
        
        Args:
            account: The email account.
            imap_client: The IMAP client instance.
        """
        self.account = account
        self.imap_client = imap_client
    
    def create_folder(self, name: str) -> Folder:
        """
        Create a new folder on the server and in cache.
        
        Args:
            name: The name of the folder to create.
            
        Returns:
            The created Folder object.
            
        Raises:
            FolderCreationError: If folder creation fails.
        """
        if not name or not name.strip():
            raise FolderCreationError("Folder name cannot be empty")
        
        # Clean folder name (remove invalid characters)
        clean_name = name.strip()
        
        # Determine server path (for now, use name as path)
        # In a hierarchical system, this might be "INBOX/Subfolder"
        server_path = clean_name
        
        try:
            # Create folder on server first (transactional: if this fails, don't update cache)
            with self.imap_client:
                result, data = self.imap_client.connection.create(server_path)
                if result != 'OK':
                    error_msg = data[0].decode('utf-8') if data and data[0] else 'Unknown error'
                    raise FolderCreationError(
                        f"Failed to create folder '{name}' on server: {error_msg}"
                    )
            
            # If server operation succeeded, update cache
            folder = Folder(
                account_id=self.account.id or 0,
                name=clean_name,
                server_path=server_path,
                is_system_folder=False,
                unread_count=0,
            )
            
            return cache_repo.upsert_folder(folder)
            
        except ImapError as e:
            raise FolderCreationError(f"IMAP error creating folder: {str(e)}") from e
        except Exception as e:
            if isinstance(e, FolderCreationError):
                raise
            raise FolderCreationError(f"Unexpected error creating folder: {str(e)}") from e
    
    def rename_folder(self, folder: Folder, new_name: str) -> Folder:
        """
        Rename a folder on the server and in cache.
        
        Args:
            folder: The folder to rename.
            new_name: The new name for the folder.
            
        Returns:
            The renamed Folder object.
            
        Raises:
            FolderRenameError: If folder renaming fails.
        """
        if not new_name or not new_name.strip():
            raise FolderRenameError("New folder name cannot be empty")
        
        if not folder.id:
            raise FolderRenameError("Folder must be saved before renaming")
        
        if folder.is_system_folder:
            raise FolderRenameError("Cannot rename system folders (Inbox, Sent, Drafts, Trash)")
        
        clean_new_name = new_name.strip()
        new_server_path = clean_new_name
        
        try:
            # Rename folder on server first (transactional: if this fails, don't update cache)
            with self.imap_client:
                result, data = self.imap_client.connection.rename(
                    folder.server_path,
                    new_server_path
                )
                if result != 'OK':
                    error_msg = data[0].decode('utf-8') if data and data[0] else 'Unknown error'
                    raise FolderRenameError(
                        f"Failed to rename folder '{folder.name}' to '{new_name}' on server: {error_msg}"
                    )
            
            # If server operation succeeded, update cache
            folder.name = clean_new_name
            folder.server_path = new_server_path
            
            return cache_repo.upsert_folder(folder)
            
        except ImapError as e:
            raise FolderRenameError(f"IMAP error renaming folder: {str(e)}") from e
        except Exception as e:
            if isinstance(e, FolderRenameError):
                raise
            raise FolderRenameError(f"Unexpected error renaming folder: {str(e)}") from e
    
    def delete_folder(self, folder: Folder) -> None:
        """
        Delete a folder from the server and cache.
        
        Args:
            folder: The folder to delete.
            
        Raises:
            FolderDeletionError: If folder deletion fails.
        """
        if not folder.id:
            raise FolderDeletionError("Folder must be saved before deletion")
        
        if folder.is_system_folder:
            raise FolderDeletionError("Cannot delete system folders (Inbox, Sent, Drafts, Trash)")
        
        try:
            # Delete folder on server first (transactional: if this fails, don't update cache)
            with self.imap_client:
                result, data = self.imap_client.connection.delete(folder.server_path)
                if result != 'OK':
                    error_msg = data[0].decode('utf-8') if data and data[0] else 'Unknown error'
                    raise FolderDeletionError(
                        f"Failed to delete folder '{folder.name}' on server: {error_msg}"
                    )
            
            # If server operation succeeded, delete from cache
            cache_repo.delete_folder(folder.id)
            
        except ImapError as e:
            raise FolderDeletionError(f"IMAP error deleting folder: {str(e)}") from e
        except Exception as e:
            if isinstance(e, FolderDeletionError):
                raise
            raise FolderDeletionError(f"Unexpected error deleting folder: {str(e)}") from e
    
    def move_email(
        self,
        email: EmailMessage,
        dest_folder: Folder
    ) -> None:
        """
        Move an email from its current folder to a destination folder.
        
        Handles both remote move (via IMAP) and cache update.
        
        Args:
            email: The email message to move.
            dest_folder: The destination folder.
            
        Raises:
            EmailMoveError: If email movement fails.
        """
        if not email.id:
            raise EmailMoveError("Email must be saved before moving")
        
        if not email.uid_on_server:
            raise EmailMoveError("Email must have a server UID before moving")
        
        if not dest_folder.id:
            raise EmailMoveError("Destination folder must be saved before moving email")
        
        # Get source folder
        source_folder = None
        if email.folder_id:
            cached_folders = cache_repo.list_folders(self.account.id or 0)
            for folder in cached_folders:
                if folder.id == email.folder_id:
                    source_folder = folder
                    break
        
        if not source_folder:
            raise EmailMoveError("Source folder not found for email")
        
        if source_folder.id == dest_folder.id:
            # Already in destination folder
            return
        
        try:
            # Move email on server first (transactional: if this fails, don't update cache)
            with self.imap_client:
                self.imap_client.move_message(
                    source_folder,
                    dest_folder,
                    str(email.uid_on_server)
                )
            
            # If server operation succeeded, update cache
            # Update email's folder_id
            email.folder_id = dest_folder.id
            cache_repo.upsert_email_header(email)
            
            # Note: The email body and attachments remain associated with the email
            # and don't need to be moved since they're referenced by email_id
            
        except ImapOperationError as e:
            raise EmailMoveError(f"IMAP error moving email: {str(e)}") from e
        except ImapError as e:
            raise EmailMoveError(f"IMAP error moving email: {str(e)}") from e
        except Exception as e:
            if isinstance(e, EmailMoveError):
                raise
            raise EmailMoveError(f"Unexpected error moving email: {str(e)}") from e

