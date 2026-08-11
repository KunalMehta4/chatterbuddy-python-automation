"""Contact storage, plus the two rules that are specific to contacts:
emails are unique, and searching is case-insensitive."""

from __future__ import annotations

from ..errors import ValidationError
from ..models import Contact
from ..services.storage import JsonStore
from .base import JsonRepository


class ContactRepository(JsonRepository[Contact]):
    entity_name = "contact"

    def __init__(self, store: JsonStore) -> None:
        super().__init__(store, Contact)

    def create(self, name: str, email: str, phone: str) -> Contact:
        """Add a contact, rejecting an email that is already on file."""
        with self._lock:
            existing = self.find_by_email(email)
            if existing is not None:
                raise ValidationError(f"{existing.name} (id {existing.id}) already uses {email}.")
            return self.add(Contact(id=self.next_id(), name=name, email=email, phone=phone))

    def emails(self) -> set[str]:
        """The set of addresses in use.

        A set rather than a list because the only question ever asked of it is
        membership, which is O(1) here and O(n) otherwise.
        """
        return {contact.email for contact in self.all()}

    def find_by_email(self, email: str) -> Contact | None:
        target = email.strip().lower()
        for contact in self.all():
            if contact.email == target:
                return contact
        return None

    def search(self, term: str) -> list[Contact]:
        """Case-insensitive substring match across name, email, and phone."""
        needle = term.strip().lower()
        if not needle:
            return []
        return [
            contact
            for contact in self.all()
            if needle in contact.name.lower()
            or needle in contact.email
            or needle in contact.phone.lower()
        ]
