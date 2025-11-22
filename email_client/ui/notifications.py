"""
Notification helpers for showing non-blocking messages.

This module provides presentation-only helpers for:
- Toast notifications (transient messages)
- Status bar updates

No business logic; just UI presentation helpers.
"""
from typing import Optional
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QStatusBar
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve


class ToastWidget(QWidget):
    """
    A transient toast notification widget.
    
    Automatically fades in, displays for a duration, then fades out.
    """
    
    def __init__(
        self,
        parent: Optional[QWidget],
        message: str,
        duration_ms: int = 3000,
        position: str = "bottom"
    ):
        """
        Initialize toast widget.
        
        Args:
            parent: Parent widget (usually main window).
            message: Message to display.
            duration_ms: How long to show the toast in milliseconds.
            position: Position on screen ("top", "bottom", "center").
        """
        super().__init__(parent)
        self.message = message
        self.duration_ms = duration_ms
        self.position = position
        
        self.setup_ui()
        self.setup_animations()
        
        # Start fade-in animation
        self.fade_in_animation.start()
    
    def setup_ui(self):
        """Setup the UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Main container
        container = QWidget(self)
        container.setStyleSheet("""
            QWidget {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                padding: 12px 16px;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Message label
        label = QLabel(self.message)
        label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 13px;
                background-color: transparent;
            }
        """)
        layout.addWidget(label)
        
        container.setLayout(layout)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
        self.setLayout(main_layout)
        
        # Size and position
        self.adjustSize()
        self._position_window()
        
        # Set initial opacity for fade-in
        self.setWindowOpacity(0.0)
    
    def _position_window(self):
        """Position the toast window based on position setting"""
        if not self.parent():
            # If no parent, try to position relative to screen
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    screen_rect = screen.availableGeometry()
                    toast_rect = self.geometry()
                    
                    if self.position == "top":
                        x = screen_rect.x() + (screen_rect.width() - toast_rect.width()) // 2
                        y = screen_rect.y() + 20
                    elif self.position == "center":
                        x = screen_rect.x() + (screen_rect.width() - toast_rect.width()) // 2
                        y = screen_rect.y() + (screen_rect.height() - toast_rect.height()) // 2
                    else:  # bottom
                        x = screen_rect.x() + (screen_rect.width() - toast_rect.width()) // 2
                        y = screen_rect.y() + screen_rect.height() - toast_rect.height() - 50
                    
                    self.move(x, y)
            return
        
        parent_rect = self.parent().geometry()
        toast_rect = self.geometry()
        
        if self.position == "top":
            x = parent_rect.x() + (parent_rect.width() - toast_rect.width()) // 2
            y = parent_rect.y() + 20
        elif self.position == "center":
            x = parent_rect.x() + (parent_rect.width() - toast_rect.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - toast_rect.height()) // 2
        else:  # bottom
            x = parent_rect.x() + (parent_rect.width() - toast_rect.width()) // 2
            y = parent_rect.y() + parent_rect.height() - toast_rect.height() - 50
        
        self.move(x, y)
    
    def setup_animations(self):
        """Setup fade-in and fade-out animations"""
        # Fade-in animation
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in_animation.finished.connect(self._start_display_timer)
        
        # Fade-out animation
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(300)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.InCubic)
        self.fade_out_animation.finished.connect(self.close)
    
    def _start_display_timer(self):
        """Start timer to show toast for duration"""
        QTimer.singleShot(self.duration_ms, self._start_fade_out)
    
    def _start_fade_out(self):
        """Start fade-out animation"""
        self.fade_out_animation.start()
    
    def show(self):
        """Show the toast"""
        super().show()
        self.raise_()
        self.activateWindow()


class StatusBarHelper:
    """
    Helper class for managing status bar messages.
    
    Provides simple functions to update status bar with different message types.
    """
    
    def __init__(self, status_bar: QStatusBar):
        """
        Initialize status bar helper.
        
        Args:
            status_bar: The QStatusBar widget to manage.
        """
        self.status_bar = status_bar
    
    def show_message(self, message: str, timeout: int = 0):
        """
        Show a message in the status bar.
        
        Args:
            message: Message to display.
            timeout: Timeout in milliseconds (0 = permanent until next message).
        """
        if self.status_bar:
            self.status_bar.showMessage(message, timeout)
    
    def show_info(self, message: str, timeout: int = 5000):
        """Show an info message."""
        self.show_message(f"ℹ️ {message}", timeout)
    
    def show_success(self, message: str, timeout: int = 5000):
        """Show a success message."""
        self.show_message(f"✓ {message}", timeout)
    
    def show_warning(self, message: str, timeout: int = 5000):
        """Show a warning message."""
        self.show_message(f"⚠ {message}", timeout)
    
    def show_error(self, message: str, timeout: int = 5000):
        """Show an error message."""
        self.show_message(f"✗ {message}", timeout)
    
    def show_sync_state(self, state: str):
        """
        Show sync state in status bar.
        
        Args:
            state: Sync state message (e.g., "Syncing...", "Offline", "Ready").
        """
        self.show_message(f"🔄 {state}", 0)  # Permanent until next update
    
    def clear(self):
        """Clear the status bar message."""
        if self.status_bar:
            self.status_bar.clearMessage()


# Global helper functions for easy access

_toast_parent: Optional[QWidget] = None
_status_bar_helper: Optional[StatusBarHelper] = None


def set_toast_parent(parent: QWidget):
    """
    Set the parent widget for toast notifications.
    
    Args:
        parent: Parent widget (usually main window).
    """
    global _toast_parent
    _toast_parent = parent


def set_status_bar(status_bar: QStatusBar):
    """
    Set the status bar for status updates.
    
    Args:
        status_bar: The QStatusBar widget.
    """
    global _status_bar_helper
    _status_bar_helper = StatusBarHelper(status_bar)


def show_toast(
    message: str,
    duration_ms: int = 3000,
    position: str = "bottom",
    parent: Optional[QWidget] = None
):
    """
    Show a toast notification.
    
    Args:
        message: Message to display.
        duration_ms: Duration in milliseconds (default: 3000).
        position: Position ("top", "bottom", "center", default: "bottom").
        parent: Parent widget (uses global if not provided).
    """
    toast_parent = parent or _toast_parent
    if not toast_parent:
        # Fallback: try to find main window
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if hasattr(widget, 'isWindow') and widget.isWindow():
                    toast_parent = widget
                    break
    
    if toast_parent:
        toast = ToastWidget(toast_parent, message, duration_ms, position)
        toast.show()


def show_toast_success(message: str, duration_ms: int = 3000):
    """Show a success toast notification."""
    show_toast(f"✓ {message}", duration_ms)


def show_toast_error(message: str, duration_ms: int = 4000):
    """Show an error toast notification."""
    show_toast(f"✗ {message}", duration_ms)


def show_toast_info(message: str, duration_ms: int = 3000):
    """Show an info toast notification."""
    show_toast(f"ℹ️ {message}", duration_ms)


def show_toast_warning(message: str, duration_ms: int = 4000):
    """Show a warning toast notification."""
    show_toast(f"⚠ {message}", duration_ms)


def update_status(message: str, timeout: int = 0):
    """
    Update status bar message.
    
    Args:
        message: Message to display.
        timeout: Timeout in milliseconds (0 = permanent).
    """
    if _status_bar_helper:
        _status_bar_helper.show_message(message, timeout)


def update_status_info(message: str, timeout: int = 5000):
    """Update status bar with info message."""
    if _status_bar_helper:
        _status_bar_helper.show_info(message, timeout)


def update_status_success(message: str, timeout: int = 5000):
    """Update status bar with success message."""
    if _status_bar_helper:
        _status_bar_helper.show_success(message, timeout)


def update_status_warning(message: str, timeout: int = 5000):
    """Update status bar with warning message."""
    if _status_bar_helper:
        _status_bar_helper.show_warning(message, timeout)


def update_status_error(message: str, timeout: int = 5000):
    """Update status bar with error message."""
    if _status_bar_helper:
        _status_bar_helper.show_error(message, timeout)


def update_sync_state(state: str):
    """
    Update sync state in status bar.
    
    Args:
        state: Sync state (e.g., "Syncing...", "Offline", "Ready").
    """
    if _status_bar_helper:
        _status_bar_helper.show_sync_state(state)


def clear_status():
    """Clear status bar message."""
    if _status_bar_helper:
        _status_bar_helper.clear()

