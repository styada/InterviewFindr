"""Unit tests for app.resume.render (WeasyPrint + python-docx)."""

from __future__ import annotations

import io
import zipfile

from app.resume.render import (
    render_cover_letter_pdf,
    render_resume_docx,
    render_resume_pdf,
    resume_to_plain_text,
)


def _sample_resume() -> dict:
    return {
        "contact": {
            "name": "Jane Doe",
            "email": "j@d.com",
            "phone": "555-1212",
            "location": "NYC",
        },
        "summary": "Engineer with experience.",
        "experience": [
            {
                "title": "Sr Eng",
                "company": "X",
                "start": "2020-01",
                "end": "present",
                "location": "NYC",
                "bullets": ["Did things", "Built things"],
            }
        ],
        "education": [{"school": "Y", "degree": "BS", "field": "CS", "year": 2015}],
        "skills": [{"name": "Python"}, {"name": "PostgreSQL"}],
    }


def test_render_resume_pdf_returns_valid_pdf() -> None:
    pdf = render_resume_pdf(_sample_resume())
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


def test_render_resume_pdf_handles_minimal_resume() -> None:
    pdf = render_resume_pdf({})
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


def test_render_resume_pdf_handles_none_sublists() -> None:
    resume = {"contact": {"name": "X"}, "summary": "s"}
    pdf = render_resume_pdf(resume)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


def test_render_resume_docx_returns_valid_docx() -> None:
    docx = render_resume_docx(_sample_resume())
    assert isinstance(docx, bytes)
    assert docx[:4] == b"PK\x03\x04"
    with zipfile.ZipFile(io.BytesIO(docx)) as zf:
        assert "word/document.xml" in zf.namelist()


def test_render_resume_docx_handles_empty_resume() -> None:
    docx = render_resume_docx({})
    assert isinstance(docx, bytes)
    assert docx[:4] == b"PK\x03\x04"


def test_render_cover_letter_pdf_returns_valid_pdf() -> None:
    text = "First paragraph here.\n\nSecond paragraph here."
    pdf = render_cover_letter_pdf(text)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


def test_render_cover_letter_pdf_skips_blank_paragraphs() -> None:
    text = "Para 1.\n\n   \n\nPara 2."
    pdf = render_cover_letter_pdf(text)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


def test_resume_to_plain_text_includes_skills() -> None:
    r = {"summary": "", "experience": [], "skills": [{"name": "Python"}]}
    assert "Python" in resume_to_plain_text(r)


def test_resume_to_plain_text_includes_experience_bullets() -> None:
    r = {
        "summary": "top summary",
        "experience": [{"title": "Engineer", "company": "X", "bullets": ["Built things"]}],
        "skills": [],
    }
    text = resume_to_plain_text(r)
    assert "top summary" in text
    assert "Engineer" in text
    assert "X" in text
    assert "Built things" in text


def test_resume_to_plain_text_handles_empty_resume() -> None:
    assert resume_to_plain_text({}) == ""
