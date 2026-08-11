"""The Contact domain object."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..errors import ValidationError
from ..utils import now


@dataclass
class Contact:
    """A single address-book entry.

    ``to_dict``/``from_dict`` keep serialisation next to the data it describes,
    so the repository layer never needs to know which fields exist.
    """

    id: int
    name: str
    email: str
    phone: str
    created_at: datetime = field(default_factory=now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Contact:
        try:
            return cls(
                id=int(raw["id"]),
                name=str(raw["name"]),
                email=str(raw["email"]),
                phone=str(raw["phone"]),
                created_at=datetime.fromisoformat(raw["created_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"Stored contact record is not usable: {exc}") from exc
