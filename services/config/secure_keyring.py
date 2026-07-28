"""Secure API key storage with system keyring fallback to encrypted file."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

SERVICE_NAME = "opportunityos"


class SecureKeyring:
    """Manages API keys with system keyring or encrypted fallback."""

    def __init__(self, config_dir: str | Path | None = None) -> None:
        """Initialize secure keyring.

        Args:
            config_dir: Directory for encrypted key storage (fallback)
        """
        self._config_dir = Path(config_dir or Path.home() / ".opportunityos")
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._cipher: Fernet | None = None
        self._keys_file = self._config_dir / "keys.encrypted"
        self._master_key_file = self._config_dir / ".master"

        # Initialize encryption if needed
        if not HAS_KEYRING:
            self._init_encryption()

    def set_key(self, key_name: str, value: str) -> bool:
        """Store an API key securely.

        Args:
            key_name: Name of the key (e.g., "openai_api_key")
            value: API key value

        Returns:
            True if stored successfully
        """
        try:
            if HAS_KEYRING:
                keyring.set_password(SERVICE_NAME, key_name, value)
                logger.debug(f"Stored {key_name} in system keyring")
                return True
            else:
                return self._set_encrypted_key(key_name, value)
        except Exception as e:
            logger.error(f"Error storing key {key_name}: {e}")
            return False

    def get_key(self, key_name: str) -> Optional[str]:
        """Retrieve an API key.

        Args:
            key_name: Name of the key to retrieve

        Returns:
            API key value or None if not found
        """
        try:
            if HAS_KEYRING:
                value = keyring.get_password(SERVICE_NAME, key_name)
                if value:
                    logger.debug(f"Retrieved {key_name} from system keyring")
                return value
            else:
                return self._get_encrypted_key(key_name)
        except Exception as e:
            logger.warning(f"Error retrieving key {key_name}: {e}")
            return None

    def delete_key(self, key_name: str) -> bool:
        """Delete a stored API key.

        Args:
            key_name: Name of the key to delete

        Returns:
            True if deleted successfully
        """
        try:
            if HAS_KEYRING:
                keyring.delete_password(SERVICE_NAME, key_name)
                logger.debug(f"Deleted {key_name} from system keyring")
                return True
            else:
                return self._delete_encrypted_key(key_name)
        except Exception as e:
            logger.error(f"Error deleting key {key_name}: {e}")
            return False

    def _init_encryption(self) -> None:
        """Initialize Fernet encryption cipher."""
        if self._master_key_file.exists():
            try:
                with open(self._master_key_file, "r") as f:
                    master_key = f.read().strip()
                self._cipher = Fernet(master_key.encode())
                logger.debug("Encryption initialized with existing master key")
            except Exception as e:
                logger.error(f"Error loading master key: {e}")
                self._generate_master_key()
        else:
            self._generate_master_key()

    def _generate_master_key(self) -> None:
        """Generate and store a new master key."""
        try:
            master_key = Fernet.generate_key().decode()
            # Set restrictive permissions
            old_umask = os.umask(0o077)
            with open(self._master_key_file, "w") as f:
                f.write(master_key)
            os.umask(old_umask)
            self._cipher = Fernet(master_key.encode())
            logger.info("Generated new master encryption key")
        except Exception as e:
            logger.error(f"Error generating master key: {e}")

    def _set_encrypted_key(self, key_name: str, value: str) -> bool:
        """Store key in encrypted file."""
        if not self._cipher:
            logger.error("Cipher not initialized")
            return False

        try:
            # Load existing keys
            keys_data = {}
            if self._keys_file.exists():
                try:
                    with open(self._keys_file, "r") as f:
                        encrypted_content = f.read()
                    decrypted = self._cipher.decrypt(encrypted_content.encode()).decode()
                    keys_data = json.loads(decrypted)
                except InvalidToken:
                    logger.warning("Could not decrypt existing keys file, starting fresh")
                    keys_data = {}

            # Add/update key
            keys_data[key_name] = value

            # Encrypt and save
            encrypted = self._cipher.encrypt(json.dumps(keys_data).encode()).decode()
            old_umask = os.umask(0o077)
            with open(self._keys_file, "w") as f:
                f.write(encrypted)
            os.umask(old_umask)
            logger.debug(f"Stored {key_name} in encrypted file")
            return True
        except Exception as e:
            logger.error(f"Error storing encrypted key: {e}")
            return False

    def _get_encrypted_key(self, key_name: str) -> Optional[str]:
        """Retrieve key from encrypted file."""
        if not self._cipher or not self._keys_file.exists():
            return None

        try:
            with open(self._keys_file, "r") as f:
                encrypted_content = f.read()
            decrypted = self._cipher.decrypt(encrypted_content.encode()).decode()
            keys_data = json.loads(decrypted)
            return keys_data.get(key_name)
        except Exception as e:
            logger.warning(f"Error retrieving encrypted key: {e}")
            return None

    def _delete_encrypted_key(self, key_name: str) -> bool:
        """Delete key from encrypted file."""
        if not self._cipher or not self._keys_file.exists():
            return False

        try:
            with open(self._keys_file, "r") as f:
                encrypted_content = f.read()
            decrypted = self._cipher.decrypt(encrypted_content.encode()).decode()
            keys_data = json.loads(decrypted)

            if key_name in keys_data:
                del keys_data[key_name]
                encrypted = self._cipher.encrypt(json.dumps(keys_data).encode()).decode()
                old_umask = os.umask(0o077)
                with open(self._keys_file, "w") as f:
                    f.write(encrypted)
                os.umask(old_umask)
                logger.debug(f"Deleted {key_name} from encrypted file")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting encrypted key: {e}")
            return False
