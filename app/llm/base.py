"""LLM provider abstraction: Protocol, response dataclass, model catalog."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""

    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    """Provider interface — every concrete provider implements complete()."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> LLMResponse: ...
