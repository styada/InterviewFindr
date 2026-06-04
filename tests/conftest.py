"""Pytest configuration and shared fixtures."""

import os

os.environ.setdefault("APP_SECRET_KEY", "x" * 32)
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/d")
os.environ.setdefault("MINIO_ACCESS_KEY", "x")
os.environ.setdefault("MINIO_SECRET_KEY", "x")
os.environ.setdefault("OPENCODE_ZEN_API_KEY", "x")
