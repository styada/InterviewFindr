"""Stage 1 — JD quality heuristic (deterministic, regex-based).

A pure function module: takes the raw JD text, returns a ``QualityResult``
with a ``0..1`` score, a list of red-flag patterns that fired, and a list
of positive-signal patterns that fired. No external I/O.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

RED_FLAGS: list[str] = [
    r"\brockstar\b",
    r"\bninja\b",
    r"\bguru\b",
    r"\bwear many hats\b",
    r"\bfast-paced\b",
    r"\bcompetitive salary\b",
]

POSITIVE_SIGNALS: list[str] = [
    r"\$\d{2,3}[,._]?\d{3}",
    r"\d+\s*-\s*\$",
    r"\$\d+\s*-\s*\$?\d",
    r"\bbenefits\b",
    r"\b401k\b",
    r"\bhealth insurance\b",
    r"\byou will\b",
    r"\bresponsibilities include\b",
]


@dataclass
class QualityResult:
    score: float
    red_flags: list[str]
    positives: list[str]


def score_jd(text: str) -> QualityResult:
    if not text or len(text) < 200:
        return QualityResult(score=0.0, red_flags=["too_short"], positives=[])
    text_l = text.lower()
    red = [p for p in RED_FLAGS if re.search(p, text_l)]
    pos = [p for p in POSITIVE_SIGNALS if re.search(p, text_l)]
    score = 0.5 + 0.1 * len(pos) - 0.15 * len(red)
    score = max(0.0, min(1.0, score))
    return QualityResult(score=score, red_flags=red, positives=pos)
