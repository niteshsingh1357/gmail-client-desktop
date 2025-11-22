"""
OAuth2 authentication handling for email providers.

This module provides an abstract base class for OAuth providers and concrete
implementations for various email service providers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List
from email_client.config import OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET


@dataclass(slots=True)
class TokenBundle:
    """Container for OAuth2 tokens."""
    access_token: str
    refresh_token: Optional[str]
    expires_at: datetime


class OAuthError(Exception):
    """Base exception for OAuth-related errors."""
    pass


class TokenRefreshError(OAuthError):
    """Raised when token refresh fails."""
    pass


class OAuthProvider(ABC):
    """Abstract base class for OAuth2 providers."""
    
    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """
        Generate the authorization URL for the OAuth2 flow.
        
        Args:
            state: A state parameter for CSRF protection.
            
        Returns:
            The authorization URL that the user should visit.
        """
        pass
    
    @abstractmethod
    def exchange_code_for_tokens(self, code: str) -> TokenBundle:
        """
        Exchange an authorization code for access and refresh tokens.
        
        Args:
            code: The authorization code received from the OAuth callback.
            
        Returns:
            A TokenBundle containing the access token, refresh token, and expiration.
            
        Raises:
            OAuthError: If the token exchange fails.
        """
        pass
    
    @abstractmethod
    def refresh_tokens(self, refresh_token: str) -> TokenBundle:
        """
        Refresh an expired access token using a refresh token.
        
        Args:
            refresh_token: The refresh token to use for obtaining a new access token.
            
        Returns:
            A TokenBundle containing the new access token, refresh token, and expiration.
            
        Raises:
            TokenRefreshError: If the token refresh fails.
        """
        pass


class GoogleOAuthProvider(OAuthProvider):
    """
    OAuth2 provider for Google/Gmail accounts.
    
    Uses the installed-app OAuth2 flow for desktop applications.
    """
    
    # Google OAuth2 endpoints
    AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    
    # Required scopes for Gmail access
    DEFAULT_SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
    ]
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: str = "http://localhost:8080/callback",
        scopes: Optional[List[str]] = None
    ):
        """
        Initialize the Google OAuth provider.
        
        Args:
            client_id: OAuth client ID (defaults to OAUTH_CLIENT_ID from config).
            client_secret: OAuth client secret (defaults to OAUTH_CLIENT_SECRET from config).
            redirect_uri: The redirect URI registered with Google (defaults to localhost).
            scopes: List of OAuth scopes to request (defaults to Gmail scopes).
        """
        self.client_id = client_id or OAUTH_CLIENT_ID
        self.client_secret = client_secret or OAUTH_CLIENT_SECRET
        self.redirect_uri = redirect_uri
        self.scopes = scopes or self.DEFAULT_SCOPES
        
        if not self.client_id or not self.client_secret:
            raise ValueError("OAuth client ID and secret must be provided")
    
    def get_authorization_url(self, state: str) -> str:
        """
        Generate the Google OAuth2 authorization URL.
        
        Args:
            state: A state parameter for CSRF protection.
            
        Returns:
            The authorization URL for the user to visit.
        """
        from urllib.parse import urlencode
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "response_type": "code",
            "access_type": "offline",  # Required to get refresh token
            "prompt": "consent",  # Force consent to get refresh token
            "state": state,
        }
        
        return f"{self.AUTHORIZATION_BASE_URL}?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, code: str) -> TokenBundle:
        """
        Exchange an authorization code for tokens.
        
        Args:
            code: The authorization code from the OAuth callback.
            
        Returns:
            A TokenBundle with access token, refresh token, and expiration.
            
        Raises:
            OAuthError: If the token exchange fails.
        """
        # TODO: Implement actual HTTP call to Google's token endpoint
        # This should make a POST request to self.TOKEN_ENDPOINT with:
        # - client_id
        # - client_secret
        # - code
        # - redirect_uri
        # - grant_type: "authorization_code"
        #
        # Example:
        # response = requests.post(
        #     self.TOKEN_ENDPOINT,
        #     data={
        #         "client_id": self.client_id,
        #         "client_secret": self.client_secret,
        #         "code": code,
        #         "redirect_uri": self.redirect_uri,
        #         "grant_type": "authorization_code",
        #     }
        # )
        # response.raise_for_status()
        # token_data = response.json()
        #
        # expires_at = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))
        # return TokenBundle(
        #     access_token=token_data["access_token"],
        #     refresh_token=token_data.get("refresh_token"),
        #     expires_at=expires_at,
        # )
        
        raise NotImplementedError(
            "Token exchange not yet implemented. "
            "TODO: Wire up HTTP call to Google's token endpoint."
        )
    
    def refresh_tokens(self, refresh_token: str) -> TokenBundle:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: The refresh token to use.
            
        Returns:
            A TokenBundle with new access token, refresh token, and expiration.
            
        Raises:
            TokenRefreshError: If the token refresh fails.
        """
        # TODO: Implement actual HTTP call to Google's token endpoint
        # This should make a POST request to self.TOKEN_ENDPOINT with:
        # - client_id
        # - client_secret
        # - refresh_token
        # - grant_type: "refresh_token"
        #
        # Example:
        # response = requests.post(
        #     self.TOKEN_ENDPOINT,
        #     data={
        #         "client_id": self.client_id,
        #         "client_secret": self.client_secret,
        #         "refresh_token": refresh_token,
        #         "grant_type": "refresh_token",
        #     }
        # )
        # response.raise_for_status()
        # token_data = response.json()
        #
        # expires_at = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))
        # return TokenBundle(
        #     access_token=token_data["access_token"],
        #     refresh_token=token_data.get("refresh_token", refresh_token),  # May not be returned
        #     expires_at=expires_at,
        # )
        
        raise NotImplementedError(
            "Token refresh not yet implemented. "
            "TODO: Wire up HTTP call to Google's token endpoint."
        )

