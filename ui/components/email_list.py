"""
Email list component
"""
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                             QHeaderView, QLineEdit, QHBoxLayout, QPushButton, QComboBox,
                             QLabel)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from email_client.models import EmailMessage
from utils.helpers import format_date, truncate_text


class EmailList(QWidget):
    """Email list widget with search and filter"""
    
    email_selected = pyqtSignal(int)  # email_id
    refresh_requested = pyqtSignal()
    page_changed = pyqtSignal(int)  # page number (0-based)
    
    PAGE_SIZE = 50  # Fixed page size
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.emails = {}  # email_id -> Email
        self.current_page = 0
        self.total_count = 0
        self.folder_id = None
    
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
        
        # Pagination controls
        pagination_layout = QHBoxLayout()
        pagination_layout.setSpacing(8)
        
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self.go_to_previous_page)
        self.prev_btn.setEnabled(False)
        pagination_layout.addWidget(self.prev_btn)
        
        self.page_info_label = QLabel("Page 1 of 1")
        self.page_info_label.setAlignment(Qt.AlignCenter)
        pagination_layout.addWidget(self.page_info_label, 1)
        
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.go_to_next_page)
        self.next_btn.setEnabled(False)
        pagination_layout.addWidget(self.next_btn)
        
        layout.addLayout(pagination_layout)
        
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
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Sender
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Subject
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Date
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Status
        header.setDefaultSectionSize(150)
        
        # Ensure all columns are visible
        for i in range(4):
            header.setSectionHidden(i, False)
        
        self.email_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.email_table.setSelectionMode(QTableWidget.SingleSelection)
        self.email_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.email_table.setAlternatingRowColors(False)
        self.email_table.verticalHeader().setVisible(False)
        self.email_table.itemDoubleClicked.connect(self.on_email_double_clicked)
        self.email_table.itemClicked.connect(self.on_email_clicked)
        
        layout.addWidget(self.email_table)
        self.setLayout(layout)
    
    def set_emails(self, emails: list[EmailMessage], total_count: int = 0, current_page: int = 0, folder_id: int = None):
        """Set emails to display with pagination info"""
        self.emails = {email.id: email for email in emails}
        self.total_count = total_count
        self.current_page = current_page
        if folder_id is not None:
            self.folder_id = folder_id
        self.update_table()
        self.update_pagination_controls()
    
    def add_email(self, email: EmailMessage):
        """Add a single email to the list"""
        self.emails[email.id] = email
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
                if search_text in (e.subject or "").lower() or
                   search_text in (e.sender or "").lower() or
                   search_text in (e.preview_text or "").lower() or
                   search_text in (e.body_plain or "").lower()
            ]
        
        # Sort by received_at (most recent first)
        filtered_emails.sort(key=lambda x: x.received_at or datetime.min, reverse=True)
        
        # Populate table
        for email in filtered_emails:
            row = self.email_table.rowCount()
            self.email_table.insertRow(row)
            
            # Sender
            sender_text = email.sender or ""
            sender_item = QTableWidgetItem(truncate_text(sender_text, 30))
            sender_item.setData(Qt.UserRole, email.id)
            if not email.is_read:
                font = QFont()
                font.setBold(True)
                sender_item.setFont(font)
            self.email_table.setItem(row, 0, sender_item)
            
            # Subject
            subject_item = QTableWidgetItem(truncate_text(email.subject or "(No Subject)", 60))
            subject_item.setData(Qt.UserRole, email.id)
            if not email.is_read:
                font = QFont()
                font.setBold(True)
                subject_item.setFont(font)
            self.email_table.setItem(row, 1, subject_item)
            
            # Date
            date_text = format_date(email.received_at) if email.received_at else ""
            date_item = QTableWidgetItem(date_text)
            date_item.setData(Qt.UserRole, email.id)
            self.email_table.setItem(row, 2, date_item)
            
            # Status
            status_text = "📎" if email.has_attachments else ""
            if not email.is_read:
                status_text = "● " + status_text
            status_item = QTableWidgetItem(status_text)
            status_item.setData(Qt.UserRole, email.id)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.email_table.setItem(row, 3, status_item)
    
    def on_email_clicked(self, item: QTableWidgetItem):
        """Handle email row click"""
        email_id = item.data(Qt.UserRole)
        if email_id:
            self.email_selected.emit(email_id)
    
    def on_email_double_clicked(self, item: QTableWidgetItem):
        """Handle email double-click"""
        message_id = item.data(Qt.UserRole)
        if message_id:
            self.email_selected.emit(message_id)
    
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
            item = self.email_table.item(current_row, 0)  # Sender column
            if item:
                return item.data(Qt.UserRole)
        return None
    
    
    def update_pagination_controls(self):
        """Update pagination button states and page info"""
        total_pages = (self.total_count + self.PAGE_SIZE - 1) // self.PAGE_SIZE if self.total_count > 0 else 1
        current_page_num = self.current_page + 1  # Display as 1-based
        
        # Update page info
        if self.total_count > 0:
            start = self.current_page * self.PAGE_SIZE + 1
            end = min((self.current_page + 1) * self.PAGE_SIZE, self.total_count)
            self.page_info_label.setText(f"Page {current_page_num} of {total_pages} ({start}-{end} of {self.total_count})")
        else:
            self.page_info_label.setText("No emails")
        
        # Update button states
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)
    
    def go_to_previous_page(self):
        """Navigate to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.page_changed.emit(self.current_page)
    
    def go_to_next_page(self):
        """Navigate to next page"""
        total_pages = (self.total_count + self.PAGE_SIZE - 1) // self.PAGE_SIZE if self.total_count > 0 else 1
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.page_changed.emit(self.current_page)

    def set_email_read_state(self, email_id: int, is_read: bool) -> None:
        """Update read/unread state for a single email in the list and refresh UI."""
        email = self.emails.get(email_id)
        if email:
            email.is_read = is_read
            self.update_table()

