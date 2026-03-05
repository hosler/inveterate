"""Custom model fields for inveterate."""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


def _get_fernet():
    """Build a Fernet instance from ``settings.FIELD_ENCRYPTION_KEY``.

    The key must be a URL-safe base64-encoded 32-byte key.
    Generate one with ``from cryptography.fernet import Fernet; Fernet.generate_key()``.
    """
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if not key:
        raise ValueError("settings.FIELD_ENCRYPTION_KEY must be set to use EncryptedCharField")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


class EncryptedCharField(models.CharField):
    """CharField that transparently encrypts values before saving to the database.

    Values are Fernet-encrypted and stored as base64.  On read, the field
    attempts decryption; if decryption fails (e.g. the value was stored as
    plaintext before encryption was enabled) the raw value is returned as-is,
    allowing a smooth migration path.
    """

    def get_prep_value(self, value):
        """Encrypt before saving to the database."""
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        f = _get_fernet()
        return f.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        """Decrypt when reading from the database."""
        if value is None or value == "":
            return value
        try:
            f = _get_fernet()
            return f.decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            # Value is still plaintext (pre-migration) — return as-is
            return value

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # Use our own import path so migrations reference this field
        path = "inveterate.fields.EncryptedCharField"
        return name, path, args, kwargs
