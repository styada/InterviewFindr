"""Pydantic schemas for the tailored-artifact read endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class TailoredArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    match_id: str
    resume_pdf_path: str | None
    resume_docx_path: str | None
    resume_text: str | None
    cover_letter_pdf: str | None
    cover_letter_text: str | None
    skill_gap_notes: str | None
    generated_at: datetime
    model_used: str | None
    prompt_version: str | None
    cost_usd: float | None
    escalation_reason: str | None

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> str:
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

    @field_validator("match_id", mode="before")
    @classmethod
    def _coerce_match_id(cls, v: Any) -> str:
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

    @field_validator("cost_usd", mode="before")
    @classmethod
    def _coerce_cost(cls, v: Any) -> float | None:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, (int, float)):
            return float(v)
        return None
