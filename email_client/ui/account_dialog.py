"""
Account management dialog.

This module provides a UI dialog for managing email accounts, including
listing, setting default, deleting, and adding new accounts via OAuth.
"""
from typing import List, Optional, Callable
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QGroupBox,
    QComboBox, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from email_client.models import EmailAccount
from email_client.auth.oauth import TokenBundle, OAuthProvider


class AccountDialog(QDialog):
    """
    Dialog for managing email accounts.
    
    Uses injected callables for all business logic, keeping the UI
    layer separate from implementation details.
    """
    
    account_added = pyqtSignal(EmailAccount)  # Signal emitted when account is added
    account_deleted = pyqtSignal(int)  # Signal emitted when account is deleted (account_id)
    default_account_changed = pyqtSignal(int)  # Signal emitted when default account changes (account_id)
    
    def __init__(
        self,
        parent=None,
        list_accounts_fn: Optional[Callable[[], List[EmailAccount]]] = None,
        set_default_account_fn: Optional[Callable[[int], None]] = None,
        delete_account_fn: Optional[Callable[[int], None]] = None,
        get_oauth_provider_fn: Optional[Callable[[str], OAuthProvider]] = None,
        create_oauth_account_fn: Optional[Callable[[str, TokenBundle, str, str], EmailAccount]] = None,
        open_browser_fn: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the account dialog.
        
        Args:
            parent: Parent widget.
            list_accounts_fn: Function to list all accounts.
            set_default_account_fn: Function to set default account (account_id).
            delete_account_fn: Function to delete an account (account_id).
            get_oauth_provider_fn: Function to get OAuth provider for a provider name (e.g., "gmail").
            create_oauth_account_fn: Function to create OAuth account (provider_name, token_bundle, email, display_name).
            open_browser_fn: Function to open browser with URL (optional, for OAuth flow).
        """
        super().__init__(parent)
        self.setWindowTitle("Manage Accounts")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        # Injected callables
        self.list_accounts_fn = list_accounts_fn
        self.set_default_account_fn = set_default_account_fn
        self.delete_account_fn = delete_account_fn
        self.get_oauth_provider_fn = get_oauth_provider_fn
        self.create_oauth_account_fn = create_oauth_account_fn
        self.open_browser_fn = open_browser_fn
        
        self.accounts: List[EmailAccount] = []
        self.current_oauth_state: Optional[str] = None
        self.current_oauth_provider: Optional[str] = None
        
        self.setup_ui()
        self.refresh_accounts()
    
    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Manage Email Accounts")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Accounts list
        accounts_group = QGroupBox("Existing Accounts")
        accounts_layout = QVBoxLayout()
        
        self.accounts_list = QListWidget()
        self.accounts_list.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                color: #cccccc;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #3e3e42;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
        """)
        self.accounts_list.itemDoubleClicked.connect(self.on_account_double_clicked)
        self.accounts_list.itemSelectionChanged.connect(self._update_button_states)
        accounts_layout.addWidget(self.accounts_list)
        
        # Account actions
        account_actions_layout = QHBoxLayout()
        
        self.set_default_btn = QPushButton("Set as Default")
        self.set_default_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:disabled {
                background-color: #3c3c3c;
                color: #666666;
            }
        """)
        self.set_default_btn.clicked.connect(self.on_set_default)
        self.set_default_btn.setEnabled(False)
        account_actions_layout.addWidget(self.set_default_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #c72e0e;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
            QPushButton:disabled {
                background-color: #3c3c3c;
                color: #666666;
            }
        """)
        self.delete_btn.clicked.connect(self.on_delete_account)
        self.delete_btn.setEnabled(False)
        account_actions_layout.addWidget(self.delete_btn)
        
        account_actions_layout.addStretch()
        accounts_layout.addLayout(account_actions_layout)
        
        accounts_group.setLayout(accounts_layout)
        layout.addWidget(accounts_group)
        
        # Add account section
        add_account_group = QGroupBox("Add New Account")
        add_account_layout = QVBoxLayout()
        
        # Provider selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Gmail", "Outlook", "Yahoo"])
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()
        add_account_layout.addLayout(provider_layout)
        
        # Add account button
        self.add_account_btn = QPushButton("Add Account (OAuth)")
        self.add_account_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        self.add_account_btn.clicked.connect(self.on_add_account)
        add_account_layout.addWidget(self.add_account_btn)
        
        add_account_group.setLayout(add_account_layout)
        layout.addWidget(add_account_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def refresh_accounts(self):
        """Refresh the accounts list"""
        if not self.list_accounts_fn:
            QMessageBox.warning(self, "Error", "Account listing function not provided.")
            return
        
        try:
            self.accounts = self.list_accounts_fn()
            self.accounts_list.clear()
            
            if not self.accounts:
                # Show message when no accounts
                item = QListWidgetItem("No accounts configured")
                item.setFlags(Qt.NoItemFlags)  # Make it non-selectable
                self.accounts_list.addItem(item)
            else:
                for account in self.accounts:
                    # Format account display text
                    display_name = account.display_name or account.email_address
                    provider_text = f" ({account.provider})" if account.provider else ""
                    default_text = " [Default]" if account.is_default else ""
                    
                    item_text = f"{display_name}{provider_text}{default_text}"
                    
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, account.id)
                    self.accounts_list.addItem(item)
            
            # Enable/disable buttons based on selection
            self._update_button_states()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load accounts: {str(e)}")
    
    def _update_button_states(self):
        """Update button enabled states based on selection"""
        selected_items = self.accounts_list.selectedItems()
        has_selection = len(selected_items) > 0
        
        self.set_default_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
    
    def on_account_double_clicked(self, item: QListWidgetItem):
        """Handle account double-click (set as default)"""
        account_id = item.data(Qt.UserRole)
        if account_id:
            self._set_default_account(account_id)
    
    def on_set_default(self):
        """Handle set default button click"""
        selected_items = self.accounts_list.selectedItems()
        if not selected_items:
            return
        
        account_id = selected_items[0].data(Qt.UserRole)
        if account_id:
            self._set_default_account(account_id)
    
    def _set_default_account(self, account_id: int):
        """Set the default account"""
        if not self.set_default_account_fn:
            QMessageBox.warning(self, "Error", "Set default account function not provided.")
            return
        
        # Check if already default
        for account in self.accounts:
            if account.id == account_id and account.is_default:
                QMessageBox.information(self, "Info", "This account is already the default account.")
                return
        
        try:
            self.set_default_account_fn(account_id)
            self.default_account_changed.emit(account_id)
            self.refresh_accounts()
            QMessageBox.information(self, "Success", "Default account updated.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set default account: {str(e)}")
    
    def on_delete_account(self):
        """Handle delete account button click"""
        selected_items = self.accounts_list.selectedItems()
        if not selected_items:
            return
        
        account_id = selected_items[0].data(Qt.UserRole)
        if not account_id:
            return
        
        # Find account for confirmation message
        account = None
        for acc in self.accounts:
            if acc.id == account_id:
                account = acc
                break
        
        if not account:
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Account",
            f"Are you sure you want to delete the account '{account.display_name or account.email_address}'?\n\n"
            "This will delete all cached emails, folders, and account data.\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._delete_account(account_id)
    
    def _delete_account(self, account_id: int):
        """Delete an account"""
        if not self.delete_account_fn:
            QMessageBox.warning(self, "Error", "Delete account function not provided.")
            return
        
        try:
            self.delete_account_fn(account_id)
            self.account_deleted.emit(account_id)
            self.refresh_accounts()
            QMessageBox.information(self, "Success", "Account deleted successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete account: {str(e)}")
    
    def on_add_account(self):
        """Handle add account button click - start OAuth flow"""
        if not self.get_oauth_provider_fn:
            QMessageBox.warning(self, "Error", "OAuth provider function not provided.")
            return
        
        if not self.create_oauth_account_fn:
            QMessageBox.warning(self, "Error", "Create OAuth account function not provided.")
            return
        
        # Get selected provider
        provider_name = self.provider_combo.currentText().lower()
        
        try:
            # Get OAuth provider
            oauth_provider = self.get_oauth_provider_fn(provider_name)
            
            # Generate state for CSRF protection
            import secrets
            self.current_oauth_state = secrets.token_urlsafe(32)
            self.current_oauth_provider = provider_name
            
            # Get authorization URL
            auth_url = oauth_provider.get_authorization_url(self.current_oauth_state)
            
            # Open browser if function provided
            if self.open_browser_fn:
                self.open_browser_fn(auth_url)
                QMessageBox.information(
                    self,
                    "OAuth Authorization",
                    f"Your browser should open to authorize the {provider_name} account.\n\n"
                    "After authorization, you will be redirected back to the application.\n\n"
                    "Please enter the authorization code below when prompted."
                )
            else:
                # Show URL in message box if no browser function
                QMessageBox.information(
                    self,
                    "OAuth Authorization",
                    f"Please visit this URL to authorize your {provider_name} account:\n\n"
                    f"{auth_url}\n\n"
                    "After authorization, you will receive an authorization code.\n"
                    "Please enter it below when prompted."
                )
            
            # Show dialog to get authorization code
            self._handle_oauth_callback(oauth_provider)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start OAuth flow: {str(e)}")
    
    def _handle_oauth_callback(self, oauth_provider: OAuthProvider):
        """
        Handle OAuth callback - get authorization code and exchange for tokens.
        
        This shows a dialog to get the authorization code from the user,
        then exchanges it for tokens and creates the account.
        """
        from PyQt5.QtWidgets import QInputDialog
        
        # Get authorization code from user
        code, ok = QInputDialog.getText(
            self,
            "Authorization Code",
            "Enter the authorization code from the OAuth redirect:"
        )
        
        if not ok or not code:
            return
        
        try:
            # Exchange code for tokens
            token_bundle = oauth_provider.exchange_code_for_tokens(code)
            
            # Get user email and display name
            # For now, we'll ask the user, but in a real implementation,
            # this could be fetched from the OAuth provider's userinfo endpoint
            email, ok = QInputDialog.getText(
                self,
                "Email Address",
                "Enter your email address:"
            )
            
            if not ok or not email:
                return
            
            display_name, ok = QInputDialog.getText(
                self,
                "Display Name",
                "Enter a display name for this account (optional):"
            )
            
            if not ok:
                display_name = ""
            
            # Create account
            account = self.create_oauth_account_fn(
                self.current_oauth_provider,
                token_bundle,
                email,
                display_name
            )
            
            self.account_added.emit(account)
            self.refresh_accounts()
            QMessageBox.information(self, "Success", f"Account '{email}' added successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create account: {str(e)}")
    
    def showEvent(self, event):
        """Override showEvent to refresh accounts when dialog is shown"""
        super().showEvent(event)
        self.refresh_accounts()

