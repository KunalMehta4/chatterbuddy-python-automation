"""The Task domain object."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from ..errors import ValidationError
from ..utils import now


class Priority(StrEnum):
    """Task priority. ``StrEnum`` means the member serialises straight to JSON
    while still giving us a closed set of valid values."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class Task:
    """A to-do item, complete or otherwise."""

    id: int
    description: str
    created_at: datetime = field(default_factory=now)
    completed_at: datetime | None = None
    priority: Priority = Priority.NORMAL
    due_date: date | None = None

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None

    def is_overdue(self, *, today: date | None = None) -> bool:
        """Overdue means unfinished and past its due date.

        ``today`` is a parameter rather than a call to ``date.today()`` so the
        behaviour is testable without patching the clock.
        """
        if self.due_date is None or self.is_complete:
            return False
        return self.due_date < (today or date.today())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "completed_at": (
                self.completed_at.isoformat(timespec="seconds") if self.completed_at else None
            ),
            "priority": str(self.priority),
            "due_date": self.due_date.isoformat() if self.due_date else None,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Task:
        try:
            completed = raw.get("completed_at")
            due = raw.get("due_date")
            return cls(
                id=int(raw["id"]),
                description=str(raw["description"]),
                created_at=datetime.fromisoformat(raw["created_at"]),
                completed_at=datetime.fromisoformat(completed) if completed else None,
                priority=Priority(raw.get("priority", Priority.NORMAL)),
                due_date=date.fromisoformat(due) if due else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"Stored task record is not usable: {exc}") from exc
