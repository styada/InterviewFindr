"""Unit tests for app.pipeline.stage1_quality — JD heuristic scoring."""
from __future__ import annotations

from app.pipeline.stage1_quality import score_jd


def test_very_short_text_scores_zero() -> None:
    r = score_jd("too short")
    assert r.score == 0.0


def test_red_flags_drag_score_down() -> None:
    text = "We are looking for a rockstar ninja to join our fast-paced team. " * 20
    r = score_jd(text)
    assert r.score < 0.5
    assert "rockstar" in r.red_flags


def test_specific_posting_scores_well() -> None:
    text = (
        "We are hiring a Senior Backend Engineer. You will design distributed systems. "
        "Responsibilities include owning the payments service. "
        "Compensation: $180,000 - $240,000 plus equity. Benefits include 401k and health insurance. "
    ) * 5
    r = score_jd(text)
    assert r.score > 0.5
