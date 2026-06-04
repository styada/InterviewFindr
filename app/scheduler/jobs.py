"""APScheduler registration + the daily refresh job.

Plan 1 registers a single cron job that runs at 02:00 UTC every day. The
implementation is intentionally a thin loop: for every user with a parsed
resume, call `run_pipeline` for every job first seen in the last 24 hours.
A real source-adapter dispatch lands in Plan 2.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.time import utcnow
from app.db.models import Job, Profile, User
from app.llm.opencode_zen import OpenCodeZenProvider
from app.llm.router import LLMRouter
from app.pipeline.run import run_pipeline

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler as _AsyncIOScheduler  # noqa: F401

log = logging.getLogger(__name__)


def _build_router() -> LLMRouter:
    return LLMRouter({"opencode_zen": OpenCodeZenProvider()})


def _session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def refresh_all_users() -> dict[str, int]:
    """Run the pipeline for every (user, new-job) pair in the last 24 hours.

    Returns a small stats dict so the admin endpoint and tests can assert
    what happened. Safe to call concurrently — each user gets its own
    short-lived session.
    """
    stats = {"users": 0, "skipped": 0, "matched": 0, "errors": 0}
    cutoff = utcnow() - timedelta(hours=24)

    try:
        Session = _session_factory()
    except Exception as exc:  # pragma: no cover - defensive
        log.exception("refresh_all_users: engine build failed: %s", exc)
        stats["errors"] += 1
        return stats

    try:
        with Session() as db:
            users = list(db.scalars(select(User)))
    except Exception as exc:
        log.exception("refresh_all_users: could not load users: %s", exc)
        stats["errors"] += 1
        return stats
    log.info("refresh_all_users: %d candidate users", len(users))

    for user in users:
        stats["users"] += 1
        try:
            with Session() as db:
                profile = db.get(Profile, user.id)
                if profile is None or not profile.resume_parsed_json:
                    log.info("skip %s — no profile or resume", user.email)
                    stats["skipped"] += 1
                    continue
                recent_jobs = list(
                    db.scalars(
                        select(Job)
                        .where(Job.first_seen_at >= cutoff)
                        .order_by(Job.first_seen_at.desc())
                    )
                )
                if not recent_jobs:
                    log.info("skip %s — no new jobs in 24h", user.email)
                    stats["skipped"] += 1
                    continue
                for job in recent_jobs:
                    result = run_pipeline(db, user.id, job.id)
                    if result is not None:
                        stats["matched"] += 1
        except Exception as exc:  # pragma: no cover - best-effort job
            log.exception("refresh_all_users: error for %s: %s", user.email, exc)
            stats["errors"] += 1

    log.info("refresh_all_users: stats=%s", stats)
    return stats


def start_scheduler() -> AsyncIOScheduler:
    """Register the daily cron job and start the scheduler. Idempotent."""
    sched = AsyncIOScheduler()
    sched.add_job(
        _run_async_safe,
        "cron",
        hour=2,
        minute=0,
        id="daily_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    log.info("scheduler started — daily refresh at 02:00 UTC")
    return sched


async def _run_async_safe() -> None:
    """Wrapper so APScheduler (which runs jobs in a thread pool) can drive the
    async pipeline without surprising the test loop."""
    try:
        await refresh_all_users()
    except Exception as exc:  # pragma: no cover - top-level safety net
        log.exception("daily_refresh failed: %s", exc)


def shutdown_scheduler(sched: AsyncIOScheduler) -> None:
    sched.shutdown(wait=False)


# Re-export the helper for the tests that want to drive the job without a
# running event loop (e.g. from a sync TestClient context).
def run_refresh_sync() -> dict[str, int]:
    return asyncio.run(refresh_all_users())
