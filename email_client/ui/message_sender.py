"""
Message sender interface for email composition.

This module provides an interface for sending emails, allowing the UI
to send emails without knowing about SMTP implementation details.
"""
from abc import ABC, abstractmethod
from typing import List
from email_client.models import EmailMessage, Attachment, EmailAccount


class MessageSender(ABC):
    """Interface for sending email messages."""
    
    @abstractmethod
    def send_message(
        self,
        account: EmailAccount,
        message: EmailMessage,
        attachments: List[Attachment]
    ) -> None:
        """
        Send an email message.
        
        Args:
            account: The email account to send from.
            message: The email message to send.
            attachments: List of attachments to include.
            
        Raises:
            SmtpError: If sending fails.
        """
        pass

