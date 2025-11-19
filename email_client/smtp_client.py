"""
SMTP client for sending emails
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Tuple
from pathlib import Path
import config


class SMTPClient:
    """SMTP client for sending emails"""
    
    def __init__(self, server: str, port: int, use_tls: bool = True):
        self.server = server
        self.port = port
        self.use_tls = use_tls
        self.connection: Optional[smtplib.SMTP] = None
        self.authenticated = False
    
    def connect(self, username: str, password: str) -> Tuple[bool, str]:
        """Connect and authenticate to SMTP server
        Returns: (success: bool, error_message: str)
        """
        try:
            # For Gmail port 465, use SMTP_SSL (direct SSL connection)
            # For port 587, use SMTP with STARTTLS
            if self.port == 465:
                # Port 465 requires SSL from the start
                self.connection = smtplib.SMTP_SSL(self.server, self.port, timeout=config.SMTP_TIMEOUT)
            else:
                # Port 587 or other ports use STARTTLS
                self.connection = smtplib.SMTP(self.server, self.port, timeout=config.SMTP_TIMEOUT)
                # Enable debug output for troubleshooting
                # self.connection.set_debuglevel(1)
                
                if self.use_tls:
                    self.connection.starttls()
            
            # Login
            result = self.connection.login(username, password)
            # login() returns a tuple (code, message) where code 235 means success
            # But it can also return just a tuple, so check both ways
            if isinstance(result, tuple):
                if len(result) > 0 and (result[0] == 235 or result[0] == '235'):
                    self.authenticated = True
                    return True, ""
                else:
                    error_msg = result[1] if len(result) > 1 else "Authentication failed"
                    return False, f"Authentication failed: {error_msg}"
            else:
                # If result is not a tuple, assume success
                self.authenticated = True
                return True, ""
        except smtplib.SMTPAuthenticationError as e:
            error_msg = str(e)
            if "Application-specific password required" in error_msg or "Username and Password not accepted" in error_msg:
                return False, f"Authentication failed. Please check:\n1. You're using an App Password (not your regular password)\n2. 2-Step Verification is enabled\n3. The App Password is correct\n\nError: {error_msg}"
            return False, f"Authentication failed: {error_msg}"
        except smtplib.SMTPConnectError as e:
            return False, f"Failed to connect to server {self.server}:{self.port}. Check your internet connection and server settings.\n\nError: {str(e)}"
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {str(e)}"
        except Exception as e:
            error_msg = str(e)
            if "timed out" in error_msg.lower():
                return False, f"Connection timed out. Check your internet connection and firewall settings.\n\nError: {error_msg}"
            return False, f"Connection error: {error_msg}"
    
    def disconnect(self):
        """Disconnect from SMTP server"""
        if self.connection and self.authenticated:
            try:
                self.connection.quit()
            except:
                try:
                    self.connection.close()
                except:
                    pass
            self.authenticated = False
            self.connection = None
    
    def send_email(self, from_addr: str, to_addrs: List[str], subject: str,
                   body_html: str = "", body_text: str = "", cc_addrs: List[str] = None,
                   bcc_addrs: List[str] = None, attachments: List[Path] = None) -> bool:
        """Send an email"""
        if not self.authenticated:
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = from_addr
            msg['To'] = ', '.join(to_addrs)
            msg['Subject'] = subject
            
            if cc_addrs:
                msg['Cc'] = ', '.join(cc_addrs)
            
            # Add body
            if body_text:
                text_part = MIMEText(body_text, 'plain', 'utf-8')
                msg.attach(text_part)
            
            if body_html:
                html_part = MIMEText(body_html, 'html', 'utf-8')
                msg.attach(html_part)
            elif not body_text:
                # If no body provided, add empty text
                msg.attach(MIMEText('', 'plain'))
            
            # Add attachments
            if attachments:
                for attachment_path in attachments:
                    if attachment_path.exists():
                        with open(attachment_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {attachment_path.name}'
                            )
                            msg.attach(part)
            
            # Prepare recipients
            all_recipients = to_addrs.copy()
            if cc_addrs:
                all_recipients.extend(cc_addrs)
            if bcc_addrs:
                all_recipients.extend(bcc_addrs)
            
            # Send email
            text = msg.as_string()
            self.connection.sendmail(from_addr, all_recipients, text)
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

