"""Job-source adapter base types."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RawJob:
    source: str
    external_id: str
    url: str
    company: str
    title: str
    location: str | None
    remote_type: str | None
    salary_min: float | None
    salary_max: float | None
    currency: str | None
    description_html: str | None
    description_text: str
    posted_at: str | None
    raw_payload: dict


class JobSource(Protocol):
    name: str

    async def fetch(self, *, company: str | None = None) -> list[RawJob]: ...
