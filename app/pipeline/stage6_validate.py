"""Stage 6 — ATS validation (deterministic).

Runs after Stage 5 tailoring. Verifies the rendered resume text and cover
letter are long enough and that each must-have keyword from Stage 2 is
present (either verbatim or as its first-3-token stem) in the resume text.
The orchestrator flips ``Match.status`` to ``tailoring_failed`` and records
the issues when validation does not pass.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationResult:
    ok: bool
    issues: list[str]


def validate_tailored(
    *,
    resume_text: str,
    must_haves: list[str],
    cover_letter: str,
) -> ValidationResult:
    issues: list[str] = []
    if not resume_text or len(resume_text) < 200:
        issues.append("resume_too_short")
    if not cover_letter or len(cover_letter) < 200:
        issues.append("cover_letter_too_short")
    resume_lower: str = resume_text.lower()
    for mh in must_haves:
        mh_l: str = mh.lower()
        token: str = " ".join(mh_l.split()[:3])
        if token and token not in resume_lower and mh_l not in resume_lower:
            issues.append(f"missing_must_have:{mh}")
    if len(issues) > 2:
        return ValidationResult(ok=False, issues=issues)
    return ValidationResult(ok=len(issues) == 0, issues=issues)
