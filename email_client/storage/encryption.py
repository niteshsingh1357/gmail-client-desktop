"""
Symmetric encryption helpers for sensitive data storage.

This module provides encryption and decryption functions using Fernet
(AES-128 in CBC mode with HMAC) for secure storage of sensitive data
like OAuth tokens and credentials.
"""
import os
import json
from pathlib import Path
from typing import Any, Dict
from cryptography.fernet import Fernet, InvalidToken


class DecryptionError(Exception):
    """Raised when decryption fails due to corruption or invalid data."""
    pass


# Secret key file path
_SECRET_KEY_FILE = Path.home() / ".email_client" / "secret.key"


def _get_or_create_key() -> bytes:
    """
    Get the encryption key from file, or generate a new one if missing.
    
    Returns:
        The encryption key as bytes.
    """
    # Ensure directory exists
    _SECRET_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if _SECRET_KEY_FILE.exists():
        # Read existing key
        with open(_SECRET_KEY_FILE, 'rb') as f:
            key = f.read()
        
        # Validate key format
        try:
            Fernet(key)  # This will raise ValueError if key is invalid
            return key
        except (ValueError, TypeError):
            # Key is corrupted, generate a new one
            pass
    
    # Generate new key
    key = Fernet.generate_key()
    
    # Write key to file
    with open(_SECRET_KEY_FILE, 'wb') as f:
        f.write(key)
    
    # Set restrictive permissions (Unix-like systems)
    try:
        os.chmod(_SECRET_KEY_FILE, 0o600)
    except OSError:
        # Permission setting may fail on some systems, but that's okay
        pass
    
    return key


def _get_cipher() -> Fernet:
    """
    Get a Fernet cipher instance with the encryption key.
    
    Returns:
        A Fernet cipher instance.
    """
    key = _get_or_create_key()
    return Fernet(key)


def encrypt_bytes(data: bytes) -> bytes:
    """
    Encrypt bytes data.
    
    Args:
        data: The bytes data to encrypt.
        
    Returns:
        Encrypted bytes.
        
    Raises:
        ValueError: If data is empty or invalid.
    """
    if not data:
        raise ValueError("Cannot encrypt empty data")
    
    cipher = _get_cipher()
    return cipher.encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    """
    Decrypt bytes data.
    
    Args:
        data: The encrypted bytes data.
        
    Returns:
        Decrypted bytes.
        
    Raises:
        DecryptionError: If decryption fails (corrupted data, wrong key, etc.).
    """
    if not data:
        raise DecryptionError("Cannot decrypt empty data")
    
    try:
        cipher = _get_cipher()
        return cipher.decrypt(data)
    except InvalidToken as e:
        raise DecryptionError(f"Decryption failed: invalid or corrupted data") from e
    except Exception as e:
        raise DecryptionError(f"Decryption failed: {str(e)}") from e


def encrypt_text(text: str) -> bytes:
    """
    Encrypt a text string.
    
    Args:
        text: The text string to encrypt.
        
    Returns:
        Encrypted bytes.
        
    Raises:
        ValueError: If text is empty or invalid.
    """
    if not text:
        raise ValueError("Cannot encrypt empty text")
    
    data = text.encode('utf-8')
    return encrypt_bytes(data)


def decrypt_text(data: bytes) -> str:
    """
    Decrypt bytes data to a text string.
    
    Args:
        data: The encrypted bytes data.
        
    Returns:
        Decrypted text string.
        
    Raises:
        DecryptionError: If decryption fails (corrupted data, wrong key, etc.).
        UnicodeDecodeError: If decrypted data is not valid UTF-8.
    """
    decrypted_bytes = decrypt_bytes(data)
    
    try:
        return decrypted_bytes.decode('utf-8')
    except UnicodeDecodeError as e:
        raise DecryptionError(f"Decrypted data is not valid UTF-8: {str(e)}") from e


def encrypt_json(payload: Dict[str, Any]) -> bytes:
    """
    Encrypt a JSON-serializable payload (e.g., token bundle).
    
    Args:
        payload: A dictionary or other JSON-serializable object.
        
    Returns:
        Encrypted bytes containing the JSON payload.
        
    Raises:
        ValueError: If payload cannot be serialized to JSON.
    """
    try:
        json_str = json.dumps(payload, default=str)  # default=str handles datetime, etc.
        return encrypt_text(json_str)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Cannot serialize payload to JSON: {str(e)}") from e


def decrypt_json(data: bytes) -> Dict[str, Any]:
    """
    Decrypt bytes data to a JSON payload (e.g., token bundle).
    
    Args:
        data: The encrypted bytes data containing JSON.
        
    Returns:
        Decrypted dictionary (or other JSON object).
        
    Raises:
        DecryptionError: If decryption fails.
        json.JSONDecodeError: If decrypted data is not valid JSON.
    """
    try:
        json_str = decrypt_text(data)
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise DecryptionError(f"Decrypted data is not valid JSON: {str(e)}") from e

