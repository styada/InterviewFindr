"""Pipeline orchestrator: run all 6 stages for a single (user, job) pair.

This module wires the deterministic stages (1, 3, 4, 6) and the LLM stages
(2, 5) into a single async function. Each stage is wrapped in its own
try/except so a single failure (e.g. an LLM timeout) does not crash the
whole run; failures are recorded on the Match row and logged with the
stage name for downstream observability.

The orchestrator pulls the User, Profile, and Job from the database by id,
so callers do not need to construct any pre-loaded entities. The router
defaults to a process-wide OpenCode-Zen-backed router built from settings;
tests can inject a router (and a custom ``PipelineConfig``) for control.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, Match, Profile, TailoredArtifact, User
from app.llm.opencode_zen import OpenCodeZenProvider
from app.llm.router import LLMRouter
from app.resume.render import (
    render_cover_letter_pdf,
    render_resume_docx,
    render_resume_pdf,
    resume_to_plain_text,
)
from app.sources.base import RawJob
from app.storage.s3 import put_object

log = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    jd_quality_min: float = 0.40
    must_have_coverage_min: float = 0.70


class _RouterLike(Protocol):
    async def complete(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Any: ...


_DEFAULT_ROUTER: _RouterLike | None = None


def _default_router() -> _RouterLike:
    """Return a process-wide router backed by the OpenCode Zen provider."""
    global _DEFAULT_ROUTER
    if _DEFAULT_ROUTER is None:
        _DEFAULT_ROUTER = LLMRouter({"opencode_zen": OpenCodeZenProvider()})
    return _DEFAULT_ROUTER


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(value)


def _job_to_raw(job: Job) -> RawJob:
    posted = job.posted_at.isoformat() if job.posted_at is not None else None
    return RawJob(
        source=job.source,
        external_id=job.external_id,
        url=job.url,
        company=job.company,
        title=job.title,
        location=job.location,
        remote_type=job.remote_type,
        salary_min=float(job.salary_min) if job.salary_min is not None else None,
        salary_max=float(job.salary_max) if job.salary_max is not None else None,
        currency=job.currency,
        description_html=job.description_html,
        description_text=job.description_text or "",
        posted_at=posted,
        raw_payload={},
    )


def _upsert_match(
    db: Session,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    match_score: float,
    jd_quality: float,
    seniority_match: float,
    must_have_cov: float,
    comp_match: float,
) -> Match:
    existing = db.scalar(select(Match).where(Match.user_id == user_id, Match.job_id == job_id))
    if existing is not None:
        existing.match_score = match_score
        existing.jd_quality = jd_quality
        existing.seniority_match = seniority_match
        existing.must_have_cov = must_have_cov
        existing.comp_match = comp_match
        return existing
    match = Match(
        user_id=user_id,
        job_id=job_id,
        match_score=match_score,
        jd_quality=jd_quality,
        seniority_match=seniority_match,
        must_have_cov=must_have_cov,
        comp_match=comp_match,
    )
    db.add(match)
    db.flush()
    return match


def _candidate_level(resume: dict[str, Any]) -> str:
    """Best-effort mapping from the most recent role's title to a level bucket."""
    experience = resume.get("experience") or []
    if not experience:
        return "unknown"
    first = experience[0] if isinstance(experience[0], dict) else {}
    title = str(first.get("title", "")).lower()
    if "vp" in title or "vice president" in title or "director" in title:
        return "director"
    if "principal" in title or "staff" in title:
        return "principal"
    if "manager" in title or "head" in title:
        return "manager"
    if "senior" in title or "sr." in title or "sr " in title:
        return "IC4"
    if "junior" in title or "jr." in title or "jr " in title:
        return "IC3"
    return "IC3"


def _comp_match(compensation: dict[str, Any] | None, preferences: dict[str, Any]) -> float:
    if not compensation or (compensation.get("min") is None and compensation.get("max") is None):
        return 0.5
    pref_min = preferences.get("salary_min") if isinstance(preferences, dict) else None
    if pref_min is None:
        return 0.8
    try:
        pref_min_f = float(pref_min)
    except (TypeError, ValueError):
        return 0.8
    lo = compensation.get("min") or compensation.get("max") or 0
    try:
        lo_val = float(lo)
    except (TypeError, ValueError):
        return 0.5
    if lo_val >= pref_min_f:
        return 1.0
    if lo_val >= pref_min_f * 0.85:
        return 0.5
    return 0.0


