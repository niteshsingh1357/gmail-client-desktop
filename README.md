# Email Desktop Client

A modern, cross-platform desktop email client built with Python and PyQt5. Manage multiple email accounts from a single interface with support for OAuth2 authentication, offline caching, and secure local storage.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database Structure](#database-structure)
- [Data Flow](#data-flow)
- [Architecture](#architecture)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

## Features

- **Multi-Account Support**: Add and manage multiple email accounts from different providers
- **OAuth2 Authentication**: Secure, token-based authentication for Gmail and Outlook
- **IMAP/SMTP Support**: Works with Gmail, Outlook, Yahoo, and any custom IMAP/SMTP server
- **Offline Access**: Local SQLite cache allows viewing emails without an internet connection
- **Rich Text Composition**: Compose emails with formatting (bold, italic, underline) and attachments
- **Search & Filter**: Quickly find emails by subject, sender, content, or date
- **Pagination**: Efficient email browsing with 50 emails per page
- **Read/Unread Management**: Mark emails as read/unread, sync status with server
- **Folder Management**: Create, rename, and delete custom folders; move emails between folders
- **Server-Side Operations**: All operations (read, delete, move) sync with IMAP server
- **Secure Storage**: All credentials and tokens encrypted locally using AES-256
- **Automatic Token Refresh**: OAuth tokens are automatically refreshed when expired

## Installation

### Prerequisites

- **Python 3.8 or higher** (Python 3.9+ recommended)
- **Git** (for cloning the repository)
- **Internet connection** (for initial setup and email synchronization)

### Supported Operating Systems

- **macOS** 10.14 or later
- **Linux** (Ubuntu 18.04+, Debian 10+, Fedora 30+, etc.)
- **Windows** 10 or later

### Step-by-Step Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd gmail-client-desktop
   ```

2. **Create and activate a virtual environment:**

   **macOS/Linux:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

   **Windows (PowerShell):**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

   **Windows (Command Prompt):**
   ```cmd
   python -m venv venv
   venv\Scripts\activate.bat
   ```

   **Note:** Your terminal prompt should now show `(venv)` indicating the virtual environment is active.

3. **Install dependencies:**

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   This will install:
   - PyQt5 (GUI framework)
   - cryptography (encryption)
   - requests (HTTP client)
   - google-auth (OAuth2 for Gmail)
   - email-validator (email validation)
   - python-dotenv (environment variable management)

4. **Initialize the database:**

   ```bash
   python -c "from email_client.storage.db import init_db; init_db()"
   ```

   The database will be created at `~/.email_client/email_client.db` (or `%USERPROFILE%\.email_client\email_client.db` on Windows).

5. **Set up OAuth credentials (required for Gmail/Outlook):**

   Create a `.env` file in the project root:

   ```env
   # Gmail OAuth2
   GMAIL_CLIENT_ID=your_gmail_client_id_here
   GMAIL_CLIENT_SECRET=your_gmail_client_secret_here
   
   # Outlook OAuth2 (optional)
   OUTLOOK_CLIENT_ID=your_outlook_client_id_here
   OUTLOOK_CLIENT_SECRET=your_outlook_client_secret_here
   ```

   See the [Configuration](#configuration) section for detailed OAuth setup instructions.

6. **Run the application:**

```bash
python main.py
```

## Configuration

### Environment Variables

The application reads configuration from environment variables and a `.env` file (if present). Create a `.env` file in the project root:

```env
# OAuth2 Credentials (Required for Gmail/Outlook OAuth)
GMAIL_CLIENT_ID=your_gmail_client_id_here
GMAIL_CLIENT_SECRET=your_gmail_client_secret_here
OUTLOOK_CLIENT_ID=your_outlook_client_id_here
OUTLOOK_CLIENT_SECRET=your_outlook_client_secret_here

# Database Path (Optional - defaults to ~/.email_client/email_client.db)
SQLITE_DB_PATH=/custom/path/to/email_client.db
```

### OAuth2 Setup

#### Gmail OAuth2

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. **Configure OAuth consent screen**:
   - Go to "APIs & Services" → "OAuth consent screen"
   - Choose "External" (unless you have a Google Workspace account)
   - Fill in required fields (App name, User support email, Developer contact)
   - Click "Scopes" → "ADD OR REMOVE SCOPES"
   - Add these scopes:
     - `https://mail.google.com/` (REQUIRED for IMAP/SMTP XOAUTH2 access)
     - `https://www.googleapis.com/auth/gmail.readonly`
     - `https://www.googleapis.com/auth/gmail.send`
     - `https://www.googleapis.com/auth/gmail.modify`
     - `https://www.googleapis.com/auth/userinfo.email`
     - `https://www.googleapis.com/auth/userinfo.profile`
     - `openid`
   - Add test users (your email address) if app is in Testing mode
   - Save and continue

5. **Create OAuth 2.0 Client ID**:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - **Choose "Web application" as the application type**
   - **Add authorized redirect URI:** `http://localhost:8080/callback`
   - Click "Create" and copy the Client ID and Client Secret to your `.env` file

#### Outlook OAuth2

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to "Azure Active Directory" → "App registrations"
3. Click "New registration"
4. Set redirect URI to: `http://localhost:8080/callback`
5. Go to "Certificates & secrets" → "New client secret"
6. Copy the Application (client) ID and Client secret to your `.env` file

### Custom IMAP/SMTP Setup

For custom email servers (Yahoo, corporate email, etc.):

1. **Select "Custom IMAP/SMTP"** in the provider dropdown when adding an account
2. **Enter server information**:
   - IMAP Server: e.g., `imap.mail.yahoo.com`
   - IMAP Port: Usually `993` (SSL) or `143` (STARTTLS)
   - SMTP Server: e.g., `smtp.mail.yahoo.com`
   - SMTP Port: Usually `587` (STARTTLS) or `465` (SSL)
   - Use TLS/SSL: Enable for encrypted connections

3. **Common Server Settings**:

   | Provider | IMAP Server | IMAP Port | SMTP Server | SMTP Port | Notes |
   |----------|-------------|-----------|-------------|-----------|-------|
   | Gmail | imap.gmail.com | 993 | smtp.gmail.com | 587 | App password required |
   | Outlook | outlook.office365.com | 993 | smtp.office365.com | 587 | - |
   | Yahoo | imap.mail.yahoo.com | 993 | smtp.mail.yahoo.com | 587 | App password required |
   | Zoho | imap.zoho.com | 993 | smtp.zoho.com | 587 | - |

   **Note:** For Gmail and Yahoo, you'll need to generate an App Password instead of using your regular password.

## Database Structure

The application uses SQLite for local email caching. The database is stored at `~/.email_client/email_client.db` by default.

### Schema

#### Accounts Table
```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    email_address TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    imap_host TEXT NOT NULL,
    smtp_host TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_default INTEGER DEFAULT 0
)
```

#### Folders Table
```sql
CREATE TABLE folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    server_path TEXT NOT NULL,
    unread_count INTEGER DEFAULT 0,
    is_system_folder INTEGER DEFAULT 0,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    UNIQUE(account_id, server_path)
)
```

#### Emails Table
```sql
CREATE TABLE emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    folder_id INTEGER NOT NULL,
    uid_on_server INTEGER NOT NULL,
    sender TEXT NOT NULL,
    recipients TEXT NOT NULL,
    subject TEXT,
    preview_text TEXT,
    sent_at TIMESTAMP,
    received_at TIMESTAMP,
    is_read INTEGER DEFAULT 0,
    has_attachments INTEGER DEFAULT 0,
    flags TEXT,
    body_plain TEXT,
    body_html TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folders(folder_id) ON DELETE CASCADE,
    UNIQUE(account_id, folder_id, uid_on_server)
)
```

#### Attachments Table
```sql
CREATE TABLE attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER DEFAULT 0,
    local_path TEXT,
    is_encrypted INTEGER DEFAULT 0,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
)
```

#### Settings Table
```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### Tokens Table
```sql
CREATE TABLE tokens (
    account_id INTEGER PRIMARY KEY,
    encrypted_token_bundle TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
)
```

### Indexes

The database includes indexes for optimal query performance:
- `idx_accounts_email` on `accounts(email_address)`
- `idx_folders_account` on `folders(account_id)`
- `idx_emails_account` on `emails(account_id)`
- `idx_emails_folder` on `emails(folder_id)`
- `idx_emails_uid` on `emails(account_id, folder_id, uid_on_server)`
- `idx_emails_timestamp` on `emails(received_at)`
- `idx_emails_subject` on `emails(subject)`
- `idx_emails_sender` on `emails(sender)`

## Data Flow

### Email Synchronization Flow

1. **Initial Sync**:
   ```
   User adds account → OAuth/Password authentication → 
   IMAP connection established → Fetch folder list → 
   For each folder: Fetch email headers (limit: 100 inbox, 50 others) → 
   Store in SQLite cache → Update UI
   ```

2. **Periodic Sync**:
   ```
   Timer triggers (every 5 minutes) → 
   For each account: Connect to IMAP → 
   Fetch latest email headers → Compare with cache → 
   Insert new emails, update changed emails → 
   Update folder unread counts → Refresh UI
   ```

3. **Email Body Fetching**:
   ```
   User opens email → Check cache for body → 
   If missing: Connect to IMAP → Fetch full email body → 
   Decrypt and store in cache → Display in UI
   ```

4. **Mark as Read**:
   ```
   User opens email → Update local cache (is_read=1) → 
   Send IMAP STORE command (+FLAGS \Seen) → 
   Update UI immediately
   ```

5. **Delete Email**:
   ```
   User deletes email → Send IMAP STORE (+FLAGS \Deleted) → 
   Send IMAP EXPUNGE → Delete from local cache → 
   Refresh UI
   ```

6. **Move Email**:
   ```
   User moves email → Send IMAP COPY to destination folder → 
   Mark as \Deleted in source folder → Send IMAP EXPUNGE → 
   Delete old record from cache → Update email with new folder_id → 
   Refresh UI
   ```

7. **Folder Operations**:
   ```
   User creates/renames/deletes folder → Send IMAP CREATE/RENAME/DELETE → 
   Update folder cache → Refresh sidebar
   ```

### Authentication Flow

1. **OAuth Flow** (Gmail/Outlook):
   ```
   User clicks "Add Account" → Select provider → 
   OAuth button clicked → Browser opens → 
   User authorizes → Callback received → 
   Exchange code for tokens → Store encrypted tokens → 
   Create account record
   ```

2. **Token Refresh**:
   ```
   IMAP/SMTP operation → Check token expiration → 
   If expired/expiring: Use refresh token → 
   Get new access token → Update encrypted storage → 
   Continue with operation
   ```

3. **Password Flow** (Custom IMAP/SMTP):
   ```
   User enters credentials → Encrypt password → 
   Store in database → Test IMAP connection → 
   Create account record
   ```

## Architecture

### Project Structure

```
gmail-client-desktop/
├── email_client/          # Core application package
│   ├── auth/              # Authentication (OAuth, accounts)
│   │   ├── accounts.py    # Account management, token storage
│   │   └── oauth.py        # OAuth provider implementations
│   ├── core/              # Business logic
│   │   ├── sync_manager.py    # Email synchronization
│   │   ├── search.py          # Email search functionality
│   │   └── settings.py         # Application settings
│   ├── network/           # Network layer
│   │   ├── imap_client.py     # IMAP protocol client
│   │   └── smtp_client.py     # SMTP protocol client
│   ├── storage/           # Data persistence
│   │   ├── db.py              # Database connection management
│   │   ├── cache_repo.py      # Repository pattern for cache
│   │   └── encryption.py      # AES-256 encryption
│   ├── ui/                # UI controllers (MVC pattern)
│   │   ├── controllers.py     # Abstract controller interfaces
│   │   └── controller_impl.py  # Concrete implementations
│   └── models.py          # Domain models (dataclasses)
├── ui/                     # UI components (PyQt5)
│   ├── main_window.py     # Main application window
│   ├── login_window.py     # Account addition dialog
│   ├── compose_window.py   # Email composition window
│   └── components/         # Reusable UI components
│       ├── sidebar.py      # Folder/account sidebar
│       ├── email_list.py   # Email list with pagination
│       └── email_preview.py # Email detail view
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

### Key Components

1. **Controllers** (`email_client/ui/controllers.py`):
   - Abstract interfaces for UI operations
   - Separates UI from business logic
   - Allows easy swapping of implementations

2. **Sync Manager** (`email_client/core/sync_manager.py`):
   - Manages synchronization between IMAP server and local cache
   - Thread-safe operations
   - Handles folder syncing, email fetching, and body caching

3. **IMAP Client** (`email_client/network/imap_client.py`):
   - High-level IMAP operations
   - XOAUTH2 authentication support
   - Automatic token refresh
   - Connection health checking

4. **Cache Repository** (`email_client/storage/cache_repo.py`):
   - Repository pattern for database operations
   - Converts between database rows and domain models
   - Handles encryption/decryption of email bodies

5. **Encryption** (`email_client/storage/encryption.py`):
   - AES-256 encryption for sensitive data
   - Encrypts passwords, tokens, and email bodies
   - Key management and rotation

## Usage

### Adding an Account

1. Click "Add Account" button or use File → Add Account
2. Select email provider (Gmail, Outlook, Yahoo, or Custom IMAP/SMTP)
3. For OAuth providers: Click "Continue with [Provider]" and complete browser authentication
4. For custom servers: Enter email, password, and server settings
5. Account will sync automatically after addition

### Composing Emails

1. Click "Compose" button or use Edit → Compose (Ctrl+N)
2. Enter recipients, subject, and body
3. Use formatting toolbar for rich text (bold, italic, underline)
4. Attach files using the "Attach File" button
5. Click "Send" or "Save Draft"

### Reading Emails

1. Select a folder from the sidebar
2. Emails are displayed with pagination (50 per page)
3. Click an email to view details
4. Use Reply, Forward, or Delete buttons
5. Click back arrow (←) to return to list

### Searching

1. Enter search query in the search bar
2. Results are filtered by subject, sender, or content
3. Use account filter dropdown to search specific accounts
4. Search works across all folders

### Managing Accounts

- **Switch Accounts**: Use the account filter dropdown in the top bar
- **Delete Account**: Right-click account in sidebar or use File → Remove Account
- **View All Accounts**: Select "All Accounts" in the filter dropdown

### Managing Folders

- **Create Folder**: Right-click any folder in the sidebar → "Create Folder" → Enter folder name
- **Rename Folder**: Right-click a custom folder (not system folders like Inbox/Sent) → "Rename Folder" → Enter new name
- **Delete Folder**: Right-click a custom folder → "Delete Folder" → Confirm deletion
  - **Note**: System folders (Inbox, Sent, Drafts, Trash) cannot be renamed or deleted
- **Move Email**: Open an email → Click "Move" button → Select destination folder
  - Emails are moved on the server and removed from the source folder
  - All folder operations are synchronized with the IMAP server

## Troubleshooting

### OAuth Callback Issues

**Problem:** OAuth redirect fails or browser doesn't open

**Solutions:**
- Verify redirect URI matches exactly: `http://localhost:8080/callback`
- Check that port 8080 is not in use by another application
- Ensure OAuth credentials are correctly set in `.env`
- For Gmail: Verify the OAuth consent screen is configured
- For Outlook: Check that the app registration is active

### Connection Issues

**Problem:** Cannot connect to email server

**Solutions:**
- Verify internet connection
- Check IMAP/SMTP server settings (use standard ports: 993 for IMAP, 587 for SMTP)
- For Gmail: Use OAuth2 or generate an App Password
- Check firewall settings aren't blocking connections
- Verify email provider isn't blocking the connection

### IMAP/SMTP Authentication Failures

**Problem:** Login fails even with correct credentials

**Solutions:**
- For Gmail: Use OAuth2 instead of password authentication
- For Gmail with password: Generate an "App Password" from Google Account settings
- For Yahoo: Generate an App Password from Yahoo Account Security
- Verify credentials are correct (test in webmail first)
- Check if account requires 2FA (two-factor authentication)

### Database Lock Errors

**Problem:** "database is locked" errors

**Solutions:**
- Close any other instances of the application
- Check for stale lock files in `~/.email_client/`
- Restart the application
- If persistent, backup and recreate the database

### Application Won't Start

**Problem:** Application crashes on startup

**Solutions:**
- Verify Python version: `python --version` (should be 3.8+)
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
- Check logs: `~/.email_client/logs/app.log`
- Verify PyQt5 is installed: `python -c "import PyQt5; print(PyQt5.__version__)"`
- On Linux: Install system Qt5 libraries if missing

### Email Not Syncing

**Problem:** Emails not appearing or not updating

**Solutions:**
- Click "Refresh" button to manually trigger sync
- Check account is properly authenticated (tokens not expired)
- Verify IMAP connection is working
- Check logs for sync errors
- Try removing and re-adding the account

## Security

### Data Protection

- **Credentials**: All passwords and OAuth tokens are encrypted using AES-256 before storage
- **Email Bodies**: Email content is encrypted in the database
- **Network**: All IMAP/SMTP connections use TLS/SSL encryption
- **Local Storage**: Database and cache files are stored in user's home directory with appropriate permissions

### Token Management

- **OAuth Tokens**: Refresh tokens are stored encrypted and automatically refreshed when expired
- **Token Expiration**: Access tokens are checked before use and refreshed if expiring within 5 minutes
- **Secure Storage**: Encryption keys are stored separately from encrypted data

### Privacy

- **No Cloud Sync**: All data remains on your local machine
- **No Telemetry**: Application does not send any data to external servers
- **Local Only**: Database and cache are stored locally, never uploaded

## License

MIT License

## Support

For issues, questions, or contributions, please refer to the project repository.
