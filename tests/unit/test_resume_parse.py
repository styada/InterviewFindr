"""Unit tests for app.resume.parse text extraction."""
from __future__ import annotations

from pathlib import Path

from app.resume.parse import extract_text


def test_extract_text_from_plain() -> None:
    p = Path("tests/fixtures/resumes/banker.txt")
    assert "Senior Vice President" in extract_text(p.read_bytes(), "banker.txt")
