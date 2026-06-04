# AGENTS.md — `app/pipeline/`

## What lives here

The 6-stage match + tailor pipeline. Each stage is a pure function module:
- `stage1_quality.py` — JD quality heuristic (deterministic).
- `stage2_parse.py` — structured JD parsing via cheap LLM call.
- `stage3_skill_match.py` — skill-graph match (deterministic).
- `stage4_probability.py` — composite probability score.
- `stage5_tailor.py` — resume + cover letter tailoring.
- `stage6_validate.py` — ATS validation (deterministic).
- `run.py` — `Pipeline` orchestrator that runs all stages for a `(user, job)` pair.

## Conventions

- Each stage takes a typed input and returns a typed output; see the Pydantic models in `app/schemas/`.
- Only `stage2_parse` and `stage5_tailor` make LLM calls. All other stages are deterministic.
- Stage results are stored in the `Match` and `TailoredArtifact` tables; the pipeline is idempotent (re-running for the same `(user, job)` overwrites, never duplicates).
- The orchestrator is invoked from `app.scheduler.jobs` (cron) and from the on-demand `/matches` API in Phase 1.
