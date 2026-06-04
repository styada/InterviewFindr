"""Greenhouse job-board adapter (Tier 1 source, Plan 1)."""
from __future__ import annotations

import datetime as dt
import html
from typing import Any

import httpx

from app.sources.base import JobSource, RawJob


class GreenhouseSource:
    name = "greenhouse"

    def __init__(self, board_token: str) -> None:
        self._token = board_token

    async def fetch(self, *, company: str | None = None) -> list[RawJob]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self._token}/jobs"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
        return [self._to_raw(j) for j in data.get("jobs", [])]

    def _to_raw(self, j: dict[str, Any]) -> RawJob:
        loc = (j.get("location") or {}).get("name")
        posted = j.get("updated_at")
        return RawJob(
            source=self.name,
            external_id=str(j["id"]),
            url=j.get("absolute_url", ""),
            company=self._token,
            title=j.get("title", ""),
            location=loc,
            remote_type=None,
            salary_min=None,
            salary_max=None,
            currency=None,
            description_html=j.get("content"),
            description_text=_strip_html(j.get("content", "")),
            posted_at=posted,
            raw_payload=j,
        )


def _strip_html(s: str) -> str:
    text = html.unescape(s)
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
