"""
Centralized error hierarchy for the email client.

This module provides a base exception class and specific error types
for different parts of the application, along with helpers for converting
technical errors to user-friendly messages.
"""
from typing import Union


class EmailClientError(Exception):
    """
    Base exception class for all email client errors.
    
    All application-specific exceptions should inherit from this class
    to enable centralized error handling and user-friendly message mapping.
    """
    pass


class OAuthError(EmailClientError):
    """Raised when OAuth authentication or token operations fail."""
    pass


class TokenRefreshError(OAuthError):
    """Raised when OAuth token refresh fails."""
    pass


class ImapError(EmailClientError):
    """Raised when IMAP operations fail."""
    pass


class SmtpError(EmailClientError):
    """Raised when SMTP operations fail."""
    pass


class DecryptionError(EmailClientError):
    """Raised when decryption operations fail."""
    pass


class SyncError(EmailClientError):
    """Raised when synchronization operations fail."""
    pass


class AccountError(EmailClientError):
    """Raised when account management operations fail."""
    pass


class FolderError(EmailClientError):
    """Raised when folder operations fail."""
    pass


def human_friendly_message(exc: Union[EmailClientError, Exception]) -> str:
    """
    Convert technical error exceptions to user-friendly messages.
    
    This function maps various error types to messages that are
    appropriate for display in the UI, hiding technical details
    while providing actionable information.
    
    Supports both the centralized error classes from this module
    and the existing error classes defined in other modules.
    
    Args:
        exc: The exception to convert.
        
    Returns:
        A user-friendly error message string.
    """
    error_msg = str(exc) if str(exc) else ""
    error_type_name = type(exc).__name__
    
    # Handle base EmailClientError and its subclasses
    if isinstance(exc, EmailClientError):
        # OAuth errors
        if isinstance(exc, TokenRefreshError):
            return (
                "Your account session has expired. Please sign in again.\n\n"
                "This usually happens when you haven't used the account for a while. "
                "You'll need to re-authenticate to continue using this account."
            )
        elif isinstance(exc, OAuthError):
            if "authentication" in error_msg.lower() or "authorization" in error_msg.lower():
                return (
                    "Authentication failed. Please check your account credentials "
                    "and try again. If the problem persists, you may need to "
                    "remove and re-add the account."
                )
            elif "token" in error_msg.lower():
                return (
                    "There was a problem with your account authentication. "
                    "Please try signing in again."
                )
            else:
                return (
                    "An authentication error occurred. Please try again or "
                    "contact support if the problem persists."
                )
        
        # IMAP errors
        elif isinstance(exc, ImapError):
            if "connection" in error_msg.lower() or "connect" in error_msg.lower():
                return (
                    "Could not connect to the email server. Please check:\n\n"
                    "• Your internet connection\n"
                    "• The server settings for this account\n"
                    "• Whether the email service is temporarily unavailable"
                )
            elif "authentication" in error_msg.lower() or "login" in error_msg.lower() or "auth" in error_msg.lower():
                return (
                    "Could not sign in to your email account. Please check:\n\n"
                    "• Your email address and password are correct\n"
                    "• Your account credentials are up to date\n"
                    "• If using OAuth, try removing and re-adding the account"
                )
            elif "timeout" in error_msg.lower():
                return (
                    "The connection to the email server timed out. This might be "
                    "due to a slow internet connection or server issues. Please try again."
                )
            else:
                return (
                    "An error occurred while accessing your email. "
                    "Please try again. If the problem continues, the email service "
                    "may be temporarily unavailable."
                )
        
        # SMTP errors
        elif isinstance(exc, SmtpError):
            if "connection" in error_msg.lower() or "connect" in error_msg.lower():
                return (
                    "Could not connect to the email server to send your message. "
                    "Please check your internet connection and try again."
                )
            elif "authentication" in error_msg.lower() or "login" in error_msg.lower() or "auth" in error_msg.lower():
                return (
                    "Could not authenticate to send email. Please check:\n\n"
                    "• Your account credentials are correct\n"
                    "• If using OAuth, your account is properly configured\n"
                    "• Try removing and re-adding the account if needed"
                )
            elif "send" in error_msg.lower() or "message" in error_msg.lower():
                return (
                    "Failed to send your email. This might be due to:\n\n"
                    "• Invalid recipient email addresses\n"
                    "• Server restrictions on message size\n"
                    "• Temporary server issues\n\n"
                    "Please check the recipient addresses and try again."
                )
            else:
                return (
                    "An error occurred while sending your email. "
                    "Please try again. If the problem continues, check your "
                    "account settings and internet connection."
                )
        
        # Decryption errors
        elif isinstance(exc, DecryptionError):
            return (
                "Could not decrypt stored data. This might indicate that:\n\n"
                "• The application data has been corrupted\n"
                "• The encryption key has been lost or changed\n\n"
                "You may need to remove and re-add your accounts."
            )
        
        # Sync errors
        elif isinstance(exc, SyncError):
            if "connection" in error_msg.lower():
                return (
                    "Synchronization failed due to a connection problem. "
                    "Please check your internet connection and try again."
                )
            elif "timeout" in error_msg.lower():
                return (
                    "Synchronization timed out. This might be due to a slow "
                    "connection or server issues. Please try again."
                )
            else:
                return (
                    "An error occurred while synchronizing your email. "
                    "Some messages may not have been updated. Please try "
                    "refreshing to sync again."
                )
        
        # Account errors
        elif isinstance(exc, AccountError):
            if "not found" in error_msg.lower():
                return "The requested account could not be found."
            elif "create" in error_msg.lower() or "creation" in error_msg.lower():
                return (
                    "Failed to create the account. Please check:\n\n"
                    "• All required information was provided\n"
                    "• Your account credentials are correct\n"
                    "• The account doesn't already exist"
                )
            else:
                return (
                    "An error occurred while managing your account. "
                    "Please try again."
                )
        
        # Folder errors
        elif isinstance(exc, FolderError):
            if "create" in error_msg.lower():
                return "Could not create the folder. The folder may already exist or the name may be invalid."
            elif "delete" in error_msg.lower():
                return "Could not delete the folder. Some folders cannot be deleted."
            elif "rename" in error_msg.lower():
                return "Could not rename the folder. The new name may be invalid or already in use."
            else:
                return "An error occurred while managing the folder. Please try again."
        
        # Generic EmailClientError
        else:
            if error_msg:
                # Try to extract a meaningful message from the error
                return f"An error occurred: {error_msg}"
            else:
                return "An unexpected error occurred. Please try again."
    
    # Handle existing error classes from other modules (by name matching)
    # This allows the function to work with existing error classes that
    # haven't been migrated to inherit from EmailClientError yet
    elif error_type_name == "OAuthError" or "oauth" in error_type_name.lower():
        if "token" in error_msg.lower() and "refresh" in error_msg.lower():
            return (
                "Your account session has expired. Please sign in again.\n\n"
                "This usually happens when you haven't used the account for a while. "
                "You'll need to re-authenticate to continue using this account."
            )
        else:
            return (
                "An authentication error occurred. Please try signing in again "
                "or contact support if the problem persists."
            )
    elif error_type_name == "TokenRefreshError":
        return (
            "Your account session has expired. Please sign in again.\n\n"
            "This usually happens when you haven't used the account for a while. "
            "You'll need to re-authenticate to continue using this account."
        )
    elif error_type_name.startswith("Imap") and "Error" in error_type_name:
        if "Connection" in error_type_name:
            return (
                "Could not connect to the email server. Please check:\n\n"
                "• Your internet connection\n"
                "• The server settings for this account\n"
                "• Whether the email service is temporarily unavailable"
            )
        elif "Authentication" in error_type_name:
            return (
                "Could not sign in to your email account. Please check:\n\n"
                "• Your email address and password are correct\n"
                "• Your account credentials are up to date\n"
                "• If using OAuth, try removing and re-adding the account"
            )
        else:
            return (
                "An error occurred while accessing your email. "
                "Please try again. If the problem continues, the email service "
                "may be temporarily unavailable."
            )
    elif error_type_name.startswith("Smtp") and "Error" in error_type_name:
        if "Connection" in error_type_name:
            return (
                "Could not connect to the email server to send your message. "
                "Please check your internet connection and try again."
            )
        elif "Authentication" in error_type_name:
            return (
                "Could not authenticate to send email. Please check:\n\n"
                "• Your account credentials are correct\n"
                "• If using OAuth, your account is properly configured\n"
                "• Try removing and re-adding the account if needed"
            )
        elif "Send" in error_type_name:
            return (
                "Failed to send your email. This might be due to:\n\n"
                "• Invalid recipient email addresses\n"
                "• Server restrictions on message size\n"
                "• Temporary server issues\n\n"
                "Please check the recipient addresses and try again."
            )
        else:
            return (
                "An error occurred while sending your email. "
                "Please try again. If the problem continues, check your "
                "account settings and internet connection."
            )
    elif error_type_name == "DecryptionError":
        return (
            "Could not decrypt stored data. This might indicate that:\n\n"
            "• The application data has been corrupted\n"
            "• The encryption key has been lost or changed\n\n"
            "You may need to remove and re-add your accounts."
        )
    elif error_type_name.startswith("Account") and "Error" in error_type_name:
        if "NotFound" in error_type_name:
            return "The requested account could not be found."
        elif "Creation" in error_type_name:
            return (
                "Failed to create the account. Please check:\n\n"
                "• All required information was provided\n"
                "• Your account credentials are correct\n"
                "• The account doesn't already exist"
            )
        else:
            return (
                "An error occurred while managing your account. "
                "Please try again."
            )
    elif error_type_name.startswith("Folder") and "Error" in error_type_name:
        if "Creation" in error_type_name:
            return "Could not create the folder. The folder may already exist or the name may be invalid."
        elif "Deletion" in error_type_name:
            return "Could not delete the folder. Some folders cannot be deleted."
        elif "Rename" in error_type_name:
            return "Could not rename the folder. The new name may be invalid or already in use."
        else:
            return "An error occurred while managing the folder. Please try again."
    
    # Handle standard Python exceptions
    elif isinstance(exc, ConnectionError):
        return (
            "Could not connect to the server. Please check your internet "
            "connection and try again."
        )
    elif isinstance(exc, TimeoutError):
        return (
            "The operation timed out. This might be due to a slow connection "
            "or server issues. Please try again."
        )
    elif isinstance(exc, PermissionError):
        return (
            "Permission denied. Please check that you have the necessary "
            "permissions to perform this operation."
        )
    elif isinstance(exc, FileNotFoundError):
        return (
            "A required file could not be found. The application may need "
            "to be reinstalled or the data directory may be missing."
        )
    elif isinstance(exc, ValueError):
        return f"Invalid input: {str(exc)}"
    elif isinstance(exc, KeyError):
        return f"Missing required information: {str(exc)}"
    
    # Fallback for unknown exceptions
    else:
        error_msg = str(exc) if str(exc) else "Unknown error"
        return f"An error occurred: {error_msg}"

