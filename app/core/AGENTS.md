# AGENTS.md — `app/core/`

## What lives here

Cross-cutting infrastructure that is not domain-specific:
- `config.py` — pydantic Settings (loads from .env).
- `security.py` — argon2id password hashing + itsdangerous session tokens.
- `logging.py` — `configure_logging(level)`.
- `time.py` — `utcnow()` for testable clock injection.

## Conventions

- Anything imported by 5+ other modules belongs here.
- No FastAPI / SQLAlchemy imports in this package.
- All settings must go through `app.core.config.get_settings()`.
