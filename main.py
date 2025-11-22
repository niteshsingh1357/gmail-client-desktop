"""
Main application entry point
"""
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow

# Initialize configuration and database before starting the app
from email_client.config import load_env
from email_client.storage.db import init_db
from email_client.utils.logging_cfg import setup_logging


def main():
    """Main function"""
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

