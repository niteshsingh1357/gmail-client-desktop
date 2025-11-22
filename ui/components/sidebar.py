"""
Sidebar navigation component
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
                             QLabel, QPushButton, QHBoxLayout, QMenu)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from database.models import Account, Folder


class Sidebar(QWidget):
    """Sidebar navigation widget"""
    
    folder_selected = pyqtSignal(int)  # folder_id
    account_selected = pyqtSignal(int)  # account_id
    account_delete_requested = pyqtSignal(int)  # account_id
    compose_clicked = pyqtSignal()
    add_account_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.folders = {}  # folder_id -> Folder
        self.accounts = {}  # account_id -> Account
        self.current_folder_id = None
        self.current_account_id = None
    
    def setup_ui(self):
        """Setup the UI"""
        # Modern dark theme styling
        self.setStyleSheet("""
            QWidget {
                background-color: #252526;
                color: #cccccc;
            }
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #0a4d73;
            }
            QLabel {
                color: #858585;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QListWidget {
                background-color: #252526;
                border: none;
                outline: none;
                color: #cccccc;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 4px;
                margin: 2px 4px;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: white;
            }
            QListWidget::item:selected:hover {
                background-color: #0e639c;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Compose button
        compose_btn = QPushButton("Compose")
        compose_btn.setMinimumHeight(44)
        compose_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #0a4d73;
            }
        """)
        compose_btn.clicked.connect(self.compose_clicked.emit)
        layout.addWidget(compose_btn)
        
        # Folders section
        folders_label = QLabel("Folders")
        folders_label.setStyleSheet("""
            QLabel {
                color: #858585;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 8px 4px 4px 4px;
            }
        """)
        layout.addWidget(folders_label)
        
        self.folder_list = QListWidget()
        self.folder_list.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                border: none;
                outline: none;
                color: #cccccc;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 6px;
                margin: 2px 0px;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: white;
            }
            QListWidget::item:selected:hover {
                background-color: #0e639c;
            }
        """)
        self.folder_list.itemClicked.connect(self.on_folder_clicked)
        layout.addWidget(self.folder_list)
        
        # Accounts section
        accounts_label = QLabel("Accounts")
        accounts_label.setStyleSheet("""
            QLabel {
                color: #858585;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 8px 4px 4px 4px;
            }
        """)
        layout.addWidget(accounts_label)
        
        self.account_list = QListWidget()
        self.account_list.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                border: none;
                outline: none;
                color: #cccccc;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 6px;
                margin: 2px 0px;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: white;
            }
            QListWidget::item:selected:hover {
                background-color: #0e639c;
            }
        """)
        self.account_list.itemClicked.connect(self.on_account_clicked)
        self.account_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.account_list.customContextMenuRequested.connect(self.on_account_context_menu)
        layout.addWidget(self.account_list)
        
        # Add account button
        add_account_btn = QPushButton("+ Add Account")
        add_account_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #464647;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """)
        add_account_btn.clicked.connect(self.add_account_clicked.emit)
        layout.addWidget(add_account_btn)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def add_folder(self, folder: Folder):
        """Add a folder to the sidebar"""
        self.folders[folder.folder_id] = folder
        
        item = QListWidgetItem()
        item.setText(folder.name)
        item.setData(Qt.UserRole, folder.folder_id)
        
        # Set icon based on folder type
        if folder.folder_type == 'inbox':
            item.setText(f"📥 {folder.name}")
        elif folder.folder_type == 'sent':
            item.setText(f"📤 {folder.name}")
        elif folder.folder_type == 'drafts':
            item.setText(f"📝 {folder.name}")
        elif folder.folder_type == 'trash':
            item.setText(f"🗑 {folder.name}")
        else:
            item.setText(f"📁 {folder.name}")
        
        self.folder_list.addItem(item)
    
    def clear_folders(self):
        """Clear all folders"""
        self.folder_list.clear()
        self.folders.clear()
    
    def set_folders(self, folders: list[Folder]):
        """Set folders (replaces existing)"""
        self.clear_folders()
        for folder in folders:
            self.add_folder(folder)
    
    def add_account(self, account: Account):
        """Add an account to the sidebar"""
        self.accounts[account.account_id] = account
        
        item = QListWidgetItem()
        display_text = account.display_name or account.email_address
        item.setText(f"👤 {display_text}")
        item.setData(Qt.UserRole, account.account_id)
        self.account_list.addItem(item)
    
    def clear_accounts(self):
        """Clear all accounts"""
        self.account_list.clear()
        self.accounts.clear()
    
    def set_accounts(self, accounts: list[Account]):
        """Set accounts (replaces existing)"""
        self.clear_accounts()
        for account in accounts:
            self.add_account(account)
    
    def on_folder_clicked(self, item: QListWidgetItem):
        """Handle folder selection"""
        folder_id = item.data(Qt.UserRole)
        self.current_folder_id = folder_id
        
        # Update selection
        for i in range(self.folder_list.count()):
            self.folder_list.item(i).setSelected(False)
        item.setSelected(True)
        
        self.folder_selected.emit(folder_id)
    
    def on_account_clicked(self, item: QListWidgetItem):
        """Handle account selection"""
        account_id = item.data(Qt.UserRole)
        self.current_account_id = account_id
        
        # Update selection
        for i in range(self.account_list.count()):
            self.account_list.item(i).setSelected(False)
        item.setSelected(True)
        
        self.account_selected.emit(account_id)
    
    def select_folder(self, folder_id: int):
        """Programmatically select a folder"""
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            if item.data(Qt.UserRole) == folder_id:
                self.folder_list.setCurrentItem(item)
                self.on_folder_clicked(item)
                break
    
    def on_account_context_menu(self, position):
        """Show context menu for account"""
        item = self.account_list.itemAt(position)
        if item:
            account_id = item.data(Qt.UserRole)
            if account_id:
                menu = QMenu(self)
                delete_action = menu.addAction("🗑 Remove Account")
                delete_action.triggered.connect(lambda: self.account_delete_requested.emit(account_id))
                menu.exec_(self.account_list.mapToGlobal(position))
    
    def remove_account(self, account_id: int):
        """Remove an account from the sidebar"""
        for i in range(self.account_list.count()):
            item = self.account_list.item(i)
            if item.data(Qt.UserRole) == account_id:
                self.account_list.takeItem(i)
                if account_id in self.accounts:
                    del self.accounts[account_id]
                break

