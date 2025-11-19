"""
Email list component
"""
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                             QHeaderView, QLineEdit, QHBoxLayout, QPushButton, QComboBox,
                             QLabel)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from database.models import Email
from utils.helpers import format_date, truncate_text


class EmailList(QWidget):
    """Email list widget with search and filter"""
    
    email_selected = pyqtSignal(int)  # email_id
    refresh_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.emails = {}  # email_id -> Email
    
    def setup_ui(self):
        """Setup the UI"""
        # Modern dark theme styling
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #cccccc;
            }
            QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px 12px;
                color: #cccccc;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #0e639c;
                background-color: #404040;
            }
            QComboBox {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                color: #cccccc;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #666666;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #cccccc;
                margin-right: 8px;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
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
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Search and filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search emails...")
        self.search_input.textChanged.connect(self.on_search_changed)
        filter_layout.addWidget(self.search_input, 3)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Unread Only", "Read Only"])
        self.filter_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_combo, 1)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        filter_layout.addWidget(refresh_btn)
        
        layout.addLayout(filter_layout)
        
        # Email table
        self.email_table = QTableWidget()
        self.email_table.setColumnCount(4)
        self.email_table.setHorizontalHeaderLabels(["Sender", "Subject", "Date", "Status"])
        
        # Modern table styling
        self.email_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                gridline-color: #2d2d2d;
                color: #cccccc;
                font-size: 13px;
                selection-background-color: #094771;
            }
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            QTableWidget::item:hover {
                background-color: #2a2d2e;
            }
            QTableWidget::item:selected {
                background-color: #094771;
                color: white;
            }
            QHeaderView::section {
                background-color: #252526;
                color: #858585;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #3e3e42;
                font-weight: 600;
                font-size: 12px;
                text-transform: uppercase;
            }
        """)
        
        # Configure table
        header = self.email_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setDefaultSectionSize(150)
        
        self.email_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.email_table.setSelectionMode(QTableWidget.SingleSelection)
        self.email_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.email_table.setAlternatingRowColors(False)
        self.email_table.verticalHeader().setVisible(False)
        self.email_table.itemDoubleClicked.connect(self.on_email_double_clicked)
        self.email_table.itemClicked.connect(self.on_email_clicked)
        
        layout.addWidget(self.email_table)
        self.setLayout(layout)
    
    def set_emails(self, emails: list[Email]):
        """Set emails to display"""
        self.emails = {email.email_id: email for email in emails}
        self.update_table()
    
    def add_email(self, email: Email):
        """Add a single email to the list"""
        self.emails[email.email_id] = email
        self.update_table()
    
    def clear_emails(self):
        """Clear all emails"""
        self.email_table.setRowCount(0)
        self.emails.clear()
    
    def update_table(self):
        """Update the table with current emails"""
        self.email_table.setRowCount(0)
        
        # Apply filter
        filter_text = self.filter_combo.currentText()
        filtered_emails = list(self.emails.values())
        
        if filter_text == "Unread Only":
            filtered_emails = [e for e in filtered_emails if not e.is_read]
        elif filter_text == "Read Only":
            filtered_emails = [e for e in filtered_emails if e.is_read]
        
        # Apply search
        search_text = self.search_input.text().lower()
        if search_text:
            filtered_emails = [
                e for e in filtered_emails
                if search_text in e.subject.lower() or
                   search_text in e.sender.lower() or
                   search_text in e.sender_name.lower() or
                   search_text in e.body_text.lower()
            ]
        
        # Sort by timestamp (most recent first)
        filtered_emails.sort(key=lambda x: x.timestamp or datetime.min, reverse=True)
        
        # Populate table
        for email in filtered_emails:
            row = self.email_table.rowCount()
            self.email_table.insertRow(row)
            
            # Sender
            sender_text = email.sender_name or email.sender
            sender_item = QTableWidgetItem(truncate_text(sender_text, 30))
            sender_item.setData(Qt.UserRole, email.email_id)
            if not email.is_read:
                font = QFont()
                font.setBold(True)
                sender_item.setFont(font)
            self.email_table.setItem(row, 0, sender_item)
            
            # Subject
            subject_item = QTableWidgetItem(truncate_text(email.subject or "(No Subject)", 60))
            subject_item.setData(Qt.UserRole, email.email_id)
            if not email.is_read:
                font = QFont()
                font.setBold(True)
                subject_item.setFont(font)
            self.email_table.setItem(row, 1, subject_item)
            
            # Date
            date_text = format_date(email.timestamp) if email.timestamp else ""
            date_item = QTableWidgetItem(date_text)
            date_item.setData(Qt.UserRole, email.email_id)
            self.email_table.setItem(row, 2, date_item)
            
            # Status
            status_text = "📎" if email.has_attachments else ""
            if not email.is_read:
                status_text = "● " + status_text
            status_item = QTableWidgetItem(status_text)
            status_item.setData(Qt.UserRole, email.email_id)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.email_table.setItem(row, 3, status_item)
    
    def on_email_clicked(self, item: QTableWidgetItem):
        """Handle email row click"""
        email_id = item.data(Qt.UserRole)
        if email_id:
            self.email_selected.emit(email_id)
    
    def on_email_double_clicked(self, item: QTableWidgetItem):
        """Handle email double-click"""
        email_id = item.data(Qt.UserRole)
        if email_id:
            self.email_selected.emit(email_id)
    
    def on_search_changed(self, text: str):
        """Handle search text change"""
        self.update_table()
    
    def on_filter_changed(self, text: str):
        """Handle filter change"""
        self.update_table()
    
    def get_selected_email_id(self) -> int:
        """Get currently selected email ID"""
        current_row = self.email_table.currentRow()
        if current_row >= 0:
            item = self.email_table.item(current_row, 0)
            if item:
                return item.data(Qt.UserRole)
        return None

