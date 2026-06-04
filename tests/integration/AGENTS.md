# AGENTS.md — `tests/integration/`

## What lives here

Full-stack tests:
- `test_auth.py` — register/login/logout/me.
- `test_profiles.py`, `test_pipeline_end_to_end.py`, `test_match_flow.py` — added in Phase 1.

## Conventions

- Use `TestClient(app)` and override `get_db` with a per-test `sqlite:///:memory:` engine (see `test_auth.py` for the canonical pattern).
- Each test file owns its own engine fixture.
- Clean up: drop the engine and call `app.dependency_overrides.clear()` in fixture finalization.
- LLM calls in integration tests should be stubbed via `respx` or by injecting a `FakeProvider` into the router.
