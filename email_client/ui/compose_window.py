"""
Email composition window.

This module provides a compose window for creating and sending emails
using the MessageSender interface.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCharFormat, QTextCursor
from email_client.models import EmailAccount, EmailMessage, Attachment
from email_client.ui.message_sender import MessageSender
from email_client.network.smtp_client import SmtpError
from utils.helpers import validate_email


class ComposeWindow(QDialog):
    """
    Email composition dialog.
    
    Uses MessageSender interface to send emails, keeping SMTP logic
    out of the UI layer.
    """
    
    draft_saved = pyqtSignal(dict)  # Signal with draft data (for backward compatibility)
    
    def __init__(
        self,
        parent=None,
        reply_to: Optional[EmailMessage] = None,
        forward_email: Optional[EmailMessage] = None,
        draft_email: Optional[EmailMessage] = None,
        accounts: Optional[List[EmailAccount]] = None,
        default_account: Optional[EmailAccount] = None,
        message_sender: Optional[MessageSender] = None
    ):
        """
        Initialize the compose window.
        
        Args:
            parent: Parent widget.
            reply_to: Email message to reply to.
            forward_email: Email message to forward.
            draft_email: Draft email to edit.
            accounts: List of available accounts for the From selector.
            default_account: Default account to select.
            message_sender: MessageSender implementation (injected dependency).
        """
        super().__init__(parent)
        if draft_email:
            self.setWindowTitle("Edit Draft")
        elif reply_to:
            self.setWindowTitle("Reply")
        elif forward_email:
            self.setWindowTitle("Forward")
        else:
            self.setWindowTitle("Compose Email")
        
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        self.attachments: List[Path] = []  # List of file paths
        self.reply_to = reply_to
        self.forward_email = forward_email
        self.draft_email = draft_email
        self.accounts = accounts or []
        self.default_account = default_account
        self.message_sender = message_sender
        
        self.setup_ui()
        self.setup_reply_forward()
        self.setup_draft()
    
    def setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout()
        
        # From (account selector)
        from_layout = QHBoxLayout()
        from_layout.addWidget(QLabel("From:"))
        self.from_combo = QComboBox()
        for account in self.accounts:
            display_text = f"{account.display_name} <{account.email_address}>" if account.display_name else account.email_address
            self.from_combo.addItem(display_text, account)
        
        # Select default account
        if self.default_account:
            for i in range(self.from_combo.count()):
                if self.from_combo.itemData(i) == self.default_account:
                    self.from_combo.setCurrentIndex(i)
                    break
        elif self.accounts:
            self.from_combo.setCurrentIndex(0)
        
        from_layout.addWidget(self.from_combo)
        layout.addLayout(from_layout)
        
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
        
        # Body editor (rich text)
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
            date_str = self.reply_to.received_at.strftime("%Y-%m-%d %H:%M") if self.reply_to.received_at else "Unknown date"
            original_text = f"\n\n--- Original Message ---\n"
            original_text += f"From: {self.reply_to.sender}\n"
            original_text += f"Date: {date_str}\n"
            original_text += f"Subject: {self.reply_to.subject}\n\n"
            original_text += self.reply_to.body_plain or self.reply_to.body_html or ""
            self.body_editor.setPlainText(original_text)
        
        elif self.forward_email:
            # Forward
            subject = self.forward_email.subject or ""
            if not subject.startswith("Fwd: ") and not subject.startswith("Fw: "):
                subject = f"Fwd: {subject}"
            self.subject_input.setText(subject)
            
            # Add forwarded message
            date_str = self.forward_email.received_at.strftime("%Y-%m-%d %H:%M") if self.forward_email.received_at else "Unknown date"
            forwarded_text = f"\n\n--- Forwarded Message ---\n"
            forwarded_text += f"From: {self.forward_email.sender}\n"
            forwarded_text += f"Date: {date_str}\n"
            forwarded_text += f"Subject: {self.forward_email.subject}\n\n"
            forwarded_text += self.forward_email.body_plain or self.forward_email.body_html or ""
            self.body_editor.setPlainText(forwarded_text)
    
    def setup_draft(self):
        """Setup draft email fields"""
        if self.draft_email:
            # Load draft content into compose window
            # Parse recipients
            recipients_str = ', '.join(self.draft_email.recipients) if self.draft_email.recipients else ""
            self.to_input.setText(recipients_str)
            
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
    
    def load_attachments(self, attachments: List[Attachment]):
        """Load attachments from a draft email"""
        for attachment in attachments:
            if attachment.local_path and Path(attachment.local_path).exists():
                file_path = Path(attachment.local_path)
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
            file_path_obj = Path(file_path)
            self.attachments.append(file_path_obj)
            item = QListWidgetItem(file_path_obj.name)
            item.setData(Qt.UserRole, file_path)
            self.attachments_list.addItem(item)
    
    def _get_selected_account(self) -> Optional[EmailAccount]:
        """Get the currently selected account."""
        current_data = self.from_combo.currentData()
        if current_data:
            return current_data
        return self.default_account or (self.accounts[0] if self.accounts else None)
    
    def _build_email_message(self) -> EmailMessage:
        """Build EmailMessage model from UI fields."""
        # Get recipients (separate To, CC, BCC)
        to_emails = [e.strip() for e in self.to_input.text().split(',') if e.strip()]
        cc_emails = [e.strip() for e in self.cc_input.text().split(',') if e.strip()] if self.cc_input.text() else []
        bcc_emails = [e.strip() for e in self.bcc_input.text().split(',') if e.strip()] if self.bcc_input.text() else []
        
        # Get body content
        body_html = self.body_editor.toHtml()
        body_text = self.body_editor.toPlainText()
        
        # Get selected account
        account = self._get_selected_account()
        
        return EmailMessage(
            account_id=account.id if account else 0,
            sender=account.email_address if account else "",
            recipients=to_emails,
            cc_recipients=cc_emails,
            bcc_recipients=bcc_emails,
            subject=self.subject_input.text(),
            body_plain=body_text,
            body_html=body_html,
            sent_at=datetime.now(),
            has_attachments=len(self.attachments) > 0,
        )
    
    def _build_attachments(self) -> List[Attachment]:
        """Build Attachment models from file paths."""
        attachments = []
        for file_path in self.attachments:
            if file_path.exists():
                attachments.append(Attachment(
                    filename=file_path.name,
                    local_path=str(file_path),
                    size_bytes=file_path.stat().st_size,
                    mime_type="application/octet-stream",  # Could be improved with mimetypes module
                ))
        return attachments
    
    def on_send(self):
        """Handle send button click"""
        # Validate recipients
        to_emails = [e.strip() for e in self.to_input.text().split(',') if e.strip()]
        
        if not to_emails:
            QMessageBox.warning(self, "Missing Recipient", "Please enter at least one recipient.")
            return
        
        # Validate email addresses
        for email in to_emails:
            if not validate_email(email):
                QMessageBox.warning(self, "Invalid Email", f"Invalid email address: {email}")
                return
        
        # Get selected account
        account = self._get_selected_account()
        if not account:
            QMessageBox.warning(self, "No Account", "Please select an account to send from.")
            return
        
        if not self.message_sender:
            QMessageBox.critical(self, "Error", "Message sender not configured.")
            return
        
        # Build email message
        message = self._build_email_message()
        attachments = self._build_attachments()
        
        # Send email using MessageSender
        try:
            self.send_btn.setEnabled(False)
            self.send_btn.setText("Sending...")
            
            self.message_sender.send_message(account, message, attachments)
            
            # Success
            QMessageBox.information(self, "Success", "Email sent successfully!")
            self.accept()
            
        except SmtpError as e:
            # Show error dialog
            error_msg = str(e)
            detailed_msg = f"Failed to send email:\n\n{error_msg}"
            QMessageBox.critical(self, "Send Failed", detailed_msg)
        except Exception as e:
            # Unexpected error
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")
        finally:
            self.send_btn.setEnabled(True)
            self.send_btn.setText("Send")
    
    def on_save_draft(self):
        """Handle save draft button click"""
        account = self._get_selected_account()
        if not account:
            QMessageBox.warning(self, "No Account", "Please select an account for saving draft.")
            return
        
        # Get email data
        to_emails = [e.strip() for e in self.to_input.text().split(',') if e.strip()] if self.to_input.text() else []
        cc_emails = [e.strip() for e in self.cc_input.text().split(',') if e.strip()] if self.cc_input.text() else []
        bcc_emails = [e.strip() for e in self.bcc_input.text().split(',') if e.strip()] if self.bcc_input.text() else []
        
        body_html = self.body_editor.toHtml()
        body_text = self.body_editor.toPlainText()
        
        draft_data = {
            'account_id': account.id,
            'to': to_emails,
            'cc': cc_emails,
            'bcc': bcc_emails,
            'subject': self.subject_input.text(),
            'body_html': body_html,
            'body_text': body_text,
            'attachments': [str(path) for path in self.attachments]
        }
        
        # If editing an existing draft, include its ID so it can be deleted
        if self.draft_email and self.draft_email.id:
            draft_data['draft_email_id'] = self.draft_email.id
        
        # Emit signal to save draft (for backward compatibility with main_window)
        self.draft_saved.emit(draft_data)
        QMessageBox.information(self, "Draft Saved", "Draft saved successfully. You can find it in the Drafts folder.")
        self.accept()

