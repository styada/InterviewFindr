"""Process-local registry of available JobSource implementations."""
from __future__ import annotations

from app.sources.base import JobSource


_REGISTRY: dict[str, JobSource] = {}


def register(source: JobSource) -> None:
    _REGISTRY[source.name] = source


def get(name: str) -> JobSource:
    return _REGISTRY[name]


def all_sources() -> list[JobSource]:
    return list(_REGISTRY.values())
