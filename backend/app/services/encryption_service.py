"""
Encryption service for sensitive data protection.

WHAT: Provides symmetric encryption using Fernet for sensitive data at rest.

WHY: OWASP A02 (Cryptographic Failures) requires encrypting sensitive data
at rest. API keys, tokens, and credentials must be encrypted before storage.

HOW: Uses Fernet (from cryptography library) which provides:
- AES-128-CBC encryption
- HMAC-SHA256 authentication
- URL-safe base64 encoding
- Automatic timestamp for key rotation support
"""

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import EncryptionError

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.

    WHAT: Handles encryption/decryption using Fernet symmetric encryption.

    WHY: Centralizes encryption logic for:
    - API keys (n8n, external services)
    - Tokens and credentials
    - Any sensitive configuration

    HOW: Uses Fernet with a key from environment variables.
    Key must be 32 bytes, URL-safe base64-encoded.

    Security notes:
    - Never log plaintext values
    - Key rotation supported via Fernet.MultiFernet
    - Invalid tokens raise EncryptionError (no silent failures)

    Example:
        service = EncryptionService()
        encrypted = service.encrypt("my-api-key")
        decrypted = service.decrypt(encrypted)
    """

    def __init__(self, key: Optional[str] = None):
        """
        Initialize encryption service.

        WHAT: Sets up Fernet cipher with encryption key.

        WHY: Key can be passed directly (for testing) or loaded from settings.

        Args:
            key: Optional Fernet key (base64-encoded). Defaults to settings.ENCRYPTION_KEY.

        Raises:
            EncryptionError: If key is missing or invalid.
        """
        encryption_key = key or settings.ENCRYPTION_KEY

        if not encryption_key:
            logger.error("Encryption key not configured")
            raise EncryptionError(
                message="Encryption key not configured",
                details={"hint": "Set ENCRYPTION_KEY environment variable"},
            )

        try:
            self._fernet = Fernet(encryption_key.encode())
            logger.debug("Encryption service initialized")
        except Exception as e:
            logger.error(f"Invalid encryption key format: {e}")
            raise EncryptionError(
                message="Invalid encryption key format",
                details={"hint": "Key must be 32 bytes, URL-safe base64-encoded"},
                original_exception=e,
            )

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        WHAT: Encrypts string using Fernet symmetric encryption.

        WHY: Protects sensitive data before storage.

        HOW: Encodes to bytes, encrypts with Fernet, returns base64 string.

        Args:
            plaintext: The string to encrypt.

        Returns:
            Base64-encoded encrypted ciphertext.

        Raises:
            EncryptionError: If encryption fails.

        Example:
            encrypted = service.encrypt("sk-abc123")
            # Returns: "gAAAAABl..."
        """
        if not plaintext:
            raise EncryptionError(
                message="Cannot encrypt empty value",
                details={"error": "plaintext is empty or None"},
            )

        try:
            ciphertext = self._fernet.encrypt(plaintext.encode())
            return ciphertext.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {type(e).__name__}")
            raise EncryptionError(
                message="Failed to encrypt data",
                original_exception=e,
            )

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted ciphertext.

        WHAT: Decrypts Fernet-encrypted string back to plaintext.

        WHY: Retrieves original value for use (API calls, etc.).

        HOW: Decodes base64, decrypts with Fernet, returns string.

        Args:
            ciphertext: Base64-encoded encrypted string.

        Returns:
            Decrypted plaintext string.

        Raises:
            EncryptionError: If decryption fails (invalid token, wrong key).

        Example:
            plaintext = service.decrypt("gAAAAABl...")
            # Returns: "sk-abc123"
        """
        if not ciphertext:
            raise EncryptionError(
                message="Cannot decrypt empty value",
                details={"error": "ciphertext is empty or None"},
            )

        try:
            plaintext = self._fernet.decrypt(ciphertext.encode())
            return plaintext.decode()
        except InvalidToken:
            logger.warning("Decryption failed: invalid token or wrong key")
            raise EncryptionError(
                message="Failed to decrypt data",
                details={"error": "Invalid token - data may be corrupted or key changed"},
            )
        except Exception as e:
            logger.error(f"Decryption failed: {type(e).__name__}")
            raise EncryptionError(
                message="Failed to decrypt data",
                original_exception=e,
            )

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        WHAT: Creates a new random encryption key.

        WHY: Utility for initial setup and key rotation.

        Returns:
            URL-safe base64-encoded 32-byte key.

        Example:
            key = EncryptionService.generate_key()
            # Returns: "abc123...=" (44 characters)
        """
        return Fernet.generate_key().decode()


# =============================================================================
# Module-level convenience functions
# =============================================================================

_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get or create the global encryption service instance.

    WHAT: Singleton pattern for encryption service.

    WHY: Ensures consistent key usage across the application.

    Returns:
        EncryptionService instance.
    """
    global _encryption_service

    if _encryption_service is None:
        _encryption_service = EncryptionService()

    return _encryption_service


def encrypt_value(plaintext: str) -> str:
    """
    Convenience function to encrypt a value.

    Args:
        plaintext: String to encrypt.

    Returns:
        Encrypted ciphertext.
    """
    return get_encryption_service().encrypt(plaintext)


def decrypt_value(ciphertext: str) -> str:
    """
    Convenience function to decrypt a value.

    Args:
        ciphertext: Encrypted string to decrypt.

    Returns:
        Decrypted plaintext.
    """
    return get_encryption_service().decrypt(ciphertext)