async def run_pipeline(
    db: Session,
    user_id: uuid.UUID | str,
    job_id: uuid.UUID | str,
    router: _RouterLike | None = None,
    cfg: PipelineConfig | None = None,
) -> Match | None:
    """Run all 6 pipeline stages for a single ``(user, job)`` pair.

    Returns the persisted ``Match`` row on success or on a late-stage
    failure (the row is created with a descriptive status either way).
    Returns ``None`` if the user, profile, or job is missing, or if an
    early filter (JD quality, must-have coverage) rejects the pair, or
    if a stage raises an unrecoverable exception.

    The function is idempotent: re-running for the same pair overwrites
    the existing ``Match`` and ``TailoredArtifact`` rows rather than
    duplicating them.
    """
    user_id = _coerce_uuid(user_id)
    job_id = _coerce_uuid(job_id)
    cfg = cfg or PipelineConfig()
    active_router = router or _default_router()

    user = db.get(User, user_id)
    if user is None:
        log.info("run_pipeline: user %s not found", user_id)
        return None
    profile = db.get(Profile, user_id)
    if profile is None:
        log.info("run_pipeline: profile for %s not found", user_id)
        return None
    job = db.get(Job, job_id)
    if job is None:
        log.info("run_pipeline: job %s not found", job_id)
        return None

    resume: dict[str, Any] = profile.resume_parsed_json or {}
    raw = _job_to_raw(job)

    # Stage 1 — JD quality heuristic (deterministic)
    from app.pipeline.stage1_quality import score_jd

    try:
        quality = score_jd(raw.description_text)
    except Exception as exc:
        log.exception("stage1_quality failed for user=%s job=%s: %s", user_id, job_id, exc)
        return None
    if quality.score < cfg.jd_quality_min:
        log.info(
            "rejected jd_quality user=%s job=%s score=%.3f",
            user_id,
            job_id,
            quality.score,
        )
        return None

    # Stage 2 — structured JD parsing via LLM
    from app.pipeline.stage2_parse import parse_jd

    try:
        parsed = await parse_jd(active_router, raw)
    except Exception as exc:
        log.exception("stage2_parse failed for user=%s job=%s: %s", user_id, job_id, exc)
        return None
    if not isinstance(parsed, dict):
        log.warning("stage2_parse returned non-dict for user=%s job=%s", user_id, job_id)
        return None

    # Stage 3 — must-have coverage (deterministic)
    from app.pipeline.stage3_skill_match import match_must_haves

    try:
        skill_match = match_must_haves(parsed.get("must_haves", []), resume.get("skills", []))
    except Exception as exc:
        log.exception("stage3_skill_match failed for user=%s job=%s: %s", user_id, job_id, exc)
        return None
    if skill_match.coverage < cfg.must_have_coverage_min:
        log.info(
            "rejected must_have_coverage user=%s job=%s coverage=%.3f",
            user_id,
            job_id,
            skill_match.coverage,
        )
        return None

    # Stage 4 — composite probability (deterministic)
    from app.pipeline.stage4_probability import (
        ProbabilityInput,
        probability,
        recency_score,
        seniority_match,
    )

    try:
        sen = seniority_match(_candidate_level(resume), parsed.get("level", "unknown"))
        rs = recency_score(raw.posted_at)
        comp = _comp_match(parsed.get("compensation"), profile.preferences or {})
        prob_inp = ProbabilityInput(
            must_have_cov=skill_match.coverage,
            jd_quality=quality.score,
            seniority_match=sen,
            comp_match=comp,
            recency_score=rs,
            source=raw.source,
        )
        prob = probability(prob_inp)
    except Exception as exc:
        log.exception("stage4_probability failed for user=%s job=%s: %s", user_id, job_id, exc)
        return None

    match = _upsert_match(
        db,
        user_id,
        job_id,
        match_score=prob,
        jd_quality=quality.score,
        seniority_match=sen,
        must_have_cov=skill_match.coverage,
        comp_match=comp,
    )

    # Stage 5 — tailor via LLM
    from app.pipeline.stage5_tailor import tailor

    try:
        tailored = await tailor(active_router, resume, parsed)
    except Exception as exc:
        log.exception("stage5_tailor failed for user=%s job=%s: %s", user_id, job_id, exc)
        match.status = "tailoring_failed"
        match.reasoning = {"error": str(exc), "stage": "tailor"}
        db.commit()
        return match

    # Stage 6 — ATS validation (deterministic)
    from app.pipeline.stage6_validate import validate_tailored

    resume_text = resume_to_plain_text(tailored.tailored_resume)
    validation = validate_tailored(
        resume_text=resume_text,
        must_haves=parsed.get("must_haves", []),
        cover_letter=tailored.cover_letter,
    )
    if not validation.ok:
        log.info(
            "validation_failed user=%s job=%s issues=%s",
            user_id,
            job_id,
            validation.issues,
        )
        match.status = "tailoring_failed"
        match.reasoning = {"validation_issues": validation.issues}
        db.commit()
        return match

    # Render + upload artifacts
    try:
        resume_pdf_bytes = render_resume_pdf(tailored.tailored_resume)
        resume_docx_bytes = render_resume_docx(tailored.tailored_resume)
        cover_pdf_bytes = render_cover_letter_pdf(tailored.cover_letter)
        resume_pdf_key = f"tailored/{user_id}/{match.id}/resume.pdf"
        resume_docx_key = f"tailored/{user_id}/{match.id}/resume.docx"
        cover_pdf_key = f"tailored/{user_id}/{match.id}/cover_letter.pdf"
        put_object(resume_pdf_key, resume_pdf_bytes, "application/pdf")
        put_object(
            resume_docx_key,
            resume_docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        put_object(cover_pdf_key, cover_pdf_bytes, "application/pdf")
        artifact = TailoredArtifact(
            match_id=match.id,
            resume_pdf_path=resume_pdf_key,
            resume_docx_path=resume_docx_key,
            resume_text=resume_text,
            cover_letter_pdf=cover_pdf_key,
            cover_letter_text=tailored.cover_letter,
            model_used=tailored.model_used,
            token_cost_usd=tailored.cost_usd,
        )
        db.add(artifact)
        match.status = "tailored"
        db.commit()
    except Exception as exc:
        log.exception("render+upload failed for user=%s job=%s: %s", user_id, job_id, exc)
        match.status = "render_failed"
        match.reasoning = {"error": str(exc), "stage": "render"}
        db.commit()

    return match
