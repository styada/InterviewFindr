# InterviewFindr

Smart job-application engine for the family. Self-hosted on a small VPS.

See `docs/superpowers/specs/2026-06-03-interviewfindr-design.md` for the design spec.
See `docs/superpowers/plans/2026-06-03-interviewfindr-plan-1.md` for the implementation plan.

## Quickstart

```bash
cp .env.example .env
# edit .env with real secrets
docker compose up -d
docker compose exec app alembic upgrade head
docker compose exec app python -m scripts.create_user admin changeme
```

## Development (no Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Layout

- `app/` — FastAPI application
- `tests/` — pytest test suite
- `docs/superpowers/specs/` — design spec
- `docs/superpowers/plans/` — implementation plans
