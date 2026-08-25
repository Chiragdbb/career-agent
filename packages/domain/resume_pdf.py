"""Deterministic ATS-friendly resume PDF rendering.

LLM must not control layout. Fixed HTML/CSS-like template rendered via PyMuPDF.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

import fitz  # PyMuPDF

from packages.domain.resume_models import StructuredResume
from packages.providers.storage import StorageProvider, StoragePutRequest

TEMPLATE_VERSION = "resume-pdf-v1"
DEFAULT_BUCKET = "resumes"


@dataclass(frozen=True)
class RenderedResumePdf:
    pdf_bytes: bytes
    content_hash: str
    template_version: str
    storage_path: str | None = None
    bucket: str | None = None


def render_resume_html(resume: StructuredResume) -> str:
    """Fixed semantic HTML used as the layout source of truth (not LLM-authored)."""
    contact = resume.contact
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{_esc(contact.full_name or 'Resume')}</title>",
        "<style>",
        "body{font-family:Helvetica,Arial,sans-serif;font-size:11pt;color:#111;margin:36px;}",
        "h1{font-size:18pt;margin:0 0 4px 0;} h2{font-size:12pt;border-bottom:1px solid #333;",
        "margin:16px 0 8px 0;text-transform:uppercase;letter-spacing:0.04em;}",
        "p,li{line-height:1.35;} .meta{color:#333;font-size:10pt;margin-bottom:12px;}",
        ".role{font-weight:bold;} .company{font-style:normal;} ul{margin:4px 0 10px 18px;}",
        "</style></head><body>",
    ]
    lines.append(f"<h1>{_esc(contact.full_name or 'Candidate')}</h1>")
    meta_bits = [
        contact.email,
        contact.phone,
        contact.location,
        contact.linkedin_url,
        contact.website_url,
    ]
    meta = " · ".join(_esc(m) for m in meta_bits if m)
    if meta:
        lines.append(f"<div class='meta'>{meta}</div>")

    if resume.summary:
        lines.append("<h2>Summary</h2>")
        lines.append(f"<p>{_esc(resume.summary)}</p>")

    if resume.skills:
        lines.append("<h2>Skills</h2>")
        lines.append(f"<p>{_esc(', '.join(resume.skills))}</p>")

    if resume.experience:
        lines.append("<h2>Experience</h2>")
        for exp in resume.experience:
            title = _esc(exp.title or "")
            company = _esc(exp.company or "")
            dates = " – ".join(d for d in (exp.start_date, exp.end_date or ("Present" if exp.is_current else None)) if d)
            lines.append(
                f"<p><span class='role'>{title}</span>"
                f"{' — ' if title and company else ''}"
                f"<span class='company'>{company}</span>"
                f"{(' (' + _esc(dates) + ')') if dates else ''}</p>"
            )
            if exp.bullets:
                lines.append("<ul>")
                lines.extend(f"<li>{_esc(b)}</li>" for b in exp.bullets)
                lines.append("</ul>")

    if resume.projects:
        lines.append("<h2>Projects</h2>")
        for project in resume.projects:
            lines.append(f"<p class='role'>{_esc(project.name or 'Project')}</p>")
            if project.description:
                lines.append(f"<p>{_esc(project.description)}</p>")
            if project.bullets:
                lines.append("<ul>")
                lines.extend(f"<li>{_esc(b)}</li>" for b in project.bullets)
                lines.append("</ul>")

    if resume.education:
        lines.append("<h2>Education</h2>")
        for edu in resume.education:
            bits = [edu.degree, edu.field_of_study, edu.institution]
            lines.append(f"<p>{_esc(' · '.join(b for b in bits if b))}</p>")

    if resume.certifications:
        lines.append("<h2>Certifications</h2>")
        for cert in resume.certifications:
            lines.append(f"<p>{_esc(cert.name or '')}</p>")

    lines.append("</body></html>")
    return "".join(lines)


def render_resume_pdf(resume: StructuredResume) -> RenderedResumePdf:
    """Render StructuredResume to PDF bytes using a fixed template (PyMuPDF)."""
    html = render_resume_html(resume)
    # Build a simple multi-page text PDF from the structured fields (deterministic).
    # HTML is retained as the canonical layout description for audit/diffing.
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # US Letter
    y = 50.0
    left = 50.0
    width = 512.0
    fontsize = 10.5

    def writeln(text: str, *, size: float = fontsize, bold: bool = False) -> None:
        nonlocal y, page
        if y > 740:
            page = doc.new_page(width=612, height=792)
            y = 50.0
        font = "helv"
        # PyMuPDF insert_textbox handles wrapping.
        rect = fitz.Rect(left, y, left + width, y + 200)
        used = page.insert_textbox(
            rect,
            text,
            fontsize=size,
            fontname=font,
            align=fitz.TEXT_ALIGN_LEFT,
        )
        # used is unused height remaining; approximate consumed height
        consumed = 200 - used if used >= 0 else size + 4
        y += max(consumed, size + 4) + (2 if not bold else 4)

    name = resume.contact.full_name or "Candidate"
    writeln(name, size=16, bold=True)
    meta_bits = [
        resume.contact.email,
        resume.contact.phone,
        resume.contact.location,
        resume.contact.linkedin_url,
    ]
    meta = " · ".join(m for m in meta_bits if m)
    if meta:
        writeln(meta, size=9)
    y += 6

    if resume.summary:
        writeln("SUMMARY", size=11, bold=True)
        writeln(resume.summary)

    if resume.skills:
        writeln("SKILLS", size=11, bold=True)
        writeln(", ".join(resume.skills))

    if resume.experience:
        writeln("EXPERIENCE", size=11, bold=True)
        for exp in resume.experience:
            header_parts = [p for p in (exp.title, exp.company) if p]
            dates = " – ".join(
                d
                for d in (
                    exp.start_date,
                    exp.end_date or ("Present" if exp.is_current else None),
                )
                if d
            )
            header = " — ".join(header_parts)
            if dates:
                header = f"{header} ({dates})" if header else dates
            writeln(header or "Role", size=10.5, bold=True)
            for bullet in exp.bullets:
                writeln(f"• {bullet}")

    if resume.projects:
        writeln("PROJECTS", size=11, bold=True)
        for project in resume.projects:
            writeln(project.name or "Project", size=10.5, bold=True)
            if project.description:
                writeln(project.description)
            for bullet in project.bullets:
                writeln(f"• {bullet}")

    if resume.education:
        writeln("EDUCATION", size=11, bold=True)
        for edu in resume.education:
            bits = [b for b in (edu.degree, edu.field_of_study, edu.institution) if b]
            writeln(" · ".join(bits))

    if resume.certifications:
        writeln("CERTIFICATIONS", size=11, bold=True)
        for cert in resume.certifications:
            if cert.name:
                writeln(cert.name)

    # Embed template version + HTML hash in PDF metadata for auditability.
    html_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    doc.set_metadata(
        {
            "producer": f"career-agent/{TEMPLATE_VERSION}",
            "title": name,
            "subject": f"template={TEMPLATE_VERSION};html_sha256={html_hash}",
        }
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    return RenderedResumePdf(
        pdf_bytes=pdf_bytes,
        content_hash=content_hash,
        template_version=TEMPLATE_VERSION,
    )


class ResumePdfService:
    """Render validated ResumeVersion content and upload via StorageProvider."""

    def __init__(
        self,
        storage: StorageProvider,
        *,
        bucket: str = DEFAULT_BUCKET,
    ) -> None:
        self._storage = storage
        self._bucket = bucket

    def render_and_upload(
        self,
        resume: StructuredResume,
        *,
        user_id: uuid.UUID,
        resume_version_id: uuid.UUID,
    ) -> RenderedResumePdf:
        rendered = render_resume_pdf(resume)
        key = f"{user_id}/resume-versions/{resume_version_id}/{TEMPLATE_VERSION}.pdf"
        self._storage.put_object(
            StoragePutRequest(
                bucket=self._bucket,
                key=key,
                data=rendered.pdf_bytes,
                content_type="application/pdf",
            )
        )
        return RenderedResumePdf(
            pdf_bytes=rendered.pdf_bytes,
            content_hash=rendered.content_hash,
            template_version=rendered.template_version,
            storage_path=key,
            bucket=self._bucket,
        )


def _esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
