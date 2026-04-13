"""Logging utilities for last30days skill."""

import os
import sys
from datetime import datetime, timezone

DEBUG = os.environ.get("LAST30DAYS_DEBUG", "").lower() in ("1", "true", "yes")


def debug(msg: str) -> None:
    """Log debug message to stderr."""
    if DEBUG:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        sys.stderr.write(f"[{ts}] {msg}\n")
        sys.stderr.flush()


def source_log(source: str, msg: str) -> None:
    """Log source-specific message to stderr."""
    if DEBUG:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        sys.stderr.write(f"[{ts}] [{source}] {msg}\n")
        sys.stderr.flush()


def info(msg: str) -> None:
    """Log info message to stderr."""
    sys.stderr.write(f"[last30days] {msg}\n")
    sys.stderr.flush()


def warn(msg: str) -> None:
    """Log warning to stderr."""
    sys.stderr.write(f"[last30days] WARNING: {msg}\n")
    sys.stderr.flush()
