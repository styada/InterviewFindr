# AGENTS.md — `app/db/`

## What lives here

SQLAlchemy ORM layer:
- `base.py` — `Base = DeclarativeBase`.
- `session.py` — `engine`, `SessionLocal`, `get_db()` FastAPI dependency.
- `models.py` — all 8 tables from spec §3.

## Conventions

- All primary keys are UUIDs via `Uuid(as_uuid=True)`.
- JSON columns use portable `JSON` (not Postgres-specific JSONB).
- List columns use portable `JSON` and are deserialized to `list[str]` in app code.
- All datetime columns are timezone-aware (`DateTime(timezone=True)`).
- When adding a model, update `app/alembic/versions/0001_initial.py` if it lands in this plan, or generate a new revision in Plan 3+.

## Test pattern

Tests use a fresh `sqlite:///:memory:` engine; see `tests/integration/test_auth.py` for the `app.dependency_overrides[get_db]` pattern.
