"""Integration tests for the profile endpoints."""
from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Profile, User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def client(engine) -> Iterator[TestClient]:
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


def _register_and_login(
    client: TestClient, engine, email: str = "p@example.com"
) -> tuple[dict, User]:
    r = client.post(
        "/auth/register",
        data={
            "email": email,
            "display_name": "Profile Tester",
            "password": "a-very-long-password-1",
        },
    )
    assert r.status_code == 200, r.text
    user_id = r.json()["id"]
    login = client.post(
        "/auth/login",
        data={"email": email, "password": "a-very-long-password-1"},
    )
    assert login.status_code == 200
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestSession() as s:
        user = s.get(User, user_id)  # type: ignore[arg-type]
        assert user is not None
    return dict(login.cookies), user


def _create_profile(engine, user_id: str) -> None:
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestSession() as s:
        s.add(
            Profile(
                user_id=user_id,
                market_primary="US",
                market_secondary=[],
                preferences={"salary_min": 120000},
                auto_apply_allowlist=[],
                tailoring_thresholds={},
            )
        )
        s.commit()


def test_get_profile_requires_auth(client: TestClient) -> None:
    r = client.get("/me/profile")
    assert r.status_code == 401


def test_get_profile_returns_404_when_no_profile_row(client: TestClient, engine) -> None:
    cookies, _ = _register_and_login(client, engine, "no-prof@example.com")
    r = client.get("/me/profile", cookies=cookies)
    assert r.status_code == 404


def test_get_profile_returns_profile(client: TestClient, engine) -> None:
    cookies, user = _register_and_login(client, engine, "get@example.com")
    _create_profile(engine, user.id)
    r = client.get("/me/profile", cookies=cookies)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["market_primary"] == "US"
    assert body["preferences"]["salary_min"] == 120000
    assert body["has_resume"] is False


def test_patch_profile_updates_fields(client: TestClient, engine) -> None:
    cookies, user = _register_and_login(client, engine, "patch@example.com")
    _create_profile(engine, user.id)
    r = client.patch(
        "/me/profile",
        json={
            "market_primary": "CA",
            "preferences": {"salary_min": 200000, "remote": True},
            "auto_apply_enabled": True,
        },
        cookies=cookies,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["market_primary"] == "CA"
    assert body["preferences"]["salary_min"] == 200000
    assert body["auto_apply_enabled"] is True


def test_upload_resume_rejects_bad_content_type(client: TestClient, engine) -> None:
    cookies, _user = _register_and_login(client, engine, "bad@example.com")
    r = client.post(
        "/me/profile/resume",
        files={"file": ("resume.exe", b"hello", "application/octet-stream")},
        cookies=cookies,
    )
    assert r.status_code == 415


def test_upload_resume_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/me/profile/resume",
        files={"file": ("r.txt", b"hi", "text/plain")},
    )
    assert r.status_code == 401


def test_upload_resume_updates_paths_and_parses(client: TestClient, engine) -> None:
    cookies, user = _register_and_login(client, engine, "pdf@example.com")
    _create_profile(engine, user.id)
    with respx.mock(base_url="https://opencode.ai") as mock:
        mock.post("/zen/go/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"name": "Jane Doe", "experiences": [],'
                                    ' "education": [], "skills": ["python"]}'
                                )
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 30},
                },
            )
        )
        r = client.post(
            "/me/profile/resume",
            files={
                "file": (
                    "resume.pdf",
                    b"%PDF-stub-bytes",
                    "application/pdf",
                )
            },
            cookies=cookies,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_resume"] is True
    assert body["resume_pdf_path"] is not None
    assert body["resume_pdf_path"].endswith("original.pdf")
    assert body["resume_parsed_json"]["name"] == "Jane Doe"
