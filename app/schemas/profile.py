"""Pydantic schemas for profile read/write."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    market_primary: str
    market_secondary: list[str]
    preferences: dict[str, Any]
    llm_default_provider: str
    llm_default_model: str
    auto_apply_enabled: bool
    tailoring_thresholds: dict[str, Any]
    has_resume: bool
    resume_pdf_path: str | None
    resume_docx_path: str | None
    resume_parsed_json: dict[str, Any] | None

    @field_validator("user_id", mode="before")
    @classmethod
    def _coerce_user_id(cls, v: Any) -> str:
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

    @field_validator("market_secondary", mode="before")
    @classmethod
    def _coerce_secondary(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return list(v)

    @field_validator("has_resume", mode="before")
    @classmethod
    def _coerce_has_resume(cls, v: Any, info: Any) -> bool:
        if isinstance(v, bool):
            return v
        data = info.data
        return bool(data.get("resume_pdf_path") or data.get("resume_docx_path"))


class ProfileUpdate(BaseModel):
    market_primary: str | None = None
    market_secondary: list[str] | None = None
    preferences: dict[str, Any] | None = None
    llm_default_provider: str | None = None
    llm_default_model: str | None = None
    llm_escalation: dict[str, Any] | None = None
    auto_apply_enabled: bool | None = None
    auto_apply_allowlist: list[str] | None = None
    tailoring_thresholds: dict[str, Any] | None = None
