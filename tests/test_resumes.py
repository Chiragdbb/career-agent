"""Resume upload, extraction, structured parsing, and tenant isolation."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest

from database.models.schema import Document, Resume, ResumeVersion
from packages.domain.resume_extract import extract_text
from packages.domain.resume_models import PARSER_VERSION, StructuredResume
from packages.domain.resume_parse import parse_structured_resume
from packages.providers.storage import (
    MockStorageProvider,
    StorageGetRequest,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _sample_resume_text() -> str:
    return """\
Alex Candidate
alex.candidate@example.com | +1 555 010 9988 | San Francisco, CA
https://linkedin.com/in/alexcandidate
https://alex.dev

SUMMARY
Backend engineer focused on reliable APIs and data pipelines.

EXPERIENCE
Software Engineer at Acme Corp | Jan 2021 - Present
• Built payment APIs serving 2M requests/day
• Led migration to Postgres

Platform Engineer - Beta Labs | 2018 - 2020
• Maintained CI/CD and observability stack

PROJECTS
Career Agent Toolkit
• Resume parsing and job tracking helpers

EDUCATION
State University — B.S. Computer Science | 2014 - 2018

SKILLS
Python, FastAPI, PostgreSQL, Redis

CERTIFICATIONS
AWS Solutions Architect — Amazon — 2022
"""


def _make_pdf_bytes(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(36, 36, 560, 800)
    page.insert_textbox(rect, text, fontsize=10, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def _make_docx_bytes(text: str) -> bytes:
    from docx import Document as DocxDocument

    document = DocxDocument()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def sample_pdf_bytes() -> bytes:
    return _make_pdf_bytes(_sample_resume_text())


@pytest.fixture(scope="module")
def sample_docx_bytes() -> bytes:
    return _make_docx_bytes(_sample_resume_text())


def _ensure_user(auth_client, token: str) -> str:
    response = auth_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _cleanup_resumes(session, user_ids: list[uuid.UUID]) -> None:
    from database.models.schema import Application

    for user_id in user_ids:
        session.query(Application).filter(Application.user_id == user_id).delete()
        session.query(Document).filter(Document.user_id == user_id).delete()
        session.query(ResumeVersion).filter(ResumeVersion.user_id == user_id).delete()
        session.query(Resume).filter(Resume.user_id == user_id).delete()
    session.commit()


@pytest.fixture
def resume_users(auth_client):
    from app.database import get_session_factory

    user_a = uuid.UUID(_ensure_user(auth_client, "token-user-a"))
    user_b = uuid.UUID(_ensure_user(auth_client, "token-user-b"))
    session = get_session_factory()()
    try:
        _cleanup_resumes(session, [user_a, user_b])
        yield {"user_a": user_a, "user_b": user_b}
    finally:
        _cleanup_resumes(session, [user_a, user_b])
        session.close()


def test_extract_text_from_pdf_and_docx(sample_pdf_bytes, sample_docx_bytes) -> None:
    pdf_text = extract_text(sample_pdf_bytes, "application/pdf")
    docx_text = extract_text(
        sample_docx_bytes,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert "Alex Candidate" in pdf_text
    assert "alex.candidate@example.com" in pdf_text
    assert "Alex Candidate" in docx_text
    assert "PostgreSQL" in docx_text


def test_structured_resume_validates_from_heuristic_parse() -> None:
    structured = parse_structured_resume(_sample_resume_text())
    assert isinstance(structured, StructuredResume)
    assert structured.parser_version == PARSER_VERSION
    assert structured.contact.email == "alex.candidate@example.com"
    assert structured.contact.full_name == "Alex Candidate"
    assert structured.summary is not None
    assert "reliable APIs" in structured.summary
    assert len(structured.experience) >= 1
    assert structured.experience[0].company == "Acme Corp"
    assert "Python" in structured.skills
    assert len(structured.education) >= 1
    assert len(structured.projects) >= 1
    assert len(structured.certifications) >= 1
    # Round-trip validation (what we store in JSONB).
    again = StructuredResume.model_validate(structured.model_dump(mode="json"))
    assert again.contact.email == structured.contact.email


def test_unauthenticated_resume_routes_rejected(auth_client) -> None:
    assert auth_client.get("/api/v1/resumes").status_code == 401
    assert (
        auth_client.post(
            "/api/v1/resumes",
            files={"file": ("resume.pdf", b"%PDF-1.4", "application/pdf")},
        ).status_code
        == 401
    )


def test_upload_pdf_and_docx_and_list(
    auth_client, resume_users, sample_pdf_bytes, sample_docx_bytes
) -> None:
    pdf_response = auth_client.post(
        "/api/v1/resumes",
        headers={"Authorization": "Bearer token-user-a"},
        files={
            "file": ("alex.pdf", sample_pdf_bytes, "application/pdf"),
        },
        data={"name": "Alex Master PDF"},
    )
    assert pdf_response.status_code == 201, pdf_response.text
    pdf_body = pdf_response.json()
    assert pdf_body["name"] == "Alex Master PDF"
    assert pdf_body["latest_version"]["parser_version"] == PARSER_VERSION
    assert pdf_body["latest_version"]["plain_text"]
    assert "Alex Candidate" in pdf_body["latest_version"]["plain_text"]
    structured = pdf_body["latest_version"]["structured"]
    assert structured["contact"]["email"] == "alex.candidate@example.com"
    assert structured["skills"]
    assert pdf_body["signed_url"]
    assert pdf_body["latest_version"]["document"]["mime_type"] == "application/pdf"

    docx_response = auth_client.post(
        "/api/v1/resumes",
        headers={"Authorization": "Bearer token-user-a"},
        files={
            "file": (
                "alex.docx",
                sample_docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert docx_response.status_code == 201, docx_response.text
    docx_body = docx_response.json()
    assert docx_body["latest_version"]["document"]["mime_type"].endswith("document")
    assert docx_body["latest_version"]["structured"]["contact"]["email"] == (
        "alex.candidate@example.com"
    )

    listed = auth_client.get(
        "/api/v1/resumes",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()}
    assert pdf_body["id"] in ids
    assert docx_body["id"] in ids

    detail = auth_client.get(
        f"/api/v1/resumes/{pdf_body['id']}",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert detail.status_code == 200
    assert detail.json()["latest_version"]["structured"]["parser_version"] == PARSER_VERSION


def test_upload_stores_object_in_mock_storage(
    auth_client, resume_users, sample_pdf_bytes
) -> None:
    from app.config import get_settings

    response = auth_client.post(
        "/api/v1/resumes",
        headers={"Authorization": "Bearer token-user-a"},
        files={"file": ("stored.pdf", sample_pdf_bytes, "application/pdf")},
        data={"name": "Stored Resume"},
    )
    assert response.status_code == 201
    storage_path = response.json()["latest_version"]["document"]["storage_path"]
    assert storage_path

    storage = auth_client.mock_storage
    assert isinstance(storage, MockStorageProvider)
    bucket = get_settings().supabase_storage_bucket or "resumes"
    assert storage._objects, f"expected stored objects, got keys={list(storage._objects)}"
    got = storage.get_object(StorageGetRequest(bucket=bucket, key=storage_path))
    assert got.data == sample_pdf_bytes


def test_tenant_isolation_on_uploaded_resumes(
    auth_client, resume_users, sample_pdf_bytes
) -> None:
    uploaded = auth_client.post(
        "/api/v1/resumes",
        headers={"Authorization": "Bearer token-user-b"},
        files={"file": ("b-only.pdf", sample_pdf_bytes, "application/pdf")},
        data={"name": "User B Only"},
    )
    assert uploaded.status_code == 201
    resume_id = uploaded.json()["id"]

    denied = auth_client.get(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "not_found"

    allowed = auth_client.get(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": "Bearer token-user-b"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["name"] == "User B Only"

    list_a = auth_client.get(
        "/api/v1/resumes",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert resume_id not in {item["id"] for item in list_a.json()}


def test_rejects_unsupported_file_type(auth_client, resume_users) -> None:
    response = auth_client.post(
        "/api/v1/resumes",
        headers={"Authorization": "Bearer token-user-a"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "domain_error"
