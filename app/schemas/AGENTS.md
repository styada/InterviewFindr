# AGENTS.md — `app/schemas/`

## What lives here

Pydantic v2 schemas for all external I/O:
- `user.py` — UserCreate, UserOut.

(More files added in Phase 1: `profile.py`, `job.py`, `match.py`, `tailored.py`.)

## Conventions

- All schemas use `from __future__ import annotations`.
- Output schemas use `model_config = ConfigDict(from_attributes=True)` so they can be built from ORM instances.
- UUID fields are serialized as `str`; add a `field_validator("id", mode="before")` that coerces `UUID` → `str`.
- Never put domain logic here — only shape.
