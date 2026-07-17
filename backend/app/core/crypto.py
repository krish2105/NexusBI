"""Reversible encryption for secrets at rest (target DSNs).

Connection strings can carry credentials, so we never store them in plaintext.
We derive a Fernet key from ``ENCRYPTION_KEY`` (or fall back to ``JWT_SECRET``)
and encrypt DSNs before they touch the app DB. If ``cryptography`` is somehow
unavailable, we refuse to silently store plaintext — encryption is required for
custom connections.
"""
from __future__ import annotations

import base64
import hashlib

from app.config import settings

_PREFIX = "enc:v1:"


def _fernet():
    from cryptography.fernet import Fernet  # local import keeps base install light

    secret = (getattr(settings, "encryption_key", None) or settings.jwt_secret).encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    token = _fernet().encrypt(plaintext.encode()).decode()
    return _PREFIX + token


def decrypt(value: str) -> str:
    if not value or not value.startswith(_PREFIX):
        return value  # tolerate legacy/plaintext (e.g. the bundled sqlite demo path)
    token = value[len(_PREFIX):]
    return _fernet().decrypt(token.encode()).decode()
