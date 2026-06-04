# AGENTS.md — `tests/unit/`

## What lives here

Pure unit tests with no I/O:
- `test_config.py`, `test_models.py`, `test_security.py`, `test_llm.py`.
- Plus per-stage tests for the pipeline (`test_stage1_quality.py`, etc.) added in Phase 1.

## Conventions

- One test file per source module.
- No `TestClient`, no DB, no network.
- Mock external calls with `respx` for httpx, and `unittest.mock` for the LLM provider.
- Each test must be runnable in isolation; no order dependencies.
