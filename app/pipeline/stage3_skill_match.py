"""Stage 3 — skill-graph must-have coverage (deterministic).

Compares the LLM-extracted must_haves against the candidate's parsed
``skills`` list. Direct substring matches count for 1.0; a hand-curated
transfer map credits partial coverage (e.g. ``Postgres`` in JD covered by
``MySQL`` in resume at 0.6). The orchestrator rejects a ``(user, job)`` pair
when coverage falls below the configured threshold.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


TRANSFER_MAP: dict[str, list[tuple[str, float]]] = {
    "HubSpot": [("Salesforce", 0.4), ("CRM", 0.3)],
    "PostgreSQL": [("MySQL", 0.6), ("SQL", 0.8)],
    "Postgres": [("MySQL", 0.6), ("SQL", 0.8)],
    "React": [("Vue", 0.4), ("Frontend", 0.6)],
    "Excel": [("Google Sheets", 0.7), ("Financial modeling", 0.5)],
    "Treasury operations": [("Cash management", 0.7), ("Banking", 0.6)],
    "Commercial banking": [("Banking", 0.8), ("Credit analysis", 0.7)],
}


@dataclass
class SkillMatch:
    coverage: float
    uncovered: list[str]


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def match_must_haves(
    must_haves: list[str],
    resume_skills: list[dict[str, Any]],
) -> SkillMatch:
    if not must_haves:
        return SkillMatch(coverage=0.0, uncovered=[])
    resume_keys: set[str] = {_normalize(s["name"]) for s in resume_skills}
    total: float = 0.0
    uncovered: list[str] = []
    for mh in must_haves:
        mh_n: str = _normalize(mh)
        if any(rk in mh_n or mh_n in rk for rk in resume_keys):
            total += 1.0
            continue
        transfer: list[tuple[str, float]] = TRANSFER_MAP.get(mh) or TRANSFER_MAP.get(mh_n) or []
        score: float = 0.0
        for target, conf in transfer:
            if _normalize(target) in resume_keys:
                score = max(score, conf)
        if score > 0:
            total += score
        else:
            uncovered.append(mh)
    return SkillMatch(coverage=total / len(must_haves), uncovered=uncovered)
