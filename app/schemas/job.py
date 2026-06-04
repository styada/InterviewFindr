"""Pydantic schemas for job read endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


def _coerce_uuid(v: Any) -> str:
    if isinstance(v, uuid.UUID):
        return str(v)
    return v


def _coerce_decimal(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    return None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    external_id: str
    url: str
    company: str
    title: str
    location: str | None
    remote_type: str | None
    salary_min: float | None
    salary_max: float | None
    currency: str | None
    description_text: str | None
    posted_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> str:
        return _coerce_uuid(v)

    @field_validator("salary_min", mode="before")
    @classmethod
    def _coerce_salary_min(cls, v: Any) -> float | None:
        return _coerce_decimal(v)

    @field_validator("salary_max", mode="before")
    @classmethod
    def _coerce_salary_max(cls, v: Any) -> float | None:
        return _coerce_decimal(v)


class JobList(BaseModel):
    items: list[JobOut]
    total: int
