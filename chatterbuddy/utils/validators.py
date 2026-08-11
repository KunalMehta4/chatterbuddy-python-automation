"""Input validation and normalisation.

These functions are deliberately pure: text in, clean value or ``ValidationError``
out. Keeping them free of I/O means the command handlers can stay thin and the
tests can cover every edge case in microseconds.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from ..errors import ValidationError

# Deliberately permissive. Fully validating an address per RFC 5322 takes a
# parser, and even a perfect regex cannot tell you whether mail is deliverable.
# This catches the mistakes people actually make (missing @, missing domain,
# stray whitespace) and gets out of the way.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

_TIME_FORMATS = ("%H:%M", "%I:%M%p", "%I%p", "%H%M")

_NON_DIGITS = re.compile(r"[^0-9]")


def normalize_email(value: str) -> str:
    """Return a lowercased, trimmed address or raise ``ValidationError``."""
    cleaned = value.strip().lower()
    if not _EMAIL_PATTERN.match(cleaned):
        raise ValidationError(
            f"{value!r} does not look like an email address "
            "(expected something like name@example.com)."
        )
    return cleaned


def normalize_phone(value: str) -> str:
    """Normalise a phone number, formatting North American numbers nicely.

    Anything between 7 and 15 digits is accepted so international numbers are
    not rejected; only the 10 and 11 digit cases get cosmetic formatting.
    """
    digits = _NON_DIGITS.sub("", value)
    if len(digits) == 11 and digits.startswith("1"):
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if 7 <= len(digits) <= 15:
        return f"+{digits}"
    raise ValidationError(f"{value!r} does not look like a phone number (expected 7 to 15 digits).")


def parse_time(value: str) -> time:
    """Parse a clock time, accepting ``18:30``, ``6:30pm``, ``6pm`` and ``1830``."""
    candidate = value.strip().lower().replace(" ", "")
    if not candidate:
        raise ValidationError("A time is required, for example 18:30 or 6:30pm.")
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).time()
        except ValueError:
            continue
    raise ValidationError(f"{value!r} is not a time I understand. Try 18:30, 6:30pm, or 6pm.")


def parse_date(value: str, *, today: date | None = None) -> date:
    """Parse ``YYYY-MM-DD``, ``today``, or ``tomorrow``.

    ``today`` is injectable so date-relative parsing is testable without
    freezing the system clock.
    """
    reference = today or date.today()
    candidate = value.strip().lower()
    if candidate == "today":
        return reference
    if candidate == "tomorrow":
        return reference + timedelta(days=1)
    try:
        return date.fromisoformat(candidate)
    except ValueError as exc:
        raise ValidationError(
            f"{value!r} is not a date I understand. Try 2026-08-20, today, or tomorrow."
        ) from exc


def require_text(value: str, *, field: str, max_length: int = 200) -> str:
    """Collapse whitespace and enforce a non-empty, bounded string."""
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValidationError(f"{field} cannot be empty.")
    if len(cleaned) > max_length:
        raise ValidationError(f"{field} must be {max_length} characters or fewer.")
    return cleaned
