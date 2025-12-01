"""
Concrete controller implementations using the core layer.
"""
from typing import List, Optional, Callable
from email_client.models import EmailAccount, Folder, EmailMessage
from email_client.ui.controllers import (
    AccountController, FolderController, MessageController, SyncController
)
from email_client.auth.accounts import (
    list_accounts, get_default_account, set_default_account,
    get_token_bundle, get_password, get_account
)
from email_client.storage import cache_repo
from email_client.core.search import search_emails
from email_client.core.sync_manager import SyncManager
from email_client.core.folder_manager import FolderManager
from email_client.network.imap_client import ImapClient


class AccountControllerImpl(AccountController):
    """Concrete account controller implementation."""
    
    def list_accounts(self) -> List[EmailAccount]:
        """List all accounts."""
        return list_accounts()
    
    def get_default_account(self) -> Optional[EmailAccount]:
        """Get the default account."""
        from email_client.auth.accounts import get_default_account as get_default
        return get_default()
    
    def set_default_account(self, account_id: int) -> None:
        """Set the default account."""
        set_default_account(account_id)


class FolderControllerImpl(FolderController):
    """Concrete folder controller implementation."""
    
    def list_folders(self, account_id: int) -> List[Folder]:
        """List all folders for an account."""
        return cache_repo.list_folders(account_id)
    
    def get_folder(self, folder_id: int) -> Optional[Folder]:
        """Get a folder by ID."""
        return cache_repo.get_folder(folder_id)
    
    def create_folder(self, account_id: int, folder_name: str) -> Folder:
        """Create a new folder."""
        account = get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        # Get authentication
        token_bundle = None
        password = None
        if account.auth_type == "oauth":
            token_bundle = get_token_bundle(account_id)
        elif account.auth_type == "password":
            password = get_password(account_id)
        
        # Create IMAP client and folder manager
        imap_client = ImapClient(account, token_bundle=token_bundle, password=password)
        folder_manager = FolderManager(account, imap_client)
        
        # Create folder
        return folder_manager.create_folder(folder_name)
    
    def rename_folder(self, folder_id: int, new_name: str) -> Folder:
        """Rename a folder."""
        folder = cache_repo.get_folder(folder_id)
        if not folder:
            raise ValueError(f"Folder {folder_id} not found")
        
        account = get_account(folder.account_id)
        if not account:
            raise ValueError(f"Account {folder.account_id} not found")
        
        # Get authentication
        token_bundle = None
        password = None
        if account.auth_type == "oauth":
            token_bundle = get_token_bundle(folder.account_id)
        elif account.auth_type == "password":
            password = get_password(folder.account_id)
        
        # Create IMAP client and folder manager
        imap_client = ImapClient(account, token_bundle=token_bundle, password=password)
        folder_manager = FolderManager(account, imap_client)
        
        # Rename folder
        return folder_manager.rename_folder(folder, new_name)
    
    def delete_folder(self, folder_id: int) -> None:
        """Delete a folder."""
        folder = cache_repo.get_folder(folder_id)
        if not folder:
            raise ValueError(f"Folder {folder_id} not found")
        
        account = get_account(folder.account_id)
        if not account:
            raise ValueError(f"Account {folder.account_id} not found")
        
        # Get authentication
        token_bundle = None
        password = None
        if account.auth_type == "oauth":
            token_bundle = get_token_bundle(folder.account_id)
        elif account.auth_type == "password":
            password = get_password(folder.account_id)
        
        # Create IMAP client and folder manager
        imap_client = ImapClient(account, token_bundle=token_bundle, password=password)
        folder_manager = FolderManager(account, imap_client)
        
        # Delete folder
        folder_manager.delete_folder(folder)
    
    def move_email(self, email_id: int, dest_folder_id: int) -> None:
        """Move an email to a different folder."""
        email = cache_repo.get_email_by_id(email_id)
        if not email:
            raise ValueError(f"Email {email_id} not found")
        
        dest_folder = cache_repo.get_folder(dest_folder_id)
        if not dest_folder:
            raise ValueError(f"Folder {dest_folder_id} not found")
        
        account = get_account(email.account_id)
        if not account:
            raise ValueError(f"Account {email.account_id} not found")
        
        # Get authentication
        token_bundle = None
        password = None
        if account.auth_type == "oauth":
            token_bundle = get_token_bundle(email.account_id)
        elif account.auth_type == "password":
            password = get_password(email.account_id)
        
        # Create IMAP client and folder manager
        imap_client = ImapClient(account, token_bundle=token_bundle, password=password)
        folder_manager = FolderManager(account, imap_client)
        
        # Move email
        folder_manager.move_email(email, dest_folder)


