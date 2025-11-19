# Email Desktop Client

A cross-platform desktop email client built with Python and PyQt5, supporting multiple email accounts with IMAP/SMTP and OAuth2 authentication.

## Features

- **Multi-Account Support**: Manage multiple email accounts from a single interface
- **Unified Inbox**: View emails from all accounts in one place
- **OAuth2 Authentication**: Secure login for Gmail and Outlook
- **IMAP/SMTP Support**: Works with any email provider
- **Offline Access**: Local caching for offline email viewing
- **Rich Text Composition**: Compose emails with formatting and attachments
- **Search & Filter**: Quickly find emails by content, sender, or date
- **Secure Storage**: Encrypted local storage of credentials and tokens

## Installation

1. Install Python 3.8 or higher
2. Create a virtual environment:

```bash
# On macOS/Linux
python3 -m venv venv

# On Windows
python -m venv venv
```

3. Activate the virtual environment:

```bash
# On macOS/Linux
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the application:

```bash
python main.py
```

## Supported Providers

- Gmail (OAuth2)
- Outlook.com (OAuth2)
- Yahoo Mail (IMAP/SMTP)
- Any custom IMAP/SMTP server

## Security

- All credentials and tokens are encrypted using AES-256
- TLS 1.2+ for all email server communication
- No passwords stored in plain text
- GDPR-compliant data handling

## License

MIT License
