# AGENTS.md — `app/`

## What lives here

The InterviewFindr FastAPI application. All production code lives under this package.

## Subpackages

- `core/` — config, logging, security primitives, time helpers.
- `db/` — SQLAlchemy engine, session, models, base.
- `alembic/` — database migrations (script_location for `alembic.ini`).
- `api/` — FastAPI routers (auth, ui, profiles, jobs, matches).
- `schemas/` — Pydantic request/response models.
- `llm/` — LLM provider abstraction + OpenCode Zen concrete + router.
- `sources/` — job-board adapters (Greenhouse in Plan 1; more in Plan 3).
- `pipeline/` — 6-stage match + tailor orchestrator and stages.
- `resume/` — resume parsing, structuring, and PDF/DOCX rendering.
- `storage/` — MinIO/S3 client wrapper.
- `scheduler/` — APScheduler jobs registration.
- `templates/` — Jinja2 HTML templates.
- `static/` — css/js assets.

## Conventions

- Routers go in `api/` and are mounted from `app.main:app`.
- Never import from `app.alembic` in production code; it is migration-only.
- New packages must include an `__init__.py` and an `AGENTS.md` describing their scope.
