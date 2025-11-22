"""
Application settings management.

This module provides user settings management with persistence
through the cache repository.
"""
import json
from dataclasses import dataclass, asdict
from typing import Optional
from email_client.storage import cache_repo


@dataclass
class UserSettings:
    """User application settings."""
    theme: str = "light"
    refresh_interval_seconds: int = 60
    show_preview_pane: bool = True
    default_account_id: Optional[int] = None


def load_settings(user_id: int) -> UserSettings:
    """
    Load user settings from storage.
    
    Args:
        user_id: The user ID.
        
    Returns:
        UserSettings object. Returns default settings if none are stored.
    """
    settings_key = f"user_{user_id}_settings"
    
    # Get all settings
    all_settings = cache_repo.get_settings()
    
    # Check if user settings exist
    if settings_key in all_settings:
        try:
            # Parse JSON settings
            settings_data = all_settings[settings_key]
            if isinstance(settings_data, str):
                settings_dict = json.loads(settings_data)
            else:
                settings_dict = settings_data
            
            # Create UserSettings from dictionary
            return UserSettings(
                theme=settings_dict.get("theme", "light"),
                refresh_interval_seconds=settings_dict.get("refresh_interval_seconds", 60),
                show_preview_pane=settings_dict.get("show_preview_pane", True),
                default_account_id=settings_dict.get("default_account_id"),
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            # If parsing fails, return defaults
            return UserSettings()
    
    # Return default settings if none stored
    return UserSettings()


def save_settings(user_id: int, settings: UserSettings) -> None:
    """
    Save user settings to storage.
    
    Args:
        user_id: The user ID.
        settings: The UserSettings object to save.
    """
    settings_key = f"user_{user_id}_settings"
    
    # Convert dataclass to dictionary
    settings_dict = asdict(settings)
    
    # Serialize to JSON
    settings_json = json.dumps(settings_dict, default=str)
    
    # Save to cache repository
    cache_repo.save_settings(settings_key, settings_json)

