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


def aggregator_listing_card_schema() -> dict[str, Any]:
    """One visible job card on an aggregator listing page (summary fields only)."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "company_name": {"type": ["string", "null"]},
            "location": {"type": ["string", "null"]},
            "snippet": {"type": ["string", "null"]},
            "posted_at": {"type": ["string", "null"]},
            "aggregator_job_id": {
                "type": ["string", "null"],
                "description": "Job id from card URL query/path when visible",
            },
            "card_url": {
                "type": ["string", "null"],
                "description": "Href on the card if present; do not invent LinkedIn view URLs",
            },
        },
        "required": [
            "title",
            "company_name",
            "location",
            "snippet",
            "posted_at",
            "aggregator_job_id",
            "card_url",
        ],
    }


def job_listings_extraction_json_schema() -> dict[str, Any]:
    """Schema for extracting multiple job cards from an aggregator listing page."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "cards": {
                "type": "array",
                "items": aggregator_listing_card_schema(),
                "description": "Distinct job cards on the listing page.",
            },
        },
        "required": ["cards"],
    }
