# AGENTS.md — `app/alembic/`

## What lives here

Alembic migration environment. `script_location = app/alembic` is set in `alembic.ini` at the repo root.

- `env.py` — loads `DATABASE_URL` from app settings; imports all models so autogenerate sees them.
- `script.py.mako` — template for new revisions.
- `versions/` — actual migration files, one per logical schema change.

## Conventions

- **Always use `alembic revision --autogenerate` after changing `app/db/models.py`.**
- Do not delete old revision files; Alembic relies on linear history.
- Migration files are SQLite- and Postgres-compatible (use `sa.Uuid`, `sa.JSON`, `sa.text('CURRENT_TIMESTAMP')` for `server_default`).
- New revisions go in `versions/` and must be committed alongside the model change.
