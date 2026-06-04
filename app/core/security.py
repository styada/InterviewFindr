"""Password hashing and signed session-token helpers."""
from __future__ import annotations

import uuid

from argon2 import PasswordHasher
from itsdangerous import BadSignature, URLSafeSerializer

from app.core.config import get_settings

_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    """Hash a password with argon2id (sensible defaults from argon2-cffi)."""
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Constant-time-ish verify. Returns False for any error (malformed hash etc)."""
    try:
        return _hasher.verify(hashed, plaintext)
    except Exception:
        return False


def create_session_token(user_id: uuid.UUID | str) -> str:
    """Sign a user_id into a URL-safe session cookie value."""
    serializer = URLSafeSerializer(get_settings().app_secret_key, salt="session")
    return serializer.dumps(str(user_id))


def verify_session_token(token: str) -> str | None:
    """Return the user_id encoded in a session token, or None if invalid/tampered."""
    serializer = URLSafeSerializer(get_settings().app_secret_key, salt="session")
    try:
        return serializer.loads(token)
    except BadSignature:
        return None
