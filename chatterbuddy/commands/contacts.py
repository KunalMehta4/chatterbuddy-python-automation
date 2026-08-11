"""Contact commands: add, list, search, remove."""

from __future__ import annotations

from ..errors import UsageError
from ..repositories import ContactRepository
from ..utils.formatting import render_table
from ..utils.validators import normalize_email, normalize_phone, require_text
from .base import Command, CommandResult

CATEGORY = "Contacts"


class AddContactCommand(Command):
    name = "add contact"
    usage = "add contact <name> <email> <phone>"
    description = "Save a contact. The name may contain spaces."
    category = CATEGORY

    def __init__(self, repository: ContactRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        # Splitting from the right takes the last two tokens as email and phone,
        # which is what lets a multi-word name work without quoting.
        parts = self.require_args(args).rsplit(" ", 2)
        if len(parts) < 3:
            raise UsageError(f"Usage: {self.usage}")

        raw_name, raw_email, raw_phone = parts
        contact = self._repository.create(
            name=require_text(raw_name, field="Contact name", max_length=80),
            email=normalize_email(raw_email),
            phone=normalize_phone(raw_phone),
        )
        return CommandResult(
            f"Saved {contact.name} as contact {contact.id} ({contact.email}, {contact.phone})."
        )


class ShowContactsCommand(Command):
    name = "show contacts"
    usage = "show contacts"
    description = "List every saved contact."
    category = CATEGORY
    aliases = ("contacts",)

    def __init__(self, repository: ContactRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        contacts = self._repository.all()
        if not contacts:
            return CommandResult(
                "No contacts yet. Add one with: add contact <name> <email> <phone>"
            )
        rows = [(c.id, c.name, c.email, c.phone) for c in contacts]
        table = render_table(("ID", "NAME", "EMAIL", "PHONE"), rows)
        return CommandResult(f"{table}\n\n{len(contacts)} contact(s).")


class FindContactCommand(Command):
    name = "find contact"
    usage = "find contact <term>"
    description = "Search contacts by name, email, or phone."
    category = CATEGORY

    def __init__(self, repository: ContactRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        term = self.require_args(args)
        matches = self._repository.search(term)
        if not matches:
            return CommandResult(f"No contacts match {term!r}.")
        rows = [(c.id, c.name, c.email, c.phone) for c in matches]
        table = render_table(("ID", "NAME", "EMAIL", "PHONE"), rows)
        return CommandResult(f"{table}\n\n{len(matches)} match(es) for {term!r}.")


class RemoveContactCommand(Command):
    name = "remove contact"
    usage = "remove contact <id>"
    description = "Delete a contact by id."
    category = CATEGORY

    def __init__(self, repository: ContactRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        contact = self._repository.remove(self.require_id(args))
        return CommandResult(f"Removed contact {contact.id} ({contact.name}).")
