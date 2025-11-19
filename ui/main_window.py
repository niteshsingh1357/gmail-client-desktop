"""
Main application window
"""
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QSplitter, QMenuBar, QMenu, QStatusBar, QMessageBox,
                             QAction, QStackedWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QKeySequence
import config
from ui.login_window import LoginWindow
from ui.compose_window import ComposeWindow
from ui.components.sidebar import Sidebar
from ui.components.email_list import EmailList
from ui.components.email_preview import EmailPreview
from database.db_manager import DatabaseManager
from database.models import Account, Folder, Email, Attachment
from email_client.imap_client import IMAPClient
from email_client.smtp_client import SMTPClient
from email_client.oauth2_handler import OAuth2Handler
from encryption.crypto import get_encryption_manager


class SyncThread(QThread):
    """Background thread for email synchronization"""
    
    sync_complete = pyqtSignal(int, list)  # account_id, list of emails
    sync_error = pyqtSignal(str)  # error message
    
    def __init__(self, account: Account, folder: Folder, db_manager: DatabaseManager):
        super().__init__()
        self.account = account
        self.folder = folder
        self.db_manager = db_manager
        self.encryption_manager = get_encryption_manager()
    
    def run(self):
        """Run email synchronization"""
        try:
            # Decrypt token/password
            encrypted_token = self.account.encrypted_token
            if not encrypted_token:
                self.sync_error.emit("No authentication token found")
                return
            
            token = self.encryption_manager.decrypt(encrypted_token)
            
            # Connect to IMAP
            imap_client = IMAPClient(
                self.account.imap_server,
                self.account.imap_port,
                self.account.use_tls
            )
            
            # For OAuth2, we'd need to use app-specific passwords or OAuth2 IMAP
            # For now, assume password-based authentication
            if not imap_client.connect(self.account.email_address, token):
                self.sync_error.emit("Failed to connect to IMAP server")
                return
            
            # Fetch emails - try both the stored full_path and the folder name
            emails = []
            
            # First try the full_path as stored
            emails = imap_client.fetch_emails(self.folder.full_path, limit=config.MAX_EMAILS_PER_SYNC)
            
            # If that returns empty and folder name is different, try the folder name
            if not emails and self.folder.name != self.folder.full_path:
                print(f"Trying folder name '{self.folder.name}' instead of full_path '{self.folder.full_path}'")
                emails = imap_client.fetch_emails(self.folder.name, limit=config.MAX_EMAILS_PER_SYNC)
            
            print(f"Fetched {len(emails)} emails from folder '{self.folder.name}' (path: '{self.folder.full_path}')")
            
            # Save to database
            saved_emails = []
            for email in emails:
                email.account_id = self.account.account_id
                email.folder_id = self.folder.folder_id
                email_id = self.db_manager.add_email(email)
                if email_id:
                    email.email_id = email_id
                    saved_emails.append(email)
            
            print(f"Saved {len(saved_emails)} emails to database")
            
            imap_client.disconnect()
            self.sync_complete.emit(self.account.account_id, saved_emails)
        except Exception as e:
            error_msg = f"Sync error for folder '{self.folder.name}': {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.sync_error.emit(error_msg)


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Email Desktop Client")
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT)
        
        # Initialize managers
        self.db_manager = DatabaseManager()
        self.encryption_manager = get_encryption_manager()
        self.current_account_id = None
        self.current_folder_id = None
        self.sync_thread = None
        
        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()
        self.load_accounts()
        
        # Auto-sync timer
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.auto_sync)
        self.sync_timer.start(config.DEFAULT_SYNC_INTERVAL * 1000)  # Convert to milliseconds
    
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
        
        # Right side - use stacked widget to switch between list and preview
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
        
        splitter.addWidget(self.right_stack)
        
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
        """Load accounts from database"""
        accounts = self.db_manager.get_all_accounts()
        if accounts:
            self.sidebar.set_accounts(accounts)
            # Select first account
            if accounts:
                self.on_account_selected(accounts[0].account_id)
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
        """Handle new account addition"""
        try:
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
                            "Would you like to use password authentication instead?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.Yes:
                            # Fall back to password authentication
                            if not account_data.get('password'):
                                QMessageBox.warning(
                                    self,
                                    "Password Required",
                                    "Please enter your password or app-specific password in the login window."
                                )
                                return
                            encrypted_token = self.encryption_manager.encrypt(account_data['password'])
                        else:
                            return
                    else:
                        oauth_handler = OAuth2Handler(provider)
                        token_json = oauth_handler.authenticate_gmail()
                        if not token_json:
                            QMessageBox.warning(self, "Authentication Failed", "OAuth2 authentication failed.")
                            return
                        encrypted_token = self.encryption_manager.encrypt(token_json)
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
                            "Would you like to use password authentication instead?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.Yes:
                            # Fall back to password authentication
                            if not account_data.get('password'):
                                QMessageBox.warning(
                                    self,
                                    "Password Required",
                                    "Please enter your password or app-specific password in the login window."
                                )
                                return
                            encrypted_token = self.encryption_manager.encrypt(account_data['password'])
                        else:
                            return
                    else:
                        oauth_handler = OAuth2Handler(provider)
                        token_json = oauth_handler.authenticate_outlook()
                        if not token_json:
                            QMessageBox.warning(self, "Authentication Failed", "OAuth2 authentication failed.")
                            return
                        encrypted_token = self.encryption_manager.encrypt(token_json)
                else:
                    # Other providers don't support OAuth2, use password
                    if not account_data.get('password'):
                        QMessageBox.warning(self, "Password Required", "Please enter your password.")
                        return
                    encrypted_token = self.encryption_manager.encrypt(account_data['password'])
            else:
                # Password-based authentication
                if not account_data.get('password'):
                    QMessageBox.warning(self, "Password Required", "Please enter your password.")
                    return
                encrypted_token = self.encryption_manager.encrypt(account_data['password'])
            
            # Create account object
            account = Account(
                email_address=account_data['email'],
                display_name=account_data['display_name'],
                provider=account_data['provider'],
                auth_type='oauth2' if account_data.get('use_oauth') else 'password',
                encrypted_token=encrypted_token,
                imap_server=account_data['imap_server'],
                imap_port=account_data['imap_port'],
                smtp_server=account_data['smtp_server'],
                smtp_port=account_data['smtp_port'],
                use_tls=account_data['use_tls']
            )
            
            # Add to database
            account_id = self.db_manager.add_account(account)
            account.account_id = account_id
            
            # Add to sidebar
            self.sidebar.add_account(account)
            
            # Sync folders
            self.sync_account_folders(account)
            
            # Select the newly added account
            self.on_account_selected(account.account_id)
            
            # Close login window if provided
            if login_window:
                login_window.accept()
            
            # Bring main window to front
            self.show()
            self.raise_()
            self.activateWindow()
            
            QMessageBox.information(self, "Success", "Account added successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add account: {str(e)}")
            # Re-enable login button on error
            if login_window:
                login_window.progress_bar.setVisible(False)
                login_window.login_button.setEnabled(True)
    
    def sync_account_folders(self, account: Account):
        """Sync folders for an account"""
        try:
            # Decrypt token
            encrypted_token = account.encrypted_token
            token = self.encryption_manager.decrypt(encrypted_token)
            
            # Connect to IMAP
            imap_client = IMAPClient(account.imap_server, account.imap_port, account.use_tls)
            if not imap_client.connect(account.email_address, token):
                return
            
            # Get folders
            folders = imap_client.list_folders()
            imap_client.disconnect()
            
            # Save folders to database
            for folder in folders:
                folder.account_id = account.account_id
                folder_id = self.db_manager.add_folder(folder)
                folder.folder_id = folder_id
            
            # Update sidebar
            db_folders = self.db_manager.get_folders(account.account_id)
            self.sidebar.set_folders(db_folders)
            
            # Auto-select inbox if available and this is the current account
            if self.current_account_id == account.account_id:
                for folder in db_folders:
                    if folder.folder_type == 'inbox':
                        self.sidebar.select_folder(folder.folder_id)
                        break
        except Exception as e:
            print(f"Error syncing folders: {e}")
    
    def on_account_selected(self, account_id: int):
        """Handle account selection"""
        self.current_account_id = account_id
        account = self.db_manager.get_account(account_id)
        if account:
            # Load folders for this account
            folders = self.db_manager.get_folders(account_id)
            self.sidebar.set_folders(folders)
            
            # Select inbox if available
            for folder in folders:
                if folder.folder_type == 'inbox':
                    self.sidebar.select_folder(folder.folder_id)
                    break
    
    def on_remove_account_menu_clicked(self):
        """Handle remove account from menu"""
        if not self.current_account_id:
            QMessageBox.warning(self, "No Account Selected", "Please select an account to remove.")
            return
        self.on_delete_account_requested(self.current_account_id)
    
    def on_delete_account_requested(self, account_id: int):
        """Handle account deletion request"""
        account = self.db_manager.get_account(account_id)
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
                # Delete account from database (cascades to folders and emails)
                self.db_manager.delete_account(account_id)
                
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
                accounts = self.db_manager.get_all_accounts()
                if accounts:
                    # Select first account if available
                    self.on_account_selected(accounts[0].account_id)
                else:
                    # No accounts left, show add account dialog
                    self.on_add_account_clicked()
                
                QMessageBox.information(self, "Account Removed", f"Account '{email_address}' has been removed successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove account: {str(e)}")
    
    def on_folder_selected(self, folder_id: int):
        """Handle folder selection"""
        self.current_folder_id = folder_id
        folder = self.db_manager.get_folder(folder_id)
        if folder:
            # Switch to list view
            self.right_stack.setCurrentIndex(0)
            
            # Load emails for this folder
            emails = self.db_manager.get_emails(folder_id, limit=100)
            self.email_list.set_emails(emails)
            
            # Sync in background if needed
            account = self.db_manager.get_account(folder.account_id)
            if account:
                self.sync_folder(account, folder)
    
    def sync_folder(self, account: Account, folder: Folder):
        """Sync emails for a folder"""
        if self.sync_thread and self.sync_thread.isRunning():
            return  # Already syncing
        
        self.status_bar.showMessage(f"Syncing {folder.name}...")
        self.sync_thread = SyncThread(account, folder, self.db_manager)
        self.sync_thread.sync_complete.connect(self.on_sync_complete)
        self.sync_thread.sync_error.connect(self.on_sync_error)
        self.sync_thread.start()
    
    def on_sync_complete(self, account_id: int, emails: list):
        """Handle sync completion"""
        self.status_bar.showMessage("Sync complete")
        if self.current_folder_id:
            # Reload emails
            folder_emails = self.db_manager.get_emails(self.current_folder_id, limit=100)
            self.email_list.set_emails(folder_emails)
    
    def on_sync_error(self, error_msg: str):
        """Handle sync error"""
        self.status_bar.showMessage(f"Sync error: {error_msg}")
        # Show error message to user if it's a critical error
        if "Could not parse command" in error_msg or "BAD" in error_msg:
            QMessageBox.warning(
                self,
                "Sync Error",
                f"Failed to sync folder. This might be due to folder name encoding issues.\n\nError: {error_msg}"
            )
    
    def auto_sync(self):
        """Auto-sync current folder"""
        if self.current_folder_id:
            folder = self.db_manager.get_folder(self.current_folder_id)
            if folder:
                account = self.db_manager.get_account(folder.account_id)
                if account:
                    self.sync_folder(account, folder)
    
    def on_email_selected(self, email_id: int):
        """Handle email selection"""
        email = self.db_manager.get_email(email_id)
        if email:
            # Mark as read
            if not email.is_read:
                self.db_manager.mark_email_read(email_id, True)
                email.is_read = True
            
            # Get attachments
            attachments = self.db_manager.get_attachments(email_id)
            
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
        
        account = self.db_manager.get_account(self.current_account_id)
        if not account:
            QMessageBox.warning(self, "No Account", "Account not found.")
            return
        
        compose_window = ComposeWindow(self, account_id=self.current_account_id, account_email=account.email_address)
        compose_window.email_sent.connect(self.handle_send_email)
        compose_window.draft_saved.connect(self.handle_save_draft)
        compose_window.exec_()
    
    def on_reply_clicked(self, email_id: int):
        """Handle reply button click"""
        email = self.db_manager.get_email(email_id)
        if email:
            account = self.db_manager.get_account(email.account_id)
            account_email = account.email_address if account else None
            compose_window = ComposeWindow(self, reply_to=email, account_id=email.account_id, account_email=account_email)
            compose_window.email_sent.connect(self.handle_send_email)
            compose_window.draft_saved.connect(self.handle_save_draft)
            compose_window.exec_()
    
    def on_forward_clicked(self, email_id: int):
        """Handle forward button click"""
        email = self.db_manager.get_email(email_id)
        if email:
            account = self.db_manager.get_account(email.account_id)
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
            self.db_manager.delete_email(email_id)
            # Reload emails
            if self.current_folder_id:
                emails = self.db_manager.get_emails(self.current_folder_id, limit=100)
                self.email_list.set_emails(emails)
            # Go back to list view
            self.on_back_to_list()
            self.email_preview.show_empty_state()
    
    def handle_save_draft(self, draft_data: dict):
        """Handle saving a draft email"""
        account_id = draft_data.get('account_id')
        if not account_id:
            QMessageBox.warning(self, "Error", "No account specified for draft.")
            return
        
        try:
            # Get or create drafts folder
            drafts_folder = self.db_manager.get_folder_by_type(account_id, 'drafts')
            if not drafts_folder:
                # Create drafts folder if it doesn't exist
                account = self.db_manager.get_account(account_id)
                if not account:
                    QMessageBox.warning(self, "Error", "Account not found.")
                    return
                
                drafts_folder = Folder(
                    account_id=account_id,
                    name="Drafts",
                    full_path="Drafts",
                    folder_type="drafts",
                    sync_enabled=True
                )
                drafts_folder.folder_id = self.db_manager.add_folder(drafts_folder)
                
                # Update sidebar to show new drafts folder
                if self.current_account_id == account_id:
                    folders = self.db_manager.get_folders(account_id)
                    self.sidebar.set_folders(folders)
            
            # Create email object for draft
            account = self.db_manager.get_account(account_id)
            recipients_str = ', '.join(draft_data.get('to', []))
            if draft_data.get('cc'):
                recipients_str += ', ' + ', '.join(draft_data.get('cc', []))
            
            draft_email = Email(
                account_id=account_id,
                folder_id=drafts_folder.folder_id,
                message_id="",  # Drafts don't have message_id yet
                uid=0,  # Drafts don't have UID yet
                sender=account.email_address if account else "",
                sender_name=account.display_name if account else "",
                recipients=recipients_str,
                subject=draft_data.get('subject', '(No Subject)'),
                body_text=draft_data.get('body_text', ''),
                body_html=draft_data.get('body_html', ''),
                timestamp=datetime.now(),
                is_read=True,  # Drafts are considered "read"
                has_attachments=len(draft_data.get('attachments', [])) > 0,
                cached=True
            )
            
            # Save draft to database
            email_id = self.db_manager.add_email(draft_email)
            
            # Save attachments if any
            if draft_data.get('attachments'):
                import config
                from pathlib import Path
                for attachment_path in draft_data['attachments']:
                    att_path = Path(attachment_path)
                    if att_path.exists():
                        # Copy attachment to attachments directory
                        import shutil
                        dest_path = config.ATTACHMENTS_DIR / f"{email_id}_{att_path.name}"
                        shutil.copy2(att_path, dest_path)
                        
                        attachment = Attachment(
                            email_id=email_id,
                            filename=att_path.name,
                            file_path=str(dest_path),
                            file_size=att_path.stat().st_size,
                            mime_type="application/octet-stream"
                        )
                        self.db_manager.add_attachment(attachment)
            
            # Refresh drafts folder if it's currently selected
            if self.current_folder_id == drafts_folder.folder_id:
                emails = self.db_manager.get_emails(drafts_folder.folder_id, limit=100)
                self.email_list.set_emails(emails)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving draft: {str(e)}")
    
    def handle_send_email(self, email_data: dict):
        """Handle sending an email"""
        if not self.current_account_id:
            QMessageBox.warning(self, "No Account", "No account selected. Please select an account first.")
            return
        
        account = self.db_manager.get_account(self.current_account_id)
        if not account:
            QMessageBox.warning(self, "No Account", "Account not found.")
            return
        
        try:
            # Decrypt token/password
            encrypted_token = account.encrypted_token
            token = self.encryption_manager.decrypt(encrypted_token)
            
            # Connect to SMTP
            smtp_client = SMTPClient(account.smtp_server, account.smtp_port, account.use_tls)
            success, error_msg = smtp_client.connect(account.email_address, token)
            if not success:
                detailed_msg = f"Failed to connect to SMTP server ({account.smtp_server}:{account.smtp_port}).\n\n{error_msg}"
                if account.provider == 'gmail':
                    detailed_msg += "\n\nFor Gmail:\n"
                    detailed_msg += "• Use port 587 with TLS, or port 465 with SSL\n"
                    detailed_msg += "• Make sure you're using an App Password (not your regular password)\n"
                    detailed_msg += "• Enable 2-Step Verification in your Google Account\n"
                    detailed_msg += "• Generate App Password at: https://myaccount.google.com/apppasswords"
                QMessageBox.critical(self, "Send Failed", detailed_msg)
                return
            
            # Send email
            success = smtp_client.send_email(
                from_addr=account.email_address,
                to_addrs=email_data['to'],
                subject=email_data['subject'],
                body_html=email_data.get('body_html', ''),
                body_text=email_data.get('body_text', ''),
                cc_addrs=email_data.get('cc', []),
                bcc_addrs=email_data.get('bcc', []),
                attachments=email_data.get('attachments', [])
            )
            
            smtp_client.disconnect()
            
            if success:
                QMessageBox.information(self, "Success", f"Email sent successfully from {account.email_address}!")
            else:
                QMessageBox.critical(self, "Send Failed", "Failed to send email.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error sending email: {str(e)}")
    
    def on_refresh_clicked(self):
        """Handle refresh button click"""
        if self.current_folder_id:
            folder = self.db_manager.get_folder(self.current_folder_id)
            if folder:
                account = self.db_manager.get_account(folder.account_id)
                if account:
                    self.sync_folder(account, folder)
    
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

