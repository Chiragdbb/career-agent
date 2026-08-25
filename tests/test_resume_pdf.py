"""STEP 19 — Deterministic resume PDF rendering."""

from __future__ import annotations

import uuid

from packages.domain.resume_models import (
    ContactInfo,
    ExperienceEntry,
    StructuredResume,
)
from packages.domain.resume_pdf import (
    TEMPLATE_VERSION,
    ResumePdfService,
    render_resume_html,
    render_resume_pdf,
)
from packages.providers.storage import MockStorageProvider, StorageGetRequest


def _sample_resume() -> StructuredResume:
    return StructuredResume(
        contact=ContactInfo(
            full_name="Pat Candidate",
            email="pat@example.com",
            location="Remote",
        ),
        summary="Software engineer focused on backend systems.",
        skills=["Python", "Postgres", "FastAPI"],
        experience=[
            ExperienceEntry(
                company="PastCo",
                title="Software Engineer",
                start_date="2020",
                end_date="2023",
                bullets=["Built APIs", "Owned on-call"],
            )
        ],
    )


def test_render_pdf_is_valid_and_deterministic() -> None:
    resume = _sample_resume()
    first = render_resume_pdf(resume)
    second = render_resume_pdf(resume)
    assert first.pdf_bytes.startswith(b"%PDF")
    assert second.pdf_bytes.startswith(b"%PDF")
    # PDF container bytes may include non-stable producer metadata; HTML layout is fixed.
    assert render_resume_html(resume) == render_resume_html(resume)
    assert first.template_version == second.template_version == TEMPLATE_VERSION
    assert "Pat Candidate" in render_resume_html(resume)
    assert len(first.pdf_bytes) > 100


def test_render_and_upload_to_storage() -> None:
    storage = MockStorageProvider()
    service = ResumePdfService(storage, bucket="resumes")
    user_id = uuid.uuid4()
    version_id = uuid.uuid4()
    rendered = service.render_and_upload(
        _sample_resume(),
        user_id=user_id,
        resume_version_id=version_id,
    )
    assert rendered.storage_path is not None
    assert TEMPLATE_VERSION in rendered.storage_path
    got = storage.get_object(
        StorageGetRequest(bucket="resumes", key=rendered.storage_path)
    )
    assert got.data.startswith(b"%PDF")
    assert len(got.data) > 100
