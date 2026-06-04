"""OpenCode Zen LLM provider (OpenAI-compatible chat completions)."""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.llm.base import LLMResponse


class OpenCodeZenProvider:
    """Concrete provider targeting https://opencode.ai/zen/go/v1."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        s = get_settings()
        self._base = (base_url or s.opencode_zen_base_url).rstrip("/")
        self._key = api_key or s.opencode_zen_api_key
        self._timeout = timeout

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(
                f"{self._base}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._key}"},
            )
            r.raise_for_status()
            data = r.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        text = choice["message"]["content"]
        in_t = int(usage.get("prompt_tokens", 0))
        out_t = int(usage.get("completion_tokens", 0))
        return LLMResponse(
            text=text,
            input_tokens=in_t,
            output_tokens=out_t,
            cost_usd=0.0,  # Router applies pricing from its catalog
            raw=data,
        )
