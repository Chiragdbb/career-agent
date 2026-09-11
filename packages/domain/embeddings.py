"""Background + on-demand embedding generation and similarity search."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.models.schema import (
    EMBEDDING_DIMENSIONS,
    CompanyResearch,
    Job,
    ResumeVersion,
    UserProfile,
)
from packages.domain.exceptions import NotFoundError
from packages.domain.skill_match import cosine_similarity
from packages.providers.embedding import (
    EMBEDDING_CONTENT_VERSION,
    EmbeddingProvider,
    EmbeddingRequest,
)

EntityKind = Literal["job", "profile", "company_research", "resume_version"]


@dataclass(frozen=True)
class SimilarHit:
    entity_id: uuid.UUID
    score: float
    entity_kind: EntityKind


class EmbeddingService:
    """Generate and store embeddings; run similarity search via pgvector."""

    def __init__(
        self,
        session: Session,
        embedding: EmbeddingProvider,
        *,
        dimensions: int = EMBEDDING_DIMENSIONS,
        content_version: str = EMBEDDING_CONTENT_VERSION,
    ) -> None:
        self._session = session
        self._embedding = embedding
        self._dimensions = dimensions
        self._content_version = content_version

    def embed_job(self, job_id: uuid.UUID) -> Job:
        job = self._session.query(Job).filter(Job.id == job_id).one_or_none()
        if job is None:
            raise NotFoundError("Job not found")
        text_blob = self._job_text(job)
        self._apply_embedding(job, text_blob)
        self._session.commit()
        self._session.refresh(job)
        return job

    def embed_profile(self, user_id: uuid.UUID) -> UserProfile:
        profile = (
            self._session.query(UserProfile)
            .filter(UserProfile.user_id == user_id)
            .one_or_none()
        )
        if profile is None:
            raise NotFoundError("Profile not found")
        text_blob = "\n".join(
            part
            for part in (
                profile.display_name,
                profile.headline,
                profile.location,
                profile.summary,
            )
            if part
        )
        self._apply_embedding(profile, text_blob or "empty profile")
        self._session.commit()
        self._session.refresh(profile)
        return profile

    def embed_company_research(self, research_id: uuid.UUID) -> CompanyResearch:
        row = (
            self._session.query(CompanyResearch)
            .filter(CompanyResearch.id == research_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Company research not found")
        data = row.data if isinstance(row.data, dict) else {}
        text_blob = "\n".join(
            part
            for part in (
                row.summary,
                str(data.get("industry") or ""),
                str(data.get("overview") or ""),
            )
            if part
        )
        self._apply_embedding(row, text_blob or "empty research")
        self._session.commit()
        self._session.refresh(row)
        return row

    def embed_resume_version(self, version_id: uuid.UUID) -> ResumeVersion:
        row = (
            self._session.query(ResumeVersion)
            .filter(ResumeVersion.id == version_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Resume version not found")
        sections = row.sections if isinstance(row.sections, dict) else {}
        section_texts: dict[str, str] = {}
        for key in ("summary", "experience", "skills", "education"):
            value = sections.get(key)
            if isinstance(value, str) and value.strip():
                section_texts[key] = value.strip()
            elif isinstance(value, list):
                joined = " ".join(str(v) for v in value if v)
                if joined.strip():
                    section_texts[key] = joined.strip()
        full_text = row.plain_text or "\n".join(section_texts.values()) or "empty resume"
        response = self._embedding.embed(
            EmbeddingRequest(
                texts=[full_text] + list(section_texts.values()),
                dimensions=self._dimensions,
            )
        )
        now = datetime.now(timezone.utc)
        row.embedding = response.embeddings[0]
        row.embedding_model = response.model
        row.embedding_version = self._content_version
        row.embedding_generated_at = now
        section_payload: dict[str, Any] = {}
        for idx, name in enumerate(section_texts.keys()):
            section_payload[name] = {
                "embedding": response.embeddings[idx + 1],
                "model": response.model,
                "version": self._content_version,
                "generated_at": now.isoformat(),
            }
        row.section_embeddings = section_payload or None
        self._session.commit()
        self._session.refresh(row)
        return row

    def similarity_search_jobs(
        self,
        *,
        query_text: str | None = None,
        query_embedding: list[float] | None = None,
        user_id: uuid.UUID | None = None,
        limit: int = 20,
    ) -> list[SimilarHit]:
        vector = query_embedding
        if vector is None:
            if not query_text:
                return []
            response = self._embedding.embed(
                EmbeddingRequest(texts=[query_text], dimensions=self._dimensions)
            )
            vector = response.embeddings[0]
        # Prefer pgvector operator when available; fall back to Python cosine.
        try:
            return self._pgvector_job_search(vector, user_id=user_id, limit=limit)
        except Exception:
            return self._python_job_search(vector, user_id=user_id, limit=limit)

    def similarity_against_profile(
        self,
        job: Job,
        profile: UserProfile | None,
        *,
        resume_version: ResumeVersion | None = None,
    ) -> float:
        """Semantic similarity in [0, 1] combining profile and resume signals."""
        job_vec = list(job.embedding) if job.embedding is not None else None
        if job_vec is None:
            return 0.5  # neutral when embeddings missing
        scores: list[float] = []
        if profile is not None and profile.embedding is not None:
            scores.append(max(0.0, min(1.0, cosine_similarity(job_vec, list(profile.embedding)))))
        if resume_version is not None and resume_version.embedding is not None:
            scores.append(
                max(0.0, min(1.0, cosine_similarity(job_vec, list(resume_version.embedding))))
            )
        if not scores:
            return 0.5
        return sum(scores) / len(scores)

    def _apply_embedding(self, row: Any, text_blob: str) -> None:
        response = self._embedding.embed(
            EmbeddingRequest(texts=[text_blob or ""], dimensions=self._dimensions)
        )
        row.embedding = response.embeddings[0]
        row.embedding_model = response.model
        row.embedding_version = self._content_version
        row.embedding_generated_at = datetime.now(timezone.utc)

    def _job_text(self, job: Job) -> str:
        details = job.details if isinstance(job.details, dict) else {}
        skills = details.get("skills") or []
        skill_text = ", ".join(str(s) for s in skills if s)
        return "\n".join(
            part
            for part in (
                job.title,
                job.description,
                str(details.get("location") or ""),
                str(details.get("seniority") or ""),
                skill_text,
            )
            if part
        )

    def _pgvector_job_search(
        self,
        vector: list[float],
        *,
        user_id: uuid.UUID | None,
        limit: int,
    ) -> list[SimilarHit]:
        # Cosine distance operator `<=>`; similarity = 1 - distance for normalized vectors.
        sql = text(
            """
            SELECT j.id AS entity_id,
                   (1 - (j.embedding <=> CAST(:vec AS vector))) AS score
            FROM jobs j
            WHERE j.embedding IS NOT NULL
              AND (
                :user_id IS NULL
                OR EXISTS (
                    SELECT 1 FROM job_matches jm
                    WHERE jm.job_id = j.id AND jm.user_id = CAST(:user_id AS uuid)
                )
              )
            ORDER BY j.embedding <=> CAST(:vec AS vector)
            LIMIT :limit
            """
        )
        vec_literal = "[" + ",".join(str(float(x)) for x in vector) + "]"
        rows = self._session.execute(
            sql,
            {
                "vec": vec_literal,
                "user_id": str(user_id) if user_id else None,
                "limit": limit,
            },
        ).mappings()
        return [
            SimilarHit(
                entity_id=row["entity_id"],
                score=float(row["score"] or 0.0),
                entity_kind="job",
            )
            for row in rows
        ]

    def _python_job_search(
        self,
        vector: list[float],
        *,
        user_id: uuid.UUID | None,
        limit: int,
    ) -> list[SimilarHit]:
        query = self._session.query(Job).filter(Job.embedding.isnot(None))
        if user_id is not None:
            from database.models.schema import JobMatch

            query = query.join(JobMatch, JobMatch.job_id == Job.id).filter(
                JobMatch.user_id == user_id
            )
        hits: list[SimilarHit] = []
        for job in query.all():
            score = cosine_similarity(vector, list(job.embedding))
            hits.append(SimilarHit(entity_id=job.id, score=score, entity_kind="job"))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
