"""StructuredResume → Jinja2 HTML → PDF (WeasyPrint or PyMuPDF fallback)."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from packages.domain.resume_models import StructuredResume
from packages.providers.storage import StorageProvider, StoragePutRequest

TEMPLATE_VERSION = "html-resume-v1"
DEFAULT_BUCKET = "resumes"

_BUILTIN_TEMPLATES = {
    "classic": Path(__file__).parent / "templates" / "classic.html.j2",
    "modern": Path(__file__).parent / "templates" / "modern.html.j2",
    "compact": Path(__file__).parent / "templates" / "compact.html.j2",
}


@dataclass(frozen=True)
class RenderedHtmlResume:
    html: str
    pdf_bytes: bytes
    content_hash: str
    template_id: str
    render_engine: str
    storage_html_path: str | None = None
    storage_pdf_path: str | None = None


class HtmlResumeRenderer:
    def __init__(
        self,
        *,
        template_id: str = "classic",
        storage: StorageProvider | None = None,
        bucket: str = DEFAULT_BUCKET,
    ) -> None:
        if template_id not in _BUILTIN_TEMPLATES:
            template_id = "classic"
        self._template_id = template_id
        self._storage = storage
        self._bucket = bucket

    def render(
        self,
        resume: StructuredResume,
        *,
        user_id: uuid.UUID,
        resume_version_id: uuid.UUID,
    ) -> RenderedHtmlResume:
        html = self._render_html(resume)
        pdf_bytes, engine = self._html_to_pdf(html)
        content_hash = hashlib.sha256(pdf_bytes).hexdigest()
        html_path: str | None = None
        pdf_path: str | None = None
        if self._storage is not None:
            base = f"users/{user_id}/resume_versions/{resume_version_id}"
            html_path = f"{base}/resume.html"
            pdf_path = f"{base}/resume.pdf"
            self._storage.put(
                StoragePutRequest(
                    bucket=self._bucket,
                    path=html_path,
                    content=html.encode("utf-8"),
                    content_type="text/html",
                )
            )
            self._storage.put(
                StoragePutRequest(
                    bucket=self._bucket,
                    path=pdf_path,
                    content=pdf_bytes,
                    content_type="application/pdf",
                )
            )
        return RenderedHtmlResume(
            html=html,
            pdf_bytes=pdf_bytes,
            content_hash=content_hash,
            template_id=self._template_id,
            render_engine=engine,
            storage_html_path=html_path,
            storage_pdf_path=pdf_path,
        )

    def _render_html(self, resume: StructuredResume) -> str:
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
        except ImportError as exc:
            raise RuntimeError("jinja2 is required for HtmlResumeRenderer") from exc

        template_dir = _BUILTIN_TEMPLATES[self._template_id].parent
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template(_BUILTIN_TEMPLATES[self._template_id].name)
        return template.render(resume=resume, template_version=TEMPLATE_VERSION)

    def _html_to_pdf(self, html: str) -> tuple[bytes, str]:
        try:
            from weasyprint import HTML

            pdf = HTML(string=html).write_pdf()
            return pdf, "weasyprint"
        except Exception:
            import fitz

            doc = fitz.open()
            page = doc.new_page(width=595, height=842)
            page.insert_htmlbox(page.rect, html)
            pdf = doc.tobytes()
            doc.close()
            return pdf, "pymupdf"
