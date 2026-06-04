"""Unit tests for the Greenhouse job-source adapter."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.sources.greenhouse import GreenhouseSource


@pytest.mark.asyncio
@respx.mock
async def test_greenhouse_parses_sample() -> None:
    fixture = json.loads(Path("tests/fixtures/jobs/greenhouse_sample.json").read_text())
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(
        return_value=httpx.Response(200, json=fixture)
    )
    src = GreenhouseSource(board_token="acme")
    jobs = await src.fetch()
    assert len(jobs) == 1
    assert jobs[0].external_id == "123"
    assert jobs[0].title == "Senior Backend Engineer"
    assert "Senior Backend Engineer" in jobs[0].description_text
