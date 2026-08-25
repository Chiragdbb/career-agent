"""Resume upload, extraction, structured parsing, and tenant-scoped access."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models.enums import DocumentStatus, ResumeStatus, ResumeVersionStatus
from database.models.schema import Document, Resume, ResumeVersion
from packages.domain.exceptions import DomainError, NotFoundError
from packages.domain.resume_extract import detect_mime_type, extract_text
from packages.domain.resume_models import (
    PARSER_VERSION,
    ResumeDetail,
    ResumeDocumentInfo,
    ResumeSummary,
    ResumeVersionInfo,
    StructuredResume,
)
from packages.domain.resume_parse import parse_structured_resume
from packages.providers.exceptions import ProviderError
from packages.providers.storage import (
    StorageProvider,
    StoragePutRequest,
    StorageSignedUrlRequest,
)

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._\-]+")


@dataclass(frozen=True)
class ResumeUploadInput:
    filename: str
    data: bytes
    content_type: str | None = None
    name: str | None = None
    description: str | None = None


class ResumeService:
    """Manage resume documents for a single tenant (user)."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        storage: StorageProvider,
        *,
        bucket: str,
    ) -> None:
        if not bucket or not bucket.strip():
            raise DomainError("Storage bucket is not configured")
        self._session = session
        self._user_id = user_id
        self._storage = storage
        self._bucket = bucket.strip()

    def list_resumes(self) -> list[ResumeSummary]:
        rows = (
            self._session.query(Resume)
            .filter(Resume.user_id == self._user_id)
            .order_by(Resume.created_at.desc())
            .all()
        )
        return [self._to_summary(row) for row in rows]

    def get_resume(
        self,
        resume_id: uuid.UUID,
        *,
        include_signed_url: bool = False,
        expires_in_seconds: int = 3600,
    ) -> ResumeDetail:
        row = self._get_owned_resume(resume_id)
        return self._to_detail(
            row,
            include_signed_url=include_signed_url,
            expires_in_seconds=expires_in_seconds,
        )

    def upload(self, payload: ResumeUploadInput) -> ResumeDetail:
        if not payload.data:
            raise DomainError("Uploaded file is empty")
        if len(payload.data) > 10 * 1024 * 1024:
            raise DomainError("Resume file must be 10MB or smaller")

        mime_type = detect_mime_type(payload.filename, payload.content_type)
        plain_text = extract_text(payload.data, mime_type)
        structured = parse_structured_resume(plain_text)
        content_hash = hashlib.sha256(payload.data).hexdigest()

        resume_id = uuid.uuid4()
        version_id = uuid.uuid4()
        document_id = uuid.uuid4()
        safe_name = _safe_filename(payload.filename)
        storage_key = f"{self._user_id}/resumes/{resume_id}/{document_id}/{safe_name}"

        display_name = (payload.name or "").strip() or _default_resume_name(
            payload.filename, structured
        )

        resume = Resume(
            id=resume_id,
            user_id=self._user_id,
            status=ResumeStatus.active,
            name=display_name,
            description=(payload.description or "").strip() or None,
        )
        version = ResumeVersion(
            id=version_id,
            resume_id=resume_id,
            user_id=self._user_id,
            status=ResumeVersionStatus.finalized,
            content_hash=content_hash,
            plain_text=plain_text,
            sections=structured.model_dump(mode="json"),
            parser_version=PARSER_VERSION,
        )
        document = Document(
            id=document_id,
            user_id=self._user_id,
            status=DocumentStatus.final,
            filename=payload.filename,
            mime_type=mime_type,
            storage_path=storage_key,
            checksum=content_hash,
            resume_version_id=version_id,
        )

        self._session.add(resume)
        self._session.add(version)
        self._session.flush()
        self._session.add(document)

        try:
            self._storage.put_object(
                StoragePutRequest(
                    bucket=self._bucket,
                    key=storage_key,
                    data=payload.data,
                    content_type=mime_type,
                )
            )
            self._session.commit()
        except ProviderError:
            self._session.rollback()
            raise DomainError("Failed to store resume file") from None
        except Exception:
            self._session.rollback()
            raise

        self._session.refresh(resume)
        return self._to_detail(resume, include_signed_url=True)

    def _get_owned_resume(self, resume_id: uuid.UUID) -> Resume:
        row = (
            self._session.query(Resume)
            .filter(Resume.id == resume_id, Resume.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Resume not found")
        return row

    def _latest_version(self, resume_id: uuid.UUID) -> ResumeVersion | None:
        return (
            self._session.query(ResumeVersion)
            .filter(
                ResumeVersion.resume_id == resume_id,
                ResumeVersion.user_id == self._user_id,
            )
            .order_by(ResumeVersion.created_at.desc())
            .first()
        )

    def _document_for_version(self, version_id: uuid.UUID) -> Document | None:
        return (
            self._session.query(Document)
            .filter(
                Document.resume_version_id == version_id,
                Document.user_id == self._user_id,
            )
            .order_by(Document.created_at.desc())
            .first()
        )

    def _to_summary(self, row: Resume) -> ResumeSummary:
        version = self._latest_version(row.id)
        return ResumeSummary(
            id=row.id,
            name=row.name,
            status=_enum_value(row.status),
            description=row.description,
            created_at=row.created_at,
            updated_at=row.updated_at,
            latest_version_id=version.id if version else None,
            parser_version=version.parser_version if version else None,
        )

    def _to_detail(
        self,
        row: Resume,
        *,
        include_signed_url: bool,
        expires_in_seconds: int = 3600,
    ) -> ResumeDetail:
        version = self._latest_version(row.id)
        version_info: ResumeVersionInfo | None = None
        signed_url: str | None = None

        if version is not None:
            document = self._document_for_version(version.id)
            document_info = None
            if document is not None:
                document_info = ResumeDocumentInfo(
                    id=document.id,
                    filename=document.filename,
                    mime_type=document.mime_type,
                    storage_path=document.storage_path,
                    checksum=document.checksum,
                    status=_enum_value(document.status),
                )
                if include_signed_url and document.storage_path:
                    signed = self._storage.create_signed_url(
                        StorageSignedUrlRequest(
                            bucket=self._bucket,
                            key=document.storage_path,
                            expires_in_seconds=expires_in_seconds,
                        )
                    )
                    signed_url = str(signed.url)

            structured = None
            if version.sections:
                try:
                    structured = StructuredResume.model_validate(version.sections)
                except Exception:
                    structured = None

            version_info = ResumeVersionInfo(
                id=version.id,
                status=_enum_value(version.status),
                content_hash=version.content_hash,
                plain_text=version.plain_text,
                structured=structured,
                parser_version=version.parser_version,
                created_at=version.created_at,
                updated_at=version.updated_at,
                document=document_info,
            )

        return ResumeDetail(
            id=row.id,
            name=row.name,
            status=_enum_value(row.status),
            description=row.description,
            created_at=row.created_at,
            updated_at=row.updated_at,
            latest_version=version_info,
            signed_url=signed_url,
        )


def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _safe_filename(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = _SAFE_FILENAME_RE.sub("_", base).strip("._")
    return cleaned or "resume.bin"


def _default_resume_name(filename: str, structured: StructuredResume) -> str:
    if structured.contact.full_name:
        return f"{structured.contact.full_name} Resume"
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    return stem.strip() or "Uploaded Resume"
