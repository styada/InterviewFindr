"""Pydantic schemas for match list/detail endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.job import JobOut
from app.schemas.tailored import TailoredArtifactOut


def _coerce_uuid(v: Any) -> str:
    if isinstance(v, uuid.UUID):
        return str(v)
    return v


def _coerce_score(v: Any) -> float:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    job_id: str
    job: JobOut | None = None
    match_score: float
    jd_quality: float | None
    seniority_match: float | None
    must_have_cov: float | None
    comp_match: float | None
    reasoning: dict[str, Any] | None
    status: str
    created_at: datetime
    updated_at: datetime
    tailored: TailoredArtifactOut | None = None

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> str:
        return _coerce_uuid(v)

    @field_validator("user_id", mode="before")
    @classmethod
    def _coerce_user_id(cls, v: Any) -> str:
        return _coerce_uuid(v)

    @field_validator("job_id", mode="before")
    @classmethod
    def _coerce_job_id(cls, v: Any) -> str:
        return _coerce_uuid(v)

    @field_validator("match_score", mode="before")
    @classmethod
    def _coerce_match_score(cls, v: Any) -> float:
        return _coerce_score(v)

    @field_validator("jd_quality", mode="before")
    @classmethod
    def _coerce_jd(cls, v: Any) -> float | None:
        if v is None:
            return None
        return _coerce_score(v)

    @field_validator("seniority_match", mode="before")
    @classmethod
    def _coerce_sen(cls, v: Any) -> float | None:
        if v is None:
            return None
        return _coerce_score(v)

    @field_validator("must_have_cov", mode="before")
    @classmethod
    def _coerce_must(cls, v: Any) -> float | None:
        if v is None:
            return None
        return _coerce_score(v)

    @field_validator("comp_match", mode="before")
    @classmethod
    def _coerce_comp(cls, v: Any) -> float | None:
        if v is None:
            return None
        return _coerce_score(v)


class MatchList(BaseModel):
    items: list[MatchOut]
    total: int


class ApplyKit(BaseModel):
    status: str
    job_id: str
    match_id: str
    application_id: str
    job_url: str
    job_title: str
    job_company: str
    resume_pdf_url: str | None
    cover_letter_pdf_url: str | None
    resume_text: str | None
    cover_letter_text: str | None
    instructions: list[str]
