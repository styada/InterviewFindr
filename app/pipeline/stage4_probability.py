"""Stage 4 — composite probability score (deterministic).

A weighted sum of five positive signals (must-have coverage, JD quality,
seniority alignment, comp match, recency) plus a source weight, minus a
competition-density penalty. The default weights match spec §6; ``None``-ish
inputs (no compensation, no posted_at) collapse to a neutral 0.5.

Also exports two helpers the orchestrator uses to fill
``ProbabilityInput``: ``seniority_match`` (leveled-ladder diff) and
``recency_score`` (linear decay over 30 days, then a floor of 0.3).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any


DEFAULT_WEIGHTS: dict[str, float] = {
    "w_match_coverage": 0.30,
    "w_jd_quality": 0.20,
    "w_seniority_match": 0.20,
    "w_comp_match": 0.10,
    "w_recency": 0.10,
    "w_source_weight": 0.05,
    "w_competition": 0.05,
}

SOURCE_WEIGHTS: dict[str, float] = {
    "greenhouse": 1.0,
    "lever": 0.9,
    "ashby": 0.9,
    "adzuna": 0.8,
    "jsearch": 0.6,
    "usajobs": 1.0,
}


@dataclass
class ProbabilityInput:
    must_have_cov: float
    jd_quality: float
    seniority_match: float
    comp_match: float
    recency_score: float
    source: str
    competition_density: float = 0.5


def probability(inp: ProbabilityInput, weights: dict[str, float] | None = None) -> float:
    w: dict[str, float] = {**DEFAULT_WEIGHTS, **(weights or {})}
    sw: float = SOURCE_WEIGHTS.get(inp.source, 0.7)
    p: float = (
        w["w_match_coverage"] * inp.must_have_cov
        + w["w_jd_quality"] * inp.jd_quality
        + w["w_seniority_match"] * inp.seniority_match
        + w["w_comp_match"] * inp.comp_match
        + w["w_recency"] * inp.recency_score
        + w["w_source_weight"] * sw
        - w["w_competition"] * inp.competition_density
    )
    return max(0.0, min(1.0, p))


def seniority_match(level: str, target: str) -> float:
    ladder: list[str] = ["entry", "IC3", "IC4", "manager", "principal", "director", "vp"]
    if level not in ladder or target not in ladder:
        return 0.5
    diff: int = abs(ladder.index(level) - ladder.index(target))
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.7
    return 0.3


def recency_score(posted_at_iso: str | None) -> float:
    if not posted_at_iso:
        return 0.5
    try:
        posted: dt.datetime = dt.datetime.fromisoformat(posted_at_iso.replace("Z", "+00:00"))
    except ValueError:
        return 0.5
    now: dt.datetime = dt.datetime.now(dt.timezone.utc)
    days: float = (now - posted).total_seconds() / 86400
    if days < 0:
        days = 0
    if days >= 30:
        return 0.3
    return 1.0 - (days / 30) * 0.7
