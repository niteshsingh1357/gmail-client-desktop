"""
Email preview component
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                             QPushButton, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from database.models import Email, Attachment
from utils.helpers import format_date, format_file_size
from pathlib import Path


class EmailPreview(QWidget):
    """Email preview widget"""
    
    reply_clicked = pyqtSignal(int)  # email_id
    forward_clicked = pyqtSignal(int)  # email_id
    delete_clicked = pyqtSignal(int)  # email_id
    attachment_clicked = pyqtSignal(str)  # file_path
    back_clicked = pyqtSignal()  # back button clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.current_email: Email = None
    
    def setup_ui(self):
        """Setup the UI"""
        # Modern dark theme styling
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #cccccc;
            }
            QFrame {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 6px;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #464647;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                color: #cccccc;
                font-size: 14px;
                padding: 12px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Back button and navigation bar
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)
        
        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #464647;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """)
        self.back_btn.clicked.connect(self.back_clicked.emit)
        nav_layout.addWidget(self.back_btn)
        nav_layout.addStretch()
        
        layout.addLayout(nav_layout)
        
        # Header section - more compact
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 10px 12px;
            }
        """)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Subject
        self.subject_label = QLabel()
        self.subject_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: 600;
                padding-bottom: 4px;
            }
        """)
        header_layout.addWidget(self.subject_label)
        
        # From, To, Date - more compact
        self.from_label = QLabel()
        self.from_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 12px;
                padding: 2px 0px;
            }
        """)
        header_layout.addWidget(self.from_label)
        
        self.to_label = QLabel()
        self.to_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 12px;
                padding: 2px 0px;
            }
        """)
        header_layout.addWidget(self.to_label)
        
        self.date_label = QLabel()
        self.date_label.setStyleSheet("""
            QLabel {
                color: #858585;
                font-size: 11px;
                padding: 2px 0px;
            }
        """)
        header_layout.addWidget(self.date_label)
        
        header_frame.setLayout(header_layout)
        layout.addWidget(header_frame)
        
        # Action buttons - compact with proper icon sizing
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.reply_btn = QPushButton("Reply")
        self.reply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #0a4d73;
            }
        """)
        self.reply_btn.clicked.connect(self.on_reply)
        button_layout.addWidget(self.reply_btn)
        
        self.forward_btn = QPushButton("Forward")
        self.forward_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #464647;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """)
        self.forward_btn.clicked.connect(self.on_forward)
        button_layout.addWidget(self.forward_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #a1260d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c42d1a;
            }
            QPushButton:pressed {
                background-color: #7d1d0a;
            }
        """)
        self.delete_btn.clicked.connect(self.on_delete)
        button_layout.addWidget(self.delete_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Attachments section
        self.attachments_label = QLabel("📎 Attachments:")
        self.attachments_label.setStyleSheet("""
            QLabel {
                color: #858585;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 4px 0px;
            }
        """)
        self.attachments_label.setVisible(False)
        layout.addWidget(self.attachments_label)
        
        self.attachments_layout = QVBoxLayout()
        self.attachments_layout.setSpacing(8)
        self.attachments_widget = QWidget()
        self.attachments_widget.setLayout(self.attachments_layout)
        self.attachments_widget.setVisible(False)
        layout.addWidget(self.attachments_widget)
        
        # Email body
        self.body_text = QTextEdit()
        self.body_text.setReadOnly(True)
        self.body_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                color: #cccccc;
                font-size: 14px;
                padding: 16px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.body_text)
        
        # Empty state
        self.empty_label = QLabel("Select an email to view")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("""
            QLabel {
                color: #858585;
                font-size: 16px;
                padding: 40px;
            }
        """)
        layout.addWidget(self.empty_label)
        
        self.setLayout(layout)
        self.show_empty_state()
    
    def show_email(self, email: Email, attachments: list[Attachment] = None):
        """Display an email"""
        self.current_email = email
        self.empty_label.setVisible(False)
        self.body_text.setVisible(True)
        self.reply_btn.setVisible(True)
        self.forward_btn.setVisible(True)
        self.delete_btn.setVisible(True)
        self.back_btn.setVisible(True)
        
        # Set header information
        self.subject_label.setText(email.subject or "(No Subject)")
        self.from_label.setText(f"From: {email.sender_name or email.sender} <{email.sender}>")
        self.to_label.setText(f"To: {email.recipients}")
        self.date_label.setText(f"Date: {format_date(email.timestamp) if email.timestamp else 'Unknown'}")
        
        # Set body
        if email.body_html:
            self.body_text.setHtml(email.body_html)
        elif email.body_text:
            self.body_text.setPlainText(email.body_text)
        else:
            self.body_text.setPlainText("(No content)")
        
        # Show attachments
        if attachments and len(attachments) > 0:
            self.attachments_label.setVisible(True)
            self.attachments_widget.setVisible(True)
            
            # Clear existing attachment widgets
            while self.attachments_layout.count():
                child = self.attachments_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # Add attachment widgets
            for attachment in attachments:
                att_layout = QHBoxLayout()
                att_label = QLabel(f"📎 {attachment.filename} ({format_file_size(attachment.file_size)})")
                att_btn = QPushButton("Open")
                att_btn.clicked.connect(lambda checked, path=attachment.file_path: self.attachment_clicked.emit(path))
                att_layout.addWidget(att_label)
                att_layout.addWidget(att_btn)
                att_layout.addStretch()
                
                att_widget = QWidget()
                att_widget.setLayout(att_layout)
                self.attachments_layout.addWidget(att_widget)
        else:
            self.attachments_label.setVisible(False)
            self.attachments_widget.setVisible(False)
    
    def show_empty_state(self):
        """Show empty state when no email is selected"""
        self.current_email = None
        self.empty_label.setVisible(True)
        self.body_text.setVisible(False)
        self.reply_btn.setVisible(False)
        self.forward_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        self.attachments_label.setVisible(False)
        self.attachments_widget.setVisible(False)
        self.back_btn.setVisible(False)
        
        self.subject_label.clear()
        self.from_label.clear()
        self.to_label.clear()
        self.date_label.clear()
        self.body_text.clear()
    
    def on_reply(self):
        """Handle reply button click"""
        if self.current_email:
            self.reply_clicked.emit(self.current_email.email_id)
    
    def on_forward(self):
        """Handle forward button click"""
        if self.current_email:
            self.forward_clicked.emit(self.current_email.email_id)
    
    def on_delete(self):
        """Handle delete button click"""
        if self.current_email:
            self.delete_clicked.emit(self.current_email.email_id)

