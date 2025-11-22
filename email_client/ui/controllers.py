"""
Controller interfaces for UI layer.

These controllers provide a clean interface between the UI and business logic,
allowing the backend to be swapped without changing the UI code.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from email_client.models import EmailAccount, Folder, EmailMessage


class AccountController(ABC):
    """Controller for account operations."""
    
    @abstractmethod
    def list_accounts(self) -> List[EmailAccount]:
        """List all accounts."""
        pass
    
    @abstractmethod
    def get_default_account(self) -> Optional[EmailAccount]:
        """Get the default account."""
        pass
    
    @abstractmethod
    def set_default_account(self, account_id: int) -> None:
        """Set the default account."""
        pass


class FolderController(ABC):
    """Controller for folder operations."""
    
    @abstractmethod
    def list_folders(self, account_id: int) -> List[Folder]:
        """List all folders for an account."""
        pass
    
    @abstractmethod
    def get_folder(self, folder_id: int) -> Optional[Folder]:
        """Get a folder by ID."""
        pass


class MessageController(ABC):
    """Controller for message operations."""
    
    @abstractmethod
    def list_messages(self, folder_id: int, limit: int = 100, offset: int = 0) -> List[EmailMessage]:
        """List messages in a folder."""
        pass
    
    @abstractmethod
    def get_message(self, message_id: int) -> Optional[EmailMessage]:
        """Get a message by ID with full body content."""
        pass
    
    @abstractmethod
    def search_messages(
        self,
        account_id: Optional[int] = None,
        query: str = "",
        folder_id: Optional[int] = None,
        read_state: Optional[str] = None,
        limit: int = 50
    ) -> List[EmailMessage]:
        """Search messages."""
        pass


class SyncController(ABC):
    """Controller for synchronization operations."""
    
    @abstractmethod
    def sync_folder(self, folder: Folder, limit: int = 100) -> int:
        """Synchronize a folder with the server."""
        pass
    
    @abstractmethod
    def initial_sync(self, account: EmailAccount, inbox_limit: int = 100) -> List[Folder]:
        """Perform initial synchronization for an account."""
        pass

