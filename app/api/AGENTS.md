# AGENTS.md — `app/api/`

## What lives here

FastAPI routers:
- `deps.py` — `current_user` dependency (session cookie → User).
- `auth.py` — `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`.
- `ui.py` — server-rendered HTMX page routes.
- `profiles.py`, `jobs.py`, `matches.py` — added in Phase 1.

## Conventions

- Form posts for browser flows; JSON only for programmatic clients.
- All protected endpoints depend on `current_user`.
- `response_model=` should always be set explicitly to drive OpenAPI docs.
- Pydantic schemas live in `app/schemas/`, not inline in the router file.
