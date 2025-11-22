# Testing Guide

This guide covers both automated testing (unit tests, integration tests) and manual testing procedures for the Email Desktop Client.

## Table of Contents

1. [Automated Testing](#automated-testing)
2. [Setting Up Test Environment](#setting-up-test-environment)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Manual Testing Checklist](#manual-testing-checklist)

## Automated Testing

The project currently does not have a comprehensive test suite. This section provides guidance on setting up tests and examples for common scenarios.

### Test Framework

We recommend using **pytest** for testing:

```bash
pip install pytest pytest-cov pytest-mock
```

### Test Structure

Create a `tests/` directory in the project root:

```
gmail-client-desktop/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest configuration and fixtures
│   ├── test_models.py       # Domain model tests
│   ├── test_storage.py      # Database and encryption tests
│   ├── test_auth.py         # Authentication tests
│   ├── test_network.py     # IMAP/SMTP client tests (mocked)
│   └── test_core.py         # Business logic tests
├── email_client/
└── ...
```

### Pytest Configuration

Create `pytest.ini` in the project root:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --tb=short
markers =
    unit: Unit tests (fast, no I/O)
    integration: Integration tests (may use database/filesystem)
    network: Tests that require network access
    slow: Tests that take a long time to run
```

## Setting Up Test Environment

### Test Database

Tests should use a separate test database to avoid affecting production data:

```python
# tests/conftest.py
import pytest
import tempfile
from pathlib import Path
from email_client.storage.db import get_connection, init_db
from email_client.config import SQLITE_DB_PATH

@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    if db_path.exists():
        db_path.unlink()

@pytest.fixture(autouse=True)
def setup_test_db(test_db_path, monkeypatch):
    """Initialize test database before each test."""
    monkeypatch.setattr('email_client.config.SQLITE_DB_PATH', test_db_path)
    init_db()
    yield
    # Cleanup after test
    if test_db_path.exists():
        test_db_path.unlink()
```

### Test Environment Variables

Create a `.env.test` file for test-specific configuration:

```env
# .env.test
OAUTH_CLIENT_ID=test_client_id
OAUTH_CLIENT_SECRET=test_client_secret
SQLITE_DB_PATH=/tmp/test_email_client.db
```

Load test environment in `conftest.py`:

```python
import os
from dotenv import load_dotenv

@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load test environment variables."""
    load_dotenv('.env.test', override=True)
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_models.py
```

### Run Specific Test Function

```bash
pytest tests/test_models.py::test_email_message_mark_read
```

### Run Tests with Coverage

```bash
pytest --cov=email_client --cov-report=html
```

View coverage report:
- Open `htmlcov/index.html` in a browser

### Run Tests by Marker

```bash
# Run only unit tests
pytest -m unit

# Skip network tests
pytest -m "not network"

# Run only fast tests
pytest -m "not slow"
```

### Verbose Output

```bash
pytest -v
```

### Stop on First Failure

```bash
pytest -x
```

## Writing Tests

### Example: Model Tests

```python
# tests/test_models.py
import pytest
from datetime import datetime
from email_client.models import EmailMessage, EmailAccount, Folder

class TestEmailMessage:
    """Tests for EmailMessage model."""
    
    def test_mark_read(self):
        """Test marking an email as read."""
        email = EmailMessage(
            sender="test@example.com",
            subject="Test",
            is_read=False
        )
        email.mark_read()
        assert email.is_read is True
        assert '\\Seen' in email.flags
    
    def test_toggle_starred(self):
        """Test toggling starred status."""
        email = EmailMessage(sender="test@example.com", subject="Test")
        assert email.is_starred() is False
        
        email.toggle_starred()
        assert email.is_starred() is True
        
        email.toggle_starred()
        assert email.is_starred() is False

class TestFolder:
    """Tests for Folder model."""
    
    def test_increment_unread(self):
        """Test incrementing unread count."""
        folder = Folder(name="Inbox", unread_count=5)
        folder.increment_unread()
        assert folder.unread_count == 6
    
    def test_decrement_unread_does_not_go_below_zero(self):
        """Test that unread count doesn't go below zero."""
        folder = Folder(name="Inbox", unread_count=0)
        folder.decrement_unread()
        assert folder.unread_count == 0
```

### Example: Storage Tests

```python
# tests/test_storage.py
import pytest
from email_client.storage.db import get_connection, init_db, execute, fetchone
from email_client.storage.encryption import encrypt_text, decrypt_text, DecryptionError

class TestEncryption:
    """Tests for encryption utilities."""
    
    def test_encrypt_decrypt_text_roundtrip(self):
        """Test that encrypt/decrypt preserves text."""
        original = "This is a secret message"
        encrypted = encrypt_text(original)
        decrypted = decrypt_text(encrypted)
        assert decrypted == original
    
    def test_decrypt_invalid_data_raises_error(self):
        """Test that decrypting invalid data raises DecryptionError."""
        with pytest.raises(DecryptionError):
            decrypt_text(b"invalid encrypted data")
    
    def test_encrypt_different_texts_produce_different_output(self):
        """Test that encryption is non-deterministic."""
        text = "Same text"
        encrypted1 = encrypt_text(text)
        encrypted2 = encrypt_text(text)
        # Encrypted outputs should be different (due to random IV)
        assert encrypted1 != encrypted2

class TestDatabase:
    """Tests for database operations."""
    
    def test_init_db_creates_tables(self):
        """Test that init_db creates all required tables."""
        init_db()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Check that accounts table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='accounts'
            """)
            result = cursor.fetchone()
            assert result is not None
        finally:
            conn.close()
    
    def test_account_insert_and_retrieve(self):
        """Test inserting and retrieving an account."""
        init_db()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO accounts (display_name, email_address, provider, imap_host, smtp_host)
                VALUES (?, ?, ?, ?, ?)
            """, ("Test User", "test@example.com", "gmail", "imap.gmail.com", "smtp.gmail.com"))
            conn.commit()
            
            cursor.execute("SELECT * FROM accounts WHERE email_address = ?", ("test@example.com",))
            row = cursor.fetchone()
            assert row is not None
            assert row["email_address"] == "test@example.com"
        finally:
            conn.close()
```

### Example: Authentication Tests (Mocked)

```python
# tests/test_auth.py
import pytest
from unittest.mock import Mock, patch
from email_client.auth.oauth import GoogleOAuthProvider, TokenBundle
from datetime import datetime, timedelta

class TestOAuthProvider:
    """Tests for OAuth provider."""
    
    def test_get_authorization_url(self):
        """Test generating authorization URL."""
        provider = GoogleOAuthProvider(
            client_id="test_id",
            client_secret="test_secret"
        )
        url = provider.get_authorization_url("test_state")
        assert "accounts.google.com" in url
        assert "test_state" in url
        assert "test_id" in url
    
    @patch('email_client.auth.oauth.requests.post')
    def test_exchange_code_for_tokens(self, mock_post):
        """Test exchanging code for tokens (mocked)."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600
        }
        mock_post.return_value = mock_response
        
        provider = GoogleOAuthProvider(
            client_id="test_id",
            client_secret="test_secret"
        )
        
        # This will fail if not implemented, but shows the test structure
        # token_bundle = provider.exchange_code_for_tokens("test_code")
        # assert isinstance(token_bundle, TokenBundle)
        # assert token_bundle.access_token == "test_access_token"
```

### Example: Core Logic Tests

```python
# tests/test_core.py
import pytest
from unittest.mock import Mock, MagicMock
from email_client.core.search import search_emails
from email_client.models import EmailMessage

class TestSearch:
    """Tests for search functionality."""
    
    @pytest.fixture
    def sample_emails(self):
        """Create sample emails for testing."""
        return [
            EmailMessage(
                id=1,
                sender="alice@example.com",
                subject="Meeting tomorrow",
                preview_text="Don't forget about the meeting"
            ),
            EmailMessage(
                id=2,
                sender="bob@example.com",
                subject="Project update",
                preview_text="Here's the latest on the project"
            ),
        ]
    
    def test_search_by_subject(self, sample_emails, setup_test_db):
        """Test searching emails by subject."""
        # Insert emails into test database
        # Then search
        results = search_emails(query="meeting", limit=10)
        # Verify results contain expected emails
        # (Implementation depends on actual search function)
```

## Manual Testing Checklist

Use this checklist to manually verify the application works correctly. Test each scenario and check off items as you complete them.

### Initial Setup

- [ ] **First Launch (No Database)**
  - [ ] Launch application: `python main.py`
  - [ ] Verify database is created at `~/.email_client/email_client.db`
  - [ ] Verify log file is created at `~/.email_client/logs/app.log`
  - [ ] Application window opens without errors
  - [ ] Status bar shows "Ready"
  - [ ] "Add Account" prompt appears (if no accounts exist)

### Account Management

- [ ] **Add Account via OAuth (Gmail)**
  - [ ] Click "Add Account" button
  - [ ] Select "Gmail" as provider
  - [ ] Enter email address
  - [ ] Check "Use OAuth2"
  - [ ] Click "Add Account"
  - [ ] Browser opens for OAuth authorization
  - [ ] Complete OAuth flow in browser
  - [ ] Return to application
  - [ ] Account appears in sidebar
  - [ ] Folders sync and appear in sidebar

- [ ] **Add Account via OAuth (Outlook)**
  - [ ] Repeat Gmail steps with Outlook provider
  - [ ] Verify Outlook-specific OAuth flow works

- [ ] **Add Account with Password (Custom IMAP/SMTP)**
  - [ ] Select "Custom IMAP/SMTP" as provider
  - [ ] Enter email, IMAP server, SMTP server, ports
  - [ ] Enter password
  - [ ] Uncheck "Use OAuth2"
  - [ ] Click "Add Account"
  - [ ] Account is added successfully
  - [ ] Folders sync

- [ ] **OAuth Cancellation**
  - [ ] Start OAuth flow
  - [ ] Cancel in browser
  - [ ] Verify application handles cancellation gracefully
  - [ ] No account is added
  - [ ] Error message is shown (if applicable)

- [ ] **OAuth Failure**
  - [ ] Use invalid OAuth credentials
  - [ ] Verify error message is user-friendly
  - [ ] Application doesn't crash

- [ ] **Set Default Account**
  - [ ] Add multiple accounts
  - [ ] Right-click account → "Set as Default"
  - [ ] Verify default indicator appears
  - [ ] Verify default account is used for new emails

- [ ] **Delete Account**
  - [ ] Right-click account → "Delete"
  - [ ] Confirm deletion
  - [ ] Account is removed from sidebar
  - [ ] Account data is removed from database
  - [ ] If it was the only account, "Add Account" prompt appears

### Email Viewing

- [ ] **Inbox Loads**
  - [ ] Select Inbox folder
  - [ ] Emails appear in message list
  - [ ] Unread emails are bold/highlighted
  - [ ] Dates are displayed correctly
  - [ ] Sender names are shown
  - [ ] Subject lines are truncated if too long
  - [ ] Preview text is shown (if available)

- [ ] **Open Email**
  - [ ] Click on an email in the list
  - [ ] Email preview pane shows content
  - [ ] Sender, subject, date are displayed
  - [ ] Email body (plain text or HTML) is rendered
  - [ ] If HTML, formatting is preserved
  - [ ] Email is marked as read (if it was unread)
  - [ ] Unread count decreases

- [ ] **View Attachments**
  - [ ] Open email with attachments
  - [ ] Attachments are listed in preview pane
  - [ ] Attachment names and sizes are shown
  - [ ] Clicking attachment opens/saves file (if implemented)

- [ ] **Navigate Folders**
  - [ ] Click different folders in sidebar
  - [ ] Message list updates for each folder
  - [ ] Folder-specific unread counts are correct
  - [ ] System folders (Inbox, Sent, Drafts, Trash) are identified

### Email Composition

- [ ] **Compose New Email**
  - [ ] Click "Compose" button
  - [ ] Compose window opens
  - [ ] "From" field shows account selector (if multiple accounts)
  - [ ] "To" field is editable
  - [ ] "CC" and "BCC" fields are available
  - [ ] Subject field is editable
  - [ ] Body editor supports rich text (bold, italic, underline)
  - [ ] Formatting toolbar works

- [ ] **Send Email (No Attachment)**
  - [ ] Enter recipient email
  - [ ] Enter subject
  - [ ] Enter body text
  - [ ] Click "Send"
  - [ ] Success message appears
  - [ ] Email appears in Sent folder
  - [ ] Email is actually sent (check recipient's inbox)

- [ ] **Send Email (With Attachment)**
  - [ ] Compose email
  - [ ] Click "Attach File"
  - [ ] Select a file
  - [ ] File appears in attachments list
  - [ ] Click "Send"
  - [ ] Email is sent with attachment
  - [ ] Verify attachment is received

- [ ] **Save Draft**
  - [ ] Compose email
  - [ ] Enter partial content
  - [ ] Click "Save Draft"
  - [ ] Success message appears
  - [ ] Draft appears in Drafts folder
  - [ ] Open draft, verify content is preserved
  - [ ] Edit and send draft

- [ ] **Reply to Email**
  - [ ] Open an email
  - [ ] Click "Reply"
  - [ ] Compose window opens
  - [ ] "To" field is pre-filled with original sender
  - [ ] Subject is prefixed with "Re: "
  - [ ] Original message is quoted
  - [ ] Send reply
  - [ ] Verify reply is sent

- [ ] **Forward Email**
  - [ ] Open an email
  - [ ] Click "Forward"
  - [ ] Compose window opens
  - [ ] Subject is prefixed with "Fwd: "
  - [ ] Original message is included
  - [ ] Enter recipient and send
  - [ ] Verify forward is sent

- [ ] **Send Failure Handling**
  - [ ] Disconnect from internet
  - [ ] Try to send email
  - [ ] Error message is shown
  - [ ] Error message is user-friendly (not technical)
  - [ ] Email is not lost (can save as draft)

### Search and Filtering

- [ ] **Search by Subject**
  - [ ] Enter search term in search bar
  - [ ] Press Enter or click search
  - [ ] Results show emails matching subject
  - [ ] Results are highlighted or marked

- [ ] **Search by Sender**
  - [ ] Enter sender email/name in search
  - [ ] Results show emails from that sender

- [ ] **Search by Content**
  - [ ] Enter keyword from email body
  - [ ] Results include emails containing that keyword

- [ ] **Account Filter**
  - [ ] Select account from filter dropdown
  - [ ] Search results are limited to that account
  - [ ] "All Accounts" shows results from all accounts

- [ ] **Folder Filter**
  - [ ] Search while in a specific folder
  - [ ] Results are limited to that folder (if implemented)

- [ ] **Read/Unread Filter**
  - [ ] Filter by read state (if implemented)
  - [ ] Results match filter criteria

### Synchronization

- [ ] **Manual Refresh**
  - [ ] Click "Refresh" button
  - [ ] Status bar shows "Syncing..."
  - [ ] New emails appear in inbox
  - [ ] Status bar updates to "Sync complete" or "Ready"
  - [ ] Unread counts update

- [ ] **Auto-Sync**
  - [ ] Wait for auto-sync interval (default: 60 seconds)
  - [ ] Verify new emails appear automatically
  - [ ] Status bar shows sync status

- [ ] **Initial Sync**
  - [ ] Add new account
  - [ ] Verify folders are synced
  - [ ] Verify recent emails are downloaded
  - [ ] Verify unread counts are correct

- [ ] **Sync Error Handling**
  - [ ] Disconnect from internet
  - [ ] Trigger sync (manual or auto)
  - [ ] Error message is shown
  - [ ] Error is user-friendly
  - [ ] Application doesn't crash
  - [ ] Cached emails are still accessible

### Folder Management

- [ ] **Create Folder**
  - [ ] Right-click account or parent folder
  - [ ] Select "Create Folder" (if implemented)
  - [ ] Enter folder name
  - [ ] Folder appears in sidebar
  - [ ] Folder is created on server (if supported)

- [ ] **Rename Folder**
  - [ ] Right-click folder
  - [ ] Select "Rename" (if implemented)
  - [ ] Enter new name
  - [ ] Folder name updates in sidebar
  - [ ] Folder is renamed on server

- [ ] **Delete Folder**
  - [ ] Right-click custom folder
  - [ ] Select "Delete" (if implemented)
  - [ ] Confirm deletion
  - [ ] Folder is removed
  - [ ] System folders cannot be deleted

- [ ] **Move Email to Folder**
  - [ ] Right-click email
  - [ ] Select "Move to Folder" (if implemented)
  - [ ] Select destination folder
  - [ ] Email moves to new folder
  - [ ] Email disappears from source folder

### Offline Functionality

- [ ] **Offline Access**
  - [ ] Disconnect from internet
  - [ ] Open application
  - [ ] Cached emails are still visible
  - [ ] Can read cached emails
  - [ ] Cannot send new emails (expected)
  - [ ] Error message indicates offline status

- [ ] **Offline to Online Transition**
  - [ ] Start application offline
  - [ ] View cached emails
  - [ ] Reconnect to internet
  - [ ] Trigger sync
  - [ ] New emails appear
  - [ ] Status updates to "Ready"

### Settings and Persistence

- [ ] **Window State Persistence**
  - [ ] Resize application window
  - [ ] Move window to different position
  - [ ] Close application
  - [ ] Reopen application
  - [ ] Window size and position are restored

- [ ] **Default Account Persistence**
  - [ ] Set default account
  - [ ] Close application
  - [ ] Reopen application
  - [ ] Default account is still set

- [ ] **Theme/Settings Persistence** (if implemented)
  - [ ] Change theme/settings
  - [ ] Close and reopen
  - [ ] Settings are preserved

### Security

- [ ] **OAuth Token Storage**
  - [ ] Add account via OAuth
  - [ ] Check database file
  - [ ] Verify tokens are encrypted (not plain text)
  - [ ] Verify encryption key is separate from database

- [ ] **Password Storage** (if using password auth)
  - [ ] Add account with password
  - [ ] Verify password is encrypted in database
  - [ ] Application never asks for password again (uses stored encrypted version)

- [ ] **No Plain Text Credentials**
  - [ ] Search codebase/logs for plain text passwords
  - [ ] Verify no credentials in log files
  - [ ] Verify `.env` file is in `.gitignore`

### Error Handling

- [ ] **Network Errors**
  - [ ] Disconnect during sync
  - [ ] Verify graceful error handling
  - [ ] Error message is user-friendly

- [ ] **Invalid Input**
  - [ ] Try to send email with invalid recipient
  - [ ] Verify validation error message
  - [ ] Try to add account with invalid email
  - [ ] Verify validation works

- [ ] **Database Errors**
  - [ ] Close application
  - [ ] Manually lock database file (if possible)
  - [ ] Reopen application
  - [ ] Verify error handling (may show "database locked" error)

### Performance

- [ ] **Large Inbox Handling**
  - [ ] Add account with many emails (1000+)
  - [ ] Verify application remains responsive
  - [ ] Verify pagination or lazy loading works
  - [ ] Verify search is still fast

- [ ] **Multiple Accounts**
  - [ ] Add 3+ accounts
  - [ ] Verify switching between accounts is fast
  - [ ] Verify sync doesn't block UI

## Test Results Template

After completing manual testing, document results:

```
Test Date: [Date]
Tester: [Name]
Environment: [OS, Python version]

Summary:
- Total Tests: [X]
- Passed: [X]
- Failed: [X]
- Blocked: [X]

Critical Issues:
1. [Issue description]

Major Issues:
1. [Issue description]

Minor Issues:
1. [Issue description]
```

## Continuous Testing

For ongoing development:

1. **Run automated tests before committing:**
   ```bash
   pytest
   ```

2. **Run manual smoke tests after major changes:**
   - Add account
   - View inbox
   - Send email
   - Search

3. **Full manual test before release:**
   - Complete entire checklist
   - Test on all supported platforms
   - Verify with multiple email providers

