"""
Email preview component
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                             QPushButton, QScrollArea, QFrame, QMenu, QToolButton, QTextBrowser)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from email_client.models import EmailMessage, Attachment
from utils.helpers import format_file_size
from pathlib import Path
from datetime import datetime


def format_date_time(date_obj) -> str:
    """Format date and time for display - always shows date and time"""
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
        except:
            return date_obj
    
    if not isinstance(date_obj, datetime):
        return str(date_obj)
    
    now = datetime.now()
    diff = now - date_obj.replace(tzinfo=None) if date_obj.tzinfo else now - date_obj
    
    if diff.days == 0:
        # Today: show "Today HH:MM"
        return f"Today {date_obj.strftime('%H:%M')}"
    elif diff.days == 1:
        # Yesterday: show "Yesterday HH:MM"
        return f"Yesterday {date_obj.strftime('%H:%M')}"
    elif diff.days < 7:
        # This week: show day and time
        return date_obj.strftime("%A %H:%M")
    elif diff.days < 365:
        # This year: show date and time
        return date_obj.strftime("%b %d, %H:%M")
    else:
        # Older: show full date and time
        return date_obj.strftime("%b %d, %Y %H:%M")


class EmailPreview(QWidget):
    """Email preview widget"""
    
    reply_clicked = pyqtSignal(int)  # email_id
    forward_clicked = pyqtSignal(int)  # email_id
    delete_clicked = pyqtSignal(int)  # email_id
    attachment_clicked = pyqtSignal(str)  # file_path
    back_clicked = pyqtSignal()  # back button clicked
    move_email_requested = pyqtSignal(int)  # email_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.current_email: EmailMessage = None
    
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
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QToolButton:hover {
                background-color: #2a2d2e;
            }
            QToolButton::menu-indicator {
                image: none;
                width: 0px;
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
        layout.setSpacing(12)
        
        # Title row: Back button (icon) + Subject + Details dropdown
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)
        
        # Back button (icon only)
        self.back_btn = QPushButton("←")
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 18px;
                font-weight: bold;
                min-width: 30px;
                max-width: 30px;
            }
            QPushButton:hover {
                background-color: #2a2d2e;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
        """)
        self.back_btn.clicked.connect(self.back_clicked.emit)
        title_layout.addWidget(self.back_btn)
        
        # Subject label (takes remaining space, no box/background)
        self.subject_label = QLabel()
        self.subject_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 18px;
                font-weight: 600;
                background-color: transparent;
                border: none;
                padding: 0px;
            }
        """)
        title_layout.addWidget(self.subject_label, 1)  # Stretch factor
        
        # Details dropdown button (From, To, Date)
        self.details_btn = QToolButton()
        self.details_btn.setText("⋯")
        self.details_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                color: #858585;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 16px;
                font-weight: bold;
                min-width: 40px;
            }
            QToolButton:hover {
                background-color: #2a2d2e;
                border-color: #555555;
                color: #cccccc;
            }
        """)
        
        # Create details menu
        self.details_menu = QMenu(self)
        self.details_menu.setStyleSheet("""
            QMenu {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px;
            }
            QMenu::item {
                padding: 8px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #094771;
            }
        """)
        
        self.from_action = self.details_menu.addAction("")
        self.to_action = self.details_menu.addAction("")
        self.date_action = self.details_menu.addAction("")
        self.details_menu.addSeparator()
        self.details_btn.setMenu(self.details_menu)
        self.details_btn.setPopupMode(QToolButton.InstantPopup)
        title_layout.addWidget(self.details_btn)
        
        layout.addLayout(title_layout)
        
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
        
        self.move_btn = QPushButton("Move")
        self.move_btn.setStyleSheet("""
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
        self.move_btn.clicked.connect(self.on_move)
        button_layout.addWidget(self.move_btn)
        
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
        
        # Email body with improved rendering (using QTextBrowser for link support)
        self.body_text = QTextBrowser()
        self.body_text.setOpenExternalLinks(True)
        self.body_text.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                color: #202124;
                font-size: 14px;
                padding: 20px;
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
    
    def show_email(self, email: EmailMessage, attachments: list[Attachment] = None):
        """Display an email"""
        self.current_email = email
        self.empty_label.setVisible(False)
        self.body_text.setVisible(True)
        self.reply_btn.setVisible(True)
        self.forward_btn.setVisible(True)
        self.delete_btn.setVisible(True)
        self.move_btn.setVisible(True)
        self.back_btn.setVisible(True)
        self.details_btn.setVisible(True)
        
        # Set subject
        self.subject_label.setText(email.subject or "(No Subject)")
        
        # Set details in dropdown menu
        self.from_action.setText(f"From: {email.sender}")
        recipients_str = ", ".join(email.recipients) if email.recipients else ""
        self.to_action.setText(f"To: {recipients_str}")
        date_to_show = email.received_at or email.sent_at
        date_str = format_date_time(date_to_show) if date_to_show else 'Unknown'
        self.date_action.setText(f"Date: {date_str}")
        
        # Set body with improved rendering
        if email.body_html:
            # Improve HTML rendering with better styling
            html_content = email.body_html
            
            # Wrap in a styled container for better rendering
            # This ensures proper background, font, and spacing
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        font-size: 14px;
                        line-height: 1.6;
                        color: #202124;
                        background-color: #ffffff;
                        margin: 0;
                        padding: 0;
                    }}
                    img {{
                        max-width: 100%;
                        height: auto;
                    }}
                    a {{
                        color: #1a73e8;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                    pre {{
                        background-color: #f5f5f5;
                        padding: 12px;
                        border-radius: 4px;
                        overflow-x: auto;
                    }}
                    blockquote {{
                        border-left: 4px solid #dadce0;
                        padding-left: 16px;
                        margin-left: 0;
                        color: #5f6368;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                    }}
                    table td, table th {{
                        border: 1px solid #dadce0;
                        padding: 8px;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            self.body_text.setHtml(styled_html)
        elif email.body_plain:
            # For plain text, preserve formatting and convert to HTML
            plain_text = email.body_plain
            # Escape HTML special characters
            plain_text = plain_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            # Convert line breaks to <br>
            plain_text = plain_text.replace('\n', '<br>')
            # Wrap in styled container
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        font-size: 14px;
                        line-height: 1.6;
                        color: #202124;
                        background-color: #ffffff;
                        margin: 0;
                        padding: 0;
                        white-space: pre-wrap;
                    }}
                </style>
            </head>
            <body>
                {plain_text}
            </body>
            </html>
            """
            self.body_text.setHtml(styled_html)
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
                # Use local_path if available, otherwise filename
                file_path = attachment.local_path if hasattr(attachment, 'local_path') and attachment.local_path else None
                file_size = attachment.size_bytes if hasattr(attachment, 'size_bytes') else 0
                att_label = QLabel(f"📎 {attachment.filename} ({format_file_size(file_size)})")
                att_btn = QPushButton("Open")
                if file_path:
                    att_btn.clicked.connect(lambda checked, path=file_path: self.attachment_clicked.emit(path))
                else:
                    att_btn.setEnabled(False)
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
        self.move_btn.setVisible(False)
        self.attachments_label.setVisible(False)
        self.attachments_widget.setVisible(False)
        self.back_btn.setVisible(False)
        self.details_btn.setVisible(False)
        
        self.subject_label.clear()
        self.from_action.setText("From: -")
        self.to_action.setText("To: -")
        self.date_action.setText("Date: -")
        self.body_text.clear()
    
    def on_reply(self):
        """Handle reply button click"""
        if self.current_email:
            self.reply_clicked.emit(self.current_email.id)
    
    def on_forward(self):
        """Handle forward button click"""
        if self.current_email:
            self.forward_clicked.emit(self.current_email.id)
    
    def on_delete(self):
        """Handle delete button click"""
        if self.current_email:
            self.delete_clicked.emit(self.current_email.id)
    
    def on_move(self):
        """Handle move button click"""
        if self.current_email:
            self.move_email_requested.emit(self.current_email.id)
