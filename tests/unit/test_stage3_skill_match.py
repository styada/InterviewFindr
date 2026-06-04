"""Unit tests for app.pipeline.stage3_skill_match — must-have coverage."""
from __future__ import annotations

from app.pipeline.stage3_skill_match import match_must_haves


def test_direct_match() -> None:
    r = match_must_haves(
        ["Python", "PostgreSQL"],
        [{"name": "Python"}, {"name": "PostgreSQL"}],
    )
    assert r.coverage == 1.0
    assert r.uncovered == []


def test_transfer_credit() -> None:
    r = match_must_haves(["Postgres"], [{"name": "MySQL"}])
    assert 0.5 < r.coverage < 1.0
    assert r.uncovered == []


def test_uncovered() -> None:
    r = match_must_haves(
        ["Kubernetes", "PostgreSQL"],
        [{"name": "PostgreSQL"}],
    )
    assert "Kubernetes" in r.uncovered
    assert r.coverage < 1.0
