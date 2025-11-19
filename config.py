"""
Configuration settings for the Email Desktop Client
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Application paths
APP_NAME = "EmailDesktopClient"
BASE_DIR = Path.home() / ".email_desktop_client"
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / "cache"
ATTACHMENTS_DIR = BASE_DIR / "attachments"
DB_PATH = DATA_DIR / "email_client.db"

# Create directories if they don't exist
for directory in [BASE_DIR, DATA_DIR, CACHE_DIR, ATTACHMENTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Encryption settings
ENCRYPTION_KEY_FILE = DATA_DIR / ".encryption_key"
ENCRYPTION_ALGORITHM = "AES-256"

# Email settings
DEFAULT_SYNC_INTERVAL = 300  # 5 minutes in seconds
MAX_CACHE_SIZE_MB = 500
CACHE_RETENTION_DAYS = 30

# IMAP/SMTP settings
IMAP_TIMEOUT = 30
SMTP_TIMEOUT = 30
MAX_EMAILS_PER_SYNC = 100

# OAuth2 settings
OAUTH_REDIRECT_PORT = 8080
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_REDIRECT_PORT}/callback"

# Gmail OAuth2
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Outlook OAuth2
OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID", "")
OUTLOOK_CLIENT_SECRET = os.getenv("OUTLOOK_CLIENT_SECRET", "")
OUTLOOK_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.ReadWrite",
]

# UI settings
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600

# Font settings
DEFAULT_FONT_SIZE = 12
MIN_FONT_SIZE = 12

