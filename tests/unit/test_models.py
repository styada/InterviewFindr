"""Unit tests for SQLAlchemy models."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    Application,
    Job,
    Match,
    MatchWeightOverride,
    Profile,
    SourceConfig,
    TailoredArtifact,
    User,
)


def test_all_tables_can_be_created() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(Base.metadata.tables.keys())
    assert {
        "users",
        "profiles",
        "jobs",
        "matches",
        "tailored_artifacts",
        "applications",
        "source_configs",
        "match_weight_overrides",
    } <= tables


def test_user_email_is_unique() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as s:
        s.add(User(email="a@b.c", display_name="A"))
        s.commit()

    with Session() as s:
        s.add(User(email="a@b.c", display_name="B"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_user_can_have_a_profile() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        u = User(email="a@b.c", display_name="A")
        s.add(u)
        s.flush()
        s.add(
            Profile(
                user_id=u.id,
                market_primary="US",
                market_secondary=["CA"],
                preferences={"salary_min": 100000},
                auto_apply_allowlist=["greenhouse"],
                tailoring_thresholds={"min_match_score": 0.4},
            )
        )
        s.commit()
        assert u.id is not None
        assert u.profile is not None
        assert u.profile.market_primary == "US"
        assert u.profile.market_secondary == ["CA"]
