# AGENTS.md — `app/sources/`

## What lives here

Job-board adapters that normalize external feeds into the local `Job` schema.

- `base.py` — `JobSource` Protocol and shared types.
- `registry.py` — load `SourceConfig` rows and dispatch to the right adapter.
- `greenhouse.py` — only Tier 1 source enabled in Plan 1.

## Off-limits (spec §5)

Do **not** add adapters for LinkedIn, Indeed, Glassdoor, ZipRecruiter, Naukri, or any site whose ToS forbids scraping/automated access. Tier 3 indirect sources (JSearch, SerpApi) are approved and arrive in Plan 3.

## Conventions

- Adapters accept an `httpx.AsyncClient` (so tests can inject a mocked client).
- Each adapter returns `list[dict]` shaped to match `Job` columns; the registry handles dedupe via the `(source, external_id)` unique constraint.
- Be respectful of rate limits — read `SourceConfig.rate_limit` and back off.
