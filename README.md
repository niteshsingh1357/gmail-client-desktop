# Email Desktop Client

A modern, cross-platform desktop email client built with Python and PyQt5. Manage multiple email accounts from a single interface with support for OAuth2 authentication, offline caching, and secure local storage.

## Project Overview

The Email Desktop Client is a full-featured desktop application that provides a unified interface for managing multiple email accounts. It supports major email providers (Gmail, Outlook, Yahoo) and any custom IMAP/SMTP server, with secure OAuth2 authentication and local caching for offline access.

## Key Features

- **Multi-Account Support**: Add and manage multiple email accounts from different providers
- **Unified Inbox**: View emails from all accounts in a single, organized interface
- **OAuth2 Authentication**: Secure, token-based authentication for Gmail and Outlook
- **IMAP/SMTP Support**: Works with any email provider that supports standard protocols
- **Offline Access**: Local SQLite cache allows viewing emails without an internet connection
- **Rich Text Composition**: Compose emails with formatting (bold, italic, underline) and attachments
- **Search & Filter**: Quickly find emails by subject, sender, content, or date
- **Folder Management**: Create, rename, and organize custom folders
- **Secure Storage**: All credentials and tokens encrypted locally using AES-256
- **Status Notifications**: Non-blocking toast notifications and status bar updates

## Quick Start

### Prerequisites

- **Python 3.8 or higher** (Python 3.9+ recommended)
- **Git** (for cloning the repository)
- **Internet connection** (for initial setup and email synchronization)
- **OAuth2 credentials** (optional, but required for Gmail/Outlook OAuth authentication)

### Supported Operating Systems

- **macOS** 10.14 or later
- **Linux** (Ubuntu 18.04+, Debian 10+, Fedora 30+, etc.)
- **Windows** 10 or later

### Installation

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

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database:**

   ```bash
   python -c "from email_client.storage.db import init_db; init_db()"
   ```

5. **Set up OAuth credentials (optional but recommended):**

   Create a `.env` file in the project root:

   ```bash
   # .env
   OAUTH_CLIENT_ID=your_client_id_here
   OAUTH_CLIENT_SECRET=your_client_secret_here
   ```

   See the [Configuration](#configuration) section for detailed OAuth setup instructions.

### Running the Application

**Single command to run:**

```bash
python main.py
```

The application will:

- Create necessary directories (`~/.email_client/`)
- Initialize the database if it doesn't exist
- Show the main window where you can add your first email account

## Configuration

### Environment Variables

The application reads configuration from environment variables and a `.env` file (if present). Create a `.env` file in the project root:

```env
# OAuth2 Credentials (Required for Gmail/Outlook OAuth)
OAUTH_CLIENT_ID=your_google_or_microsoft_client_id
OAUTH_CLIENT_SECRET=your_google_or_microsoft_client_secret

# Database Path (Optional - defaults to ~/.email_client/email_client.db)
SQLITE_DB_PATH=/custom/path/to/email_client.db
```

### OAuth2 Setup

#### Gmail OAuth2

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Choose "Desktop app" as the application type
6. Set the redirect URI to: `http://localhost:8080/callback`
7. Copy the Client ID and Client Secret to your `.env` file

#### Outlook OAuth2

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to "Azure Active Directory" → "App registrations"
3. Click "New registration"
4. Set redirect URI to: `http://localhost:8080/callback`
5. Go to "Certificates & secrets" → "New client secret"
6. Copy the Application (client) ID and Client secret to your `.env` file

### Database Configuration

The SQLite database is stored at `~/.email_client/email_client.db` by default. You can override this by setting the `SQLITE_DB_PATH` environment variable.

### Logging Configuration

Logs are written to `~/.email_client/logs/app.log` with automatic rotation (10 MB max, 5 backup files). To enable debug logging, modify `main.py` to call:

```python
from email_client.utils.logging_cfg import setup_logging
setup_logging(debug=True)
```

## Running the App

### Development Mode

For development with debug logging:

```bash
# Set debug mode in main.py or use environment variable
DEBUG=true python main.py
```

### Normal User Mode

Simply run:

```bash
python main.py
```

### OS-Specific Notes

**macOS:**

- The application uses native macOS window management
- High DPI scaling is automatically enabled
- May require granting accessibility permissions for some features

**Linux:**

- Requires X11 or Wayland display server
- May need to install system packages: `sudo apt-get install python3-pyqt5` (Ubuntu/Debian)
- For Wayland, ensure proper environment variables are set

**Windows:**

- No additional system packages required
- The application runs as a standard Windows application
- Antivirus software may flag PyQt5; add an exception if needed

## Testing

See [docs/TESTING.md](docs/TESTING.md) for comprehensive testing documentation.

### Quick Test Commands

**Run all tests (if test suite exists):**

```bash
pytest
```

**Run specific test file:**

```bash
pytest tests/test_models.py
```

**Run with coverage:**

```bash
pytest --cov=email_client
```

## Project Structure

```
gmail-client-desktop/
├── email_client/          # Core application package
│   ├── auth/              # Authentication (OAuth, accounts)
│   ├── core/              # Business logic (sync, search, settings)
│   ├── models.py          # Domain models
│   ├── network/           # IMAP/SMTP clients
│   ├── storage/           # Database and encryption
│   ├── ui/                # UI components and controllers
│   └── utils/              # Utilities (errors, logging)
├── ui/                     # Legacy UI components
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

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
- For Gmail: Ensure "Less secure app access" is enabled OR use OAuth2
- Check firewall settings aren't blocking connections
- Verify email provider isn't blocking the connection (check account security settings)

### IMAP/SMTP Authentication Failures

**Problem:** Login fails even with correct credentials

**Solutions:**

- For Gmail: Use OAuth2 instead of password authentication
- For Gmail with password: Generate an "App Password" from Google Account settings
- Verify credentials are correct (test in webmail first)
- Check if account requires 2FA (two-factor authentication)
- For custom servers: Verify server addresses and ports are correct

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
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
- Check logs: `~/.email_client/logs/app.log`
- Verify PyQt5 is installed: `python -c "import PyQt5; print(PyQt5.__version__)"`
- On Linux: Install system Qt5 libraries if missing

### Missing Dependencies

**Problem:** Import errors or missing modules

**Solutions:**

- Ensure virtual environment is activated
- Reinstall requirements: `pip install -r requirements.txt`
- Check that you're using the correct Python interpreter
- Verify all dependencies in `requirements.txt` are compatible with your Python version

## Security Notes

- **Credentials**: All passwords and OAuth tokens are encrypted using AES-256 before storage
- **Network**: All IMAP/SMTP connections use TLS/SSL encryption
- **Local Storage**: Database and cache files are stored in user's home directory with appropriate permissions
- **OAuth Tokens**: Refresh tokens are stored encrypted and automatically refreshed when expired
- **No Cloud Sync**: All data remains on your local machine

## Contributing

This is a desktop email client application. For contributions:

1. Follow Python PEP 8 style guidelines
2. Add tests for new features
3. Update documentation for user-facing changes
4. Ensure all tests pass before submitting

## License

MIT License

## Support

For issues, questions, or contributions, please refer to the project repository.
