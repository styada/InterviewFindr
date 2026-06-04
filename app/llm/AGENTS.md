# AGENTS.md — `app/llm/`

## What lives here

LLM provider abstraction:
- `base.py` — `LLMResponse` dataclass + `LLMProvider` Protocol.
- `opencode_zen.py` — concrete provider for `https://opencode.ai/zen/go/v1`.
- `router.py` — `LLMRouter` with per-model pricing (`PRICES`) and 24h in-process cache.

## Conventions

- Pipeline code must go through the router, never call providers directly. This is what gives us caching and cost accounting.
- New providers implement the `LLMProvider` Protocol and are registered in `LLMRouter(providers=...)`.
- Pricing lives in `app.llm.router.PRICES`. Add new models there.
- The router cache is in-process; restart the service to clear it. Persistent caching is intentionally out of scope for v1.
