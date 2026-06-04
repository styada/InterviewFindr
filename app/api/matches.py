"""Matches API: list, detail, tailored artifact, PDFs, and assisted apply."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.db.models import Application, Job, Match, TailoredArtifact, User
from app.db.session import get_db
from app.schemas.job import JobOut
from app.schemas.match import ApplyKit, MatchList, MatchOut
from app.schemas.tailored import TailoredArtifactOut
from app.storage.s3 import get_object, object_exists

log = logging.getLogger(__name__)

router = APIRouter()


def _to_tailored_out(ta: TailoredArtifact) -> TailoredArtifactOut:
    return TailoredArtifactOut(
        id=ta.id,
        match_id=ta.match_id,
        resume_pdf_path=ta.resume_pdf_path,
        resume_docx_path=ta.resume_docx_path,
        resume_text=ta.resume_text,
        cover_letter_pdf=ta.cover_letter_pdf,
        cover_letter_text=ta.cover_letter_text,
        skill_gap_notes=ta.skill_gap_notes,
        generated_at=ta.generated_at,
        model_used=ta.model_used,
        prompt_version=ta.prompt_version,
        cost_usd=float(ta.token_cost_usd) if ta.token_cost_usd is not None else None,
        escalation_reason=ta.escalation_reason,
    )


def _to_match_out(m: Match) -> MatchOut:
    job = m.job
    return MatchOut(
        id=m.id,
        user_id=m.user_id,
        job_id=m.job_id,
        job=JobOut.model_validate(job) if job is not None else None,
        match_score=float(m.match_score or 0),
        jd_quality=float(m.jd_quality) if m.jd_quality is not None else None,
        seniority_match=float(m.seniority_match) if m.seniority_match is not None else None,
        must_have_cov=float(m.must_have_cov) if m.must_have_cov is not None else None,
        comp_match=float(m.comp_match) if m.comp_match is not None else None,
        reasoning=dict(m.reasoning) if m.reasoning else None,
        status=m.status,
        created_at=m.created_at,
        updated_at=m.updated_at,
        tailored=_to_tailored_out(m.tailored) if m.tailored else None,
    )


@router.get("/me/matches", response_model=MatchList)
def list_matches(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    status_filter: str | None = Query(default=None, alias="status"),
) -> MatchList:
    limit = max(1, min(int(limit), 200))
    stmt = (
        select(Match)
        .where(Match.user_id == user.id)
        .options(selectinload(Match.job), selectinload(Match.tailored))
        .order_by(Match.match_score.desc())
    )
    if status_filter:
        stmt = stmt.where(Match.status == status_filter)
    rows = list(db.scalars(stmt.limit(limit)))
    total = db.scalar(
        select(func.count())
        .select_from(Match)
        .where(Match.user_id == user.id)
    )
    return MatchList(items=[_to_match_out(m) for m in rows], total=int(total or 0))


@router.get("/me/matches/{match_id}", response_model=MatchOut)
def get_match(
    match_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MatchOut:
    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    m = db.get(Match, mid, options=[selectinload(Match.job), selectinload(Match.tailored)])
    if not m or m.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    return _to_match_out(m)


@router.get("/me/matches/{match_id}/tailored", response_model=TailoredArtifactOut)
def get_tailored(
    match_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TailoredArtifactOut:
    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    m = db.get(Match, mid)
    if not m or m.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    ta = db.scalar(select(TailoredArtifact).where(TailoredArtifact.match_id == mid))
    if not ta:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no tailored artifact yet")
    return _to_tailored_out(ta)


@router.get("/me/matches/{match_id}/resume.pdf")
def resume_pdf(
    match_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    m = db.get(Match, mid)
    if not m or m.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    ta = db.scalar(select(TailoredArtifact).where(TailoredArtifact.match_id == mid))
    if not ta or not ta.resume_pdf_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no resume PDF")
    if not object_exists(ta.resume_pdf_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "resume PDF missing on disk")
    return Response(content=get_object(ta.resume_pdf_path), media_type="application/pdf")


@router.get("/me/matches/{match_id}/cover_letter.pdf")
def cover_letter_pdf(
    match_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    m = db.get(Match, mid)
    if not m or m.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    ta = db.scalar(select(TailoredArtifact).where(TailoredArtifact.match_id == mid))
    if not ta or not ta.cover_letter_pdf:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no cover letter PDF")
    if not object_exists(ta.cover_letter_pdf):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "cover letter PDF missing on disk")
    return Response(content=get_object(ta.cover_letter_pdf), media_type="application/pdf")


@router.post("/me/matches/{match_id}/skip")
def skip_match(
    match_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    m = db.get(Match, mid)
    if not m or m.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    m.status = "skipped"
    db.commit()
    return {"status": "ok"}


@router.post("/me/matches/{match_id}/apply/assisted", response_model=ApplyKit)
def assisted_apply(
    match_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApplyKit:
    """Build an apply kit for the user to submit manually.

    We never auto-submit in Plan 1. We record an Application row in `queued`
    state and return the resume / cover-letter / job-url bundle the user needs
    to copy-paste into the employer site.
    """
    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    m = db.get(Match, mid)
    if not m or m.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    if m.status not in ("tailored", "new"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"match not ready to apply: status={m.status}"
        )
    job = db.get(Job, m.job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job missing for match")
    ta = db.scalar(select(TailoredArtifact).where(TailoredArtifact.match_id == mid))

    app_row = Application(
        match_id=m.id,
        user_id=user.id,
        job_id=job.id,
        mode="assisted",
        status="queued",
        resume_snapshot=ta.resume_pdf_path if ta else None,
        cover_letter_snap=ta.cover_letter_pdf if ta else None,
    )
    db.add(app_row)
    m.status = "queued_apply"
    db.commit()
    db.refresh(app_row)

    resume_pdf_url = (
        f"/me/matches/{m.id}/resume.pdf" if ta and ta.resume_pdf_path else None
    )
    cover_letter_pdf_url = (
        f"/me/matches/{m.id}/cover_letter.pdf"
        if ta and ta.cover_letter_pdf
        else None
    )

    return ApplyKit(
        status="ok",
        job_id=str(job.id),
        match_id=str(m.id),
        application_id=str(app_row.id),
        job_url=job.url,
        job_title=job.title,
        job_company=job.company,
        resume_pdf_url=resume_pdf_url,
        cover_letter_pdf_url=cover_letter_pdf_url,
        resume_text=ta.resume_text if ta else None,
        cover_letter_text=ta.cover_letter_text if ta else None,
        instructions=[
            "Open the job URL in a new tab.",
            "Download the tailored resume PDF (link in the match page).",
            "Download the cover letter PDF.",
            "Fill the application form. Paste the cover letter text into the cover letter field if text-only.",
            "Upload the resume PDF.",
            "Submit. Come back here and update the application status to 'submitted' so we can track outcomes.",
        ],
    )


@router.post("/me/matches/{match_id}/refresh")
def refresh_match(
    match_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Re-run the pipeline for a single match (admin / user-triggered)."""
    from app.pipeline.run import run_pipeline

    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    m = db.get(Match, mid)
    if not m or m.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    run_pipeline(db, user.id, m.job_id)
    return {"status": "ok", "refreshed_at": datetime.now(tz=timezone.utc).isoformat()}
