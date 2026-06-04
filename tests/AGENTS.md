# AGENTS.md — `tests/`

## What lives here

Pytest test suite.
- `conftest.py` — top-level fixtures and required env defaults.
- `factories.py` — ORM object builders (one per model).
- `unit/` — fast tests with no I/O, in-memory SQLite.
- `integration/` — full-stack tests using FastAPI `TestClient` + dependency overrides.
- `fixtures/` — sample resumes, sample job-board JSON, etc.

## Conventions

- All tests are in `unit/` or `integration/` — no top-level test files.
- Unit tests use `sqlite:///:memory:` directly; integration tests override `app.db.session.get_db` with a per-test engine.
- Network calls in tests use `respx` to mock `httpx`.
- Run the full suite with `make test`; pre-commit runs ruff and pytest.
