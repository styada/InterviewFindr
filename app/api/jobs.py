"""Jobs API: read-only job endpoints + admin manual refresh trigger."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.models import Job, User
from app.db.session import get_db
from app.schemas.job import JobList, JobOut
from app.scheduler.jobs import refresh_all_users

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return JobOut.model_validate(j)


@router.get("/jobs", response_model=JobList)
def list_jobs(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> JobList:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    rows = list(db.scalars(select(Job).order_by(Job.last_seen_at.desc()).limit(limit).offset(offset)))
    total = len(list(db.scalars(select(Job))))
    return JobList(items=[JobOut.model_validate(j) for j in rows], total=total)


@router.post("/jobs/refresh")
async def refresh_now(
    user: User = Depends(current_user),
) -> dict[str, str]:
    """Schedule a background refresh of all users' pipelines.

    Plan 1 doesn't yet pull fresh jobs from sources — this endpoint kicks
    the scheduler's `refresh_all_users` coroutine in the background. Auth
    is required but no body is needed.
    """
    import asyncio

    asyncio.create_task(refresh_all_users())
    return {
        "status": "scheduled",
        "requested_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@router.post("/admin/refresh")
async def admin_refresh(user: User = Depends(current_user)) -> dict[str, str]:
    """Synchronous admin-only pipeline refresh.

    Blocks until the scheduler has finished running the pipeline for every
    active user. Useful for testing and one-off backfills.
    """
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    await refresh_all_users()
    return {
        "status": "ok",
        "completed_at": datetime.now(tz=timezone.utc).isoformat(),
    }
