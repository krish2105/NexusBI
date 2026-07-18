"""Hashing, API-key issuance, and JWT helpers.

Uses stdlib only (hashlib/hmac/secrets) so the free-tier install stays light —
no bcrypt/passlib wheels required. API keys are shown once and stored only as a
salted SHA-256 hash.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.config import settings

_PBKDF_ITERS = 120_000


# --- API keys ---------------------------------------------------------------
def new_api_key() -> str:
    return "nxs_" + secrets.token_urlsafe(32)


def api_key_id(key: str) -> str:
    """A non-secret, deterministic index derived from an API key, so a presented
    key maps to exactly one user via an indexed column — turning O(n)-PBKDF2-scan
    auth into O(1) lookup + a single verify. Not reversible to the key, and
    knowing it grants nothing (auth still requires the key itself)."""
    return "kid_" + hashlib.sha256(key.encode()).hexdigest()[:24]


def hash_secret(secret: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), _PBKDF_ITERS)
    return f"pbkdf2_sha256${_PBKDF_ITERS}${salt}${dk.hex()}"


def verify_secret(secret: str, stored: str) -> bool:
    try:
        _algo, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, AttributeError):
        return False


# --- Minimal HS256 JWT (no external dependency) -----------------------------
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def create_jwt(sub: str, extra: dict | None = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": sub, "iat": int(time.time()),
               "exp": int(time.time()) + settings.jwt_expire_minutes * 60}
    if extra:
        payload.update(extra)
    segments = [_b64(json.dumps(header).encode()), _b64(json.dumps(payload).encode())]
    signing_input = ".".join(segments).encode()
    sig = hmac.new(settings.jwt_secret.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64(sig))
    return ".".join(segments)


def decode_jwt(token: str) -> dict | None:
    try:
        h_seg, p_seg, s_seg = token.split(".")
        signing_input = f"{h_seg}.{p_seg}".encode()
        expected = hmac.new(settings.jwt_secret.encode(), signing_input,
                            hashlib.sha256).digest()
        if not hmac.compare_digest(_b64d(s_seg), expected):
            return None
        payload = json.loads(_b64d(p_seg))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
