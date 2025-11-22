"""
Concrete implementation of MessageSender using SmtpClient.
"""
from typing import List
from email_client.models import EmailAccount, EmailMessage, Attachment
from email_client.ui.message_sender import MessageSender
from email_client.network.smtp_client import SmtpClient, SmtpError
from email_client.auth.accounts import get_token_bundle


class MessageSenderImpl(MessageSender):
    """Concrete message sender implementation using SmtpClient."""
    
    def send_message(
        self,
        account: EmailAccount,
        message: EmailMessage,
        attachments: List[Attachment]
    ) -> None:
        """
        Send an email message using SmtpClient.
        
        Args:
            account: The email account to send from.
            message: The email message to send.
            attachments: List of attachments to include.
            
        Raises:
            SmtpError: If sending fails.
        """
        # Get token bundle for the account
        token_bundle = None
        if account.id:
            try:
                token_bundle = get_token_bundle(account.id)
            except Exception:
                # No token bundle available, will raise error in SmtpClient
                pass
        
        # Create SMTP client
        smtp_client = SmtpClient(account, token_bundle)
        
        try:
            # Send the email
            smtp_client.send_email(message, attachments)
        finally:
            # Always close the connection
            smtp_client.close()

