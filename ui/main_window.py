"""
Main application window
"""
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QSplitter, QMenuBar, QMenu, QStatusBar, QMessageBox,
                             QAction, QStackedWidget, QLineEdit, QComboBox, QPushButton)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject, QMetaObject
from PyQt5.QtWidgets import QProgressDialog, QDialog, QApplication
from PyQt5.QtGui import QKeySequence
import config
from ui.login_window import LoginWindow
from ui.compose_window import ComposeWindow
from ui.components.sidebar import Sidebar
from ui.components.email_list import EmailList
from ui.components.email_preview import EmailPreview
from email_client.ui.controller_impl import (
    AccountControllerImpl, FolderControllerImpl, 
    MessageControllerImpl, SyncControllerImpl
)
from email_client.models import EmailAccount, Folder, EmailMessage
from email_client.storage import cache_repo


class OAuthThread(QThread):
    """Thread for handling OAuth authentication without blocking UI"""
    authentication_complete = pyqtSignal(str)  # token_json on success
    authentication_failed = pyqtSignal(str)  # error message on failure
    
    def __init__(self, provider: str, auth_method: str):
        super().__init__()
        self.provider = provider
        self.auth_method = auth_method  # 'gmail' or 'outlook'
    
    def run(self):
        """Run OAuth authentication in background thread"""
        try:
            from email_client.oauth2_handler import OAuth2Handler
            oauth_handler = OAuth2Handler(self.provider)
            
            if self.auth_method == 'gmail':
                token_json = oauth_handler.authenticate_gmail()
            elif self.auth_method == 'outlook':
                token_json = oauth_handler.authenticate_outlook()
            else:
                self.authentication_failed.emit(f"Unknown auth method: {self.auth_method}")
                return
            
            if token_json:
                self.authentication_complete.emit(token_json)
            else:
                self.authentication_failed.emit("OAuth authentication failed or was cancelled.")
        except Exception as e:
            self.authentication_failed.emit(f"OAuth error: {str(e)}")


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Email Desktop Client")
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT)
        
        # Initialize controllers (injected dependencies)
        self.account_controller = AccountControllerImpl()
        self.folder_controller = FolderControllerImpl()
        self.message_controller = MessageControllerImpl()
        self.sync_controller = SyncControllerImpl()
        
        self.current_account_id = None
        self.current_folder_id = None
        self.sync_thread = None
        self.oauth_thread = None
        self.oauth_progress_dialog = None
        
        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()
        self.load_accounts()
        
        # Auto-sync timer
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.auto_sync)
        from email_client.config import DEFAULT_REFRESH_INTERVAL_SECONDS
        self.sync_timer.start(DEFAULT_REFRESH_INTERVAL_SECONDS * 1000)  # Convert to milliseconds
    
    def setup_ui(self):
        """Setup the main UI"""
        # Apply modern dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QSplitter::handle {
                background-color: #2d2d2d;
            }
            QSplitter::handle:horizontal {
                width: 2px;
            }
            QSplitter::handle:vertical {
                height: 2px;
            }
        """)
        
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #1e1e1e;")
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.folder_selected.connect(self.on_folder_selected)
        self.sidebar.account_selected.connect(self.on_account_selected)
        self.sidebar.account_delete_requested.connect(self.on_delete_account_requested)
        self.sidebar.compose_clicked.connect(self.on_compose_clicked)
        self.sidebar.add_account_clicked.connect(self.on_add_account_clicked)
        splitter.addWidget(self.sidebar)
        
        # Right side container
        right_container = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Top bar with search, account filter, and refresh
        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: #252526; padding: 8px;")
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(8, 8, 8, 8)
        
        # App title
        title_label = QPushButton("Email Client")
        title_label.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #cccccc;
                font-size: 16px;
                font-weight: bold;
                text-align: left;
                padding: 4px;
            }
        """)
        title_label.setEnabled(False)
        top_bar_layout.addWidget(title_label)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search emails...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                color: #cccccc;
                min-width: 200px;
            }
            QLineEdit:focus {
                border: 1px solid #0e639c;
            }
        """)
        self.search_input.returnPressed.connect(self.on_search)
        top_bar_layout.addWidget(self.search_input)
        
        # Account filter dropdown
        self.account_filter = QComboBox()
        self.account_filter.setStyleSheet("""
            QComboBox {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                color: #cccccc;
                min-width: 150px;
            }
        """)
        self.account_filter.addItem("All Accounts")
        self.account_filter.currentIndexChanged.connect(self.on_account_filter_changed)
        top_bar_layout.addWidget(self.account_filter)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
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
            QPushButton:pressed {
                background-color: #094771;
            }
        """)
        refresh_btn.clicked.connect(self.on_refresh_clicked)
        top_bar_layout.addWidget(refresh_btn)
        
        top_bar.setLayout(top_bar_layout)
        right_layout.addWidget(top_bar)
        
        # Email list/preview stack
        self.right_stack = QStackedWidget()
        
        # Email list
        self.email_list = EmailList()
        self.email_list.email_selected.connect(self.on_email_selected)
        self.email_list.refresh_requested.connect(self.on_refresh_clicked)
        self.right_stack.addWidget(self.email_list)  # Index 0
        
        # Email preview
        self.email_preview = EmailPreview()
        self.email_preview.reply_clicked.connect(self.on_reply_clicked)
        self.email_preview.forward_clicked.connect(self.on_forward_clicked)
        self.email_preview.delete_clicked.connect(self.on_delete_clicked)
        self.email_preview.back_clicked.connect(self.on_back_to_list)
        self.right_stack.addWidget(self.email_preview)  # Index 1
        
        # Start with email list view
        self.right_stack.setCurrentIndex(0)
        
        right_layout.addWidget(self.right_stack)
        right_container.setLayout(right_layout)
        splitter.addWidget(right_container)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([250, 1000])  # Initial sidebar width
        
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
    
    def setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #252526;
                color: #cccccc;
                border-bottom: 1px solid #3e3e42;
                padding: 2px;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #2a2d2e;
            }
            QMenuBar::item:pressed {
                background-color: #094771;
            }
            QMenu {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #094771;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3e3e42;
                margin: 4px 8px;
            }
        """)
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        add_account_action = QAction("Add Account", self)
        add_account_action.setShortcut(QKeySequence.New)
        add_account_action.triggered.connect(self.on_add_account_clicked)
        file_menu.addAction(add_account_action)
        
        remove_account_action = QAction("Remove Account", self)
        remove_account_action.triggered.connect(self.on_remove_account_menu_clicked)
        file_menu.addAction(remove_account_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        compose_action = QAction("Compose", self)
        compose_action.setShortcut(QKeySequence("Ctrl+N"))
        compose_action.triggered.connect(self.on_compose_clicked)
        edit_menu.addAction(compose_action)
        
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.triggered.connect(self.on_refresh_clicked)
        edit_menu.addAction(refresh_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #252526;
                color: #cccccc;
                border-top: 1px solid #3e3e42;
                padding: 2px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def load_accounts(self):
        """Load accounts using the new database system"""
        accounts = self.account_controller.list_accounts()
        if accounts:
            # Update sidebar (now supports EmailAccount directly)
            self.sidebar.set_accounts(accounts)
            # Update account filter dropdown
            self.account_filter.clear()
            self.account_filter.addItem("All Accounts")
            for account in accounts:
                if account.id:
                    self.account_filter.addItem(account.display_name or account.email_address, account.id)
            # Select first account
            if accounts and accounts[0].id:
                self.on_account_selected(accounts[0].id)
        else:
            # No accounts, show login dialog
            # Make sure main window is visible first
            self.show()
            self.raise_()
            self.activateWindow()
            self.on_add_account_clicked()
    
    def on_add_account_clicked(self):
        """Handle add account button click"""
        login_window = LoginWindow(self)
        login_window.account_added.connect(lambda data: self.handle_account_added(data, login_window))
        login_window.exec_()
    
    def handle_account_added(self, account_data: dict, login_window: LoginWindow = None):
        """
        Handle new account addition.
        
        This method now only handles OAuth2 authentication flow.
        Non-OAuth accounts should use the OAuth flow or be added via the new system.
        """
        try:
            from email_client.oauth2_handler import OAuth2Handler
            
            # Handle OAuth2 authentication
            if account_data.get('use_oauth'):
                # Check if OAuth2 credentials are configured
                provider = account_data['provider']
                if provider == 'gmail':
                    if not config.GMAIL_CLIENT_ID or not config.GMAIL_CLIENT_SECRET:
                        reply = QMessageBox.question(
                            self,
                            "OAuth2 Not Configured",
                            "Gmail OAuth2 credentials are not configured.\n\n"
                            "To use OAuth2, please:\n"
                            "1. Create a .env file in the project directory\n"
                            "2. Add GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET\n"
                            "3. Get credentials from: https://console.cloud.google.com/apis/credentials\n\n"
                            "OAuth2 is required for Gmail.",
                            QMessageBox.Ok
                        )
                        return
                    else:
                        # Run OAuth in a separate thread to avoid blocking UI
                        self._authenticate_oauth_async(provider, 'gmail', account_data, login_window, None, None)
                        return  # Exit early, will continue in callback
                elif provider == 'outlook':
                    if not config.OUTLOOK_CLIENT_ID or not config.OUTLOOK_CLIENT_SECRET:
                        reply = QMessageBox.question(
                            self,
                            "OAuth2 Not Configured",
                            "Outlook OAuth2 credentials are not configured.\n\n"
                            "To use OAuth2, please:\n"
                            "1. Create a .env file in the project directory\n"
                            "2. Add OUTLOOK_CLIENT_ID and OUTLOOK_CLIENT_SECRET\n"
                            "3. Get credentials from: https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade\n\n"
                            "OAuth2 is required for Outlook.",
                            QMessageBox.Ok
                        )
                        return
                    else:
                        # Run OAuth in a separate thread to avoid blocking UI
                        self._authenticate_oauth_async(provider, 'outlook', account_data, login_window, None, None)
                        return  # Exit early, will continue in callback
                else:
                    QMessageBox.warning(self, "OAuth2 Required", "OAuth2 is required for this provider.")
                    return
            else:
                QMessageBox.warning(self, "OAuth2 Required", "OAuth2 authentication is required. Please enable it in the login window.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add account: {str(e)}")
            # Re-enable login button on error
            if login_window:
                login_window.progress_bar.setVisible(False)
                login_window.login_button.setEnabled(True)
    
    def _authenticate_oauth_async(self, provider: str, auth_method: str, account_data: dict, 
                                  login_window: LoginWindow, db_manager, encryption_manager):
        """Start OAuth authentication in a background thread"""
        # Show progress dialog
        self.oauth_progress_dialog = QProgressDialog(
            f"Authenticating with {provider.capitalize()}...\n\n"
            "A browser window will open for authentication.\n"
            "Please complete the authentication in your browser.",
            "Cancel",
            0,
            0,
            self
        )
        self.oauth_progress_dialog.setWindowTitle("OAuth Authentication")
        self.oauth_progress_dialog.setWindowModality(Qt.WindowModal)
        self.oauth_progress_dialog.setCancelButton(None)  # Don't allow cancel for now
        self.oauth_progress_dialog.show()
        
        # Create and start OAuth thread
        self.oauth_thread = OAuthThread(provider, auth_method)
        self.oauth_thread.authentication_complete.connect(
            lambda token_json: self._on_oauth_success(token_json, account_data, login_window, db_manager, encryption_manager)
        )
        self.oauth_thread.authentication_failed.connect(
            lambda error: self._on_oauth_failure(error, login_window)
        )
        self.oauth_thread.finished.connect(self._on_oauth_thread_finished)
        self.oauth_thread.start()
    
    def _on_oauth_success(self, token_json: str, account_data: dict, login_window: LoginWindow,
                          db_manager, encryption_manager):
        """Handle successful OAuth authentication (called from main thread via signal)"""
        try:
            # Close progress dialog first
            if self.oauth_progress_dialog:
                self.oauth_progress_dialog.close()
                self.oauth_progress_dialog = None
            
            # Close login window IMMEDIATELY - before any other operations
            # This provides immediate feedback to the user
            if login_window:
                # Since we're called via signal, we're already on the main thread
                # Call accept() directly to close the modal dialog
                login_window.accept()  # This exits exec_() and closes the dialog
                
                # Process events immediately to ensure the window closes
                QApplication.processEvents()
                
                # Also hide it explicitly as a backup
                login_window.hide()
                login_window.setVisible(False)
                
            # Process events one more time to ensure UI updates
            QApplication.processEvents()
            
            # Defer heavy operations using a timer so the dialog can close first
            # This ensures the window closing happens immediately
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._complete_account_setup_after_oauth(
                token_json, account_data, db_manager, encryption_manager
            ))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add account: {str(e)}")
            if login_window:
                login_window.progress_bar.setVisible(False)
                login_window.login_button.setEnabled(True)
    
    def _on_oauth_failure(self, error: str, login_window: LoginWindow):
        """Handle OAuth authentication failure (called from main thread via signal)"""
        # Close progress dialog
        if self.oauth_progress_dialog:
            self.oauth_progress_dialog.close()
            self.oauth_progress_dialog = None
        
        # Re-enable login button first
        if login_window:
            login_window.progress_bar.setVisible(False)
            login_window.login_button.setEnabled(True)
            # Keep login window open so user can try again
        
        # Show error message
        QMessageBox.warning(
            self,
            "Authentication Failed",
            f"OAuth2 authentication failed.\n\n{error}\n\nPlease try again."
        )
    
    def _on_oauth_thread_finished(self):
        """Clean up when OAuth thread finishes"""
        if self.oauth_thread:
            self.oauth_thread.deleteLater()
            self.oauth_thread = None
    
    def _complete_account_setup_after_oauth(self, token_json: str, account_data: dict,
                                            db_manager=None, encryption_manager=None):
        """Complete account setup after OAuth success (called after dialog closes)"""
        try:
            # Parse token JSON to create TokenBundle
            import json
            from datetime import datetime, timedelta
            from email_client.auth.oauth import TokenBundle
            from email_client.auth.accounts import create_oauth_account
            
            token_data = json.loads(token_json)
            
            # OAuth2Handler returns token in format: {'token': ..., 'refresh_token': ..., ...}
            # Extract token information (handle both formats)
            access_token = token_data.get('token') or token_data.get('access_token', '')
            refresh_token = token_data.get('refresh_token')
            
            # Calculate expiration time
            # OAuth2Handler doesn't provide expires_in, so we'll use a default
            # or try to get it from the token data
            expires_in = token_data.get('expires_in', 3600)  # Default to 1 hour
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Create TokenBundle
            token_bundle = TokenBundle(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at
            )
            
            # Create account using new system
            provider_name = account_data['provider'].lower()
            profile_email = account_data['email']
            display_name = account_data['display_name'] or profile_email.split('@')[0]
            
            # Use the new account creation system
            account = create_oauth_account(
                provider_name=provider_name,
                token_bundle=token_bundle,
                profile_email=profile_email,
                display_name=display_name
            )
            
            # Reload accounts to refresh UI
            self.load_accounts()
            
            # Select the newly added account
            if account.id:
                self.on_account_selected(account.id)
            
            # Sync folders in background (using new system)
            try:
                self._sync_account_folders_new(account)
            except Exception as sync_error:
                print(f"Warning: Folder sync failed: {sync_error}")
                # Continue anyway - account is added
            
            # Bring main window to front
            self.show()
            self.raise_()
            self.activateWindow()
            
            QMessageBox.information(self, "Success", "Account added successfully!")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to complete account setup: {str(e)}")
        finally:
            # Clean up old database manager if it exists
            if db_manager:
                try:
                    db_manager.close()
                except:
                    pass
    
    
    def on_account_selected(self, account_id: int):
        """Handle account selection"""
        self.current_account_id = account_id
        # Load folders using controller
        folders = self.folder_controller.list_folders(account_id)
        self.sidebar.set_folders(folders)
        
        # Select inbox if available
        for folder in folders:
            if folder.is_system_folder and (
                folder.server_path.upper() == 'INBOX' or 
                folder.name.upper() == 'INBOX'
            ):
                if folder.id:
                    self.sidebar.select_folder(folder.id)
                break
    
    def on_remove_account_menu_clicked(self):
        """Handle remove account from menu"""
        if not self.current_account_id:
            QMessageBox.warning(self, "No Account Selected", "Please select an account to remove.")
            return
        self.on_delete_account_requested(self.current_account_id)
    
    def on_delete_account_requested(self, account_id: int):
        """Handle account deletion request"""
        accounts = self.account_controller.list_accounts()
        account = None
        for acc in accounts:
            if acc.id == account_id:
                account = acc
                break
        
        if not account:
            return
        
        email_address = account.email_address
        reply = QMessageBox.question(
            self,
            "Remove Account",
            f"Are you sure you want to remove the account '{email_address}'?\n\n"
            "This will delete all cached emails, folders, and account data.\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Delete account using controller
                from email_client.auth.accounts import delete_account
                delete_account(account_id)
                
                # Remove from sidebar
                self.sidebar.remove_account(account_id)
                
                # Clear current account if it was the deleted one
                if self.current_account_id == account_id:
                    self.current_account_id = None
                    self.current_folder_id = None
                    self.sidebar.clear_folders()
                    self.email_list.clear_emails()
                    self.email_preview.show_empty_state()
                
                # Reload accounts list
                accounts = self.account_controller.list_accounts()
                if accounts:
                    # Select first account if available
                    self.on_account_selected(accounts[0].id)
                else:
                    # No accounts left, show add account dialog
                    self.on_add_account_clicked()
                
                QMessageBox.information(self, "Account Removed", f"Account '{email_address}' has been removed successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove account: {str(e)}")
    
    def on_folder_selected(self, folder_id: int):
        """Handle folder selection"""
        self.current_folder_id = folder_id
        folder = self.folder_controller.get_folder(folder_id)
        if folder:
            # Switch to list view
            self.right_stack.setCurrentIndex(0)
            
            # Load emails using controller
            emails = self.message_controller.list_messages(folder_id, limit=100)
            self.email_list.set_emails(emails)
            
            # Sync in background if needed
            accounts = self.account_controller.list_accounts()
            account = None
            for acc in accounts:
                if acc.id == folder.account_id:
                    account = acc
                    break
            if account:
                self.sync_folder(account, folder)
    
    def sync_folder(self, account: EmailAccount, folder: Folder):
        """Sync emails for a folder using SyncController"""
        try:
            self.status_bar.showMessage(f"Syncing {folder.name}...")
            # Use sync controller (runs synchronously, but we can make it async if needed)
            synced_count = self.sync_controller.sync_folder(folder, limit=100)
            self.status_bar.showMessage(f"Synced {synced_count} messages from {folder.name}")
            # Reload emails
            if self.current_folder_id:
                emails = self.message_controller.list_messages(self.current_folder_id, limit=100)
                self.email_list.set_emails(emails)
        except Exception as e:
            self.status_bar.showMessage(f"Sync error: {str(e)}")
            QMessageBox.warning(self, "Sync Error", f"Failed to sync folder: {str(e)}")
    
    def auto_sync(self):
        """Auto-sync current folder"""
        if self.current_folder_id:
            folder = self.folder_controller.get_folder(self.current_folder_id)
            if folder:
                accounts = self.account_controller.list_accounts()
                account = None
                for acc in accounts:
                    if acc.id == folder.account_id:
                        account = acc
                        break
                if account:
                    self.sync_folder(account, folder)
    
    def on_search(self):
        """Handle search"""
        query = self.search_input.text().strip()
        if not query:
            # If search is empty, reload current folder
            if self.current_folder_id:
                self.on_folder_selected(self.current_folder_id)
            return
        
        # Get account filter
        account_id = None
        if self.account_filter.currentIndex() > 0:
            account_id = self.account_filter.currentData()
        
        # Search using controller
        results = self.message_controller.search_messages(
            account_id=account_id,
            query=query,
            folder_id=self.current_folder_id,
            limit=100
        )
        self.email_list.set_emails(results)
        self.status_bar.showMessage(f"Found {len(results)} results")
    
    def on_account_filter_changed(self, index: int):
        """Handle account filter change"""
        # If searching, re-run search
        if self.search_input.text().strip():
            self.on_search()
    
    def on_email_selected(self, email_id: int):
        """Handle email selection"""
        email = self.message_controller.get_message(email_id)
        if email:
            # Check if this is a draft email
            folder = self.folder_controller.get_folder(email.folder_id)
            if folder and 'draft' in folder.name.lower():
                # Open draft in compose window for editing
                accounts = self.account_controller.list_accounts()
                account = None
                for acc in accounts:
                    if acc.id == email.account_id:
                        account = acc
                        break
                account_email = account.email_address if account else None
                # Get attachments for the draft
                attachments = cache_repo.list_attachments(email_id)
                compose_window = ComposeWindow(self, draft_email=email, account_id=email.account_id, account_email=account_email)
                # Load attachments into compose window
                if attachments:
                    compose_window.load_attachments(attachments)
                compose_window.email_sent.connect(self.handle_send_email)
                compose_window.draft_saved.connect(self.handle_save_draft)
                compose_window.exec_()
                # Reload emails after closing compose window (in case draft was deleted/updated)
                if self.current_folder_id:
                    emails = self.message_controller.list_messages(self.current_folder_id, limit=100)
                    self.email_list.set_emails(emails)
                return
            
            # Mark as read
            if not email.is_read:
                cache_repo.mark_email_read(email_id, True)
                email.is_read = True
            
            # Get attachments
            attachments = cache_repo.list_attachments(email_id)
            
            # Show in preview and switch to preview view
            self.email_preview.show_email(email, attachments)
            self.right_stack.setCurrentIndex(1)  # Switch to preview view
    
    def on_back_to_list(self):
        """Handle back button click - return to email list"""
        self.right_stack.setCurrentIndex(0)  # Switch back to list view
    
    def on_compose_clicked(self):
        """Handle compose button click"""
        if not self.current_account_id:
            QMessageBox.warning(self, "No Account", "Please select an account first.")
            return
        
        accounts = self.account_controller.list_accounts()
        account = None
        for acc in accounts:
            if acc.id == self.current_account_id:
                account = acc
                break
        
        if not account:
            QMessageBox.warning(self, "No Account", "Account not found.")
            return
        
        compose_window = ComposeWindow(self, account_id=self.current_account_id, account_email=account.email_address)
        compose_window.email_sent.connect(self.handle_send_email)
        compose_window.draft_saved.connect(self.handle_save_draft)
        compose_window.exec_()
    
    def on_reply_clicked(self, email_id: int):
        """Handle reply button click"""
        email = self.message_controller.get_message(email_id)
        if email:
            accounts = self.account_controller.list_accounts()
            account = None
            for acc in accounts:
                if acc.id == email.account_id:
                    account = acc
                    break
            account_email = account.email_address if account else None
            compose_window = ComposeWindow(self, reply_to=email, account_id=email.account_id, account_email=account_email)
            compose_window.email_sent.connect(self.handle_send_email)
            compose_window.draft_saved.connect(self.handle_save_draft)
            compose_window.exec_()
    
    def on_forward_clicked(self, email_id: int):
        """Handle forward button click"""
        email = self.message_controller.get_message(email_id)
        if email:
            accounts = self.account_controller.list_accounts()
            account = None
            for acc in accounts:
                if acc.id == email.account_id:
                    account = acc
                    break
            account_email = account.email_address if account else None
            compose_window = ComposeWindow(self, forward_email=email, account_id=email.account_id, account_email=account_email)
            compose_window.email_sent.connect(self.handle_send_email)
            compose_window.draft_saved.connect(self.handle_save_draft)
            compose_window.exec_()
    
    def on_delete_clicked(self, email_id: int):
        """Handle delete button click"""
        reply = QMessageBox.question(self, "Delete Email", "Are you sure you want to delete this email?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Delete email from cache
            from email_client.storage import db
            db.execute("DELETE FROM emails WHERE id = ?", (email_id,))
            # Reload emails
            if self.current_folder_id:
                emails = self.message_controller.list_messages(self.current_folder_id, limit=100)
                self.email_list.set_emails(emails)
            # Go back to list view
            self.on_back_to_list()
            self.email_preview.show_empty_state()
    
    def handle_save_draft(self, draft_data: dict):
        """
        Handle saving a draft email.
        
        Note: This method still uses the old database manager for draft storage.
        In a full refactor, this would use the new cache repository.
        """
        from email_client.models import EmailMessage, Attachment as AttachmentModel
        from email_client.storage import cache_repo
        from datetime import datetime
            
        account_id = draft_data.get('account_id')
        if not account_id:
            QMessageBox.warning(self, "Error", "No account specified for draft.")
            return
        
        try:
            # If we're editing an existing draft, delete it first
            draft_email_id = draft_data.get('draft_email_id')
            if draft_email_id:
                from email_client.storage import db
                db.execute("DELETE FROM emails WHERE id = ?", (draft_email_id,))
            
            # Get or create drafts folder
            folders = self.folder_controller.list_folders(account_id)
            drafts_folder = None
            for folder in folders:
                if folder.is_system_folder and (folder.server_path.upper() == 'DRAFTS' or folder.name.upper() == 'DRAFTS'):
                    drafts_folder = folder
                    break
            
            if not drafts_folder:
                # Create drafts folder if it doesn't exist
                from email_client.core.folder_manager import FolderManager
                from email_client.network.imap_client import ImapClient
                from email_client.auth.accounts import get_token_bundle, get_account
                
                account = get_account(account_id)
                if not account:
                    QMessageBox.warning(self, "Error", "Account not found.")
                    return
                
                token_bundle = get_token_bundle(account_id)
                imap_client = ImapClient(account, token_bundle)
                folder_manager = FolderManager(imap_client, cache_repo.upsert_folder)
                
                drafts_folder = folder_manager.create_folder("Drafts")
                
                # Update sidebar to show new drafts folder
                if self.current_account_id == account_id:
                    folders = self.folder_controller.list_folders(account_id)
                    self.sidebar.set_folders(folders)
            
            # Create email object for draft
            accounts = self.account_controller.list_accounts()
            account = None
            for acc in accounts:
                if acc.id == account_id:
                    account = acc
                    break
            
            recipients = draft_data.get('to', [])
            cc_recipients = draft_data.get('cc', [])
            bcc_recipients = draft_data.get('bcc', [])
            
            draft_email = EmailMessage(
                account_id=account_id,
                folder_id=drafts_folder.id if drafts_folder else 0,
                uid_on_server=0,  # Drafts don't have UID yet
                sender=account.email_address if account else "",
                recipients=recipients,
                cc_recipients=cc_recipients,
                bcc_recipients=bcc_recipients,
                subject=draft_data.get('subject', '(No Subject)'),
                body_plain=draft_data.get('body_text', ''),
                body_html=draft_data.get('body_html', ''),
                received_at=datetime.now(),
                is_read=True,  # Drafts are considered "read"
                has_attachments=len(draft_data.get('attachments', [])) > 0,
            )
            
            # Save draft using cache_repo
            saved_email = cache_repo.upsert_email_header(draft_email)
            if saved_email.id:
                # Save body content
                cache_repo.update_email_body(
                    saved_email.id,
                    draft_email.body_plain,
                    draft_email.body_html
                )
                
                # Save attachments if any
                if draft_data.get('attachments'):
                    import config
                    from pathlib import Path
                    for attachment_path in draft_data['attachments']:
                        att_path = Path(attachment_path)
                        if att_path.exists():
                            # Copy attachment to attachments directory
                            import shutil
                            dest_path = config.ATTACHMENTS_DIR / f"{saved_email.id}_{att_path.name}"
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(att_path, dest_path)
                            
                            attachment = AttachmentModel(
                                email_id=saved_email.id,
                                filename=att_path.name,
                                local_path=str(dest_path),
                                size_bytes=att_path.stat().st_size,
                                mime_type="application/octet-stream"
                            )
                            cache_repo.add_attachment(attachment)
            
            # Refresh drafts folder if it's currently selected
            if drafts_folder and self.current_folder_id == drafts_folder.id:
                emails = self.message_controller.list_messages(drafts_folder.id, limit=100)
                self.email_list.set_emails(emails)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving draft: {str(e)}")
    
    def handle_send_email(self, email_data: dict):
        """Handle sending an email using the new SmtpClient"""
        from email_client.network.smtp_client import SmtpClient
        from email_client.auth.accounts import get_token_bundle, get_account
        from email_client.models import EmailMessage, Attachment
        
        if not self.current_account_id:
            QMessageBox.warning(self, "No Account", "No account selected. Please select an account first.")
            return
        
        account = get_account(self.current_account_id)
        if not account:
            QMessageBox.warning(self, "No Account", "Account not found.")
            return
        
        try:
            # If sending from a draft, delete the draft first
            draft_email_id = email_data.get('draft_email_id')
            if draft_email_id:
                from email_client.storage import db
                db.execute("DELETE FROM emails WHERE id = ?", (draft_email_id,))
            
            # Get token bundle
            token_bundle = get_token_bundle(self.current_account_id)
            
            # Create SMTP client
            smtp_client = SmtpClient(account, token_bundle)
            
            # Build EmailMessage
            email_message = EmailMessage(
                account_id=account.id,
                sender=account.email_address,
                recipients=email_data.get('to', []),
                cc_recipients=email_data.get('cc', []),
                bcc_recipients=email_data.get('bcc', []),
                subject=email_data.get('subject', ''),
                body_plain=email_data.get('body_text', ''),
                body_html=email_data.get('body_html', ''),
            )
            
            # Build attachments list
            attachments = []
            if email_data.get('attachments'):
                from pathlib import Path
                for att_path in email_data['attachments']:
                    path = Path(att_path)
                    if path.exists():
                        attachments.append(Attachment(
                            filename=path.name,
                            local_path=str(path),
                            size_bytes=path.stat().st_size,
                            mime_type="application/octet-stream"
                        ))
            
            # Send email
            smtp_client.send_email(email_message, attachments)
            
            QMessageBox.information(self, "Success", f"Email sent successfully from {account.email_address}!")
            
            # Refresh current folder if it's drafts (to remove sent draft)
            if self.current_folder_id:
                folder = self.folder_controller.get_folder(self.current_folder_id)
                if folder and folder.is_system_folder and (folder.server_path.upper() == 'DRAFTS' or folder.name.upper() == 'DRAFTS'):
                    emails = self.message_controller.list_messages(self.current_folder_id, limit=100)
                    self.email_list.set_emails(emails)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error sending email: {str(e)}")
    
    def on_refresh_clicked(self):
        """Handle refresh button click - sync current folder"""
        if self.current_folder_id:
            folder = self.folder_controller.get_folder(self.current_folder_id)
            if folder:
                accounts = self.account_controller.list_accounts()
                account = None
                for acc in accounts:
                    if acc.id == folder.account_id:
                        account = acc
                        break
                if account:
                    self.sync_folder(account, folder)
        else:
            # If no folder selected, do initial sync for current account
            if self.current_account_id:
                accounts = self.account_controller.list_accounts()
                account = None
                for acc in accounts:
                    if acc.id == self.current_account_id:
                        account = acc
                        break
                if account:
                    try:
                        self.status_bar.showMessage("Performing initial sync...")
                        folders = self.sync_controller.initial_sync(account, inbox_limit=100)
                        self.status_bar.showMessage(f"Initial sync complete: {len(folders)} folders")
                        # Reload folders
                        self.on_account_selected(self.current_account_id)
                    except Exception as e:
                        self.status_bar.showMessage(f"Sync error: {str(e)}")
                        QMessageBox.warning(self, "Sync Error", f"Failed to sync: {str(e)}")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About", "Email Desktop Client\n\nA cross-platform email client built with Python and PyQt5.")
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.sync_thread and self.sync_thread.isRunning():
            self.sync_thread.terminate()
            self.sync_thread.wait()
        self.db_manager.close()
        event.accept()

