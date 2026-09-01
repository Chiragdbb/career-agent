"""Load the repository root `.env` into os.environ for provider factories."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_LOADED = False


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from *start* (or cwd) until a `.env` or `pyproject.toml` is found."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        if (directory / ".env").is_file():
            return directory
        if (directory / "pyproject.toml").is_file():
            return directory
        if (directory / "requirements.txt").is_file() and (directory / "apps").is_dir():
            return directory
    return None


def load_project_env(*, override: bool = False) -> Path | None:
    """Load root `.env` once. Returns the project root path when found."""
    global _LOADED
    if _LOADED and not override:
        root = find_project_root()
        return root

    root = find_project_root()
    if root is None:
        return None

    env_file = root / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=override)

    _LOADED = True
    return root


def project_env_file() -> str:
    """Path to `.env` for pydantic-settings (falls back to cwd `.env`)."""
    root = find_project_root()
    if root is not None:
        candidate = root / ".env"
        if candidate.is_file():
            return str(candidate)
    return ".env"


def env_flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes")
