"""Versioned LLM prompt templates.

Prompt text lives here; domain services load specs and record prompt versions
with every generation for auditability.
"""

from packages.prompts.application_content import (
    PROMPT_REGISTRY,
    ContentGenerationRecord,
    ContentPromptKind,
    PromptSpec,
    get_prompt,
)

__all__ = [
    "PROMPT_REGISTRY",
    "ContentGenerationRecord",
    "ContentPromptKind",
    "PromptSpec",
    "get_prompt",
]
