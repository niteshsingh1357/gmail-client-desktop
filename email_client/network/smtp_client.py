"""
SMTP client for sending emails.

This module provides a high-level SMTP client that supports XOAUTH2
authentication and handles email composition and sending.
"""
import smtplib
import base64
import logging
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional
from email_client.models import EmailAccount, EmailMessage as EmailMessageModel, Attachment
from email_client.auth.oauth import TokenBundle
from email_client.config import DEFAULT_SMTP_PORT


logger = logging.getLogger(__name__)


class SmtpError(Exception):
    """Base exception for SMTP-related errors."""
    pass


class SmtpConnectionError(SmtpError):
    """Raised when SMTP connection fails."""
    pass


class SmtpAuthenticationError(SmtpError):
    """Raised when SMTP authentication fails."""
    pass


class SmtpSendError(SmtpError):
    """Raised when sending an email fails."""
    pass


class SmtpClient:
    """
    High-level SMTP client for sending emails.
    
    Supports XOAUTH2 authentication and provides a clean interface
    for composing and sending emails with attachments.
    """
    
    def __init__(self, account: EmailAccount, token_bundle: Optional[TokenBundle] = None):
        """
        Initialize the SMTP client.
        
        Args:
            account: The email account configuration.
            token_bundle: Optional OAuth token bundle for XOAUTH2 authentication.
        """
        self.account = account
        self.token_bundle = token_bundle
        self.connection: Optional[smtplib.SMTP] = None
        self._authenticated = False
    
    def _build_xoauth2_string(self) -> str:
        """
        Build the XOAUTH2 authentication string for SMTP.
        
        Format: user=email\1auth=Bearer access_token\1\1
        
        Returns:
            Base64-encoded XOAUTH2 string.
            
        Raises:
            SmtpAuthenticationError: If no access token is available.
        """
        if not self.token_bundle or not self.token_bundle.access_token:
            raise SmtpAuthenticationError("No access token available for XOAUTH2")
        
        auth_string = f"user={self.account.email_address}\x01auth=Bearer {self.token_bundle.access_token}\x01\x01"
        return base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    
    def _authenticate_xoauth2(self, smtp_conn: smtplib.SMTP) -> None:
        """
        Authenticate using XOAUTH2.
        
        Args:
            smtp_conn: The SMTP connection object.
            
        Raises:
            SmtpAuthenticationError: If authentication fails.
        """
        try:
            xoauth2_string = self._build_xoauth2_string()
            
            # SMTP XOAUTH2 authentication
            # The AUTH command expects the base64-encoded string
            code, response = smtp_conn.docmd('AUTH', 'XOAUTH2 ' + xoauth2_string)
            
            if code == 235:
                # 235 is success
                self._authenticated = True
                logger.info("XOAUTH2 authentication successful")
            else:
                error_msg = response.decode('utf-8') if isinstance(response, bytes) else str(response)
                raise SmtpAuthenticationError(
                    f"XOAUTH2 authentication failed: {error_msg}"
                )
        except smtplib.SMTPAuthenticationError as e:
            raise SmtpAuthenticationError(f"SMTP authentication failed: {str(e)}")
        except Exception as e:
            if isinstance(e, SmtpAuthenticationError):
                raise
            raise SmtpAuthenticationError(f"Authentication error: {str(e)}")
    
    def _connect(self) -> None:
        """Establish connection to SMTP server and authenticate."""
        if self.connection and self._authenticated:
            return
        
        try:
            host = self.account.smtp_host
            port = DEFAULT_SMTP_PORT
            
            logger.info(f"Connecting to SMTP server {host}:{port}")
            
            # Connect to SMTP server
            # Port 465 uses SSL from the start, port 587 uses STARTTLS
            if port == 465:
                self.connection = smtplib.SMTP_SSL(host, port)
            else:
                self.connection = smtplib.SMTP(host, port)
                # Enable STARTTLS
                self.connection.starttls()
            
            # Authenticate
            if self.token_bundle:
                self._authenticate_xoauth2(self.connection)
            else:
                raise SmtpAuthenticationError(
                    "No token bundle provided. XOAUTH2 authentication required."
                )
            
            logger.info("SMTP connection established and authenticated")
        except smtplib.SMTPConnectError as e:
            raise SmtpConnectionError(f"Failed to connect to SMTP server {host}:{port}: {str(e)}")
        except (SmtpAuthenticationError, SmtpError):
            raise
        except Exception as e:
            raise SmtpConnectionError(f"Failed to connect to SMTP server: {str(e)}")
    
    def _ensure_connected(self) -> None:
        """Ensure connection is established."""
        if not self._authenticated or not self.connection:
            self._connect()
    
    def _build_mime_message(
        self,
        message: EmailMessageModel,
        attachments: List[Attachment]
    ) -> EmailMessage:
        """
        Build a MIME message from EmailMessage model and attachments.
        
        Args:
            message: The email message model.
            attachments: List of attachment models.
            
        Returns:
            A constructed EmailMessage object ready to send.
        """
        # Use MIMEMultipart to support both text and HTML, plus attachments
        msg = MIMEMultipart('alternative')
        
        # Set headers
        # Format: "Display Name <email@example.com>" or just "email@example.com"
        if self.account.display_name:
            msg['From'] = f"{self.account.display_name} <{self.account.email_address}>"
        else:
            msg['From'] = self.account.email_address
        msg['To'] = ', '.join(message.recipients) if message.recipients else ''
        if message.cc_recipients:
            msg['Cc'] = ', '.join(message.cc_recipients)
        if message.bcc_recipients:
            msg['Bcc'] = ', '.join(message.bcc_recipients)
        msg['Subject'] = message.subject
        
        # Add date if available
        if message.sent_at:
            msg['Date'] = message.sent_at.strftime('%a, %d %b %Y %H:%M:%S %z')
        
        # Add body parts
        if message.body_plain:
            text_part = MIMEText(message.body_plain, 'plain', 'utf-8')
            msg.attach(text_part)
        
        if message.body_html:
            html_part = MIMEText(message.body_html, 'html', 'utf-8')
            msg.attach(html_part)
        elif not message.body_plain:
            # If no body provided, add empty text
            msg.attach(MIMEText('', 'plain'))
        
        # Add attachments
        for attachment in attachments:
            if attachment.local_path and Path(attachment.local_path).exists():
                try:
                    with open(attachment.local_path, 'rb') as f:
                        attachment_data = f.read()
                    
                    # Determine MIME type
                    mime_type = attachment.mime_type or 'application/octet-stream'
                    main_type, sub_type = mime_type.split('/', 1) if '/' in mime_type else ('application', 'octet-stream')
                    
                    # Create attachment part
                    part = MIMEBase(main_type, sub_type)
                    part.set_payload(attachment_data)
                    encoders.encode_base64(part)
                    
                    # Set headers
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{attachment.filename}"'
                    )
                    
                    msg.attach(part)
                    logger.debug(f"Added attachment: {attachment.filename}")
                except Exception as e:
                    logger.warning(f"Failed to attach {attachment.filename}: {str(e)}")
                    # Continue with other attachments
            else:
                logger.warning(f"Attachment file not found: {attachment.local_path}")
        
        return msg
    
    def send_email(
        self,
        message: EmailMessageModel,
        attachments: List[Attachment]
    ) -> None:
        """
        Send an email message with optional attachments.
        
        Args:
            message: The email message to send.
            attachments: List of attachments to include.
            
        Raises:
            SmtpError: If sending fails for any reason.
        """
        self._ensure_connected()
        
        try:
            # Validate message
            if not message.recipients:
                raise SmtpSendError("No recipients specified")
            
            if not message.subject:
                logger.warning("Sending email without subject")
            
            # Build MIME message
            mime_msg = self._build_mime_message(message, attachments)
            
            # Prepare recipient list (all recipients for SMTP sendmail)
            recipients = message.recipients.copy()
            recipients.extend(message.cc_recipients)
            recipients.extend(message.bcc_recipients)
            
            logger.info(f"Sending email to {len(recipients)} recipient(s)")
            
            # Send the email
            failed_recipients = self.connection.sendmail(
                self.account.email_address,
                recipients,
                mime_msg.as_string()
            )
            
            if failed_recipients:
                # Some recipients failed
                error_msg = f"Failed to send to recipients: {', '.join(failed_recipients.keys())}"
                logger.error(error_msg)
                raise SmtpSendError(error_msg)
            
            logger.info("Email sent successfully")
        except smtplib.SMTPRecipientsRefused as e:
            raise SmtpSendError(f"Recipients refused: {str(e)}")
        except smtplib.SMTPDataError as e:
            raise SmtpSendError(f"Server rejected message data: {str(e)}")
        except smtplib.SMTPException as e:
            raise SmtpSendError(f"SMTP error: {str(e)}")
        except SmtpError:
            raise
        except Exception as e:
            raise SmtpSendError(f"Failed to send email: {str(e)}")
    
    def close(self) -> None:
        """Close the SMTP connection."""
        if self.connection and self._authenticated:
            try:
                self.connection.quit()
                logger.debug("SMTP connection closed gracefully")
            except Exception:
                try:
                    self.connection.close()
                    logger.debug("SMTP connection closed")
                except Exception:
                    pass
            finally:
                self.connection = None
                self._authenticated = False

