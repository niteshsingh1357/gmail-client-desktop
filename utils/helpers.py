"""
Helper utility functions
"""
import re
from email.utils import parseaddr
from datetime import datetime, timedelta


def validate_email(email: str) -> bool:
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def parse_email_address(email_string: str) -> tuple[str, str]:
    """Parse email address string into (name, email) tuple"""
    name, email = parseaddr(email_string)
    return name, email


def format_date(date_obj) -> str:
    """Format date for display"""
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
        except:
            return date_obj
    
    if not isinstance(date_obj, datetime):
        return str(date_obj)
    
    now = datetime.now()
    diff = now - date_obj.replace(tzinfo=None) if date_obj.tzinfo else now - date_obj
    
    if diff.days == 0:
        return date_obj.strftime("%H:%M")
    elif diff.days == 1:
        return "Yesterday"
    elif diff.days < 7:
        return date_obj.strftime("%A")
    elif diff.days < 365:
        return date_obj.strftime("%b %d")
    else:
        return date_obj.strftime("%b %d, %Y")


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to max length with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

