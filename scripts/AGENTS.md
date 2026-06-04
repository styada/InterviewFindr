# AGENTS.md — `scripts/`

## What lives here

Operator scripts (one-off, not part of the running app):
- `create_user.py` — `python -m scripts.create_user admin <password>`.
- `create_profile.py` — adds a `Profile` row for an existing user.

## Conventions

- Scripts are run as `python -m scripts.<name>` from the repo root.
- They read config via `app.core.config.get_settings()`.
- No business logic here — they are CLI wrappers over the same APIs.
- Add a new script only if a recurring operator task cannot be done via the web UI.
