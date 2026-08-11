"""Small, dependency-free helpers shared across the application."""

from __future__ import annotations

from datetime import datetime


def now() -> datetime:
    """Current local time, truncated to whole seconds.

    Every timestamp in the application is created here. The stored ISO format
    keeps only whole seconds, so generating microsecond-precision timestamps
    would mean a record no longer compares equal to itself after a save/load
    round-trip -- a subtle bug that is much easier to prevent than to find.
    """
    return datetime.now().replace(microsecond=0)


__all__ = ["now"]
