"""Unit tests for app.core.config."""
from __future__ import annotations

import pytest

from app.core.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:5432/d")
    s = Settings()
    assert s.app_secret_key == "x" * 32
    assert s.database_url.startswith("postgresql+psycopg://")


def test_settings_requires_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    with pytest.raises(Exception):
        Settings()


def test_get_settings_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("APP_SECRET_KEY", "y" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:5432/d")
    a = get_settings()
    b = get_settings()
    assert a is b
