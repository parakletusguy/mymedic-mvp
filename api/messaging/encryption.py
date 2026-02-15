"""
Messaging Domain — Encryption Utilities.

Provides Fernet symmetric encryption for message content at rest.
The key is derived from the application's JWT secret key using
PBKDF2HMAC, ensuring consistency across server restarts.

IMPORTANT: This is application-level encryption (defense in depth).
Database-level encryption (TDE) and TLS for data in transit are
separate concerns handled at the infrastructure layer.
"""

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from api.core.config import settings


def _derive_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from the JWT secret using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"mymedic-msg-salt-v1",  # Static salt (key rotation = new salt)
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))


# Singleton cipher — derived once at import time.
_fernet = Fernet(_derive_key(settings.jwt_secret_key))


def encrypt_message(plaintext: str) -> str:
    """Encrypt a plaintext message. Returns a Fernet token string."""
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_message(ciphertext: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
