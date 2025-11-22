"""
Helper functions for AccountDialog to wire up with business logic.

This module provides factory functions that create the callables needed
by AccountDialog, keeping the UI layer clean and testable.
"""
from typing import Callable, List
from email_client.models import EmailAccount
from email_client.auth.accounts import (
    list_accounts,
    set_default_account,
    delete_account,
    create_oauth_account
)
from email_client.auth.oauth import OAuthProvider, GoogleOAuthProvider, OAuthError
from email_client.auth.oauth import TokenBundle


def get_account_dialog_callables() -> dict:
    """
    Get all callables needed by AccountDialog.
    
    Returns:
        Dictionary with keys:
        - list_accounts_fn: Callable[[], List[EmailAccount]]
        - set_default_account_fn: Callable[[int], None]
        - delete_account_fn: Callable[[int], None]
        - get_oauth_provider_fn: Callable[[str], OAuthProvider]
        - create_oauth_account_fn: Callable[[str, TokenBundle, str, str], EmailAccount]
        - open_browser_fn: Callable[[str], None] (optional)
    """
    def list_accounts_wrapper() -> List[EmailAccount]:
        """Wrapper for list_accounts."""
        return list_accounts()
    
    def set_default_account_wrapper(account_id: int) -> None:
        """Wrapper for set_default_account."""
        set_default_account(account_id)
    
    def delete_account_wrapper(account_id: int) -> None:
        """Wrapper for delete_account."""
        delete_account(account_id)
    
    def get_oauth_provider_wrapper(provider_name: str) -> OAuthProvider:
        """
        Get OAuth provider for a given provider name.
        
        Args:
            provider_name: Provider name ('gmail', 'outlook', 'yahoo').
            
        Returns:
            OAuthProvider instance.
            
        Raises:
            ValueError: If provider is not supported.
        """
        provider_name_lower = provider_name.lower()
        
        if provider_name_lower in ['gmail', 'google']:
            return GoogleOAuthProvider()
        elif provider_name_lower in ['outlook', 'microsoft']:
            # TODO: Implement OutlookOAuthProvider when available
            raise ValueError(f"OAuth provider for '{provider_name}' not yet implemented")
        elif provider_name_lower in ['yahoo']:
            # TODO: Implement YahooOAuthProvider when available
            raise ValueError(f"OAuth provider for '{provider_name}' not yet implemented")
        else:
            raise ValueError(f"Unknown OAuth provider: {provider_name}")
    
    def create_oauth_account_wrapper(
        provider_name: str,
        token_bundle: TokenBundle,
        email: str,
        display_name: str
    ) -> EmailAccount:
        """Wrapper for create_oauth_account."""
        return create_oauth_account(provider_name, token_bundle, email, display_name)
    
    def open_browser_wrapper(url: str) -> None:
        """
        Open URL in default browser.
        
        Args:
            url: The URL to open.
        """
        import webbrowser
        webbrowser.open(url)
    
    return {
        'list_accounts_fn': list_accounts_wrapper,
        'set_default_account_fn': set_default_account_wrapper,
        'delete_account_fn': delete_account_wrapper,
        'get_oauth_provider_fn': get_oauth_provider_wrapper,
        'create_oauth_account_fn': create_oauth_account_wrapper,
        'open_browser_fn': open_browser_wrapper,
    }

