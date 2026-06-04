"""Stage 2 — structured JD parsing via the LLM router.

Calls the cheap model (default ``kimi-k2.6``) over OpenCode Zen in JSON mode
and returns the parsed dict. The orchestrator (Stage 3-6) consumes the
shape directly: ``must_haves``, ``level``, ``compensation``, ``years_*``,
``role_function``, etc.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.llm.router import LLMRouter
from app.sources.base import RawJob

log = logging.getLogger(__name__)


PARSE_PROMPT: str = """\
Extract structured fields from the following job description. Return ONLY valid JSON matching this shape:

{{
  "must_haves": ["string", ...],
  "nice_to_haves": ["string", ...],
  "compensation": {{"min": number|null, "max": number|null, "currency": "USD", "period": "yearly"}},
  "level": "IC3|IC4|manager|director|vp|principal|entry|unknown",
  "role_function": "engineering|product|design|operations|finance|marketing|sales|customer_success|public_health|other",
  "team": "string|null",
  "employment_type": "full_time|contract|part_time|intern|unknown",
  "remote_policy": "remote|hybrid|onsite|null",
  "years_experience_min": number|null,
  "years_experience_max": number|null
}}

JOB DESCRIPTION:
\"\"\"
{job}
\"\"\"
"""


async def parse_jd(
    router: LLMRouter,
    job: RawJob,
    *,
    model: str = "kimi-k2.6",
) -> dict[str, Any]:
    text: str = job.description_text or ""
    prompt: str = PARSE_PROMPT.format(job=text)
    response = await router.complete(
        "opencode_zen",
        model,
        [{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.0,
        json_mode=True,
    )
    try:
        parsed: dict[str, Any] = json.loads(response.text)
    except json.JSONDecodeError as exc:
        log.warning("parse_jd: invalid JSON from LLM: %s", exc)
        raise
    return parsed
