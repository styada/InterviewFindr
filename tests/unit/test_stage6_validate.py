"""Unit tests for app.pipeline.stage6_validate — ATS keyword coverage."""
from __future__ import annotations

from app.pipeline.stage6_validate import validate_tailored


def test_passes_when_all_must_haves_present() -> None:
    r = validate_tailored(
        resume_text="x" * 300 + " Python PostgreSQL",
        must_haves=["Python", "PostgreSQL"],
        cover_letter="y" * 300,
    )
    assert r.ok


def test_fails_when_must_have_missing() -> None:
    r = validate_tailored(
        resume_text="x" * 300 + " Python",
        must_haves=["Python", "Kubernetes"],
        cover_letter="y" * 300,
    )
    assert not r.ok
    assert any("Kubernetes" in i for i in r.issues)
