"""JSON schema for structured job extraction (OpenAI strict mode compatible)."""

from __future__ import annotations

from typing import Any


def job_extraction_json_schema() -> dict[str, Any]:
    """Schema for LLM structured output when extracting a single job posting."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "description": "Job title"},
            "company_name": {
                "type": ["string", "null"],
                "description": "Hiring company name if stated",
            },
            "location": {"type": ["string", "null"]},
            "work_arrangement": {
                "type": ["string", "null"],
                "description": "remote, hybrid, or on_site when stated",
            },
            "employment_type": {"type": ["string", "null"]},
            "seniority": {"type": ["string", "null"]},
            "salary_min": {"type": ["integer", "null"]},
            "salary_max": {"type": ["integer", "null"]},
            "currency": {"type": ["string", "null"]},
            "description": {"type": ["string", "null"]},
            "skills": {
                "type": "array",
                "items": {"type": "string"},
            },
            "url": {"type": "string"},
            "external_id": {"type": ["string", "null"]},
            "posted_at": {"type": ["string", "null"]},
        },
        "required": [
            "title",
            "company_name",
            "location",
            "work_arrangement",
            "employment_type",
            "seniority",
            "salary_min",
            "salary_max",
            "currency",
            "description",
            "skills",
            "url",
            "external_id",
            "posted_at",
        ],
    }
