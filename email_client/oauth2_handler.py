"""
OAuth2 handler for Gmail and Outlook authentication
"""
import json
import webbrowser
import http.server
import socketserver
import urllib.parse
from typing import Optional, Dict
import requests
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import config


class OAuth2Handler:
    """Handles OAuth2 authentication for email providers"""
    
    def __init__(self, provider: str):
        self.provider = provider.lower()
        self.token: Optional[Dict] = None
        self._server: Optional[socketserver.TCPServer] = None
        self._code: Optional[str] = None
    
    def authenticate_gmail(self) -> Optional[str]:
        """Authenticate with Gmail using OAuth2"""
        if not config.GMAIL_CLIENT_ID or not config.GMAIL_CLIENT_SECRET:
            raise ValueError("Gmail OAuth2 credentials not configured")
        
        try:
            # Create OAuth flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": config.GMAIL_CLIENT_ID,
                        "client_secret": config.GMAIL_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [config.OAUTH_REDIRECT_URI]
                    }
                },
                scopes=config.GMAIL_SCOPES,
                redirect_uri=config.OAUTH_REDIRECT_URI
            )
            
            # Get authorization URL
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            # Start local server to receive callback
            self._start_callback_server()
            
            # Open browser for authentication
            webbrowser.open(auth_url)
            
            # Wait for callback
            self._wait_for_callback()
            
            if not self._code:
                return None
            
            # Exchange code for token
            flow.fetch_token(code=self._code)
            credentials = flow.credentials
            
            # Store token
            self.token = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            return json.dumps(self.token)
        except Exception as e:
            print(f"Gmail OAuth2 error: {e}")
            return None
        finally:
            self._stop_callback_server()
    
    def authenticate_outlook(self) -> Optional[str]:
        """Authenticate with Outlook using OAuth2"""
        if not config.OUTLOOK_CLIENT_ID or not config.OUTLOOK_CLIENT_SECRET:
            raise ValueError("Outlook OAuth2 credentials not configured")
        
        try:
            # Build authorization URL
            auth_url = (
                f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
                f"client_id={config.OUTLOOK_CLIENT_ID}&"
                f"response_type=code&"
                f"redirect_uri={urllib.parse.quote(config.OAUTH_REDIRECT_URI)}&"
                f"response_mode=query&"
                f"scope={' '.join(config.OUTLOOK_SCOPES)}"
            )
            
            # Start local server to receive callback
            self._start_callback_server()
            
            # Open browser for authentication
            webbrowser.open(auth_url)
            
            # Wait for callback
            self._wait_for_callback()
            
            if not self._code:
                return None
            
            # Exchange code for token
            token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            token_data = {
                'client_id': config.OUTLOOK_CLIENT_ID,
                'client_secret': config.OUTLOOK_CLIENT_SECRET,
                'code': self._code,
                'redirect_uri': config.OAUTH_REDIRECT_URI,
                'grant_type': 'authorization_code',
                'scope': ' '.join(config.OUTLOOK_SCOPES)
            }
            
            response = requests.post(token_url, data=token_data)
            if response.status_code == 200:
                token_response = response.json()
                self.token = {
                    'access_token': token_response.get('access_token'),
                    'refresh_token': token_response.get('refresh_token'),
                    'token_type': token_response.get('token_type'),
                    'expires_in': token_response.get('expires_in')
                }
                return json.dumps(self.token)
            else:
                print(f"Outlook token exchange failed: {response.text}")
                return None
        except Exception as e:
            print(f"Outlook OAuth2 error: {e}")
            return None
        finally:
            self._stop_callback_server()
    
    def _start_callback_server(self):
        """Start local HTTP server to receive OAuth callback"""
        class CallbackHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, oauth_handler=None, **kwargs):
                self.oauth_handler = oauth_handler
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                if '/callback' in self.path:
                    # Parse query parameters
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    
                    # Extract code
                    if 'code' in params:
                        self.oauth_handler._code = params['code'][0]
                    
                    # Send response
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<html><body><h1>Authentication successful!</h1><p>You can close this window.</p></body></html>')
                else:
                    self.send_response(404)
                    self.end_headers()
        
        handler = lambda *args, **kwargs: CallbackHandler(*args, oauth_handler=self, **kwargs)
        self._server = socketserver.TCPServer(("", config.OAUTH_REDIRECT_PORT), handler)
        self._server.timeout = 1
    
    def _wait_for_callback(self, timeout: int = 300):
        """Wait for OAuth callback"""
        import time
        start_time = time.time()
        while not self._code and (time.time() - start_time) < timeout:
            self._server.handle_request()
            if self._code:
                break
    
    def _stop_callback_server(self):
        """Stop the callback server"""
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except:
                pass
            self._server = None
    
    def get_access_token(self) -> Optional[str]:
        """Get current access token"""
        if not self.token:
            return None
        
        if self.provider == 'gmail':
            return self.token.get('token')
        elif self.provider == 'outlook':
            return self.token.get('access_token')
        return None
    
    def refresh_token(self) -> bool:
        """Refresh the access token if expired"""
        if not self.token:
            return False
        
        try:
            if self.provider == 'gmail':
                # Use google-auth library to refresh
                from google.oauth2.credentials import Credentials
                creds = Credentials(
                    token=self.token.get('token'),
                    refresh_token=self.token.get('refresh_token'),
                    token_uri=self.token.get('token_uri'),
                    client_id=self.token.get('client_id'),
                    client_secret=self.token.get('client_secret')
                )
                creds.refresh(Request())
                self.token['token'] = creds.token
                return True
            elif self.provider == 'outlook':
                # Refresh Outlook token
                token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
                token_data = {
                    'client_id': config.OUTLOOK_CLIENT_ID,
                    'client_secret': config.OUTLOOK_CLIENT_SECRET,
                    'refresh_token': self.token.get('refresh_token'),
                    'grant_type': 'refresh_token',
                    'scope': ' '.join(config.OUTLOOK_SCOPES)
                }
                response = requests.post(token_url, data=token_data)
                if response.status_code == 200:
                    token_response = response.json()
                    self.token['access_token'] = token_response.get('access_token')
                    if 'refresh_token' in token_response:
                        self.token['refresh_token'] = token_response.get('refresh_token')
                    return True
        except Exception as e:
            print(f"Token refresh error: {e}")
        
        return False

