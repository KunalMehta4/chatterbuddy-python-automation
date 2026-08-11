"""The Alarm domain object."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from ..errors import ValidationError


@dataclass
class Alarm:
    """A daily recurring reminder.

    ``last_triggered`` records the date the alarm most recently fired, which is
    what lets the scheduler show useful history and lets a restarted process
    avoid re-firing something the user already saw.
    """

    id: int
    at: time
    message: str
    active: bool = True
    last_triggered: date | None = None

    def occurrence_on(self, day: date) -> datetime:
        """The exact moment this alarm is due on a given day."""
        return datetime.combine(day, self.at)

    @property
    def label(self) -> str:
        return self.at.strftime("%H:%M")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "at": self.at.strftime("%H:%M"),
            "message": self.message,
            "active": self.active,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Alarm:
        try:
            triggered = raw.get("last_triggered")
            return cls(
                id=int(raw["id"]),
                at=datetime.strptime(str(raw["at"]), "%H:%M").time(),
                message=str(raw["message"]),
                active=bool(raw.get("active", True)),
                last_triggered=date.fromisoformat(triggered) if triggered else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"Stored alarm record is not usable: {exc}") from exc
