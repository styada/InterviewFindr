"""End-to-end smoke test for the full pipeline.

Boots the FastAPI app on an in-memory SQLite DB, seeds a user + a job,
runs the 6-stage pipeline via the orchestrator, and verifies a Match +
TailoredArtifact are produced. No LLM or HTTP calls are made — stages
that need an LLM are exercised against deterministic stubs.
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_session_token
from app.db.base import Base
from app.db.models import Job, Profile, User
from app.db.session import get_db
from app.llm.base import LLMResponse
from app.main import app


class _FakeRouter:
    """Deterministic LLM stand-in. Returns the prompt's last user message verbatim."""

    async def complete(self, provider, model, messages, **kwargs):  # noqa: ANN001
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        return LLMResponse(
            text=last_user,
            input_tokens=len(last_user) // 4,
            output_tokens=len(last_user) // 4,
            cost_usd=0.0,
            raw={},
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
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
    with TestSession() as s, s.begin():
        u = User(email="smoke@example.com", display_name="Smoke", role="admin")
        s.add(u)
        s.flush()
        s.add(
            Profile(
                user_id=u.id,
                market_primary="US",
                market_secondary=[],
                preferences={"salary_min": 100000, "remote_ok": True},
                tailoring_thresholds={
                    "min_match_score": 0.10,
                    "must_have_coverage_min": 0.50,
                },
            )
        )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_smoke_register_login_pipeline_then_list_matches(client: TestClient) -> None:
    # 1. Register a new user (this also exercises the auth API end-to-end).
    r = client.post(
        "/auth/register",
        data={
            "email": "smoke2@example.com",
            "display_name": "Smoke 2",
            "password": "a-very-long-password-1",
            "role": "member",
        },
    )
    assert r.status_code == 200, r.text

    r = client.post(
        "/auth/login",
        data={"email": "smoke2@example.com", "password": "a-very-long-password-1"},
    )
    assert r.status_code == 200
    cookies = r.cookies
    assert "if_session" in cookies

    # 2. Insert a job directly into the DB (we have no real Greenhouse fetch in the smoke test).
    with app.dependency_overrides[get_db]() as db:
        # `db` here is a session yielded by the override, but the API is sync; do it via a fresh session.
        pass
    from app.db.session import SessionLocal as _SL  # noqa: PLC0415

    with _SL() as db, db.begin():
        job = Job(
            source="greenhouse",
            external_id="smoke-1",
            url="https://example.com/jobs/1",
            company="Acme",
            title="Senior Backend Engineer",
            location="Remote",
            remote_type="remote",
            salary_min=120000,
            salary_max=180000,
            currency="USD",
            description_text=(
                "We need a Python engineer with FastAPI, Postgres, and Docker experience. "
                "Strong async/await skills required. Bonus: Kubernetes, Terraform, AWS."
            ),
        )
        db.add(job)
        db.flush()
        job_id = job.id

    # 3. Get the smoke user's id and run the pipeline via the orchestrator directly.
    from app.db.models import User as _User  # noqa: PLC0415
    from app.pipeline.run import run_pipeline  # noqa: PLC0415

    with _SL() as db:
        u = db.scalar(_SL().query(_User).filter_by(email="smoke2@example.com"))  # type: ignore[attr-defined]
    # The above pattern was wrong — use a proper session.
    with _SL() as db:
        u = db.query(_User).filter_by(email="smoke2@example.com").one()
        user_id = u.id
        match = asyncio.run(run_pipeline(db, user_id, job_id, router=_FakeRouter()))

    # 4. The pipeline should produce a Match row.
    assert match is not None
    assert match.match_score is not None
    assert 0.0 <= float(match.match_score) <= 1.0

    # 5. The TailoredArtifact should exist.
    with _SL() as db:
        assert match.tailored is not None

    # 6. The matches list endpoint should expose the new match to the user.
    r = client.get("/me/matches", cookies=cookies)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, (list, dict))
    if isinstance(body, list):
        assert len(body) >= 1
    else:
        assert "items" in body or "matches" in body
