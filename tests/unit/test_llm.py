"""Unit tests for app.llm: OpenCode Zen provider + router (cache, pricing)."""
from __future__ import annotations

import httpx
import pytest
import respx

from app.llm.base import LLMResponse
from app.llm.opencode_zen import OpenCodeZenProvider
from app.llm.router import LLMRouter


@pytest.mark.asyncio
@respx.mock
async def test_opencode_zen_provider_parses_response() -> None:
    respx.post("https://opencode.ai/zen/go/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )
    )
    p = OpenCodeZenProvider(api_key="x")
    r = await p.complete([{"role": "user", "content": "hello"}], model="kimi-k2.6")
    assert r.text == "hi"
    assert r.input_tokens == 10
    assert r.output_tokens == 5


@pytest.mark.asyncio
@respx.mock
async def test_opencode_zen_sends_json_mode_when_requested() -> None:
    route = respx.post("https://opencode.ai/zen/go/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
    )
    p = OpenCodeZenProvider(api_key="x")
    await p.complete(
        [{"role": "user", "content": "x"}], model="kimi-k2.6", json_mode=True
    )
    sent = route.calls.last.request
    import json as _json

    body = _json.loads(sent.content)
    assert body["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_router_caches_identical_calls() -> None:
    calls = {"n": 0}

    class FakeProvider:
        async def complete(self, messages, *, model, **kw):
            calls["n"] += 1
            return LLMResponse(
                text="ok", input_tokens=1, output_tokens=1, cost_usd=0.0, raw={}
            )

    router = LLMRouter({"p": FakeProvider()})
    msg = [{"role": "user", "content": "hello"}]
    r1 = await router.complete("p", "kimi-k2.6", msg, max_tokens=10)
    r2 = await router.complete("p", "kimi-k2.6", msg, max_tokens=10)
    assert calls["n"] == 1
    assert r1.text == "ok"


@pytest.mark.asyncio
async def test_router_applies_pricing() -> None:
    class FakeProvider:
        async def complete(self, messages, *, model, **kw):
            return LLMResponse(
                text="x",
                input_tokens=1_000_000,
                output_tokens=1_000_000,
                cost_usd=0.0,
                raw={},
            )

    router = LLMRouter({"p": FakeProvider()})
    r = await router.complete("p", "kimi-k2.6", [{"role": "user", "content": "a"}])
    expected = 1_000_000 * 0.000_000_6 + 1_000_000 * 0.000_003
    assert abs(r.cost_usd - expected) < 1e-6


@pytest.mark.asyncio
async def test_router_unknown_model_costs_zero() -> None:
    class FakeProvider:
        async def complete(self, messages, *, model, **kw):
            return LLMResponse(text="x", input_tokens=100, output_tokens=100, cost_usd=0.0, raw={})

    router = LLMRouter({"p": FakeProvider()})
    r = await router.complete("p", "unknown-model", [{"role": "user", "content": "a"}])
    assert r.cost_usd == 0.0
