"""Resume structuring — convert raw text to a structured JSON via the LLM.

Profile.resume_parsed_json holds the result of this function. The orchestrator
(app.pipeline.run) consumes the shape directly when running Stages 3-6.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.llm.router import LLMRouter

log = logging.getLogger(__name__)


_STRUCTURE_PROMPT = """\
You are a resume parser. Convert the following resume text into JSON with this exact shape:

{
  "summary": "one-line professional summary",
  "contact": {"name": "...", "email": "...", "phone": "...", "location": "..."},
  "experience": [
    {"company": "...", "title": "...", "start": "YYYY-MM", "end": "YYYY-MM or present",
     "location": "...", "bullets": ["...", "..."]}
  ],
  "education": [{"school": "...", "degree": "...", "field": "...", "year": 2024}],
  "skills": [
    {"name": "...", "years": 5, "context": "..."}
  ],
  "certifications": [],
  "languages": []
}

Use null for any field you cannot determine. Return only valid JSON, no commentary.

RESUME TEXT:
\"\"\"
{resume}
\"\"\"
"""


_EMPTY: dict[str, Any] = {
    "summary": "",
    "contact": {"name": None, "email": None, "phone": None, "location": None},
    "experience": [],
    "education": [],
    "skills": [],
    "certifications": [],
    "languages": [],
}


async def structure_resume(
    router: LLMRouter,
    raw_text: str,
    *,
    model: str = "kimi-k2.6",
) -> dict[str, Any]:
    """Convert raw resume text into a structured dict via the LLM router.

    On empty input or any LLM/parse failure, return a minimal skeleton so
    the upload endpoint never raises — the orchestrator's quality filters
    will reject the row downstream if the skeleton is too empty.
    """
    if not raw_text or not raw_text.strip():
        return dict(_EMPTY)
    prompt = _STRUCTURE_PROMPT.format(resume=raw_text[:12000])
    try:
        response = await router.complete(
            "opencode_zen",
            model,
            [{"role": "user", "content": prompt}],
            max_tokens=2500,
            temperature=0.0,
            json_mode=True,
        )
        data = json.loads(response.text)
    except Exception as exc:  # pragma: no cover - LLM errors are non-fatal
        log.warning("structure_resume failed: %s", exc)
        return dict(_EMPTY)
    if not isinstance(data, dict):
        log.warning("structure_resume: LLM returned non-object JSON")
        return dict(_EMPTY)
    return data
