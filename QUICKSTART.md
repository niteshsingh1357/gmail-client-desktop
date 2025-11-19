# Quick Start Guide

## Installation

1. **Install Python 3.8 or higher**

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up OAuth2 credentials (optional, for Gmail/Outlook):**
   - Copy `.env.example` to `.env`
   - Add your OAuth2 credentials:
     - For Gmail: Get credentials from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
     - For Outlook: Get credentials from [Azure Portal](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)

## Running the Application

```bash
python main.py
```

## First Time Setup

1. When you first launch the application, you'll be prompted to add an email account.

2. **Adding an Account:**
   - Select your email provider (Gmail, Outlook, Yahoo Mail, or Custom)
   - Enter your email address
   - For Gmail/Outlook: Use OAuth2 (recommended) - you'll be redirected to your browser for authentication
   - For other providers: Enter your password or app-specific password
   - For custom IMAP/SMTP: Enter server details manually

3. **Using the Application:**
   - Click "Compose" to write a new email
   - Select a folder from the sidebar to view emails
   - Click on an email to preview it
   - Use the search bar to find emails
   - Use filters to show only read/unread emails

## Features

- **Multi-Account Support**: Add multiple email accounts
- **Unified Inbox**: View all emails in one place
- **Rich Text Composition**: Format your emails with bold, italic, underline
- **Attachments**: Attach files to your emails
- **Search & Filter**: Quickly find emails
- **Offline Access**: View cached emails offline
- **Secure Storage**: All credentials encrypted locally

## Troubleshooting

### OAuth2 Not Working
- Make sure you've set up OAuth2 credentials in `.env`
- For Gmail, ensure redirect URI is set to `http://localhost:8080/callback`
- For Outlook, ensure redirect URI matches in Azure portal

### Connection Issues
- Check your internet connection
- Verify IMAP/SMTP server settings
- For Gmail, you may need to enable "Less secure app access" or use an app-specific password
- Ensure firewall isn't blocking the application

### Email Sync Issues
- Check account credentials
- Verify IMAP is enabled on your email account
- Try refreshing manually using the refresh button

## Notes

- The application stores all data locally in `~/.email_desktop_client/`
- Emails are cached locally for offline access
- All credentials and tokens are encrypted using AES-256
- The application syncs emails automatically every 5 minutes (configurable)

