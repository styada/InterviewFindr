"""Stage 5 — resume + cover letter tailoring via the LLM.

Two OpenCode Zen calls per match: a JSON-mode resume rewrite that mirrors
must-have keywords and reorders bullets to emphasize relevant experience,
then a non-JSON 3-paragraph cover letter. Costs are summed on the returned
``TailoringResult`` so the orchestrator can persist them on
``TailoredArtifact.token_cost_usd``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.llm.router import LLMRouter

log = logging.getLogger(__name__)


RESUME_PROMPT: str = """\
You are tailoring a resume for a specific job. Given the candidate's structured
resume and the parsed job, produce a tailored resume JSON matching the candidate's
schema. Mirror the must_have keywords verbatim in the bullets where they don't
misrepresent experience. Reorder bullets to emphasize relevant experience.

CANDIDATE RESUME (JSON):
{resume}

JOB (JSON):
{job}

Return ONLY the tailored resume JSON.
"""

COVER_LETTER_PROMPT: str = """\
Write a 3-paragraph cover letter for this candidate applying to this job.
Paragraph 1: specific opener referencing the company/role/team, not generic.
Paragraph 2: 2-3 concrete examples from the resume that map to the must-haves, with quantification.
Paragraph 3: specific closer about why this company/team, not boilerplate.

CANDIDATE (JSON): {resume}
JOB (JSON): {job}
"""


@dataclass
class TailoringResult:
    tailored_resume: dict[str, Any]
    cover_letter: str
    model_used: str
    cost_usd: float


async def tailor(
    router: LLMRouter,
    resume: dict[str, Any],
    job_parsed: dict[str, Any],
    *,
    model: str = "kimi-k2.6",
) -> TailoringResult:
    resume_resp = await router.complete(
        "opencode_zen",
        model,
        [{"role": "user", "content": RESUME_PROMPT.format(
            resume=json.dumps(resume, indent=2),
            job=json.dumps(job_parsed, indent=2),
        )}],
        max_tokens=3000,
        temperature=0.2,
        json_mode=True,
    )
    try:
        tailored: dict[str, Any] = json.loads(resume_resp.text)
    except json.JSONDecodeError as exc:
        log.warning("tailor: invalid JSON from LLM for resume: %s", exc)
        raise

    cl_resp = await router.complete(
        "opencode_zen",
        model,
        [{"role": "user", "content": COVER_LETTER_PROMPT.format(
            resume=json.dumps(resume, indent=2),
            job=json.dumps(job_parsed, indent=2),
        )}],
        max_tokens=900,
        temperature=0.5,
    )
    return TailoringResult(
        tailored_resume=tailored,
        cover_letter=cl_resp.text,
        model_used=model,
        cost_usd=resume_resp.cost_usd + cl_resp.cost_usd,
    )
