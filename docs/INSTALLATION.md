# Installation Guide

This guide provides detailed, step-by-step instructions for installing and setting up the Email Desktop Client on Windows, macOS, and Linux.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installing Python](#installing-python)
3. [Installing Git](#installing-git)
4. [Cloning the Repository](#cloning-the-repository)
5. [Setting Up Virtual Environment](#setting-up-virtual-environment)
6. [Installing Dependencies](#installing-dependencies)
7. [Initializing the Database](#initializing-the-database)
8. [Setting Up OAuth2 Credentials](#setting-up-oauth2-credentials)
9. [Verifying Installation](#verifying-installation)
10. [Optional: Creating an Executable](#optional-creating-an-executable)

## Prerequisites

Before installing, ensure you have:

- A computer running Windows 10+, macOS 10.14+, or a modern Linux distribution
- Administrator/root access (for installing system packages if needed)
- An internet connection
- At least 500 MB of free disk space

## Installing Python

### Windows

1. **Download Python:**
   - Visit [python.org/downloads](https://www.python.org/downloads/)
   - Download Python 3.8 or higher (3.9+ recommended)
   - Choose the "Windows installer (64-bit)" option

2. **Install Python:**
   - Run the installer
   - **Important:** Check "Add Python to PATH" during installation
   - Click "Install Now"
   - Wait for installation to complete

3. **Verify Installation:**
   Open PowerShell or Command Prompt and run:
   ```powershell
   python --version
   ```
   You should see something like `Python 3.9.7` or higher.

### macOS

1. **Check if Python is installed:**
   Open Terminal and run:
   ```bash
   python3 --version
   ```
   If you see Python 3.8+, you're good to go. Otherwise, continue.

2. **Install Python using Homebrew (recommended):**
   ```bash
   # Install Homebrew if you don't have it
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   
   # Install Python
   brew install python3
   ```

3. **Or download from python.org:**
   - Visit [python.org/downloads](https://www.python.org/downloads/)
   - Download the macOS installer
   - Run the installer and follow the prompts

4. **Verify Installation:**
   ```bash
   python3 --version
   ```

### Linux (Ubuntu/Debian)

1. **Update package list:**
   ```bash
   sudo apt update
   ```

2. **Install Python 3.8+:**
   ```bash
   sudo apt install python3 python3-pip python3-venv
   ```

3. **Verify Installation:**
   ```bash
   python3 --version
   ```

### Linux (Fedora/RHEL)

1. **Install Python:**
   ```bash
   sudo dnf install python3 python3-pip
   ```

2. **Verify Installation:**
   ```bash
   python3 --version
   ```

## Installing Git

### Windows

1. **Download Git:**
   - Visit [git-scm.com/download/win](https://git-scm.com/download/win)
   - Download the installer

2. **Install Git:**
   - Run the installer
   - Use default options (or customize as needed)
   - Complete the installation

3. **Verify Installation:**
   Open PowerShell and run:
   ```powershell
   git --version
   ```

### macOS

1. **Install Git using Homebrew:**
   ```bash
   brew install git
   ```

2. **Or download from git-scm.com:**
   - Visit [git-scm.com/download/mac](https://git-scm.com/download/mac)
   - Download and run the installer

3. **Verify Installation:**
   ```bash
   git --version
   ```

### Linux

**Ubuntu/Debian:**
```bash
sudo apt install git
```

**Fedora/RHEL:**
```bash
sudo dnf install git
```

**Verify:**
```bash
git --version
```

## Cloning the Repository

1. **Open a terminal/command prompt**

2. **Navigate to where you want to install the application:**
   
   **Windows (PowerShell):**
   ```powershell
   cd C:\Users\YourUsername\Documents
   ```
   
   **macOS/Linux:**
   ```bash
   cd ~/Documents
   ```

3. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd gmail-client-desktop
   ```
   
   Replace `<repository-url>` with the actual repository URL.

## Setting Up Virtual Environment

A virtual environment isolates the application's dependencies from your system Python.

### Windows

**PowerShell:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If you get an execution policy error, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Command Prompt:**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### macOS/Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

**Note:** Your terminal prompt should now show `(venv)` indicating the virtual environment is active.

## Installing Dependencies

With the virtual environment activated, install the required packages:

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

**Expected output:** You should see packages being downloaded and installed. This may take a few minutes.

## Initializing the Database

The application uses SQLite to cache emails locally. Initialize the database schema:

```bash
python -c "from email_client.storage.db import init_db; init_db()"
```

**Expected output:** No output means success. The database will be created at `~/.email_client/email_client.db` (or `%USERPROFILE%\.email_client\email_client.db` on Windows).

**Verify:** Check that the database file was created:
- **Windows:** `%USERPROFILE%\.email_client\email_client.db`
- **macOS/Linux:** `~/.email_client/email_client.db`

## Setting Up OAuth2 Credentials

OAuth2 credentials are required for Gmail and Outlook authentication. You can skip this if you only plan to use password-based authentication or custom IMAP/SMTP servers.

### Gmail OAuth2 Setup

1. **Go to Google Cloud Console:**
   - Visit [console.cloud.google.com](https://console.cloud.google.com/)
   - Sign in with your Google account

2. **Create a Project:**
   - Click "Select a project" → "New Project"
   - Enter a project name (e.g., "Email Desktop Client")
   - Click "Create"

3. **Enable Gmail API:**
   - Go to "APIs & Services" → "Library"
   - Search for "Gmail API"
   - Click "Enable"

4. **Create OAuth 2.0 Credentials:**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - If prompted, configure the OAuth consent screen:
     - Choose "External" (unless you have a Google Workspace account)
     - Fill in required fields (App name, User support email, Developer contact)
     - Add scopes: `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.send`, `https://www.googleapis.com/auth/gmail.modify`
     - Add test users (your email address)
     - Save and continue
   - Application type: **Desktop app**
   - Name: "Email Desktop Client" (or any name)
   - Click "Create"

5. **Copy Credentials:**
   - Copy the "Client ID" and "Client secret"
   - Keep these secure (don't share publicly)

6. **Set Redirect URI:**
   - In the OAuth client settings, add authorized redirect URI: `http://localhost:8080/callback`
   - Save changes

### Outlook OAuth2 Setup

1. **Go to Azure Portal:**
   - Visit [portal.azure.com](https://portal.azure.com/)
   - Sign in with your Microsoft account

2. **Register an Application:**
   - Go to "Azure Active Directory" → "App registrations"
   - Click "New registration"
   - Name: "Email Desktop Client"
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI: Platform "Web", URI: `http://localhost:8080/callback`
   - Click "Register"

3. **Create Client Secret:**
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Description: "Email Desktop Client Secret"
   - Expires: Choose an expiration (24 months recommended)
   - Click "Add"
   - **Important:** Copy the secret value immediately (it won't be shown again)

4. **Copy Credentials:**
   - Go to "Overview"
   - Copy the "Application (client) ID"
   - Use this along with the client secret from step 3

### Configuring the Application

1. **Create `.env` file:**
   In the project root directory (`gmail-client-desktop/`), create a file named `.env`:

   **Windows (PowerShell):**
   ```powershell
   New-Item -Path .env -ItemType File
   ```

   **macOS/Linux:**
   ```bash
   touch .env
   ```

2. **Add OAuth credentials to `.env`:**
   Open `.env` in a text editor and add:

   ```env
   # Gmail OAuth2 (if using Gmail)
   OAUTH_CLIENT_ID=your_gmail_client_id_here
   OAUTH_CLIENT_SECRET=your_gmail_client_secret_here

   # Or for Outlook:
   # OAUTH_CLIENT_ID=your_outlook_client_id_here
   # OAUTH_CLIENT_SECRET=your_outlook_client_secret_here
   ```

   Replace the placeholder values with your actual credentials.

3. **Save the file:**
   Ensure `.env` is in the project root (same directory as `main.py`).

## Verifying Installation

1. **Check Python and dependencies:**
   ```bash
   python --version  # Should show 3.8+
   python -c "import PyQt5; print('PyQt5:', PyQt5.__version__)"
   python -c "from email_client.storage.db import init_db; print('Database module OK')"
   ```

2. **Run the application:**
   ```bash
   python main.py
   ```

3. **Expected behavior:**
   - Application window should open
   - If no accounts exist, you'll see a prompt to add an account
   - Status bar should show "Ready"

4. **Check logs (if issues occur):**
   - Logs are at `~/.email_client/logs/app.log` (or `%USERPROFILE%\.email_client\logs\app.log` on Windows)
   - Open the log file to see any error messages

## Optional: Creating an Executable

The repository does not currently include packaging scripts for creating standalone executables. However, you can create one using PyInstaller:

### Installing PyInstaller

```bash
pip install pyinstaller
```

### Creating an Executable

**Windows:**
```powershell
pyinstaller --onefile --windowed --name "EmailClient" main.py
```

**macOS/Linux:**
```bash
pyinstaller --onefile --name "EmailClient" main.py
```

**Note:** The executable will be in the `dist/` directory. You'll need to:
- Include the `.env` file or configure OAuth credentials separately
- Ensure the database directory (`~/.email_client/`) is writable
- Test thoroughly as PyInstaller can have compatibility issues with PyQt5

### Limitations

- The executable will be large (100+ MB) due to bundled dependencies
- First launch may be slower
- Some antivirus software may flag PyInstaller executables
- Platform-specific: Windows executable won't run on macOS/Linux and vice versa

## Next Steps

After installation:

1. **Run the application:** `python main.py`
2. **Add your first account:** Use the "Add Account" button in the UI
3. **Configure OAuth:** If using Gmail/Outlook, the OAuth flow will open in your browser
4. **Start using:** Your emails will sync and be available offline

For usage instructions, see the main [README.md](../README.md).

## Troubleshooting Installation

### "python: command not found"

- **Windows:** Reinstall Python and ensure "Add to PATH" is checked
- **macOS/Linux:** Use `python3` instead of `python`

### "pip: command not found"

- Install pip: `python -m ensurepip --upgrade` (Windows) or `python3 -m ensurepip --upgrade` (macOS/Linux)

### Virtual environment activation fails

- **Windows PowerShell:** Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- **macOS/Linux:** Ensure you're using `source venv/bin/activate` (not `./venv/bin/activate`)

### PyQt5 installation fails

- **Linux:** Install system Qt5 libraries: `sudo apt install python3-pyqt5` (Ubuntu/Debian) or `sudo dnf install python3-qt5` (Fedora)
- **macOS:** May need Xcode command line tools: `xcode-select --install`
- **Windows:** Usually works without additional steps

### Database initialization fails

- Check that you have write permissions in your home directory
- Verify the path: `~/.email_client/` should be created automatically
- On Windows, check `%USERPROFILE%\.email_client\`

### OAuth credentials not working

- Verify `.env` file is in the project root
- Check that credentials are correct (no extra spaces)
- Ensure redirect URI matches exactly: `http://localhost:8080/callback`
- For Gmail: Verify OAuth consent screen is configured
- For Outlook: Check that app registration is active in Azure Portal

For more troubleshooting, see the main [README.md](../README.md#troubleshooting).

