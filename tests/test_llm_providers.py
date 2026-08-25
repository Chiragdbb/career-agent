"""STEP 13 — Groq/Gemini adapters + LLMTaskService (mocked)."""

from __future__ import annotations

import json

import pytest

from packages.domain.exceptions import DomainError
from packages.domain.llm_tasks import LLMTaskService
from packages.providers.exceptions import ProviderNotConfiguredError
from packages.providers.llm import MockLLMProvider
from packages.providers.llm_adapters import GeminiLLMProvider, GroqLLMProvider, parse_llm_json


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.headers = {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_groq_and_gemini_require_keys() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        GroqLLMProvider(api_key="")
    with pytest.raises(ProviderNotConfiguredError):
        GeminiLLMProvider(api_key="")


def test_groq_complete_parses_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(**kwargs):
        assert "groq.com" in kwargs["url"]
        return _FakeResponse(
            200,
            {
                "model": "llama-3.3-70b-versatile",
                "choices": [
                    {"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            },
        )

    monkeypatch.setattr(
        "packages.providers.llm_adapters.request_with_retries",
        fake_request,
    )
    provider = GroqLLMProvider(api_key="gsk-test")
    from packages.providers.llm import LLMMessage, LLMRequest

    response = provider.complete(
        LLMRequest(messages=[LLMMessage(role="user", content="hi")], response_format="json")
    )
    assert response.content == '{"ok": true}'
    assert response.usage.units == 18.0
    assert response.usage.extra["prompt_tokens"] == 11


def test_gemini_complete_parses_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(**kwargs):
        assert "generativelanguage.googleapis.com" in kwargs["url"]
        return _FakeResponse(
            200,
            {
                "candidates": [
                    {"content": {"parts": [{"text": '{"hello":"world"}'}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 3},
            },
        )

    monkeypatch.setattr(
        "packages.providers.llm_adapters.request_with_retries",
        fake_request,
    )
    provider = GeminiLLMProvider(api_key="gem-test")
    from packages.providers.llm import LLMMessage, LLMRequest

    response = provider.complete(
        LLMRequest(messages=[LLMMessage(role="user", content="hi")], response_format="json")
    )
    assert '"hello"' in response.content
    assert response.usage.units == 8.0


def test_parse_llm_json_strips_fences() -> None:
    assert parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_llm_task_extract_job_validates() -> None:
    payload = {
        "title": "Backend Engineer",
        "company_name": "Acme",
        "location": "Remote",
        "work_arrangement": "remote",
        "salary_min": 140000,
        "salary_max": 180000,
        "skills": ["Python", "Postgres"],
        "url": "https://example.com/jobs/1",
        "description": "Build APIs",
    }
    llm = MockLLMProvider(content=json.dumps(payload))
    job = LLMTaskService(llm).extract_job(url="https://example.com/jobs/1", scraped_markdown="# Job")
    assert job.title == "Backend Engineer"
    assert job.company_name == "Acme"
    assert job.salary_min == 140000


def test_llm_task_rejects_malformed_output() -> None:
    llm = MockLLMProvider(content="not-json")
    with pytest.raises(DomainError):
        LLMTaskService(llm).extract_job(url="https://example.com/x", scraped_markdown="x")


def test_llm_task_rejects_invalid_schema() -> None:
    llm = MockLLMProvider(content=json.dumps({"title": "", "url": "https://x"}))
    with pytest.raises(DomainError):
        LLMTaskService(llm).extract_job(url="https://x", scraped_markdown="x")


def test_tailor_resume_and_cover_letter_validate() -> None:
    llm = MockLLMProvider(
        content=json.dumps(
            {
                "summary": "Emphasize APIs",
                "emphasis_bullets": ["Payment APIs"],
                "warnings": [],
                "subject": "Application",
                "body": "I am interested.",
            }
        )
    )
    # Separate calls with dedicated payloads.
    tailor_llm = MockLLMProvider(
        content=json.dumps(
            {"summary": "Emphasize APIs", "emphasis_bullets": ["Payment APIs"], "warnings": []}
        )
    )
    cover_llm = MockLLMProvider(
        content=json.dumps({"subject": "Hello", "body": "Letter body", "warnings": []})
    )
    resume = {"contact": {"full_name": "Alex"}, "experience": [], "skills": ["Python"]}
    job = {"title": "Backend Engineer"}
    tailored = LLMTaskService(tailor_llm).tailor_resume(structured_resume=resume, job=job)
    assert tailored.summary == "Emphasize APIs"
    cover = LLMTaskService(cover_llm).generate_cover_letter(structured_resume=resume, job=job)
    assert "Letter" in cover.body
