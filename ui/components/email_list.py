"""
Email list component
"""
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                             QHeaderView, QLineEdit, QHBoxLayout, QPushButton, QComboBox,
                             QLabel, QCheckBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from email_client.models import EmailMessage
from utils.helpers import format_date, truncate_text


class EmailList(QWidget):
    """Email list widget with search and filter"""
    
    email_selected = pyqtSignal(int)  # email_id
    refresh_requested = pyqtSignal()
    page_changed = pyqtSignal(int)  # page number (0-based)
    bulk_selection_changed = pyqtSignal(list)  # list of selected email_ids
    bulk_delete_requested = pyqtSignal(list)  # list of selected email_ids
    bulk_move_requested = pyqtSignal(list)  # list of selected email_ids
    
    PAGE_SIZE = 50  # Fixed page size
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.emails = {}  # email_id -> Email
        self.current_page = 0
        self.total_count = 0
        self.folder_id = None
        self.selected_email_ids = set()  # Track selected email IDs
    
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
        
        # Bulk action buttons (initially hidden)
        bulk_actions_layout = QHBoxLayout()
        bulk_actions_layout.setContentsMargins(0, 0, 0, 0)
        bulk_actions_layout.setSpacing(8)
        bulk_actions_layout.addStretch()
        
        self.bulk_actions_widget = QWidget()
        self.bulk_actions_widget.setVisible(False)
        
        self.bulk_delete_btn = QPushButton("🗑 Delete")
        self.bulk_delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #c9302c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #d9534f;
            }
            QPushButton:pressed {
                background-color: #ac2925;
            }
        """)
        self.bulk_delete_btn.clicked.connect(self.on_bulk_delete_clicked)
        bulk_actions_layout.addWidget(self.bulk_delete_btn)
        
        self.bulk_move_btn = QPushButton("📁 Move")
        self.bulk_move_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #0a4d73;
            }
        """)
        self.bulk_move_btn.clicked.connect(self.on_bulk_move_clicked)
        bulk_actions_layout.addWidget(self.bulk_move_btn)
        
        self.bulk_actions_widget.setLayout(bulk_actions_layout)
        layout.addWidget(self.bulk_actions_widget)
        
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
        self.email_table.setColumnCount(5)
        self.email_table.setHorizontalHeaderLabels(["", "Sender", "Subject", "Date", "Status"])
        
        # Create select all checkbox for header (will be positioned in header)
        self.select_all_checkbox = QCheckBox()
        self.select_all_checkbox.stateChanged.connect(self.on_select_all_changed)
        self.select_all_checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #555555;
                border-radius: 4px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:hover {
                border-color: #0e639c;
                background-color: #3c3c3c;
            }
            QCheckBox::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QCheckBox::indicator:indeterminate {
                background-color: #0e639c;
                border-color: #0e639c;
            }
        """)
        
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
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Checkbox column
        header.resizeSection(0, 30)  # Reduced width for checkbox column
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setDefaultSectionSize(150)
        
        # Ensure all columns are visible
        for i in range(5):
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
        
        # Position checkbox in header after widget is shown
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self._position_header_checkbox)
    
    def showEvent(self, event):
        """Override showEvent to position checkbox when widget becomes visible"""
        super().showEvent(event)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, self._position_header_checkbox)
    
    def resizeEvent(self, event):
        """Override resizeEvent to reposition checkbox on resize"""
        super().resizeEvent(event)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(10, self._position_header_checkbox)
    
    def _position_header_checkbox(self):
        """Position checkbox in header's first column"""
        from PyQt5.QtCore import QTimer
        try:
            header = self.email_table.horizontalHeader()
            if header and self.email_table.isVisible():
                # Calculate position relative to EmailList widget
                table_rect = self.email_table.geometry()
                header_height = header.height()
                
                # Position at start of first column, centered vertically in header
                checkbox_x = table_rect.x() + 6  # 6px padding from left
                checkbox_y = table_rect.y() + max(0, (header_height - 18) // 2)
                
                # Ensure checkbox is parented and visible
                if self.select_all_checkbox.parent() != self:
                    self.select_all_checkbox.setParent(self)
                
                self.select_all_checkbox.move(checkbox_x, checkbox_y)
                self.select_all_checkbox.setVisible(True)
                self.select_all_checkbox.show()
                self.select_all_checkbox.raise_()
                
                # Connect resize handlers only once
                if not hasattr(self, '_header_resize_connected'):
                    def reposition():
                        QTimer.singleShot(10, self._position_header_checkbox)
                    
                    header.sectionResized.connect(reposition)
                    self._header_resize_connected = True
        except Exception:
            # Silently fail if positioning doesn't work
            pass
    
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
        self.selected_email_ids.clear()
        self.select_all_checkbox.setCheckState(Qt.Unchecked)
        self.update_bulk_actions_visibility()
    
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
            
            # Checkbox
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout()
            checkbox_layout.setContentsMargins(8, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox = QCheckBox()
            checkbox.setChecked(email.id in self.selected_email_ids)
            checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 2px solid #555555;
                    border-radius: 4px;
                    background-color: #2d2d2d;
                }
                QCheckBox::indicator:hover {
                    border-color: #0e639c;
                    background-color: #3c3c3c;
                }
                QCheckBox::indicator:checked {
                    background-color: #0e639c;
                    border-color: #0e639c;
                }
            """)
            checkbox.stateChanged.connect(lambda state, email_id=email.id: self.on_checkbox_changed(email_id, state))
            checkbox_layout.addWidget(checkbox)
            checkbox_widget.setLayout(checkbox_layout)
            self.email_table.setCellWidget(row, 0, checkbox_widget)
            
            # Sender
            sender_text = email.sender or ""
            sender_item = QTableWidgetItem(truncate_text(sender_text, 30))
            sender_item.setData(Qt.UserRole, email.id)
            if not email.is_read:
                font = QFont()
                font.setBold(True)
                sender_item.setFont(font)
            self.email_table.setItem(row, 1, sender_item)
            
            # Subject
            subject_item = QTableWidgetItem(truncate_text(email.subject or "(No Subject)", 60))
            subject_item.setData(Qt.UserRole, email.id)
            if not email.is_read:
                font = QFont()
                font.setBold(True)
                subject_item.setFont(font)
            self.email_table.setItem(row, 2, subject_item)
            
            # Date
            date_text = format_date(email.received_at) if email.received_at else ""
            date_item = QTableWidgetItem(date_text)
            date_item.setData(Qt.UserRole, email.id)
            self.email_table.setItem(row, 3, date_item)
            
            # Status
            status_text = "📎" if email.has_attachments else ""
            if not email.is_read:
                status_text = "● " + status_text
            status_item = QTableWidgetItem(status_text)
            status_item.setData(Qt.UserRole, email.id)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.email_table.setItem(row, 4, status_item)
    
    def on_email_clicked(self, item: QTableWidgetItem):
        """Handle email row click (skip checkbox column)"""
        # Skip clicks on checkbox column (column 0)
        if item.column() == 0:
            return
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
            item = self.email_table.item(current_row, 1)  # Changed from 0 to 1 (checkbox is now column 0)
            if item:
                return item.data(Qt.UserRole)
        return None
    
    def get_selected_email_ids(self) -> list:
        """Get list of all selected email IDs (from checkboxes)"""
        return list(self.selected_email_ids)
    
    def on_checkbox_changed(self, email_id: int, state: int):
        """Handle checkbox state change"""
        if state == Qt.Checked:
            self.selected_email_ids.add(email_id)
        else:
            self.selected_email_ids.discard(email_id)
        
        # Update select all checkbox state
        self.update_select_all_checkbox()
        
        # Update bulk action buttons visibility
        self.update_bulk_actions_visibility()
        
        # Emit signal with selected email IDs
        self.bulk_selection_changed.emit(self.get_selected_email_ids())
    
    def update_bulk_actions_visibility(self):
        """Show/hide bulk action buttons based on selection"""
        has_selection = len(self.selected_email_ids) > 0
        self.bulk_actions_widget.setVisible(has_selection)
    
    def on_bulk_delete_clicked(self):
        """Handle bulk delete button click"""
        selected_ids = self.get_selected_email_ids()
        if selected_ids:
            self.bulk_delete_requested.emit(selected_ids)
    
    def on_bulk_move_clicked(self):
        """Handle bulk move button click"""
        selected_ids = self.get_selected_email_ids()
        if selected_ids:
            self.bulk_move_requested.emit(selected_ids)
    
    def on_select_all_changed(self, state: int):
        """Handle select all checkbox change"""
        # Temporarily block signals to prevent individual checkbox updates
        select_all = (state == Qt.Checked)
        
        # Update all checkboxes in the table
        for row in range(self.email_table.rowCount()):
            checkbox_widget = self.email_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    # Block signals to prevent triggering individual checkbox handlers
                    checkbox.blockSignals(True)
                    checkbox.setChecked(select_all)
                    checkbox.blockSignals(False)
                    
                    # Get email ID from the row
                    item = self.email_table.item(row, 1)
                    if item:
                        email_id = item.data(Qt.UserRole)
                        if select_all:
                            self.selected_email_ids.add(email_id)
                        else:
                            self.selected_email_ids.discard(email_id)
        
        # Update bulk action buttons visibility
        self.update_bulk_actions_visibility()
        
        # Emit signal with selected email IDs
        self.bulk_selection_changed.emit(self.get_selected_email_ids())
    
    def update_select_all_checkbox(self):
        """Update select all checkbox state based on current selection"""
        total_emails = self.email_table.rowCount()
        if total_emails == 0:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
            return
        
        # Count selected emails in current view
        selected_count = sum(
            1 for row in range(total_emails)
            for item in [self.email_table.item(row, 1)]
            if item and item.data(Qt.UserRole) in self.selected_email_ids
        )
        
        if selected_count == 0:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
        elif selected_count == total_emails:
            self.select_all_checkbox.setCheckState(Qt.Checked)
        else:
            self.select_all_checkbox.setCheckState(Qt.PartiallyChecked)
    
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

