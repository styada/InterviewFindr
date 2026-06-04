# AGENTS.md — `app/scheduler/`

## What lives here

APScheduler setup. Runs in-process inside the FastAPI app (started from `app.main:lifespan`).
- `jobs.py` — `register_jobs(scheduler)` and the actual job functions.

## Conventions

- Job functions are sync; if they need to call the LLM, use `asyncio.run()` (the scheduler runs in a thread pool).
- The only job in Plan 1 is `daily_pipeline_for_active_profiles` (cron: 06:00 UTC). More land in Plan 2.
- Jobs must be idempotent and re-entrant.
