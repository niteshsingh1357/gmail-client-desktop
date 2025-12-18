"""
Email preview component
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                             QPushButton, QScrollArea, QFrame, QMenu, QToolButton, QTextBrowser, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QPainter, QColor
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
        # Today: show time only
        return date_obj.strftime('%I:%M %p')
    elif diff.days == 1:
        # Yesterday
        return f"Yesterday, {date_obj.strftime('%I:%M %p')}"
    elif diff.days < 7:
        # This week: show day and time
        return date_obj.strftime("%a, %I:%M %p")
    elif diff.days < 365:
        # This year: show date and time
        return date_obj.strftime("%b %d, %I:%M %p")
    else:
        # Older: show full date and time
        return date_obj.strftime("%b %d, %Y, %I:%M %p")


class AvatarWidget(QLabel):
    """Custom widget to display a circular avatar with initials"""
    
    def __init__(self, initials: str = "?", size: int = 40, parent=None):
        super().__init__(parent)
        self.initials = initials.upper()[:2] if initials else "?"
        self.avatar_size = size
        self.setFixedSize(size, size)
        
        # Set styles
        self.setStyleSheet(f"""
            QLabel {{
                background-color: #4285f4;
                color: white;
                border-radius: {size // 2}px;
                font-size: {size // 3}px;
                font-weight: 600;
            }}
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setText(self.initials)


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
        self.details_expanded = False
    
    def setup_ui(self):
        """Setup the UI with Gmail-like design"""
        # Modern styling
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                color: #202124;
            }
            QFrame {
                background-color: #ffffff;
                border: 1px solid #dadce0;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #f1f3f4;
                color: #202124;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton:pressed {
                background-color: #d2d4d7;
            }
        """)
        
        # Create scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: #f5f5f5; border: none; }")
        
        # Content widget inside scroll area
        content_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Back button row
        back_layout = QHBoxLayout()
        back_layout.setContentsMargins(0, 0, 0, 0)
        
        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #5f6368;
                border: none;
                border-radius: 20px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #f1f3f4;
            }
            QPushButton:pressed {
                background-color: #e8eaed;
            }
        """)
        self.back_btn.clicked.connect(self.back_clicked.emit)
        back_layout.addWidget(self.back_btn)
        back_layout.addStretch()
        layout.addLayout(back_layout)
        
        # Email card (Gmail-like white card)
        self.email_card = QFrame()
        self.email_card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 0px;
            }
        """)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(16)
        
        # Subject line - prominent
        self.subject_label = QLabel()
        self.subject_label.setStyleSheet("""
            QLabel {
                color: #202124;
                font-size: 22px;
                font-weight: 400;
                background-color: transparent;
                border: none;
                padding: 0px 0px 12px 0px;
            }
        """)
        self.subject_label.setWordWrap(True)
        card_layout.addWidget(self.subject_label)
        
        # Header section: Avatar + Sender info + Actions
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        # Avatar
        self.avatar = AvatarWidget("?", 40)
        header_layout.addWidget(self.avatar)
        
        # Sender info column
        sender_layout = QVBoxLayout()
        sender_layout.setSpacing(2)
        
        # Sender name and recipient preview (one line)
        sender_row = QHBoxLayout()
        sender_row.setSpacing(8)
        
        self.sender_label = QLabel()
        self.sender_label.setStyleSheet("""
            QLabel {
                color: #202124;
                font-size: 14px;
                font-weight: 500;
            }
        """)
        sender_row.addWidget(self.sender_label)
        
        self.recipient_preview = QLabel()
        self.recipient_preview.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 13px;
                font-weight: 400;
            }
        """)
        sender_row.addWidget(self.recipient_preview)
        sender_row.addStretch()
        sender_layout.addLayout(sender_row)
        
        # Expandable details link
        self.details_toggle = QPushButton("Show details ▼")
        self.details_toggle.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #5f6368;
                border: none;
                padding: 0px;
                font-size: 12px;
                text-align: left;
            }
            QPushButton:hover {
                color: #202124;
                text-decoration: underline;
            }
        """)
        self.details_toggle.clicked.connect(self.toggle_details)
        sender_layout.addWidget(self.details_toggle)
        
        header_layout.addLayout(sender_layout, 1)
        
        # Date/time
        self.date_label = QLabel()
        self.date_label.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 13px;
            }
        """)
        header_layout.addWidget(self.date_label)
        
        card_layout.addLayout(header_layout)
        
        # Expandable details section (hidden by default)
        self.details_widget = QWidget()
        self.details_widget.setVisible(False)
        details_layout = QVBoxLayout()
        details_layout.setContentsMargins(52, 0, 0, 0)  # Indent to align with sender info
        details_layout.setSpacing(4)
        
        self.from_detail = QLabel()
        self.from_detail.setStyleSheet("QLabel { color: #5f6368; font-size: 13px; }")
        details_layout.addWidget(self.from_detail)
        
        self.to_detail = QLabel()
        self.to_detail.setStyleSheet("QLabel { color: #5f6368; font-size: 13px; }")
        self.to_detail.setWordWrap(True)
        details_layout.addWidget(self.to_detail)
        
        self.date_detail = QLabel()
        self.date_detail.setStyleSheet("QLabel { color: #5f6368; font-size: 13px; }")
        details_layout.addWidget(self.date_detail)
        
        self.details_widget.setLayout(details_layout)
        card_layout.addWidget(self.details_widget)
        
        self.email_card.setLayout(card_layout)
        layout.addWidget(self.email_card)
        
        # Action buttons (Gmail-style)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.reply_btn = QPushButton("↩ Reply")
        self.reply_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #202124;
                border: none;
                border-radius: 20px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton:pressed {
                background-color: #d2d4d7;
            }
        """)
        self.reply_btn.clicked.connect(self.on_reply)
        button_layout.addWidget(self.reply_btn)
        
        self.forward_btn = QPushButton("→ Forward")
        self.forward_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #202124;
                border: none;
                border-radius: 20px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton:pressed {
                background-color: #d2d4d7;
            }
        """)
        self.forward_btn.clicked.connect(self.on_forward)
        button_layout.addWidget(self.forward_btn)
        
        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #d93025;
                border: none;
                border-radius: 20px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #fce8e6;
            }
            QPushButton:pressed {
                background-color: #f6bcb6;
            }
        """)
        self.delete_btn.clicked.connect(self.on_delete)
        button_layout.addWidget(self.delete_btn)
        
        self.move_btn = QPushButton("📁 Move")
        self.move_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #202124;
                border: none;
                border-radius: 20px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton:pressed {
                background-color: #d2d4d7;
            }
        """)
        self.move_btn.clicked.connect(self.on_move)
        button_layout.addWidget(self.move_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Attachments section (Gmail card style)
        self.attachments_card = QFrame()
        self.attachments_card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        self.attachments_card.setVisible(False)
        
        attachments_card_layout = QVBoxLayout()
        attachments_card_layout.setSpacing(12)
        
        attachments_header = QLabel("📎 Attachments")
        attachments_header.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        attachments_card_layout.addWidget(attachments_header)
        
        self.attachments_layout = QVBoxLayout()
        self.attachments_layout.setSpacing(8)
        attachments_card_layout.addLayout(self.attachments_layout)
        
        self.attachments_card.setLayout(attachments_card_layout)
        layout.addWidget(self.attachments_card)
        
        # Email body card (Gmail-style white card)
        self.body_card = QFrame()
        self.body_card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: none;
                border-radius: 8px;
            }
        """)
        
        body_card_layout = QVBoxLayout()
        body_card_layout.setContentsMargins(0, 0, 0, 0)
        body_card_layout.setSpacing(0)
        
        # Email body with improved rendering (using QTextBrowser for link support)
        self.body_text = QTextBrowser()
        self.body_text.setOpenExternalLinks(True)
        self.body_text.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                border: none;
                border-radius: 8px;
                color: #202124;
                font-size: 14px;
                padding: 24px;
                line-height: 1.6;
            }
        """)
        body_card_layout.addWidget(self.body_text)
        
        self.body_card.setLayout(body_card_layout)
        layout.addWidget(self.body_card, 1)  # Give body card stretch factor to take all available space
        
        content_widget.setLayout(layout)
        scroll.setWidget(content_widget)
        
        # Main layout for this widget
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Empty state (shown when no email selected)
        self.empty_label = QLabel("Select an email to view")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 18px;
                padding: 40px;
                background-color: #f5f5f5;
            }
        """)
        main_layout.addWidget(self.empty_label)
        main_layout.addWidget(scroll)
        
        self.setLayout(main_layout)
        self.show_empty_state()
    
    def toggle_details(self):
        """Toggle the expandable details section"""
        self.details_expanded = not self.details_expanded
        self.details_widget.setVisible(self.details_expanded)
        
        if self.details_expanded:
            self.details_toggle.setText("Hide details ▲")
        else:
            self.details_toggle.setText("Show details ▼")
    
    def show_email(self, email: EmailMessage, attachments: list[Attachment] = None):
        """Display an email in Gmail-like layout"""
        self.current_email = email
        self.empty_label.setVisible(False)
        self.email_card.setVisible(True)
        self.body_card.setVisible(True)
        self.reply_btn.setVisible(True)
        self.forward_btn.setVisible(True)
        self.delete_btn.setVisible(True)
        self.move_btn.setVisible(True)
        self.back_btn.setVisible(True)
        
        # Set subject
        self.subject_label.setText(email.subject or "(No Subject)")
        
        # Extract sender name and email
        sender_name = email.sender
        sender_email = email.sender
        if '<' in email.sender and '>' in email.sender:
            # Format: "Name <email@example.com>"
            parts = email.sender.split('<')
            sender_name = parts[0].strip()
            sender_email = parts[1].strip('>').strip()
        
        # Set avatar initials
        initials = ""
        if sender_name:
            name_parts = sender_name.split()
            if len(name_parts) >= 2:
                initials = name_parts[0][0] + name_parts[-1][0]
            elif len(name_parts) == 1:
                initials = name_parts[0][:2]
        if not initials:
            initials = sender_email[0] if sender_email else "?"
        self.avatar.initials = initials.upper()
        self.avatar.setText(initials.upper())
        
        # Set sender name
        self.sender_label.setText(sender_name)
        
        # Set recipient preview (short version)
        if email.recipients:
            if len(email.recipients) == 1:
                recipient_text = f"to {email.recipients[0]}"
            else:
                recipient_text = f"to {email.recipients[0]} +{len(email.recipients)-1} more"
            self.recipient_preview.setText(recipient_text)
        else:
            self.recipient_preview.setText("")
        
        # Set date/time
        date_to_show = email.received_at or email.sent_at
        date_str = format_date_time(date_to_show) if date_to_show else 'Unknown'
        self.date_label.setText(date_str)
        
        # Set detailed info (for expandable section)
        self.from_detail.setText(f"from: {sender_email}")
        recipients_str = ", ".join(email.recipients) if email.recipients else "None"
        self.to_detail.setText(f"to: {recipients_str}")
        
        # Full date/time for details
        if date_to_show:
            if isinstance(date_to_show, str):
                try:
                    date_to_show = datetime.fromisoformat(date_to_show.replace('Z', '+00:00'))
                except:
                    pass
            if isinstance(date_to_show, datetime):
                full_date = date_to_show.strftime("%A, %B %d, %Y at %I:%M %p")
                self.date_detail.setText(f"date: {full_date}")
            else:
                self.date_detail.setText(f"date: {date_to_show}")
        else:
            self.date_detail.setText("date: Unknown")
        
        # Reset details expansion
        self.details_expanded = False
        self.details_widget.setVisible(False)
        self.details_toggle.setText("Show details ▼")
        
        # Set body with Gmail-like rendering
        if email.body_html:
            # Improve HTML rendering with Gmail-like styling
            html_content = email.body_html
            
            # Wrap in a styled container for better rendering
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                        font-size: 14px;
                        line-height: 1.7;
                        color: #202124;
                        background-color: #ffffff;
                        margin: 0;
                        padding: 0;
                    }}
                    p {{
                        margin: 0 0 12px 0;
                    }}
                    img {{
                        max-width: 100%;
                        height: auto;
                        border-radius: 4px;
                    }}
                    a {{
                        color: #1a73e8;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                    pre, code {{
                        background-color: #f8f9fa;
                        padding: 12px;
                        border-radius: 4px;
                        overflow-x: auto;
                        font-family: 'Courier New', monospace;
                        font-size: 13px;
                    }}
                    code {{
                        padding: 2px 6px;
                    }}
                    blockquote {{
                        border-left: 3px solid #dadce0;
                        padding-left: 16px;
                        margin: 12px 0;
                        color: #5f6368;
                        font-style: italic;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin: 12px 0;
                    }}
                    table td, table th {{
                        border: 1px solid #dadce0;
                        padding: 10px;
                        text-align: left;
                    }}
                    table th {{
                        background-color: #f8f9fa;
                        font-weight: 500;
                    }}
                    hr {{
                        border: none;
                        border-top: 1px solid #dadce0;
                        margin: 20px 0;
                    }}
                    h1, h2, h3, h4, h5, h6 {{
                        margin: 16px 0 8px 0;
                        font-weight: 500;
                        color: #202124;
                    }}
                    h1 {{ font-size: 24px; }}
                    h2 {{ font-size: 20px; }}
                    h3 {{ font-size: 18px; }}
                    h4 {{ font-size: 16px; }}
                    ul, ol {{
                        padding-left: 24px;
                        margin: 12px 0;
                    }}
                    li {{
                        margin: 4px 0;
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
            # Convert URLs to clickable links
            import re
            url_pattern = r'(https?://[^\s]+)'
            plain_text = re.sub(url_pattern, r'<a href="\1">\1</a>', plain_text)
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
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                        font-size: 14px;
                        line-height: 1.7;
                        color: #202124;
                        background-color: #ffffff;
                        margin: 0;
                        padding: 0;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                    }}
                    a {{
                        color: #1a73e8;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
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
        
        # Show attachments (Gmail card style)
        if attachments and len(attachments) > 0:
            self.attachments_card.setVisible(True)
            
            # Clear existing attachment widgets
            while self.attachments_layout.count():
                child = self.attachments_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # Add attachment widgets with Gmail-like styling
            for attachment in attachments:
                att_frame = QFrame()
                att_frame.setStyleSheet("""
                    QFrame {
                        background-color: #f8f9fa;
                        border: none;
                        border-radius: 6px;
                        padding: 12px;
                    }
                    QFrame:hover {
                        background-color: #f1f3f4;
                    }
                """)
                
                att_layout = QHBoxLayout()
                att_layout.setContentsMargins(0, 0, 0, 0)
                att_layout.setSpacing(12)
                
                # File icon
                file_icon = QLabel("📄")
                file_icon.setStyleSheet("QLabel { font-size: 24px; }")
                att_layout.addWidget(file_icon)
                
                # File info
                file_info_layout = QVBoxLayout()
                file_info_layout.setSpacing(2)
                
                file_path = attachment.local_path if hasattr(attachment, 'local_path') and attachment.local_path else None
                file_size = attachment.size_bytes if hasattr(attachment, 'size_bytes') else 0
                
                file_name = QLabel(attachment.filename)
                file_name.setStyleSheet("QLabel { color: #202124; font-size: 13px; font-weight: 500; }")
                file_info_layout.addWidget(file_name)
                
                file_size_label = QLabel(format_file_size(file_size))
                file_size_label.setStyleSheet("QLabel { color: #5f6368; font-size: 12px; }")
                file_info_layout.addWidget(file_size_label)
                
                att_layout.addLayout(file_info_layout, 1)
                
                # Download/Open button
                att_btn = QPushButton("↓")
                att_btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #5f6368;
                        border: none;
                        border-radius: 20px;
                        padding: 6px;
                        font-size: 16px;
                        min-width: 32px;
                        max-width: 32px;
                        min-height: 32px;
                        max-height: 32px;
                    }
                    QPushButton:hover {
                        background-color: #e8eaed;
                        color: #202124;
                    }
                    QPushButton:pressed {
                        background-color: #d2d4d7;
                    }
                """)
                if file_path:
                    att_btn.clicked.connect(lambda checked, path=file_path: self.attachment_clicked.emit(path))
                else:
                    att_btn.setEnabled(False)
                att_layout.addWidget(att_btn)
                
                att_frame.setLayout(att_layout)
                self.attachments_layout.addWidget(att_frame)
        else:
            self.attachments_card.setVisible(False)
    
    def show_empty_state(self):
        """Show empty state when no email is selected"""
        self.current_email = None
        self.empty_label.setVisible(True)
        self.email_card.setVisible(False)
        self.body_card.setVisible(False)
        self.reply_btn.setVisible(False)
        self.forward_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        self.move_btn.setVisible(False)
        self.attachments_card.setVisible(False)
        self.back_btn.setVisible(False)
        
        self.subject_label.clear()
        self.sender_label.clear()
        self.recipient_preview.clear()
        self.date_label.clear()
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
