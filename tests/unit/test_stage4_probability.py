"""Unit tests for app.pipeline.stage4_probability — composite scoring."""
from __future__ import annotations

import datetime as dt

from app.pipeline.stage4_probability import (
    ProbabilityInput,
    probability,
    recency_score,
    seniority_match,
)


def test_perfect_match() -> None:
    inp = ProbabilityInput(
        must_have_cov=1.0,
        jd_quality=1.0,
        seniority_match=1.0,
        comp_match=1.0,
        recency_score=1.0,
        source="greenhouse",
    )
    p = probability(inp)
    assert p > 0.8


def test_poor_match_penalized() -> None:
    inp = ProbabilityInput(
        must_have_cov=0.1,
        jd_quality=0.2,
        seniority_match=0.3,
        comp_match=0.0,
        recency_score=0.3,
        source="jsearch",
        competition_density=1.0,
    )
    p = probability(inp)
    assert p < 0.3


def test_seniority_match() -> None:
    assert seniority_match("IC4", "IC4") == 1.0
    assert seniority_match("IC4", "IC3") == 0.7
    assert seniority_match("IC4", "director") < 0.5


def test_recency_decay() -> None:
    fresh = dt.datetime.now(dt.timezone.utc).isoformat()
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=60)).isoformat()
    assert recency_score(fresh) > 0.9
    assert recency_score(old) == 0.3
