# AGENTS.md — `app/resume/`

## What lives here

Resume handling:
- `parse.py` — extract raw text from PDF (pdfplumber) and DOCX (python-docx).
- `structure.py` — LLM call to convert raw text to a structured JSON form (name, contact, experience, education, skills).
- `render.py` — WeasyPrint PDF rendering from a structured resume + a per-job diff.

## Conventions

- `parse.py` must not call LLMs — it is pure text extraction.
- `structure.py` calls `LLMRouter` with the cheap model (kimi-k2.6).
- The `Profile.resume_parsed_json` column holds the result of `structure.py`. `TailoredArtifact.resume_text` holds the job-tailored variant.
- Rendered artifacts (PDF, DOCX) are uploaded to MinIO and the path is stored in the DB; do not store binary blobs in SQLite.
