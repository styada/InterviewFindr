"""Profile read/write endpoints for the current user.

Routes (all require auth):
  GET   /me/profile         -> ProfileOut
  PATCH /me/profile         -> ProfileOut
  POST  /me/profile/resume  -> ProfileOut (multipart upload)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.models import Profile, User
from app.db.session import get_db
from app.llm.opencode_zen import OpenCodeZenProvider
from app.llm.router import LLMRouter
from app.resume.parse import extract_text
from app.resume.structure import structure_resume
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.storage.s3 import put_object

log = logging.getLogger(__name__)

router = APIRouter()

_router_singleton: LLMRouter | None = None


def _llm_router() -> LLMRouter:
    global _router_singleton
    if _router_singleton is None:
        _router_singleton = LLMRouter({"opencode_zen": OpenCodeZenProvider()})
    return _router_singleton


def _build_profile_out(p: Profile) -> ProfileOut:
    return ProfileOut(
        user_id=p.user_id,
        market_primary=p.market_primary,
        market_secondary=list(p.market_secondary or []),
        preferences=dict(p.preferences or {}),
        llm_default_provider=p.llm_default_provider,
        llm_default_model=p.llm_default_model,
        auto_apply_enabled=bool(p.auto_apply_enabled),
        tailoring_thresholds=dict(p.tailoring_thresholds or {}),
        has_resume=bool(p.resume_pdf_path or p.resume_docx_path),
        resume_pdf_path=p.resume_pdf_path,
        resume_docx_path=p.resume_docx_path,
        resume_parsed_json=dict(p.resume_parsed_json) if p.resume_parsed_json else None,
    )


@router.get("/me/profile", response_model=ProfileOut)
def get_me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> ProfileOut:
    p = db.get(Profile, user.id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no profile for user")
    return _build_profile_out(p)


@router.patch("/me/profile", response_model=ProfileOut)
def update_me(
    payload: ProfileUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProfileOut:
    p = db.get(Profile, user.id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no profile for user")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(p, key, value)
    db.commit()
    db.refresh(p)
    return _build_profile_out(p)


@router.post("/me/profile/resume", response_model=ProfileOut)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProfileOut:
    allowed = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }
    if file.content_type not in allowed:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"unsupported content-type: {file.content_type}",
        )
    p = db.get(Profile, user.id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no profile for user")

    data = await file.read()
    filename = file.filename or "resume"
    text = extract_text(data, filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    key = f"resumes/{user.id}/original.{ext}"
    put_object(key, data, file.content_type or "application/octet-stream")
    if ext == "pdf":
        p.resume_pdf_path = key
    elif ext == "docx":
        p.resume_docx_path = key
    p.resume_parsed_json = await structure_resume(_llm_router(), text)
    db.commit()
    db.refresh(p)
    return _build_profile_out(p)
