"""Unit tests for app.core.security."""
from __future__ import annotations

import uuid

from app.core.security import (
    create_session_token,
    hash_password,
    verify_password,
    verify_session_token,
)


def test_password_hash_round_trip() -> None:
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong", h)


def test_session_token_round_trip() -> None:
    user_id = "11111111-1111-1111-1111-111111111111"
    token = create_session_token(user_id=user_id)
    assert verify_session_token(token) == user_id


def test_session_token_rejects_tampering() -> None:
    user_id = "11111111-1111-1111-1111-111111111111"
    token = create_session_token(user_id=user_id)
    assert verify_session_token(token + "x") is None


def test_session_token_accepts_uuid() -> None:
    u = uuid.UUID("22222222-2222-2222-2222-222222222222")
    token = create_session_token(user_id=u)
    assert verify_session_token(token) == str(u)
