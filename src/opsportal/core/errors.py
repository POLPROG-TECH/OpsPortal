"""Structured logging configuration for OpsPortal."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "info") -> None:
    """Configure root and opsportal loggers with a consistent format."""
    numeric = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger("opsportal")
    root.setLevel(numeric)
    root.handlers.clear()
    root.addHandler(handler)
    root.propagate = False

    # Quieten noisy libraries
    for lib in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``opsportal`` namespace."""
    return logging.getLogger(f"opsportal.{name}")
