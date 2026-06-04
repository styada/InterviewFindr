"""Seed the database with the first admin user and an example profile.

Run after `alembic upgrade head`:

    docker compose exec app python -m scripts.seed
    # or, locally:
    .venv/bin/python -m scripts.seed
"""
from __future__ import annotations

import argparse
import sys
import uuid
from getpass import getpass

from sqlalchemy import select

from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.models import Profile, User
from app.db.session import SessionLocal


def seed_admin(email: str, password: str, display_name: str) -> uuid.UUID:
    """Create the admin user + a default profile if they don't already exist."""
    with SessionLocal() as db, db.begin():
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            print(f"User {email} already exists (id={existing.id}).")
            return existing.id
        user = User(
            email=email,
            display_name=display_name,
            role="admin",
            password_hash=hash_password(password),
        )
        db.add(user)
        db.flush()
        db.add(
            Profile(
                user_id=user.id,
                market_primary="US",
                market_secondary=[],
                preferences={
                    "salary_min": 100000,
                    "remote_ok": True,
                    "titles_include": [],
                    "titles_exclude": [],
                },
                tailoring_thresholds={
                    "min_match_score": 0.40,
                    "must_have_coverage_min": 0.70,
                    "top_n_per_day": 25,
                },
            )
        )
        return user.id


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed InterviewFindr with the first admin user.")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--display-name", default="Admin")
    args = parser.parse_args()

    configure_logging("INFO")
    password = getpass("Password (min 12 chars): ")
    if len(password) < 12:
        print("Password must be at least 12 characters.", file=sys.stderr)
        return 1

    user_id = seed_admin(args.email, password, args.display_name)
    print(f"Seeded admin user {args.email} (id={user_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
