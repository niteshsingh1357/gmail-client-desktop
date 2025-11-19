"""
Login window for adding email accounts
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QComboBox, QGroupBox, QFormLayout, QMessageBox,
                             QCheckBox, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
import config
from utils.helpers import validate_email


class LoginWindow(QDialog):
    """Login dialog for adding email accounts"""
    
    account_added = pyqtSignal(dict)  # Signal emitted when account is successfully added
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Email Account")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Add Email Account")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Provider selection
        provider_group = QGroupBox("Email Provider")
        provider_layout = QVBoxLayout()
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Gmail", "Outlook", "Yahoo Mail", "Custom IMAP/SMTP"])
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(QLabel("Provider:"))
        provider_layout.addWidget(self.provider_combo)
        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)
        
        # Email input
        email_group = QGroupBox("Account Information")
        email_layout = QFormLayout()
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@example.com")
        email_layout.addRow("Email Address:", self.email_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Password or App Password")
        password_label = QLabel("Password:")
        email_layout.addRow(password_label, self.password_input)
        
        # Help text for Gmail app password
        self.password_help_label = QLabel()
        self.password_help_label.setWordWrap(True)
        self.password_help_label.setStyleSheet("color: #666; font-size: 10px;")
        self.password_help_label.setVisible(False)
        email_layout.addRow("", self.password_help_label)
        
        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Your Name (optional)")
        email_layout.addRow("Display Name:", self.display_name_input)
        
        email_group.setLayout(email_layout)
        layout.addWidget(email_group)
        
        # Server settings (for custom)
        self.server_group = QGroupBox("Server Settings")
        server_layout = QFormLayout()
        
        self.imap_server_input = QLineEdit()
        self.imap_server_input.setPlaceholderText("imap.example.com")
        server_layout.addRow("IMAP Server:", self.imap_server_input)
        
        self.imap_port_input = QLineEdit()
        self.imap_port_input.setText("993")
        server_layout.addRow("IMAP Port:", self.imap_port_input)
        
        self.smtp_server_input = QLineEdit()
        self.smtp_server_input.setPlaceholderText("smtp.example.com")
        server_layout.addRow("SMTP Server:", self.smtp_server_input)
        
        self.smtp_port_input = QLineEdit()
        self.smtp_port_input.setText("587")
        server_layout.addRow("SMTP Port:", self.smtp_port_input)
        
        self.use_tls_checkbox = QCheckBox("Use TLS/SSL")
        self.use_tls_checkbox.setChecked(True)
        server_layout.addRow("", self.use_tls_checkbox)
        
        self.server_group.setLayout(server_layout)
        self.server_group.setVisible(False)  # Hidden by default
        layout.addWidget(self.server_group)
        
        # OAuth checkbox (for Gmail/Outlook)
        self.oauth_checkbox = QCheckBox("Use OAuth2 (Recommended)")
        self.oauth_checkbox.setChecked(True)
        self.oauth_checkbox.stateChanged.connect(self.update_password_help)
        layout.addWidget(self.oauth_checkbox)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.login_button = QPushButton("Add Account")
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self.on_login_clicked)
        button_layout.addWidget(self.login_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Initialize based on default provider
        self.on_provider_changed(self.provider_combo.currentText())
    
    def update_password_help(self):
        """Update password help text visibility"""
        provider = self.provider_combo.currentText()
        if provider == "Gmail" and not self.oauth_checkbox.isChecked():
            self.password_help_label.setVisible(True)
        elif provider == "Gmail" and self.oauth_checkbox.isChecked():
            self.password_help_label.setVisible(False)
    
    def on_provider_changed(self, provider_text: str):
        """Handle provider selection change"""
        if provider_text == "Custom IMAP/SMTP":
            self.server_group.setVisible(True)
            self.oauth_checkbox.setVisible(False)
            self.oauth_checkbox.setChecked(False)
            self.password_help_label.setVisible(False)
        else:
            self.server_group.setVisible(False)
            self.oauth_checkbox.setVisible(True)
            self.oauth_checkbox.setChecked(True)
            
            # Set default servers
            if provider_text == "Gmail":
                self.imap_server_input.setText("imap.gmail.com")
                self.imap_port_input.setText("993")
                self.smtp_server_input.setText("smtp.gmail.com")
                # Gmail supports both 587 (STARTTLS) and 465 (SSL)
                # Default to 587, but user can change to 465 if needed
                self.smtp_port_input.setText("587")
                # Show help text for Gmail app password
                self.password_help_label.setText(
                    "💡 For Gmail: If OAuth2 is disabled, use an App Password.\n"
                    "Generate one at: https://myaccount.google.com/apppasswords"
                )
                self.update_password_help()
            elif provider_text == "Outlook":
                self.imap_server_input.setText("outlook.office365.com")
                self.imap_port_input.setText("993")
                self.smtp_server_input.setText("smtp.office365.com")
                self.smtp_port_input.setText("587")
            elif provider_text == "Yahoo Mail":
                self.imap_server_input.setText("imap.mail.yahoo.com")
                self.imap_port_input.setText("993")
                self.smtp_server_input.setText("smtp.mail.yahoo.com")
                self.smtp_port_input.setText("587")
    
    def on_login_clicked(self):
        """Handle login button click"""
        email = self.email_input.text().strip()
        
        if not email or not validate_email(email):
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address.")
            return
        
        provider = self.provider_combo.currentText().lower().replace(" ", "_")
        use_oauth = self.oauth_checkbox.isChecked() and provider in ["gmail", "outlook"]
        
        account_data = {
            'email': email,
            'display_name': self.display_name_input.text().strip() or email.split('@')[0],
            'provider': provider,
            'use_oauth': use_oauth,
            'password': self.password_input.text(),  # Always include password for fallback
            'imap_server': self.imap_server_input.text().strip(),
            'imap_port': int(self.imap_port_input.text() or "993"),
            'smtp_server': self.smtp_server_input.text().strip(),
            'smtp_port': int(self.smtp_port_input.text() or "587"),
            'use_tls': self.use_tls_checkbox.isChecked()
        }
        
        if not use_oauth and not account_data['password']:
            QMessageBox.warning(self, "Missing Password", "Please enter a password or use OAuth2.")
            return
        
        if provider == "custom_imap/smtp":
            if not account_data['imap_server'] or not account_data['smtp_server']:
                QMessageBox.warning(self, "Missing Information", "Please enter IMAP and SMTP server addresses.")
                return
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.login_button.setEnabled(False)
        
        # Emit signal with account data (parent will handle authentication)
        self.account_added.emit(account_data)
    
    def reset_form(self):
        """Reset the form after successful login"""
        self.progress_bar.setVisible(False)
        self.login_button.setEnabled(True)
        self.email_input.clear()
        self.password_input.clear()
        self.display_name_input.clear()

