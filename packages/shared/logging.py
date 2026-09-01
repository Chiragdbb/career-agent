"""Shared logging configuration for API and workers."""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging so application loggers appear in the terminal."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    if logging.getLogger().handlers:
        logging.getLogger().setLevel(log_level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(levelname)s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(handler)

    # Keep third-party noise down unless debugging.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
