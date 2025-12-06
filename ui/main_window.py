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
            # Check for interruption request
            if self.isInterruptionRequested():
                return
            
            from email_client.oauth2_handler import OAuth2Handler
            oauth_handler = OAuth2Handler(self.provider)
            
            print(f"🔐 Starting OAuth authentication ({self.auth_method})...")
            import sys
            sys.stdout.flush()
            
            token_json = None
            
            if self.auth_method == 'gmail':
                try:
                    token_json = oauth_handler.authenticate_gmail()
                except Exception as inner_e:
                    print(f"❌ OAuth authentication error: {inner_e}")
                    import traceback
                    traceback.print_exc()
                    sys.stdout.flush()
                    raise
            elif self.auth_method == 'outlook':
                token_json = oauth_handler.authenticate_outlook()
            else:
                error_msg = f"Unknown auth method: {self.auth_method}"
                print(f"❌ {error_msg}")
                if not self.isInterruptionRequested():
                    self.authentication_failed.emit(error_msg)
                return
            
            # Check the result
            if token_json and not self.isInterruptionRequested():
                print(f"✅ OAuth authentication successful")
                self.authentication_complete.emit(token_json)
                import time
                time.sleep(0.1)  # Give signal time to be processed
            elif not self.isInterruptionRequested():
                error_msg = "OAuth authentication failed or was cancelled."
                if hasattr(oauth_handler, '_error') and oauth_handler._error:
                    error_msg = oauth_handler._error
                print(f"❌ OAuth authentication failed: {error_msg}")
                self.authentication_failed.emit(error_msg)
            else:
                print(f"⏹️  OAuth authentication cancelled")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ OAuth exception: {e}")
            traceback.print_exc()
            sys.stdout.flush()
            if not self.isInterruptionRequested():
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
        self.sidebar.folder_create_requested.connect(self.on_create_folder_requested)
        self.sidebar.folder_rename_requested.connect(self.on_rename_folder_requested)
        self.sidebar.folder_delete_requested.connect(self.on_delete_folder_requested)
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
        self.email_list.page_changed.connect(self.on_email_page_changed)
        self.email_list.bulk_delete_requested.connect(self.on_bulk_delete_requested)
        self.email_list.bulk_move_requested.connect(self.on_bulk_move_requested)
        self.right_stack.addWidget(self.email_list)  # Index 0
        self.current_folder_id = None  # Track current folder for pagination
        
        # Email preview
        self.email_preview = EmailPreview()
        self.email_preview.reply_clicked.connect(self.on_reply_clicked)
        self.email_preview.forward_clicked.connect(self.on_forward_clicked)
        self.email_preview.delete_clicked.connect(self.on_delete_clicked)
        self.email_preview.move_email_requested.connect(self.on_move_email_requested)
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
    
    def load_accounts(self, select_account_id: int = None):
        """Load accounts using the new database system
        
        Args:
            select_account_id: Optional account ID to select after loading.
                              If None, selects the first account.
        """
        accounts = self.account_controller.list_accounts()
        if accounts:
            # Update sidebar (now supports EmailAccount directly)
            self.sidebar.set_accounts(accounts)
            # Update account filter dropdown
            self.account_filter.clear()
            self.account_filter.addItem("All Accounts")
            for account in accounts:
                if account.id:
                    # Show email address instead of display name
                    self.account_filter.addItem(account.email_address or account.display_name, account.id)
            # Select account - prefer the specified one, otherwise first account
            account_to_select = None
            if select_account_id:
                # Find the specified account
                for account in accounts:
                    if account.id == select_account_id:
                        account_to_select = account
                        break
            # If not found or not specified, use first account
            if not account_to_select and accounts:
                account_to_select = accounts[0]
            
            if account_to_select and account_to_select.id:
                self.on_account_selected(account_to_select.id)
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
                # Password-based authentication
                self._create_password_account(account_data, login_window)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add account: {str(e)}")
            # Re-enable login button on error
            if login_window:
                login_window.progress_bar.setVisible(False)
                login_window.login_button.setEnabled(True)
    
    def _create_password_account(self, account_data: dict, login_window: LoginWindow = None):
        """Create a password-based account"""
        try:
            from email_client.auth.accounts import create_password_account
            
            account = create_password_account(
                provider_name=account_data['provider'],
                email=account_data['email'],
                password=account_data['password'],
                display_name=account_data['display_name'],
                imap_host=account_data.get('imap_server'),
                smtp_host=account_data.get('smtp_server'),
                imap_port=account_data.get('imap_port', 993),
                smtp_port=account_data.get('smtp_port', 587),
                use_tls=account_data.get('use_tls', True)
            )
            
            # Close login window
            if login_window:
                login_window.accept()
            
            # Reload accounts to refresh UI
            self.load_accounts()
            
            # Select the newly added account
            if account.id:
                self.on_account_selected(account.id)
            
            # Sync folders in background thread with progress updates
            self._start_initial_sync(account)
            
            # Bring main window to front
            self.show()
            self.raise_()
            self.activateWindow()
            
            QMessageBox.information(self, "Success", f"Account '{account_data['email']}' added successfully!")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to create account: {str(e)}")
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
        # Enable cancel button - connect to cancellation handler
        self.oauth_progress_dialog.canceled.connect(
            lambda: self._on_oauth_cancelled(login_window)
        )
        self.oauth_progress_dialog.show()
        
        # Store account_data and login_window for signal handlers
        self._pending_oauth_account_data = account_data
        self._pending_oauth_login_window = login_window
        self._pending_oauth_db_manager = db_manager
        self._pending_oauth_encryption_manager = encryption_manager
        
        # Create and start OAuth thread
        self.oauth_thread = OAuthThread(provider, auth_method)
        self.oauth_thread.authentication_complete.connect(self._on_oauth_success_signal)
        self.oauth_thread.authentication_failed.connect(self._on_oauth_failure_signal)
        self.oauth_thread.finished.connect(self._on_oauth_thread_finished)
        self.oauth_thread.start()
    
    def _on_oauth_success_signal(self, token_json: str):
        """Handle OAuth success signal - extract stored data and call actual handler"""
        account_data = getattr(self, '_pending_oauth_account_data', {})
        login_window = getattr(self, '_pending_oauth_login_window', None)
        db_manager = getattr(self, '_pending_oauth_db_manager', None)
        encryption_manager = getattr(self, '_pending_oauth_encryption_manager', None)
        
        # Clear stored data
        self._pending_oauth_account_data = None
        self._pending_oauth_login_window = None
        self._pending_oauth_db_manager = None
        self._pending_oauth_encryption_manager = None
        
        # Call the actual handler
        self._on_oauth_success(token_json, account_data, login_window, db_manager, encryption_manager)
    
    def _on_oauth_failure_signal(self, error: str):
        """Handle OAuth failure signal - extract stored data and call actual handler"""
        login_window = getattr(self, '_pending_oauth_login_window', None)
        
        # Clear stored data
        self._pending_oauth_account_data = None
        self._pending_oauth_login_window = None
        self._pending_oauth_db_manager = None
        self._pending_oauth_encryption_manager = None
        
        # Call the actual handler
        self._on_oauth_failure(error, login_window)
    
    def _on_oauth_cancelled(self, login_window: LoginWindow):
        """Handle OAuth authentication cancellation by user"""
        # Close progress dialog first to give immediate feedback
        if self.oauth_progress_dialog:
            self.oauth_progress_dialog.close()
            self.oauth_progress_dialog = None
        
        # Interrupt the OAuth thread if it's running
        if self.oauth_thread and self.oauth_thread.isRunning():
            self.oauth_thread.requestInterruption()
            # Don't wait for thread to finish - let it clean up in background
            # The thread will check for interruption and exit gracefully
        
        # Re-enable login button
        if login_window:
            login_window.progress_bar.setVisible(False)
            login_window.login_button.setEnabled(True)
            # Keep login window open so user can try again
    
    def _on_oauth_success(self, token_json: str, account_data: dict, login_window: LoginWindow,
                          db_manager, encryption_manager):
        """Handle successful OAuth authentication (called from main thread via signal)"""
        # Check if this was cancelled - if so, don't proceed
        if self.oauth_thread and self.oauth_thread.isInterruptionRequested():
            if self.oauth_progress_dialog:
                self.oauth_progress_dialog.close()
                self.oauth_progress_dialog = None
            return
        
        try:
            # Close progress dialog first
            if self.oauth_progress_dialog:
                self.oauth_progress_dialog.close()
                self.oauth_progress_dialog = None
            
            # Close login window immediately for better UX
            if login_window:
                login_window.accept()
                QApplication.processEvents()
                login_window.hide()
                login_window.setVisible(False)
            
            QApplication.processEvents()
            
            # Defer heavy operations using a timer so the dialog can close first
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
        # Check if this was due to user cancellation
        if self.oauth_thread and self.oauth_thread.isInterruptionRequested():
            # User cancelled - already handled in _on_oauth_cancelled
            # Just clean up the dialog if it's still open
            if self.oauth_progress_dialog:
                self.oauth_progress_dialog.close()
                self.oauth_progress_dialog = None
            return
        
        # Close progress dialog
        if self.oauth_progress_dialog:
            self.oauth_progress_dialog.close()
            self.oauth_progress_dialog = None
        
        # Re-enable login button first
        if login_window:
            login_window.progress_bar.setVisible(False)
            login_window.login_button.setEnabled(True)
            # Keep login window open so user can try again
        
        # Show error message only if not cancelled
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
            
            # Extract token information
            access_token = token_data.get('token') or token_data.get('access_token', '')
            refresh_token = token_data.get('refresh_token')
            
            # Calculate expiration time
            expires_in = token_data.get('expires_in', 3600)
            if expires_in <= 0 or expires_in > 7200:
                expires_in = 3600
            
            # Calculate expires_at: current time + expires_in seconds
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Validate access token before creating bundle
            if not access_token:
                raise ValueError("Access token is empty or None - cannot create account")
            
            # Create TokenBundle
            token_bundle = TokenBundle(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at
            )
            
            # Get user email from OAuth user info (fetched during authentication)
            # This is CRITICAL - account_data['email'] is empty!
            # Strip whitespace to prevent XOAUTH2 authentication failures
            profile_email = (token_data.get('user_email') or account_data.get('email') or '').strip()
            
            if not profile_email:
                raise ValueError(
                    "Could not retrieve email address from OAuth authentication. "
                    "Please try again or contact support."
                )
            
            # Get display name from OAuth user info or fall back to account_data
            user_name = token_data.get('user_name', '')
            display_name = (
                account_data.get('display_name') or 
                user_name or 
                profile_email.split('@')[0]
            )
            
            # Create account
            provider_name = account_data['provider'].lower()
            account = create_oauth_account(
                provider_name=provider_name,
                token_bundle=token_bundle,
                profile_email=profile_email,
                display_name=display_name
            )
            
            if not account.id:
                raise ValueError("Account was created but has no ID. This is a critical error.")
            
            # Reload accounts to refresh UI
            self.load_accounts(select_account_id=account.id)
            
            # Select the newly added account and start sync
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(200, lambda: self._select_and_sync_account(account.id))
            
            # Bring main window to front
            self.show()
            self.raise_()
            self.activateWindow()
            
            QMessageBox.information(self, "Success", f"Account '{profile_email}' added successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to complete account setup: {str(e)}")
        finally:
            # Clean up old database manager if it exists
            if db_manager:
                try:
                    db_manager.close()
                except:
                    pass
    
    
    def _select_and_sync_account(self, account_id: int):
        """Helper method to select an account and start initial sync"""
        try:
            # Select the account
            self.on_account_selected(account_id)
            
            # Get the account object
            accounts = self.account_controller.list_accounts()
            account = None
            for acc in accounts:
                if acc.id == account_id:
                    account = acc
                    break
            
            if account:
                # Start initial sync in background
                self._start_initial_sync(account)
            else:
                print(f"Warning: Account {account_id} not found after creation")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error in _select_and_sync_account: {e}")
    
    def on_account_selected(self, account_id: int):
        """Handle account selection"""
        self.current_account_id = account_id
        # Load folders using controller
        folders = self.folder_controller.list_folders(account_id)
        self.sidebar.set_folders(folders)
        
        # Select inbox if available
        inbox_folder = None
        for folder in folders:
            if folder.is_system_folder and (
                folder.server_path.upper() == 'INBOX' or 
                folder.name.upper() == 'INBOX'
            ):
                inbox_folder = folder
                break
        
        # If no inbox found, select first folder
        if not inbox_folder and folders:
            inbox_folder = folders[0]
        
        if inbox_folder and inbox_folder.id:
            self.sidebar.select_folder(inbox_folder.id)
    
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
        if not folder:
            print(f"Warning: Folder with id {folder_id} not found")
            return
        
            # Switch to list view
            self.right_stack.setCurrentIndex(0)
            
        # Check if this is "All Mail" - it should show emails from all folders
        is_all_mail = (
            folder.name.upper() == 'ALL MAIL' or 
            folder.server_path.upper().endswith('/ALL MAIL') or
            '[GMAIL]/ALL MAIL' in folder.server_path.upper()
        )
        
        if is_all_mail:
            # For "All Mail", load emails from all folders for this account
            all_folders = self.folder_controller.list_folders(folder.account_id)
            all_emails = []
            for f in all_folders:
                if f.id and f.id != folder_id:  # Exclude "All Mail" itself to avoid duplicates
                    folder_emails = self.message_controller.list_messages(f.id, limit=1000)
                    all_emails.extend(folder_emails)
            
            # Remove duplicates by email ID (in case same email exists in multiple folders)
            seen_ids = set()
            unique_emails = []
            for email in all_emails:
                if email.id and email.id not in seen_ids:
                    seen_ids.add(email.id)
                    unique_emails.append(email)
            
            # For "All Mail", pagination is more complex - show all for now
            # Sort by date (newest first)
            unique_emails.sort(key=lambda x: x.received_at or x.sent_at or datetime.min, reverse=True)
            # Take first page (50 emails)
            page_size = 50
            total_count = len(unique_emails)
            page_emails = unique_emails[:page_size]
            self.email_list.set_emails(page_emails, total_count=total_count, current_page=0, folder_id=folder_id)
        else:
            # For regular folders, load emails with pagination (page 0, page size 50)
            self.current_folder_id = folder_id
            self.load_folder_emails(folder_id, page=0)
            
            # Sync in background if needed
            accounts = self.account_controller.list_accounts()
            account = None
            for acc in accounts:
                if acc.id == folder.account_id:
                    account = acc
                    break
            if account:
                # Sync with higher limit to ensure we get latest emails
                self.sync_folder(account, folder, limit=500)
    
    def load_folder_emails(self, folder_id: int, page: int = 0):
        """Load emails for a folder with pagination"""
        PAGE_SIZE = 50  # Fixed page size
        
        # Get total count
        total_count = self.message_controller.count_messages(folder_id)
        
        # Calculate offset
        offset = page * PAGE_SIZE
        
        # Load emails for this page
        emails = self.message_controller.list_messages(folder_id, limit=PAGE_SIZE, offset=offset)
        
        # Set emails with pagination info
        self.email_list.set_emails(emails, total_count=total_count, current_page=page, folder_id=folder_id)
    
    def on_email_page_changed(self, page: int):
        """Handle email list page change"""
        if self.current_folder_id:
            self.load_folder_emails(self.current_folder_id, page=page)
    
    def sync_folder(self, account: EmailAccount, folder: Folder, limit: int = 500):
        """Sync emails for a folder using SyncController (runs in background)"""
        # Run sync in background to avoid blocking UI
        from PyQt5.QtCore import QThread, pyqtSignal
        
        class SyncThread(QThread):
            finished_signal = pyqtSignal(int)  # synced_count
            error_signal = pyqtSignal(str)  # error message
            
            def __init__(self, sync_controller, folder, limit):
                super().__init__()
                self.sync_controller = sync_controller
                self.folder = folder
                self.limit = limit
            
            def run(self):
                try:
                    # Check for interruption request
                    if self.isInterruptionRequested():
                        return
                    synced_count = self.sync_controller.sync_folder(self.folder, limit=self.limit)
                    if not self.isInterruptionRequested():
                        self.finished_signal.emit(synced_count)
                except Exception as e:
                    if not self.isInterruptionRequested():
                        self.error_signal.emit(str(e))
        
        # Show status message
        self.status_bar.showMessage(f"Syncing {folder.name}...")
        
        # Create and start sync thread with specified limit (default 500 to get more emails)
        sync_thread = SyncThread(self.sync_controller, folder, limit=limit)
        sync_thread.finished_signal.connect(
            lambda count: self._on_sync_complete(folder, count)
        )
        sync_thread.error_signal.connect(
            lambda error: self._on_sync_error(folder, error)
        )
        
        # Store thread reference to prevent garbage collection and allow cleanup
        if not hasattr(self, '_sync_threads'):
            self._sync_threads = []
        self._sync_threads.append(sync_thread)
        
        # Connect finished signal to remove from list when done
        def on_finished():
            if hasattr(self, '_sync_threads') and sync_thread in self._sync_threads:
                self._sync_threads.remove(sync_thread)
        
        sync_thread.finished.connect(on_finished)
        sync_thread.start()
    
    def _start_initial_sync(self, account: EmailAccount):
        """Start initial sync in background thread with progress updates"""
        from PyQt5.QtCore import QThread, pyqtSignal, QTimer
        
        class InitialSyncThread(QThread):
            progress_signal = pyqtSignal(str, int, int)  # folder_name, synced_count, total_folders
            finished_signal = pyqtSignal(list)  # folders
            error_signal = pyqtSignal(str)  # error message
            
            def __init__(self, sync_controller, account, inbox_limit, folder_limit):
                super().__init__()
                self.sync_controller = sync_controller
                self.account = account
                self.inbox_limit = inbox_limit
                self.folder_limit = folder_limit
            
            def run(self):
                try:
                    # Check for interruption request
                    if self.isInterruptionRequested():
                        return
                    
                    def progress_callback(folder_name, synced_count, total_folders):
                        if not self.isInterruptionRequested():
                            self.progress_signal.emit(folder_name, synced_count, total_folders)
                    
                    folders = self.sync_controller.initial_sync(
                        self.account, 
                        inbox_limit=self.inbox_limit,
                        folder_limit=self.folder_limit,
                        progress_callback=progress_callback
                    )
                    if not self.isInterruptionRequested():
                        self.finished_signal.emit(folders)
                except Exception as e:
                    if not self.isInterruptionRequested():
                        import traceback
                        traceback.print_exc()
                        self.error_signal.emit(str(e))
        
        # Create and start sync thread
        sync_thread = InitialSyncThread(
            self.sync_controller, 
            account, 
            inbox_limit=100,
            folder_limit=50
        )
        sync_thread.progress_signal.connect(
            lambda folder_name, synced_count, total: self._on_sync_progress(account, folder_name, synced_count, total)
        )
        sync_thread.finished_signal.connect(
            lambda folders: self._on_initial_sync_complete(account, folders)
        )
        sync_thread.error_signal.connect(
            lambda error: self._on_initial_sync_error(account, error)
        )
        
        # Store thread reference to prevent garbage collection
        if not hasattr(self, '_sync_threads'):
            self._sync_threads = []
        self._sync_threads.append(sync_thread)
        
        # Defer sync by 500ms to ensure UI is responsive
        QTimer.singleShot(500, sync_thread.start)
    
    def _on_sync_progress(self, account: EmailAccount, folder_name: str, synced_count: int, total_folders: int):
        """Handle sync progress updates"""
        self.status_bar.showMessage(
            f"Syncing {account.email_address}: {folder_name} ({synced_count} messages) "
            f"[{total_folders} folders total]"
        )
    
    def _on_initial_sync_complete(self, account: EmailAccount, folders: list):
        """Handle initial sync completion"""
        total_messages = sum(folder.unread_count or 0 for folder in folders)
        self.status_bar.showMessage(
            f"Initial sync complete: {len(folders)} folders, {total_messages} messages for {account.email_address}"
        )
        # Reload folders
        if account.id:
            self.on_account_selected(account.id)
    
    def _on_initial_sync_error(self, account: EmailAccount, error: str):
        """Handle initial sync error"""
        import traceback
        traceback.print_exc()
        self.status_bar.showMessage(f"Sync error for {account.email_address}: {error}")
        print(f"Warning: Folder sync failed: {error}")
    
    def _on_sync_complete(self, folder: Folder, synced_count: int):
        """Handle successful folder sync"""
        if synced_count > 0:
            self.status_bar.showMessage(f"Synced {synced_count} new messages from {folder.name}")
            # Reload current page to show newly synced messages
            if self.current_folder_id and self.current_folder_id == folder.id:
                current_page = self.email_list.current_page
                self.load_folder_emails(self.current_folder_id, page=current_page)
    
    def _on_sync_error(self, folder: Folder, error: str):
        """Handle folder sync error"""
        self.status_bar.showMessage(f"Sync error: {error}")
        QMessageBox.warning(self, "Sync Error", f"Failed to sync folder {folder.name}: {error}")
    
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
        # Sort search results by date (newest first) and apply pagination
        results.sort(key=lambda x: x.received_at or x.sent_at or datetime.min, reverse=True)
        total_count = len(results)
        page_size = 50
        page_results = results[:page_size]
        self.email_list.set_emails(page_results, total_count=total_count, current_page=0, folder_id=self.current_folder_id)
        self.status_bar.showMessage(f"Found {total_count} results")
    
    def on_account_filter_changed(self, index: int):
        """Handle account filter change - switch between accounts"""
        if index == 0:
            # "All Accounts" selected - show all emails from all accounts
            self.current_account_id = None
            # Clear folder selection and show all folders
            folders = []
            accounts = self.account_controller.list_accounts()
            for account in accounts:
                account_folders = self.folder_controller.list_folders(account.id)
                folders.extend(account_folders)
            self.sidebar.set_folders(folders)
            # Clear email list
            self.email_list.set_emails([], total_count=0, current_page=0, folder_id=None)
        else:
            # Specific account selected
            account_id = self.account_filter.currentData()
            if account_id:
                self.current_account_id = account_id
                # Load folders for this account
                folders = self.folder_controller.list_folders(account_id)
                self.sidebar.set_folders(folders)
                # Clear current folder selection and email list
                self.current_folder_id = None
                self.email_list.set_emails([], total_count=0, current_page=0, folder_id=None)
        
        # If searching, re-run search
        if self.search_input.text().strip():
            self.on_search()
    
    def on_email_selected(self, email_id: int):
        """Handle email selection"""
        email = self.message_controller.get_message(email_id)
        if not email:
            return
        
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
                current_page = self.email_list.current_page
                self.load_folder_emails(self.current_folder_id, page=current_page)
            return
        
        # Check if body content is missing and fetch it if needed
        if not email.body_plain and not email.body_html:
            # Body not cached, fetch it from server
            if folder and email.uid_on_server:
                try:
                    # Get account for sync manager
                    accounts = self.account_controller.list_accounts()
                    account = None
                    for acc in accounts:
                        if acc.id == email.account_id:
                            account = acc
                            break
                    
                    if account:
                        # Fetch body using sync controller
                        email = self.sync_controller.fetch_email_body(account, folder, email)
                except Exception as e:
                    # If fetch fails, show email without body
                    print(f"Failed to fetch email body: {e}")
        
        # Mark as read (both locally and on the server)
        if not email.is_read:
            # Update local cache
            cache_repo.mark_email_read(email_id, True)
            email.is_read = True

            # Update server flags if possible
            if folder and email.uid_on_server:
                try:
                    accounts = self.account_controller.list_accounts()
                    account = None
                    for acc in accounts:
                        if acc.id == email.account_id:
                            account = acc
                            break
                    if account:
                        self.sync_controller.mark_message_read(account, folder, email)
                except Exception as e:
                    # Don't block UI if server update fails
                    print(f"Failed to mark message as read on server: {e}")

            # Update list UI so the row is no longer bold/unread
            if hasattr(self, "email_list") and self.email_list:
                try:
                    self.email_list.set_email_read_state(email_id, True)
                except Exception:
                    pass
        
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
            # Get email and folder information
            email = self.message_controller.get_message(email_id)
            if not email:
                QMessageBox.warning(self, "Error", "Email not found.")
                return
            
            folder = self.folder_controller.get_folder(email.folder_id)
            if not folder:
                QMessageBox.warning(self, "Error", "Folder not found.")
                return
            
            # Get account
            accounts = self.account_controller.list_accounts()
            account = None
            for acc in accounts:
                if acc.id == email.account_id:
                    account = acc
                    break
            
            if not account:
                QMessageBox.warning(self, "Error", "Account not found.")
                return
            
            try:
                # Delete from server first
                if email.uid_on_server:
                    self.sync_controller.delete_message(account, folder, email)
                
                # Delete email from cache
                from email_client.storage import db
                db.execute("DELETE FROM emails WHERE id = ?", (email_id,))
                
                # Reload emails with pagination
                if self.current_folder_id:
                    current_page = self.email_list.current_page
                    self.load_folder_emails(self.current_folder_id, page=current_page)
                
                # Go back to list view
                self.on_back_to_list()
                self.email_preview.show_empty_state()
                
                self.status_bar.showMessage(f"Email deleted successfully")
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete email from server: {str(e)}")
                # Still delete from cache if server deletion fails (user can manually delete later)
                try:
                    from email_client.storage import db
                    db.execute("DELETE FROM emails WHERE id = ?", (email_id,))
                    if self.current_folder_id:
                        current_page = self.email_list.current_page
                        self.load_folder_emails(self.current_folder_id, page=current_page)
                    self.on_back_to_list()
                    self.email_preview.show_empty_state()
                except Exception:
                    pass
    
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
                from email_client.auth.accounts import get_token_bundle, get_password, get_account
                
                account = get_account(account_id)
                if not account:
                    QMessageBox.warning(self, "Error", "Account not found.")
                    return
                
                # Get authentication credentials based on account type
                token_bundle = None
                password = None
                if account.auth_type == "oauth":
                    try:
                        token_bundle = get_token_bundle(account_id)
                    except Exception:
                        pass
                elif account.auth_type == "password":
                    try:
                        password = get_password(account_id)
                    except Exception:
                        pass
                
                imap_client = ImapClient(account, token_bundle=token_bundle, password=password)
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
                current_page = self.email_list.current_page
                self.load_folder_emails(drafts_folder.id, page=current_page)
            
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
            
            # Get authentication credentials based on account type
            token_bundle = None
            password = None
            
            if account.auth_type == "oauth":
                try:
                    token_bundle = get_token_bundle(self.current_account_id)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to get OAuth token: {str(e)}")
                    return
            elif account.auth_type == "password":
                try:
                    from email_client.auth.accounts import get_password
                    password = get_password(self.current_account_id)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to get password: {str(e)}")
                    return
            
            # Create SMTP client with appropriate authentication
            smtp_client = SmtpClient(account, token_bundle=token_bundle, password=password)
            
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
                    current_page = self.email_list.current_page
                    self.load_folder_emails(self.current_folder_id, page=current_page)
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
    
    def on_create_folder_requested(self, account_id: int):
        """Handle create folder request"""
        from ui.components.folder_dialog import CreateFolderDialog
        
        dialog = CreateFolderDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            folder_name = dialog.get_folder_name()
            if folder_name:
                try:
                    folder = self.folder_controller.create_folder(account_id, folder_name)
                    # Reload folders for the account
                    folders = self.folder_controller.list_folders(account_id)
                    self.sidebar.set_folders(folders)
                    self.status_bar.showMessage(f"Folder '{folder_name}' created successfully")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to create folder: {str(e)}")
    
    def on_rename_folder_requested(self, folder_id: int):
        """Handle rename folder request"""
        from ui.components.folder_dialog import RenameFolderDialog
        
        folder = self.folder_controller.get_folder(folder_id)
        if not folder:
            QMessageBox.warning(self, "Error", "Folder not found.")
            return
        
        dialog = RenameFolderDialog(folder.name, self)
        if dialog.exec_() == QDialog.Accepted:
            new_name = dialog.get_new_name()
            if new_name and new_name != folder.name:
                try:
                    updated_folder = self.folder_controller.rename_folder(folder_id, new_name)
                    # Reload folders for the account
                    folders = self.folder_controller.list_folders(folder.account_id)
                    self.sidebar.set_folders(folders)
                    # If this was the current folder, update selection
                    if self.current_folder_id == folder_id:
                        self.sidebar.select_folder(updated_folder.id)
                    self.status_bar.showMessage(f"Folder renamed to '{new_name}' successfully")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to rename folder: {str(e)}")
    
    def on_delete_folder_requested(self, folder_id: int):
        """Handle delete folder request"""
        folder = self.folder_controller.get_folder(folder_id)
        if not folder:
            QMessageBox.warning(self, "Error", "Folder not found.")
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Folder",
            f"Are you sure you want to delete the folder '{folder.name}'?\n\n"
            "All emails in this folder will be deleted from the server.\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.folder_controller.delete_folder(folder_id)
                # Reload folders for the account
                folders = self.folder_controller.list_folders(folder.account_id)
                self.sidebar.set_folders(folders)
                # If this was the current folder, clear selection
                if self.current_folder_id == folder_id:
                    self.current_folder_id = None
                    self.email_list.set_emails([], total_count=0, current_page=0, folder_id=None)
                self.status_bar.showMessage(f"Folder '{folder.name}' deleted successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete folder: {str(e)}")
    
    def on_move_email_requested(self, email_id: int):
        """Handle move email request"""
        from ui.components.folder_dialog import MoveEmailDialog
        
        email = self.message_controller.get_message(email_id)
        if not email:
            QMessageBox.warning(self, "Error", "Email not found.")
            return
        
        # Get all folders for the account
        folders = self.folder_controller.list_folders(email.account_id)
        if not folders:
            QMessageBox.warning(self, "Error", "No folders available.")
            return
        
        dialog = MoveEmailDialog(folders, current_folder_id=email.folder_id, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            dest_folder_id = dialog.get_selected_folder_id()
            if dest_folder_id:
                try:
                    self.folder_controller.move_email(email_id, dest_folder_id)
                    # Reload current folder to reflect the move
                    if self.current_folder_id:
                        current_page = self.email_list.current_page
                        self.load_folder_emails(self.current_folder_id, page=current_page)
                    # Go back to list view
                    self.on_back_to_list()
                    self.email_preview.show_empty_state()
                    dest_folder = self.folder_controller.get_folder(dest_folder_id)
                    if dest_folder:
                        self.status_bar.showMessage(f"Email moved to '{dest_folder.name}' successfully")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to move email: {str(e)}")
    
    def on_bulk_delete_requested(self, email_ids: list):
        """Handle bulk delete request"""
        if not email_ids:
            return
        
        count = len(email_ids)
        reply = QMessageBox.question(
            self, 
            "Delete Emails", 
            f"Are you sure you want to delete {count} email{'s' if count > 1 else ''}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success_count = 0
            failed_count = 0
            
            for email_id in email_ids:
                try:
                    # Get email and folder information
                    email = self.message_controller.get_message(email_id)
                    if not email:
                        failed_count += 1
                        continue
                    
                    folder = self.folder_controller.get_folder(email.folder_id)
                    if not folder:
                        failed_count += 1
                        continue
                    
                    # Get account
                    accounts = self.account_controller.list_accounts()
                    account = None
                    for acc in accounts:
                        if acc.id == email.account_id:
                            account = acc
                            break
                    
                    if account:
                        # Delete from server
                        try:
                            self.sync_controller.delete_message(account, folder, email)
                        except Exception as e:
                            print(f"Failed to delete email {email_id} from server: {e}")
                    
                    # Delete from cache
                    try:
                        from email_client.storage import db
                        db.execute("DELETE FROM emails WHERE id = ?", (email_id,))
                        success_count += 1
                    except Exception:
                        failed_count += 1
                        
                except Exception as e:
                    print(f"Error deleting email {email_id}: {e}")
                    failed_count += 1
            
            # Reload folder
            if self.current_folder_id:
                current_page = self.email_list.current_page
                self.load_folder_emails(self.current_folder_id, page=current_page)
            
            # Clear selection and refresh
            self.email_list.selected_email_ids.clear()
            self.email_list.update_table()
            self.email_list.update_bulk_actions_visibility()
            
            # Show status message
            if failed_count == 0:
                self.status_bar.showMessage(f"Successfully deleted {success_count} email{'s' if success_count > 1 else ''}")
            else:
                self.status_bar.showMessage(f"Deleted {success_count} email{'s' if success_count > 1 else ''}, {failed_count} failed")
    
    def on_bulk_move_requested(self, email_ids: list):
        """Handle bulk move request"""
        if not email_ids:
            return
        
        # Get first email to determine account and current folder
        first_email = self.message_controller.get_message(email_ids[0])
        if not first_email:
            QMessageBox.warning(self, "Error", "Email not found.")
            return
        
        # Get all folders for the account
        folders = self.folder_controller.list_folders(first_email.account_id)
        if not folders:
            QMessageBox.warning(self, "Error", "No folders available.")
            return
        
        from ui.components.folder_dialog import MoveEmailDialog
        dialog = MoveEmailDialog(folders, current_folder_id=first_email.folder_id, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            dest_folder_id = dialog.get_selected_folder_id()
            if dest_folder_id:
                success_count = 0
                failed_count = 0
                
                for email_id in email_ids:
                    try:
                        self.folder_controller.move_email(email_id, dest_folder_id)
                        success_count += 1
                    except Exception as e:
                        print(f"Failed to move email {email_id}: {e}")
                        failed_count += 1
                
                # Reload current folder to reflect the moves
                if self.current_folder_id:
                    current_page = self.email_list.current_page
                    self.load_folder_emails(self.current_folder_id, page=current_page)
                
                # Clear selection
                self.email_list.selected_email_ids.clear()
                self.email_list.update_table()
                
                # Show status message
                dest_folder = self.folder_controller.get_folder(dest_folder_id)
                if dest_folder:
                    if failed_count == 0:
                        self.status_bar.showMessage(f"Successfully moved {success_count} email{'s' if success_count > 1 else ''} to '{dest_folder.name}'")
                    else:
                        self.status_bar.showMessage(f"Moved {success_count} email{'s' if success_count > 1 else ''} to '{dest_folder.name}', {failed_count} failed")
    
    def closeEvent(self, event):
        """Handle window close event - graceful shutdown"""
        try:
            # Stop auto-sync timer
            if hasattr(self, 'sync_timer') and self.sync_timer:
                try:
                    self.sync_timer.stop()
                except Exception:
                    pass
            
            # Stop OAuth thread gracefully if running
            if hasattr(self, 'oauth_thread') and self.oauth_thread:
                if self.oauth_thread.isRunning():
                    # Request thread to stop gracefully
                    self.oauth_thread.requestInterruption()
                    # Wait for OAuth thread to finish (with timeout)
                    if not self.oauth_thread.wait(2000):  # Wait up to 2 seconds
                        # If still running, terminate it
                        try:
                            self.oauth_thread.terminate()
                            self.oauth_thread.wait(1000)  # Wait up to 1 more second
                        except Exception:
                            pass
                try:
                    self.oauth_thread.deleteLater()
                except Exception:
                    pass
                self.oauth_thread = None
            
            # Close OAuth progress dialog if open
            if hasattr(self, 'oauth_progress_dialog') and self.oauth_progress_dialog:
                try:
                    self.oauth_progress_dialog.close()
                    self.oauth_progress_dialog = None
                except Exception:
                    pass
            
            # Stop sync thread gracefully if running
            if hasattr(self, 'sync_thread') and self.sync_thread:
                if self.sync_thread.isRunning():
                    # Request thread to stop gracefully
                    self.sync_thread.requestInterruption()
                    # Wait for sync thread to finish (with timeout)
                    if not self.sync_thread.wait(2000):  # Wait up to 2 seconds
                        # If still running, terminate it
                        try:
                            self.sync_thread.terminate()
                            self.sync_thread.wait(1000)  # Wait up to 1 more second
                        except Exception:
                            pass
                try:
                    self.sync_thread.deleteLater()
                except Exception:
                    pass
                self.sync_thread = None
            
            # Stop all sync threads from _sync_threads list
            if hasattr(self, '_sync_threads') and self._sync_threads:
                threads_to_cleanup = list(self._sync_threads)  # Copy list to avoid modification during iteration
                for sync_thread in threads_to_cleanup:
                    if sync_thread:
                        try:
                            if sync_thread.isRunning():
                                # Request thread to stop gracefully
                                sync_thread.requestInterruption()
                                # Wait for thread to finish (with timeout)
                                if not sync_thread.wait(2000):  # Wait up to 2 seconds
                                    # If still running, terminate it
                                    try:
                                        sync_thread.terminate()
                                        sync_thread.wait(1000)  # Wait up to 1 more second
                                    except Exception:
                                        pass
                            # Clean up thread
                            sync_thread.deleteLater()
                        except Exception:
                            pass
                self._sync_threads.clear()
            
            # Close database manager if it exists (legacy code)
            if hasattr(self, 'db_manager') and self.db_manager:
                try:
                    self.db_manager.close()
                except Exception:
                    pass  # Ignore errors during shutdown
            
            # Process any pending events to ensure cleanup completes
            # But limit it to avoid reentrant calls
            try:
                QApplication.processEvents(QApplication.ExcludeUserInputEvents)
            except Exception:
                pass
            
        except Exception as e:
            # Log but don't prevent shutdown
            print(f"Error during shutdown: {e}")
        
        # Always accept the close event to allow the app to close
        event.accept()

