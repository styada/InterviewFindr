"""LLM router: model selection, cost accounting, in-process caching."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from app.llm.base import LLMProvider, LLMResponse


# Per-token USD pricing (input, output). Update as OpenCode Zen pricing changes.
PRICES: dict[str, tuple[float, float]] = {
    "kimi-k2.6": (0.000_000_6, 0.000_003),
    "deepseek-v4-pro": (0.000_001, 0.000_005),
    "glm-5.1": (0.000_000_8, 0.000_004),
    "qwen3.7-max": (0.000_001, 0.000_004_5),
}


class _Cache:
    def __init__(self, ttl_seconds: int = 86400) -> None:
        self._store: dict[str, tuple[datetime, LLMResponse]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def get(self, key: str) -> LLMResponse | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, val = entry
        if datetime.now(tz=timezone.utc) - ts < self._ttl:
            return val
        del self._store[key]
        return None

    def set(self, key: str, value: LLMResponse) -> None:
        self._store[key] = (datetime.now(tz=timezone.utc), value)


class LLMRouter:
    """Routes completion requests to the right provider and applies pricing/caching."""

    def __init__(
        self,
        providers: dict[str, LLMProvider],
        cache: _Cache | None = None,
    ) -> None:
        self._providers = providers
        self._cache = cache or _Cache()

    @staticmethod
    def _key(
        provider: str, model: str, messages: list[dict[str, Any]], kwargs: dict[str, Any]
    ) -> str:
        h = hashlib.sha256()
        h.update(provider.encode())
        h.update(b"|")
        h.update(model.encode())
        h.update(b"|")
        h.update(json.dumps(messages, sort_keys=True).encode())
        h.update(b"|")
        h.update(json.dumps(kwargs, sort_keys=True).encode())
        return h.hexdigest()

    async def complete(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        key = self._key(provider, model, messages, kwargs)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        raw = await self._providers[provider].complete(messages, model=model, **kwargs)
        ip, op = PRICES.get(model, (0.0, 0.0))
        cost = raw.input_tokens * ip + raw.output_tokens * op
        priced = replace(raw, cost_usd=cost)
        self._cache.set(key, priced)
        return priced
