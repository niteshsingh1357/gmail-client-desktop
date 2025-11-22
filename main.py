"""
Main application entry point
"""
import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow

# Initialize configuration and database before starting the app
from email_client.config import load_env
from email_client.storage.db import init_db
from email_client.utils.logging_cfg import setup_logging


def check_dependencies():
    """Check if required dependencies are available"""
    missing = []
    
    # Check for google-auth-oauthlib
    try:
        import google_auth_oauthlib
    except ImportError:
        missing.append("google-auth-oauthlib")
    
    if missing:
        # Check if we're in a venv
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        
        error_msg = (
            f"Missing required dependencies: {', '.join(missing)}\n\n"
            f"Python path: {sys.executable}\n"
            f"Virtual environment: {'Yes' if in_venv else 'No'}\n\n"
        )
        
        if in_venv:
            error_msg += "Please install missing packages:\n"
            error_msg += f"  pip install {' '.join(missing)}\n"
        else:
            error_msg += (
                "It looks like you're not using a virtual environment.\n"
                "Please activate the virtual environment first:\n"
                "  source venv/bin/activate\n"
                "Then install missing packages:\n"
                f"  pip install {' '.join(missing)}\n"
            )
        
        # Print error (we can't show GUI before QApplication is created)
        print("=" * 60, file=sys.stderr)
        print("ERROR: Missing Dependencies", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(error_msg, file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        sys.exit(1)


def main():
    """Main function"""
    # Check dependencies before proceeding
    check_dependencies()
    
    # Load environment variables and ensure directories exist
    load_env()
    
    # Initialize database schema
    init_db()
    
    # Setup logging
    setup_logging(debug=False)
    
    # Enable high DPI scaling BEFORE creating QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Email Desktop Client")
    app.setOrganizationName("EmailDesktopClient")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