class MessageControllerImpl(MessageController):
    """Concrete message controller implementation."""
    
    def list_messages(self, folder_id: int, limit: int = 100, offset: int = 0) -> List[EmailMessage]:
        """List messages in a folder."""
        return cache_repo.list_emails(folder_id, limit=limit, offset=offset)
    
    def count_messages(self, folder_id: int) -> int:
        """Count total messages in a folder."""
        return cache_repo.count_emails(folder_id)
    
    def get_message(self, message_id: int) -> Optional[EmailMessage]:
        """Get a message by ID with full body content."""
        return cache_repo.get_email_by_id(message_id)
    
    def search_messages(
        self,
        account_id: Optional[int] = None,
        query: str = "",
        folder_id: Optional[int] = None,
        read_state: Optional[str] = None,
        limit: int = 50
    ) -> List[EmailMessage]:
        """Search messages."""
        return search_emails(
            account_id=account_id,
            query=query,
            folder_id=folder_id,
            read_state=read_state,
            limit=limit
        )


class SyncControllerImpl(SyncController):
    """Concrete sync controller implementation."""
    
    def __init__(self):
        self._sync_managers = {}  # Cache sync managers by account_id
    
    def _get_sync_manager(self, account: EmailAccount) -> SyncManager:
        """Get or create a sync manager for an account."""
        if account.id not in self._sync_managers:
            # Get authentication credentials based on account type
            token_bundle = None
            password = None
            
            if account.id:
                if account.auth_type == "oauth":
                    try:
                        token_bundle = get_token_bundle(account.id)
                        if token_bundle:
                            print(f"SyncController: Retrieved token bundle for account {account.id}")
                            print(f"SyncController: Token bundle has access_token: {bool(token_bundle.access_token)}")
                            print(f"SyncController: Token bundle expires_at: {token_bundle.expires_at}")
                            if token_bundle.access_token:
                                print(f"SyncController: Access token length: {len(token_bundle.access_token)}")
                                print(f"SyncController: Access token preview: {token_bundle.access_token[:20]}...")
                            else:
                                print(f"SyncController: ERROR - Token bundle has no access_token!")
                                raise ValueError("Token bundle retrieved but access_token is None or empty")
                        else:
                            print(f"SyncController: WARNING - token_bundle is None for account {account.id}")
                            raise ValueError("Token bundle is None")
                    except Exception as e:
                        print(f"SyncController: ERROR retrieving token bundle for account {account.id}: {e}")
                        import traceback
                        traceback.print_exc()
                        # Don't silently fail - raise the error so we know what's wrong
                        raise
                if account.auth_type == "password":
                    try:
                        password = get_password(account.id)
                    except Exception:
                        pass  # No password available    
            
            # Create IMAP client with appropriate authentication
            imap_client = ImapClient(account, token_bundle=token_bundle, password=password)
            
            # Create sync manager
            self._sync_managers[account.id] = SyncManager(account, imap_client)
        
        return self._sync_managers[account.id]
    
    def sync_folder(self, folder: Folder, limit: int = 100) -> int:
        """Synchronize a folder with the server."""
        # Get account
        accounts = list_accounts()
        account = None
        for acc in accounts:
            if acc.id == folder.account_id:
                account = acc
                break
        
        if not account:
            raise ValueError(f"Account {folder.account_id} not found")
        
        sync_manager = self._get_sync_manager(account)
        return sync_manager.sync_folder(folder, limit=limit)
    
    def initial_sync(
        self, 
        account: EmailAccount, 
        inbox_limit: int = 100,
        folder_limit: int = 50,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Folder]:
        """Perform initial synchronization for an account."""
        sync_manager = self._get_sync_manager(account)
        return sync_manager.initial_sync(
            inbox_limit=inbox_limit,
            folder_limit=folder_limit,
            progress_callback=progress_callback
        )
    
    def fetch_email_body(self, account: EmailAccount, folder: Folder, message: EmailMessage) -> EmailMessage:
        """Fetch email body from server if not cached."""
        sync_manager = self._get_sync_manager(account)
        return sync_manager.fetch_and_cache_body(folder, message)

    def mark_message_read(self, account: EmailAccount, folder: Folder, message: EmailMessage) -> None:
        """Mark a message as read on the server and in the local cache."""
        sync_manager = self._get_sync_manager(account)
        sync_manager.mark_message_read(folder, message)
    
    def delete_message(self, account: EmailAccount, folder: Folder, message: EmailMessage) -> None:
        """Delete a message from the server."""
        sync_manager = self._get_sync_manager(account)
        sync_manager.delete_message(folder, message)

