# AGENTS.md

## Project

InterviewFindr — a self-hosted job-application engine. Python 3.12, FastAPI, Postgres, HTMX. LLM calls go through OpenCode Zen.

## Authoritative docs

- Spec: `docs/superpowers/specs/2026-06-03-interviewfindr-design.md`
- Plan 1 (current): `docs/superpowers/plans/2026-06-03-interviewfindr-plan-1.md`

Always read the spec and plan before making non-trivial changes. If the spec and code disagree, fix the code. If the spec is wrong, fix the spec first and note the change in the commit.

## Conventions

- Type hints on every function signature.
- Tests live next to code (`tests/unit/`, `tests/integration/`).
- TDD for any new logic: write the failing test, then implement, then commit.
- One logical change per commit.
- No `print()` in production code; use `app.core.logging`.
- Pydantic for all external boundaries (API I/O, LLM I/O, DB rows).
- SQLAlchemy 2.x style; no legacy Query API.

## Things to NOT do

- Do not auto-apply to LinkedIn, Indeed, Glassdoor, ZipRecruiter, Naukri, or any site that prohibits it in ToS. The spec §5 lists the off-limits list.
- Do not call LLMs from inside request handlers. Use the background pipeline.
- Do not commit `.env`. Use `.env.example` as the template.
- Do not use Ollama; LLM calls go to OpenCode Zen.

## Common commands

```bash
# run tests
pytest

# lint
ruff check .
ruff format .

# typecheck
mypy app/

# start dev server
uvicorn app.main:app --reload

# database migration
alembic revision --autogenerate -m "msg"
alembic upgrade head
```
