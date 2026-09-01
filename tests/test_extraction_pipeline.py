"""Tests for extraction pipeline fixes: truncation, retry, pre-filter, error logging."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from packages.domain.content_truncation import truncate_for_extraction
from packages.domain.discovery_logger import DiscoveryFileLogger
from packages.domain.exceptions import DomainError
from packages.domain.extraction_constants import (
    EXTRACTION_CONTENT_MAX_CHARS,
    EXTRACTION_CONTENT_PREFILTER_MAX_CHARS,
    EXTRACTION_CONTENT_RETRY_MAX_CHARS,
)
from packages.domain.job_discovery import JobDiscoveryService
from packages.domain.llm_tasks import LLMTaskService, _is_retriable_extraction_error
from packages.providers.exceptions import (
    ProviderError,
    ProviderRateLimitError,
    ProviderStructuredOutputError,
)
from packages.providers.http_utils import parse_error_response_body
from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.llm import LLMMessage, LLMProvider, LLMRequest, LLMResponse
from packages.providers.llm_adapters import OpenAILLMProvider


def test_truncate_for_extraction_keeps_prefix() -> None:
    content = "A" * 100
    result = truncate_for_extraction(content, 50)
    assert len(result) == 50
    assert result.endswith("[... content truncated for extraction ...]")
    assert result.startswith("A")


def test_truncate_for_extraction_noop_when_short() -> None:
    content = "short content"
    assert truncate_for_extraction(content, EXTRACTION_CONTENT_MAX_CHARS) == content


def test_prefilter_constants() -> None:
    assert EXTRACTION_CONTENT_RETRY_MAX_CHARS == EXTRACTION_CONTENT_MAX_CHARS // 2
    assert EXTRACTION_CONTENT_PREFILTER_MAX_CHARS > EXTRACTION_CONTENT_MAX_CHARS


def test_parse_error_response_body_extracts_failed_generation() -> None:
    body = json.dumps(
        {
            "error": {
                "message": "Failed to validate JSON",
                "code": "json_validate_failed",
                "failed_generation": '{"title": "bad"}',
            }
        }
    )
    details = parse_error_response_body(body)
    assert details["error_code"] == "json_validate_failed"
    assert details["failed_generation"] == '{"title": "bad"}'


def test_is_retriable_extraction_error() -> None:
    assert _is_retriable_extraction_error(
        ProviderStructuredOutputError("x", details={"error_code": "json_validate_failed"})
    )
    assert _is_retriable_extraction_error(
        ProviderRateLimitError("too large", details={"status_code": 413})
    )
    assert not _is_retriable_extraction_error(ProviderError("other"))


class _RecordingLLM(LLMProvider):
    def __init__(self, responses: list[str | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[LLMRequest] = []

    @property
    def metadata(self):
        return ProviderMetadata(name="recording-llm", vendor="mock", capabilities=frozenset())

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(
            content=item,
            model="test",
            usage=UsageInfo(operation="complete", unit_type="tokens", units=1.0, provider="recording-llm"),
        )


def test_extract_job_retries_with_shrunk_content_on_schema_failure() -> None:
    payload = {
        "title": "Engineer",
        "company_name": "Acme",
        "location": None,
        "work_arrangement": None,
        "employment_type": None,
        "seniority": None,
        "salary_min": None,
        "salary_max": None,
        "currency": None,
        "description": "Build things",
        "skills": [],
        "url": "https://example.com/job",
        "external_id": None,
        "posted_at": None,
    }
    llm = _RecordingLLM(
        [
            ProviderStructuredOutputError(
                "bad",
                provider="openai-llm",
                details={"error_code": "json_validate_failed", "failed_generation": "partial"},
            ),
            json.dumps(payload),
        ]
    )
    long_markdown = "x" * (EXTRACTION_CONTENT_MAX_CHARS + 1000)
    job = LLMTaskService(llm).extract_job(url="https://example.com/job", scraped_markdown=long_markdown)
    assert job.title == "Engineer"
    assert len(llm.calls) == 2
    first_user = llm.calls[0].messages[1].content
    second_user = llm.calls[1].messages[1].content
    assert len(first_user) > len(second_user)
    assert llm.calls[0].json_schema is not None
    assert llm.calls[0].json_schema_name == "extracted_job"


def test_extract_job_logs_schema_failure_to_discovery_log(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "discovery.log"
    monkeypatch.setenv("DISCOVERY_LOG_FILE", str(log_file))
    discovery_log = DiscoveryFileLogger(uuid.uuid4())
    exc = ProviderStructuredOutputError(
        "bad",
        provider="groq-llm",
        details={
            "error_code": "json_validate_failed",
            "failed_generation": '{"title":"x"}',
            "raw_body": '{"error":{"code":"json_validate_failed"}}',
        },
    )
    llm = _RecordingLLM([exc, exc])
    service = LLMTaskService(llm, discovery_log=discovery_log)
    with pytest.raises(DomainError):
        service.extract_job(url="https://example.com/job", scraped_markdown="# Job")
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(line) for line in lines]
    schema_events = [r for r in records if r["event"] == "extract_schema_failed"]
    assert len(schema_events) >= 1
    assert schema_events[0]["failed_generation"] == '{"title":"x"}'


def test_openai_adapter_sends_json_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_request(**kwargs):
        captured.update(kwargs.get("json") or {})
        return MagicMock(
            status_code=200,
            text='{"choices":[{"message":{"content":"{\\"ok\\":true}"},"finish_reason":"stop"}],"usage":{"prompt_tokens":1,"completion_tokens":1}}',
            json=lambda: json.loads(
                '{"choices":[{"message":{"content":"{\\"ok\\":true}"},"finish_reason":"stop"}],"usage":{"prompt_tokens":1,"completion_tokens":1}}'
            ),
        )

    monkeypatch.setattr("packages.providers.llm_adapters.request_with_retries", fake_request)
    provider = OpenAILLMProvider(api_key="sk-test")
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    provider.complete(
        LLMRequest(
            messages=[LLMMessage(role="user", content="hi")],
            json_schema=schema,
            json_schema_name="test_schema",
        )
    )
    response_format = captured["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "test_schema"
    assert response_format["json_schema"]["schema"] == schema


def test_job_discovery_skips_oversized_scraped_content() -> None:
    from app.database import get_session_factory
    from database.models.enums import UserStatus
    from database.models.schema import JobMatch, User, WorkflowRun, WorkflowTask
    from packages.providers.llm import MockLLMProvider
    from packages.providers.scraper import MockScraperProvider, ScrapedPage
    from packages.providers.search import MockSearchProvider, SearchHit

    session = get_session_factory()()
    user = User(id=uuid.uuid4(), auth_subject=f"huge-{uuid.uuid4()}", status=UserStatus.active)
    session.add(user)
    session.commit()
    try:
        url = f"https://jobs.example.com/huge-{uuid.uuid4()}"
        huge = "x" * (EXTRACTION_CONTENT_PREFILTER_MAX_CHARS + 1)
        search = MockSearchProvider(
            results=[SearchHit(title="Huge", url=url, snippet="snippet", score=1.0)]
        )
        scraper = MockScraperProvider(
            pages=[ScrapedPage(url=url, title="Huge", markdown=huge)]
        )
        llm = MockLLMProvider()
        service = JobDiscoveryService(
            session, user.id, search=search, scraper=scraper, llm=llm, max_results=1
        )
        result = service.run()
        assert result.skipped_invalid == 1
        assert not result.created_jobs
        assert any("too large" in err for err in result.errors)
    finally:
        session.query(WorkflowTask).filter(WorkflowTask.user_id == user.id).delete()
        session.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).delete()
        session.query(JobMatch).filter(JobMatch.user_id == user.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()
