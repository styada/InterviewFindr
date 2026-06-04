"""Integration tests for the matches / apply / scheduler endpoints."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Application, Job, Match, Profile, TailoredArtifact, User
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
    client: TestClient, engine, email: str, role: str = "member"
) -> tuple[dict, User]:
    r = client.post(
        "/auth/register",
        data={
            "email": email,
            "display_name": email.split("@")[0].title(),
            "password": "a-very-long-password-1",
            "role": role,
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


def _seed_minimum(engine, user: User) -> tuple[Job, Match, TailoredArtifact]:
    """Profile + Job + Match + TailoredArtifact (status=tailored)."""
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestSession() as s:
        s.add(
            Profile(
                user_id=user.id,
                market_primary="US",
                market_secondary=[],
                preferences={},
                auto_apply_allowlist=[],
                tailoring_thresholds={},
                resume_parsed_json={"name": "X"},
            )
        )
        job = Job(
            source="greenhouse",
            external_id="job-1",
            url="https://example.com/jobs/1",
            company="Acme",
            title="Senior Engineer",
            location="Remote",
        )
        s.add(job)
        s.flush()
        m = Match(
            user_id=user.id,
            job_id=job.id,
            match_score=0.72,
            status="tailored",
        )
        s.add(m)
        s.flush()
        ta = TailoredArtifact(
            match_id=m.id,
            resume_text="Tailored resume body",
            resume_pdf_path=f"resumes/{user.id}/tailored.pdf",
            cover_letter_text="Dear Acme...",
            cover_letter_pdf=f"resumes/{user.id}/cover.pdf",
            model_used="kimi-k2.6",
            token_cost_usd=0.000123,
        )
        s.add(ta)
        s.commit()
        s.refresh(job)
        s.refresh(m)
        s.refresh(ta)
        return job, m, ta


def test_list_matches_requires_auth(client: TestClient) -> None:
    r = client.get("/me/matches")
    assert r.status_code == 401


def test_list_matches_returns_empty_when_none(client: TestClient, engine) -> None:
    cookies, _ = _register_and_login(client, engine, "list@example.com")
    r = client.get("/me/matches", cookies=cookies)
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_matches_returns_seeded_matches(client: TestClient, engine) -> None:
    cookies, user = _register_and_login(client, engine, "seed@example.com")
    job, m, _ta = _seed_minimum(engine, user)
    r = client.get("/me/matches", cookies=cookies)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == str(m.id)
    assert item["match_score"] == pytest.approx(0.72)
    assert item["status"] == "tailored"
    assert item["job"]["title"] == "Senior Engineer"
    assert item["job"]["company"] == "Acme"
    assert item["tailored"]["resume_text"] == "Tailored resume body"


def test_list_matches_status_filter(client: TestClient, engine) -> None:
    cookies, user = _register_and_login(client, engine, "filt@example.com")
    _job, _m, _ta = _seed_minimum(engine, user)
    r = client.get("/me/matches?status=skipped", cookies=cookies)
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_get_match_detail(client: TestClient, engine) -> None:
    cookies, user = _register_and_login(client, engine, "det@example.com")
    _job, m, _ta = _seed_minimum(engine, user)
    r = client.get(f"/me/matches/{m.id}", cookies=cookies)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(m.id)
    assert body["tailored"]["cover_letter_text"] == "Dear Acme..."


def test_get_match_404_for_other_user(client: TestClient, engine) -> None:
    cookies_a, user_a = _register_and_login(client, engine, "a@example.com")
    _job, m, _ta = _seed_minimum(engine, user_a)
    cookies_b, _ = _register_and_login(client, engine, "b@example.com")
    r = client.get(f"/me/matches/{m.id}", cookies=cookies_b)
    assert r.status_code == 404


def test_get_job_requires_auth(client: TestClient) -> None:
    r = client.get(f"/jobs/{uuid.uuid4()}")
    assert r.status_code == 401


def test_get_job_returns_seeded_job(client: TestClient, engine) -> None:
    cookies, user = _register_and_login(client, engine, "job@example.com")
    job, _m, _ta = _seed_minimum(engine, user)
    r = client.get(f"/jobs/{job.id}", cookies=cookies)
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Senior Engineer"
    assert body["company"] == "Acme"


def test_assisted_apply_creates_application_row(client: TestClient, engine) -> None:
    cookies, user = _register_and_login(client, engine, "apply@example.com")
    job, m, _ta = _seed_minimum(engine, user)
    r = client.post(f"/me/matches/{m.id}/apply/assisted", cookies=cookies)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["job_url"] == "https://example.com/jobs/1"
    assert body["job_title"] == "Senior Engineer"
    assert body["job_company"] == "Acme"
    assert body["resume_pdf_url"] == f"/me/matches/{m.id}/resume.pdf"
    assert body["cover_letter_pdf_url"] == f"/me/matches/{m.id}/cover_letter.pdf"
    assert isinstance(body["instructions"], list) and body["instructions"]

    # Application row should exist in the DB
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestSession() as s:
        apps = list(s.query(Application).all())
        assert len(apps) == 1
        a = apps[0]
        assert a.user_id == user.id
        assert a.job_id == job.id
        assert a.match_id == m.id
        assert a.mode == "assisted"
        assert a.status == "queued"


def test_assisted_apply_409_when_match_not_tailored(
    client: TestClient, engine
) -> None:
    cookies, user = _register_and_login(client, engine, "409@example.com")
    _job, m, _ta = _seed_minimum(engine, user)
    # Move match to "skipped" — not eligible
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestSession() as s:
        match = s.get(Match, m.id)
        assert match is not None
        match.status = "skipped"
        s.commit()
    r = client.post(f"/me/matches/{m.id}/apply/assisted", cookies=cookies)
    assert r.status_code == 409


def test_assisted_apply_404_for_other_user(client: TestClient, engine) -> None:
    cookies_a, user_a = _register_and_login(client, engine, "own@example.com")
    _job, m, _ta = _seed_minimum(engine, user_a)
    cookies_b, _ = _register_and_login(client, engine, "intruder@example.com")
    r = client.post(f"/me/matches/{m.id}/apply/assisted", cookies=cookies_b)
    assert r.status_code == 404


def test_skip_match_updates_status(client: TestClient, engine) -> None:
    cookies, user = _register_and_login(client, engine, "skip@example.com")
    _job, m, _ta = _seed_minimum(engine, user)
    r = client.post(f"/me/matches/{m.id}/skip", cookies=cookies)
    assert r.status_code == 200
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestSession() as s:
        assert s.get(Match, m.id).status == "skipped"  # type: ignore[union-attr]


def test_admin_refresh_requires_admin_role(client: TestClient, engine) -> None:
    cookies, _ = _register_and_login(client, engine, "nonadmin@example.com")
    r = client.post("/admin/refresh", cookies=cookies)
    assert r.status_code == 403


def test_admin_refresh_runs_for_admin(client: TestClient, engine) -> None:
    cookies, _ = _register_and_login(
        client, engine, "admin@example.com", role="admin"
    )
    r = client.post("/admin/refresh", cookies=cookies)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert "completed_at" in body


def test_jobs_refresh_endpoint_kicks_scheduler(
    client: TestClient, engine
) -> None:
    cookies, _ = _register_and_login(client, engine, "kick@example.com")
    r = client.post("/jobs/refresh", cookies=cookies)
    assert r.status_code == 200
    assert r.json()["status"] == "scheduled"
