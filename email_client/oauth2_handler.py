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
import config

# Lazy import for Google OAuth - only import when needed
try:
    from google_auth_oauthlib.flow import Flow
    from google.auth.transport.requests import Request
    GOOGLE_OAUTH_AVAILABLE = True
except ImportError:
    GOOGLE_OAUTH_AVAILABLE = False
    Flow = None
    Request = None


class OAuth2Handler:
    """Handles OAuth2 authentication for email providers"""
    
    def __init__(self, provider: str):
        self.provider = provider.lower()
        self.token: Optional[Dict] = None
        self._server: Optional[socketserver.TCPServer] = None
        self._code: Optional[str] = None
    
    def authenticate_gmail(self) -> Optional[str]:
        """Authenticate with Gmail using OAuth2"""
        if not GOOGLE_OAUTH_AVAILABLE:
            raise ImportError(
                "google-auth-oauthlib is not installed. "
                "Please install it with: pip install google-auth-oauthlib"
            )
        
        if not config.GMAIL_CLIENT_ID or not config.GMAIL_CLIENT_SECRET:
            raise ValueError("Gmail OAuth2 credentials not configured")
        
        self._code = None
        self._error = None
        
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
            
            # Give server a moment to be ready
            import time
            time.sleep(0.5)
            
            # Open browser for authentication
            print(f"Opening browser for authentication: {auth_url}")
            webbrowser.open(auth_url)
            
            # Wait for callback (with timeout)
            callback_received = self._wait_for_callback(timeout=300)  # 5 minute timeout
            
            # Check for errors
            if self._error:
                print(f"❌ OAuth error: {self._error}")
                return None
            
            if not callback_received or not self._code:
                print("❌ OAuth callback timeout or cancelled")
                return None
            
            # Exchange code for token
            try:
                print(f"🔄 Exchanging authorization code for token...")
                # The fetch_token call makes an HTTP request to Google's token endpoint
                # This should complete quickly (< 5 seconds) but we'll let it run
                # Since we're in a background thread, this won't block the UI
                
                # Suppress scope mismatch warnings - Google automatically adds 'openid' scope
                # when using userinfo scopes, which is expected behavior, not an error
                import warnings
                import sys
                
                credentials = None
                token_exchange_exception = None
                
                # Suppress warnings completely during token exchange
                # AND catch all exceptions (including warnings raised as exceptions)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    old_showwarning = warnings.showwarning
                    warnings.showwarning = lambda *args, **kwargs: None
                    
                    try:
                        flow.fetch_token(code=self._code)
                        credentials = flow.credentials
                    except Exception as e:
                        # Catch exceptions including scope warnings
                        # oauthlib may set credentials before raising warnings
                        credentials = flow.credentials
                        if not credentials or not credentials.token:
                            token_exchange_exception = e
                    finally:
                        warnings.showwarning = old_showwarning
                        
                # Final check - if we don't have credentials, try one more time
                if not credentials:
                    credentials = flow.credentials
                
                # Verify we have credentials
                if not credentials:
                    error_msg = "No credentials object returned after token exchange"
                    if token_exchange_exception:
                        error_msg += f": {str(token_exchange_exception)}"
                    self._error = error_msg
                    return None
                    
                if not credentials.token:
                    self._error = "Token exchange failed: No access token in credentials"
                    return None
                
                # Check for required IMAP scope
                granted_scopes = credentials.scopes if credentials.scopes else []
                has_imap_scope = 'https://mail.google.com/' in granted_scopes
                
                if not has_imap_scope:
                    print("⚠️  WARNING: Token does NOT include https://mail.google.com/ scope! IMAP will fail.")
                
                # Store token
                self.token = {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                }
                
                # Fetch user info from Google to get email address
                # This is CRITICAL - we need the email address to create the account
                user_info = self._fetch_google_user_info(credentials.token)
                
                # Store user info in token dict for easy access
                if user_info and user_info.get('email'):
                    # Strip whitespace from email to prevent XOAUTH2 authentication failures
                    user_email = user_info.get('email', '').strip()
                    self.token['user_email'] = user_email
                    self.token['user_name'] = user_info.get('name', '').strip() if user_info.get('name') else ''
                    self.token['user_picture'] = user_info.get('picture', '')
                else:
                    self._error = "Failed to fetch user email from Google. Please ensure you granted all required permissions."
                    return None
                
                # Include expiry time if available
                if hasattr(credentials, 'expiry') and credentials.expiry:
                    from datetime import datetime, timezone
                    now_utc = datetime.now(timezone.utc)
                    expiry_utc = credentials.expiry.replace(tzinfo=timezone.utc) if credentials.expiry.tzinfo is None else credentials.expiry
                    expires_in = int((expiry_utc - now_utc).total_seconds())
                    
                    # Validate expires_in (Google tokens are ~3600 seconds)
                    if expires_in > 0 and expires_in <= 7200:
                        self.token['expires_in'] = expires_in
                    else:
                        self.token['expires_in'] = 3600
                else:
                    self.token['expires_in'] = 3600
                
                token_json = json.dumps(self.token)
                return token_json
            except Exception as e:
                if not hasattr(self, '_error') or not self._error:
                    self._error = f"OAuth error: {str(e)}"
                return None
        finally:
            # Always stop the callback server
            self._stop_callback_server()
    
    def authenticate_outlook(self) -> Optional[str]:
        """Authenticate with Outlook using OAuth2"""
        if not config.OUTLOOK_CLIENT_ID or not config.OUTLOOK_CLIENT_SECRET:
            raise ValueError("Outlook OAuth2 credentials not configured")
        
        self._code = None
        self._error = None
        
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
            
            # Give server a moment to be ready
            import time
            time.sleep(0.5)
            
            # Open browser for authentication
            print(f"Opening browser for authentication: {auth_url}")
            webbrowser.open(auth_url)
            
            # Wait for callback (with timeout)
            callback_received = self._wait_for_callback(timeout=300)  # 5 minute timeout
            
            # Check for errors
            if self._error:
                print(f"OAuth error: {self._error}")
                return None
            
            if not callback_received or not self._code:
                print("OAuth callback timeout or cancelled")
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
            
            try:
                response = requests.post(token_url, data=token_data, timeout=30)
                if response.status_code == 200:
                    token_response = response.json()
                    self.token = {
                        'access_token': token_response.get('access_token'),
                        'refresh_token': token_response.get('refresh_token'),
                        'token_type': token_response.get('token_type'),
                        'expires_in': token_response.get('expires_in')
                    }
                    print("Outlook OAuth2 authentication successful")
                    return json.dumps(self.token)
                else:
                    error_msg = response.text
                    print(f"Outlook token exchange failed: {error_msg}")
                    return None
            except requests.exceptions.Timeout:
                print("Token exchange request timed out")
                return None
            except Exception as e:
                print(f"Token exchange error: {e}")
                return None
                
        except Exception as e:
            print(f"Outlook OAuth2 error: {e}")
            return None
        finally:
            # Always stop the callback server
            self._stop_callback_server()
    
    def _start_callback_server(self):
        """Start local HTTP server to receive OAuth callback"""
        class CallbackHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, oauth_handler=None, **kwargs):
                self.oauth_handler = oauth_handler
                super().__init__(*args, **kwargs)
            
            def log_message(self, format, *args):
                """Suppress default logging"""
                pass
            
            def do_GET(self):
                # Only process /callback path
                if '/callback' not in self.path:
                    # Handle favicon and other requests
                    if '/favicon.ico' in self.path:
                        self.send_response(204)  # No content
                        self.end_headers()
                    else:
                        self.send_response(404)
                        self.end_headers()
                    return
                
                try:
                    # Parse query parameters
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    
                    print(f"OAuth callback received: {self.path}")
                    
                    # Check for error in callback
                    if 'error' in params:
                        error = params['error'][0]
                        error_description = params.get('error_description', [''])[0]
                        
                        print(f"OAuth error in callback: {error} - {error_description}")
                        
                        # Handle user cancellation
                        if error == 'access_denied':
                            self.oauth_handler._error = "Authentication was cancelled by user."
                        else:
                            self.oauth_handler._error = f"OAuth error: {error}. {error_description}"
                        
                        # Send error response
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        error_html = (
                            b'<html><head><title>Authentication Failed</title></head><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">'
                            b'<h1 style="color: #d32f2f;">Authentication Failed</h1>'
                            b'<p>You can close this window and try again.</p>'
                            b'<script>setTimeout(function(){window.close();}, 3000);</script>'
                            b'</body></html>'
                        )
                        self.wfile.write(error_html)
                        self.wfile.flush()
                        return
                    
                    # Extract code
                    if 'code' in params:
                        code = params['code'][0]
                        print(f"OAuth callback: Code received in callback handler: {code[:20]}...")
                        
                        # Set the code FIRST - this is what the waiting thread checks
                        self.oauth_handler._code = code
                        print(f"OAuth callback: Code has been set, waiting thread should detect it now")
                        
                        # Send success response IMMEDIATELY
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        success_html = (
                            b'<html><head><title>Authentication Successful</title></head><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">'
                            b'<h1 style="color: #4caf50;">Authentication Successful!</h1>'
                            b'<p>You can close this window.</p>'
                            b'<script>setTimeout(function(){window.close();}, 2000);</script>'
                            b'</body></html>'
                        )
                        self.wfile.write(success_html)
                        self.wfile.flush()
                        print("OAuth callback: Success response sent to browser, connection closed")
                    else:
                        # No code, no error - might be a redirect issue
                        print("Callback received but no code or error found")
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(
                            b'<html><head><title>Waiting</title></head><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">'
                            b'<h1>Waiting for authentication...</h1></body></html>'
                        )
                        self.wfile.flush()
                except Exception as e:
                    print(f"Error processing callback: {e}")
                    import traceback
                    traceback.print_exc()
                    self.oauth_handler._error = f"Error processing callback: {str(e)}"
                    self.send_response(500)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(
                        b'<html><head><title>Error</title></head><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">'
                        b'<h1 style="color: #d32f2f;">Error</h1><p>An error occurred. Please try again.</p></body></html>'
                    )
                    self.wfile.flush()
        
        # Initialize error tracking
        self._error = None
        
        handler = lambda *args, **kwargs: CallbackHandler(*args, oauth_handler=self, **kwargs)
        try:
            # Use ThreadingMixIn for better request handling
            class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
                allow_reuse_address = True
                daemon_threads = True
            
            self._server = ThreadedTCPServer(("", config.OAUTH_REDIRECT_PORT), handler)
            self._server.timeout = 0.5
            print(f"Callback server started on port {config.OAUTH_REDIRECT_PORT}")
        except OSError as e:
            if "Address already in use" in str(e):
                raise RuntimeError(f"Port {config.OAUTH_REDIRECT_PORT} is already in use. Please close any other applications using this port.")
            raise
    
    def _wait_for_callback(self, timeout: int = 300):
        """Wait for OAuth callback with proper timeout and error handling"""
        import time
        import threading
        start_time = time.time()
        
        print(f"Waiting for OAuth callback (timeout: {timeout}s)...")
        
        # Use a threading event to ensure proper synchronization
        callback_received = threading.Event()
        
        # Check more frequently for the code
        check_interval = 0.05  # Check every 50ms instead of 100ms
        
        while (time.time() - start_time) < timeout:
            # Check for error first (user cancellation, etc.)
            if hasattr(self, '_error') and self._error:
                print(f"OAuth error received: {self._error}")
                return False
            
            # Check if we got the code (check FIRST before handling requests)
            if self._code:
                print(f"OAuth callback received successfully - code detected")
                return True
            
            # Handle one request (non-blocking with timeout)
            # With ThreadingMixIn, each request is handled in its own thread
            try:
                self._server.handle_request()
            except Exception as e:
                # Log but continue - might be connection issues
                if "timed out" not in str(e).lower() and "Address already in use" not in str(e):
                    print(f"Error handling callback request: {e}")
            
            # Check again immediately after handling request (code might have been set)
            if self._code:
                print(f"OAuth callback received successfully - code detected after request")
                return True
            
            # Smaller sleep to check more frequently
            time.sleep(check_interval)
        
        # Timeout reached
        if not self._code:
            if not hasattr(self, '_error') or not self._error:
                self._error = "Authentication timeout. Please try again."
            print(f"OAuth callback timeout after {timeout}s - no code received")
            return False
        
        return True
    
    def _stop_callback_server(self):
        """Stop the callback server gracefully"""
        if self._server:
            try:
                print("_stop_callback_server: Starting server shutdown...")
                import sys
                sys.stdout.flush()
                
                # Get reference to server before clearing
                server = self._server
                self._server = None  # Clear reference immediately to prevent new requests
                
                # With ThreadingMixIn and daemon_threads=True, shutdown() blocks waiting for threads
                # Since we're daemon threads, we can just close the socket and let them exit naturally
                # Close the server socket directly - this is non-blocking
                server.server_close()
                print("_stop_callback_server: Server socket closed (daemon threads will exit automatically)")
                sys.stdout.flush()
                
                # Don't call shutdown() - it blocks waiting for threads to finish
                # Daemon threads will exit when the main thread exits
                
            except Exception as e:
                print(f"_stop_callback_server: Error stopping callback server: {e}")
                import sys
                sys.stdout.flush()
                import traceback
                traceback.print_exc()
                sys.stdout.flush()
                # Clear server reference even on error
                self._server = None
    
    def _fetch_google_user_info(self, access_token: str) -> Optional[Dict]:
        """Fetch user information from Google's userinfo API"""
        try:
            url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {
                'Authorization': f'Bearer {access_token}'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_info = response.json()
                print(f"Successfully fetched user info from Google: {user_info.get('email', 'unknown')}")
                return user_info
            else:
                print(f"Failed to fetch user info: HTTP {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error fetching user info from Google: {e}")
            import traceback
            traceback.print_exc()
            return None
    
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

