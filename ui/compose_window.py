"""
Email composition window
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QTextEdit, QPushButton, QListWidget, QListWidgetItem,
                             QFileDialog, QMessageBox, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCharFormat, QTextCursor
from pathlib import Path
from email_client.models import EmailMessage, Attachment
from utils.helpers import validate_email


class ComposeWindow(QDialog):
    """Email composition dialog"""
    
    email_sent = pyqtSignal(dict)  # Signal with email data
    draft_saved = pyqtSignal(dict)  # Signal with draft data
    
    def __init__(self, parent=None, reply_to: EmailMessage = None, forward_email: EmailMessage = None, draft_email: EmailMessage = None, account_id: int = None, account_email: str = None):
        super().__init__(parent)
        if draft_email:
            self.setWindowTitle("Edit Draft")
        else:
            self.setWindowTitle("Compose Email")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.attachments = []  # List of file paths
        self.reply_to = reply_to
        self.forward_email = forward_email
        self.draft_email = draft_email
        self.account_id = account_id
        self.account_email = account_email
        self.setup_ui()
        self.setup_reply_forward()
        self.setup_draft()
    
    def setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout()
        
        # Account info (which account is sending)
        if self.account_email:
            account_label = QLabel(f"From: {self.account_email}")
            account_label.setStyleSheet("color: #666; font-weight: bold; padding: 5px;")
            layout.addWidget(account_label)
        
        # To, CC, BCC fields
        form_layout = QVBoxLayout()
        
        to_layout = QHBoxLayout()
        to_layout.addWidget(QLabel("To:"))
        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("recipient@example.com")
        to_layout.addWidget(self.to_input)
        form_layout.addLayout(to_layout)
        
        cc_layout = QHBoxLayout()
        cc_layout.addWidget(QLabel("CC:"))
        self.cc_input = QLineEdit()
        self.cc_input.setPlaceholderText("cc@example.com (optional)")
        cc_layout.addWidget(self.cc_input)
        form_layout.addLayout(cc_layout)
        
        bcc_layout = QHBoxLayout()
        bcc_layout.addWidget(QLabel("BCC:"))
        self.bcc_input = QLineEdit()
        self.bcc_input.setPlaceholderText("bcc@example.com (optional)")
        bcc_layout.addWidget(self.bcc_input)
        form_layout.addLayout(bcc_layout)
        
        subject_layout = QHBoxLayout()
        subject_layout.addWidget(QLabel("Subject:"))
        self.subject_input = QLineEdit()
        subject_layout.addWidget(self.subject_input)
        form_layout.addLayout(subject_layout)
        
        layout.addLayout(form_layout)
        
        # Formatting toolbar
        toolbar_layout = QHBoxLayout()
        
        self.bold_btn = QPushButton("B")
        self.bold_btn.setFont(QFont("", 12, QFont.Bold))
        self.bold_btn.clicked.connect(self.toggle_bold)
        toolbar_layout.addWidget(self.bold_btn)
        
        self.italic_btn = QPushButton("I")
        italic_font = QFont()
        italic_font.setItalic(True)
        self.italic_btn.setFont(italic_font)
        self.italic_btn.clicked.connect(self.toggle_italic)
        toolbar_layout.addWidget(self.italic_btn)
        
        self.underline_btn = QPushButton("U")
        underline_font = QFont()
        underline_font.setUnderline(True)
        self.underline_btn.setFont(underline_font)
        self.underline_btn.clicked.connect(self.toggle_underline)
        toolbar_layout.addWidget(self.underline_btn)
        
        toolbar_layout.addStretch()
        
        attach_btn = QPushButton("📎 Attach File")
        attach_btn.clicked.connect(self.attach_file)
        toolbar_layout.addWidget(attach_btn)
        
        layout.addLayout(toolbar_layout)
        
        # Body editor
        self.body_editor = QTextEdit()
        self.body_editor.setAcceptRichText(True)
        layout.addWidget(self.body_editor)
        
        # Attachments list
        attachments_label = QLabel("Attachments:")
        layout.addWidget(attachments_label)
        
        self.attachments_list = QListWidget()
        self.attachments_list.setMaximumHeight(100)
        layout.addWidget(self.attachments_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setDefault(True)
        self.send_btn.clicked.connect(self.on_send)
        button_layout.addWidget(self.send_btn)
        
        self.save_draft_btn = QPushButton("Save Draft")
        self.save_draft_btn.clicked.connect(self.on_save_draft)
        button_layout.addWidget(self.save_draft_btn)
        
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.discard_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def setup_reply_forward(self):
        """Setup reply or forward fields"""
        if self.reply_to:
            # Reply
            self.to_input.setText(self.reply_to.sender)
            subject = self.reply_to.subject or ""
            if not subject.startswith("Re: "):
                subject = f"Re: {subject}"
            self.subject_input.setText(subject)
            
            # Add quoted original message
            # Prefer received_at, then sent_at, formatted nicely
            from datetime import datetime
            msg_dt = self.reply_to.received_at or self.reply_to.sent_at
            if isinstance(msg_dt, datetime):
                date_str = msg_dt.strftime("%Y-%m-%d %H:%M")
            else:
                date_str = ""
            original_text = f"\n\n--- Original Message ---\n"
            original_text += f"From: {self.reply_to.sender}\n"
            if date_str:
                original_text += f"Date: {date_str}\n"
            original_text += f"Subject: {self.reply_to.subject}\n\n"
            body = self.reply_to.body_plain or self.reply_to.body_html or ""
            original_text += body
            self.body_editor.setPlainText(original_text)
        
        elif self.forward_email:
            # Forward
            subject = self.forward_email.subject or ""
            if not subject.startswith("Fwd: "):
                subject = f"Fwd: {subject}"
            self.subject_input.setText(subject)
            
            # Add forwarded message
            from datetime import datetime
            msg_dt = self.forward_email.received_at or self.forward_email.sent_at
            if isinstance(msg_dt, datetime):
                date_str = msg_dt.strftime("%Y-%m-%d %H:%M")
            else:
                date_str = ""
            forwarded_text = f"\n\n--- Forwarded Message ---\n"
            forwarded_text += f"From: {self.forward_email.sender}\n"
            if date_str:
                forwarded_text += f"Date: {date_str}\n"
            forwarded_text += f"Subject: {self.forward_email.subject}\n\n"
            body = self.forward_email.body_plain or self.forward_email.body_html or ""
            forwarded_text += body
            self.body_editor.setPlainText(forwarded_text)
    
    def setup_draft(self):
        """Setup draft email fields"""
        if self.draft_email:
            # Load draft content into compose window
            # Parse recipients (recipients is a list, need to join)
            recipients_list = self.draft_email.recipients or []
            recipients_str = ", ".join(recipients_list) if recipients_list else ""
            self.to_input.setText(recipients_str)
            
            # Set CC recipients if available
            cc_list = getattr(self.draft_email, 'cc_recipients', []) or []
            cc_str = ", ".join(cc_list) if cc_list else ""
            self.cc_input.setText(cc_str)
            
            # Set BCC recipients if available
            bcc_list = getattr(self.draft_email, 'bcc_recipients', []) or []
            bcc_str = ", ".join(bcc_list) if bcc_list else ""
            self.bcc_input.setText(bcc_str)
            
            # Set subject
            subject = self.draft_email.subject or ""
            if subject == "(No Subject)":
                subject = ""
            self.subject_input.setText(subject)
            
            # Set body content (prefer HTML if available)
            if self.draft_email.body_html:
                self.body_editor.setHtml(self.draft_email.body_html)
            elif self.draft_email.body_plain:
                self.body_editor.setPlainText(self.draft_email.body_plain)
    
    def load_attachments(self, attachments: list[Attachment]):
        """Load attachments from a draft email"""
        from pathlib import Path
        for attachment in attachments:
            file_path = Path(attachment.file_path)
            if file_path.exists():
                self.attachments.append(file_path)
                item = QListWidgetItem(attachment.filename)
                item.setData(Qt.UserRole, str(file_path))
                self.attachments_list.addItem(item)
    
    def toggle_bold(self):
        """Toggle bold formatting"""
        cursor = self.body_editor.textCursor()
        format = QTextCharFormat()
        format.setFontWeight(QFont.Bold if cursor.charFormat().fontWeight() != QFont.Bold else QFont.Normal)
        cursor.mergeCharFormat(format)
        self.body_editor.setFocus()
    
    def toggle_italic(self):
        """Toggle italic formatting"""
        cursor = self.body_editor.textCursor()
        format = QTextCharFormat()
        format.setFontItalic(not cursor.charFormat().fontItalic())
        cursor.mergeCharFormat(format)
        self.body_editor.setFocus()
    
    def toggle_underline(self):
        """Toggle underline formatting"""
        cursor = self.body_editor.textCursor()
        format = QTextCharFormat()
        format.setUnderlineStyle(1 if cursor.charFormat().underlineStyle() == 0 else 0)
        cursor.mergeCharFormat(format)
        self.body_editor.setFocus()
    
    def attach_file(self):
        """Attach a file"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Attach")
        if file_path:
            self.attachments.append(Path(file_path))
            item = QListWidgetItem(Path(file_path).name)
            item.setData(Qt.UserRole, file_path)
            self.attachments_list.addItem(item)
    
    def on_send(self):
        """Handle send button click"""
        to_emails = [e.strip() for e in self.to_input.text().split(',') if e.strip()]
        
        if not to_emails:
            QMessageBox.warning(self, "Missing Recipient", "Please enter at least one recipient.")
            return
        
        # Validate email addresses
        for email in to_emails:
            if not validate_email(email):
                QMessageBox.warning(self, "Invalid Email", f"Invalid email address: {email}")
                return
        
        cc_emails = [e.strip() for e in self.cc_input.text().split(',') if e.strip()] if self.cc_input.text() else []
        bcc_emails = [e.strip() for e in self.bcc_input.text().split(',') if e.strip()] if self.bcc_input.text() else []
        
        # Get body content
        body_html = self.body_editor.toHtml()
        body_text = self.body_editor.toPlainText()
        
        email_data = {
            'to': to_emails,
            'cc': cc_emails,
            'bcc': bcc_emails,
            'subject': self.subject_input.text(),
            'body_html': body_html,
            'body_text': body_text,
            'attachments': self.attachments
        }
        
        # If sending from a draft, include draft ID to delete it after sending
        if self.draft_email and self.draft_email.id:
            email_data['draft_email_id'] = self.draft_email.id
        
        self.email_sent.emit(email_data)
        self.accept()
    
    def on_save_draft(self):
        """Handle save draft button click"""
        if not self.account_id:
            QMessageBox.warning(self, "No Account", "No account selected for saving draft.")
            return
        
        # Get email data
        to_emails = [e.strip() for e in self.to_input.text().split(',') if e.strip()] if self.to_input.text() else []
        cc_emails = [e.strip() for e in self.cc_input.text().split(',') if e.strip()] if self.cc_input.text() else []
        bcc_emails = [e.strip() for e in self.bcc_input.text().split(',') if e.strip()] if self.bcc_input.text() else []
        
        body_html = self.body_editor.toHtml()
        body_text = self.body_editor.toPlainText()
        
        draft_data = {
            'account_id': self.account_id,
            'to': to_emails,
            'cc': cc_emails,
            'bcc': bcc_emails,
            'subject': self.subject_input.text(),
            'body_html': body_html,
            'body_text': body_text,
            'attachments': self.attachments
        }
        
        # If editing an existing draft, include its ID so it can be deleted
        if self.draft_email and self.draft_email.id:
            draft_data['draft_email_id'] = self.draft_email.id
        
        # Emit signal to save draft
        self.draft_saved.emit(draft_data)
        QMessageBox.information(self, "Draft Saved", "Draft saved successfully. You can find it in the Drafts folder.")
        self.accept()

