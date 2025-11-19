"""
Encryption utilities for secure storage of credentials and tokens
"""
import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import config


class EncryptionManager:
    """Manages encryption and decryption of sensitive data"""
    
    def __init__(self):
        self.key_file = config.ENCRYPTION_KEY_FILE
        self._key = self._get_or_create_key()
        self._cipher = Fernet(self._key)
    
    def _get_or_create_key(self) -> bytes:
        """Get existing encryption key or create a new one"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            # Generate a new key
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions (Unix-like systems)
            try:
                os.chmod(self.key_file, 0o600)
            except:
                pass
            return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt a string and return base64-encoded result"""
        if not data:
            return ""
        encrypted = self._cipher.encrypt(data.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt a base64-encoded string"""
        if not encrypted_data:
            return ""
        try:
            decoded = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted = self._cipher.decrypt(decoded)
            return decrypted.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")


# Global encryption manager instance
_encryption_manager = None

def get_encryption_manager() -> EncryptionManager:
    """Get the global encryption manager instance"""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager

