"""Integration tests for authentication endpoints."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Test client backed by an in-memory sqlite DB (separate from prod engine)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override_get_db() -> Iterator:
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_register_login_me_flow(client: TestClient) -> None:
    r = client.post(
        "/auth/register",
        data={
            "email": "test@example.com",
            "display_name": "Test",
            "password": "a-very-long-password-1",
            "role": "member",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "test@example.com"

    r = client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "a-very-long-password-1"},
    )
    assert r.status_code == 200
    assert "if_session" in r.cookies

    r = client.get("/auth/me", cookies=r.cookies)
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"


def test_login_with_wrong_password_fails(client: TestClient) -> None:
    r = client.post(
        "/auth/register",
        data={
            "email": "x@y.z",
            "display_name": "X",
            "password": "a-very-long-password-1",
        },
    )
    assert r.status_code == 200, r.text
    r = client.post("/auth/login", data={"email": "x@y.z", "password": "wrong"})
    assert r.status_code == 401


def test_me_without_cookie_returns_401(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_register_duplicate_email_returns_409(client: TestClient) -> None:
    r1 = client.post(
        "/auth/register",
        data={
            "email": "dup@example.com",
            "display_name": "A",
            "password": "a-very-long-password-1",
        },
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/auth/register",
        data={
            "email": "dup@example.com",
            "display_name": "B",
            "password": "a-very-long-password-1",
        },
    )
    assert r2.status_code == 409


def test_me_with_malformed_session_token_returns_401(client: TestClient) -> None:
    """Regression: session token containing a non-UUID string should be rejected
    (not raise a SQLAlchemy StatementError about UUID.hex)."""
    r = client.get("/auth/me", cookies={"if_session": "not-a-valid-uuid-payload"})
    assert r.status_code == 401


def test_logout_clears_cookie(client: TestClient) -> None:
    client.post(
        "/auth/register",
        data={
            "email": "lo@example.com",
            "display_name": "LO",
            "password": "a-very-long-password-1",
        },
    )
    login = client.post(
        "/auth/login",
        data={"email": "lo@example.com", "password": "a-very-long-password-1"},
    )
    assert "if_session" in login.cookies
    logout = client.post("/auth/logout")
    assert logout.status_code == 200
    assert "if_session" not in logout.cookies or logout.cookies.get("if_session") in (None, "")
