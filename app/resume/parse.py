"""Resume text extraction (PDF / DOCX / plain text).

This is a thin wrapper around pdfplumber and python-docx. The plan-task 20
endpoint uses `extract_text(bytes, filename) -> str`.
"""
from __future__ import annotations

import io
import logging

log = logging.getLogger(__name__)


def extract_text(data: bytes, filename: str) -> str:
    """Return plain text extracted from a PDF, DOCX, or plain-text file.

    The returned text is what `structure_resume` will feed to the LLM, so we
    fall back to a UTF-8 decode on any extraction error.
    """
    name = filename.lower()
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    if name.endswith(".docx"):
        return _extract_docx(data)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="ignore")


def _extract_pdf(data: bytes) -> str:
    try:
        import pdfplumber  # type: ignore[import-not-found]

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            chunks: list[str] = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text:
                    chunks.append(text)
        return "\n".join(chunks)
    except Exception as exc:  # pragma: no cover - extractor errors are non-fatal
        log.warning("PDF extraction failed: %s", exc)
        return ""


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document  # type: ignore[import-not-found]

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:  # pragma: no cover
        log.warning("DOCX extraction failed: %s", exc)
        return ""
