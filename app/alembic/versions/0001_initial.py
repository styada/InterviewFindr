"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-04 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("market_primary", sa.String(2), server_default="US", nullable=False),
        sa.Column(
            "market_secondary",
            postgresql.ARRAY(sa.String),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("resume_pdf_path", sa.Text(), nullable=True),
        sa.Column("resume_docx_path", sa.Text(), nullable=True),
        sa.Column("resume_parsed_json", postgresql.JSONB(), nullable=True),
        sa.Column("linkedin_raw_path", sa.Text(), nullable=True),
        sa.Column("linkedin_parsed_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "preferences",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "llm_default_provider",
            sa.String(50),
            server_default="opencode_zen",
            nullable=False,
        ),
        sa.Column(
            "llm_default_model",
            sa.String(100),
            server_default="kimi-k2.6",
            nullable=False,
        ),
        sa.Column(
            "llm_escalation",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "auto_apply_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "auto_apply_allowlist",
            postgresql.ARRAY(sa.String),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "tailoring_thresholds",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("remote_type", sa.String(20), nullable=True),
        sa.Column("salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("description_html", sa.Text(), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_jobs_source_extid"),
    )
    op.create_index("ix_jobs_posted_at", "jobs", ["posted_at"])
    op.create_index("ix_jobs_company", "jobs", ["company"])

    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("jd_quality", sa.Numeric(5, 4), nullable=True),
        sa.Column("seniority_match", sa.Numeric(5, 4), nullable=True),
        sa.Column("must_have_cov", sa.Numeric(5, 4), nullable=True),
        sa.Column("comp_match", sa.Numeric(5, 4), nullable=True),
        sa.Column("reasoning", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="new"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "job_id", name="uq_matches_user_job"),
    )
    op.create_index("ix_matches_user_score", "matches", ["user_id", "match_score"])

    op.create_table(
        "tailored_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("resume_pdf_path", sa.Text(), nullable=True),
        sa.Column("resume_docx_path", sa.Text(), nullable=True),
        sa.Column("resume_text", sa.Text(), nullable=True),
        sa.Column("resume_diff", postgresql.JSONB(), nullable=True),
        sa.Column("cover_letter_pdf", sa.Text(), nullable=True),
        sa.Column("cover_letter_text", sa.Text(), nullable=True),
        sa.Column("skill_gap_notes", sa.Text(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(40), nullable=True),
        sa.Column("token_cost_usd", sa.Numeric(8, 6), nullable=True),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
    )

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),
        sa.Column("resume_snapshot", sa.Text(), nullable=True),
        sa.Column("cover_letter_snap", sa.Text(), nullable=True),
        sa.Column("user_outcome_note", sa.Text(), nullable=True),
        sa.Column("outcome_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_applications_user_status", "applications", ["user_id", "status"])

    op.create_table(
        "source_configs",
        sa.Column("source", sa.String(50), primary_key=True),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "per_profile_overrides",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "rate_limit",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("api_key_env", sa.String(100), nullable=True),
    )

    op.create_table(
        "match_weight_overrides",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("weights", postgresql.JSONB(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("match_weight_overrides")
    op.drop_table("source_configs")
    op.drop_index("ix_applications_user_status", table_name="applications")
    op.drop_table("applications")
    op.drop_table("tailored_artifacts")
    op.drop_index("ix_matches_user_score", table_name="matches")
    op.drop_table("matches")
    op.drop_index("ix_jobs_company", table_name="jobs")
    op.drop_index("ix_jobs_posted_at", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("profiles")
    op.drop_table("users")
