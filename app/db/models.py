"""SQLAlchemy ORM models for all 8 tables defined in spec section 3.

JSONB is used on Postgres and falls back to generic JSON on other dialects
(used in unit tests against SQLite). ARRAY likewise falls back to JSON
text serialization on non-Postgres dialects.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Type aliases that work on both Postgres (production) and SQLite (tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")
StringListType = ARRAY(String).with_variant(JSON(), "sqlite")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    profile: Mapped[Optional["Profile"]] = relationship(
        back_populates="user", uselist=False
    )


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    market_primary: Mapped[str] = mapped_column(String(2), default="US")
    market_secondary: Mapped[list[str]] = mapped_column(
        StringListType, default=list
    )
    resume_pdf_path: Mapped[Optional[str]] = mapped_column(Text)
    resume_docx_path: Mapped[Optional[str]] = mapped_column(Text)
    resume_parsed_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    linkedin_raw_path: Mapped[Optional[str]] = mapped_column(Text)
    linkedin_parsed_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    llm_default_provider: Mapped[str] = mapped_column(
        String(50), default="opencode_zen"
    )
    llm_default_model: Mapped[str] = mapped_column(String(100), default="kimi-k2.6")
    llm_escalation: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    auto_apply_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_apply_allowlist: Mapped[list[str]] = mapped_column(
        StringListType, default=list
    )
    tailoring_thresholds: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(300))
    remote_type: Mapped[Optional[str]] = mapped_column(String(20))
    salary_min: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    description_html: Mapped[Optional[str]] = mapped_column(Text)
    description_text: Mapped[Optional[str]] = mapped_column(Text)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_extid"),
    )


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    match_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    jd_quality: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    seniority_match: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    must_have_cov: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    comp_match: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    reasoning: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    job: Mapped[Job] = relationship()
    tailored: Mapped[Optional["TailoredArtifact"]] = relationship(
        back_populates="match", uselist=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_matches_user_job"),
    )


class TailoredArtifact(Base):
    __tablename__ = "tailored_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("matches.id", ondelete="CASCADE"),
        unique=True,
    )
    resume_pdf_path: Mapped[Optional[str]] = mapped_column(Text)
    resume_docx_path: Mapped[Optional[str]] = mapped_column(Text)
    resume_text: Mapped[Optional[str]] = mapped_column(Text)
    resume_diff: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    cover_letter_pdf: Mapped[Optional[str]] = mapped_column(Text)
    cover_letter_text: Mapped[Optional[str]] = mapped_column(Text)
    skill_gap_notes: Mapped[Optional[str]] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    prompt_version: Mapped[Optional[str]] = mapped_column(String(40))
    token_cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(8, 6))
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text)

    match: Mapped[Match] = relationship(back_populates="tailored")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    external_ref: Mapped[Optional[str]] = mapped_column(Text)
    resume_snapshot: Mapped[Optional[str]] = mapped_column(Text)
    cover_letter_snap: Mapped[Optional[str]] = mapped_column(Text)
    user_outcome_note: Mapped[Optional[str]] = mapped_column(Text)
    outcome_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )


class SourceConfig(Base):
    __tablename__ = "source_configs"

    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    per_profile_overrides: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    rate_limit: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    api_key_env: Mapped[Optional[str]] = mapped_column(String(100))


class MatchWeightOverride(Base):
    __tablename__ = "match_weight_overrides"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    weights: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
