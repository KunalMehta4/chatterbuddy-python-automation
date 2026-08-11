"""Contacts cover the validation-heavy path: two fields that must be well formed
and one uniqueness rule."""

from __future__ import annotations

from pathlib import Path

import pytest

from chatterbuddy.commands.contacts import (
    AddContactCommand,
    FindContactCommand,
    RemoveContactCommand,
    ShowContactsCommand,
)
from chatterbuddy.errors import NotFoundError, UsageError, ValidationError
from chatterbuddy.repositories import ContactRepository
from chatterbuddy.services.storage import JsonStore


def test_add_normalises_email_and_phone(contacts: ContactRepository) -> None:
    result = AddContactCommand(contacts).execute("John Smith John@Email.COM 416-555-1234")
    assert "john@email.com" in result.message
    assert "(416) 555-1234" in result.message

    stored = contacts.all()[0]
    assert stored.name == "John Smith"
    assert stored.email == "john@email.com"


def test_add_accepts_a_multi_word_name(contacts: ContactRepository) -> None:
    AddContactCommand(contacts).execute("Mary Anne Van Der Berg mary@example.com 4165551234")
    assert contacts.all()[0].name == "Mary Anne Van Der Berg"


def test_add_with_too_few_arguments_raises_usage_error(contacts: ContactRepository) -> None:
    with pytest.raises(UsageError):
        AddContactCommand(contacts).execute("John john@email.com")


def test_add_rejects_a_malformed_email(contacts: ContactRepository) -> None:
    with pytest.raises(ValidationError, match="email address"):
        AddContactCommand(contacts).execute("John not-an-email 4165551234")


def test_add_rejects_a_malformed_phone(contacts: ContactRepository) -> None:
    with pytest.raises(ValidationError, match="phone number"):
        AddContactCommand(contacts).execute("John john@email.com 12")


def test_duplicate_email_is_rejected_and_names_the_holder(contacts: ContactRepository) -> None:
    command = AddContactCommand(contacts)
    command.execute("John john@email.com 4165551234")
    with pytest.raises(ValidationError, match="John"):
        command.execute("Johnny JOHN@email.com 6475559999")
    assert len(contacts.all()) == 1


def test_emails_returns_a_set(contacts: ContactRepository) -> None:
    contacts.create("Jo", "jo@example.com", "4165551234")
    assert contacts.emails() == {"jo@example.com"}


def test_show_is_helpful_when_empty(contacts: ContactRepository) -> None:
    assert "No contacts yet" in ShowContactsCommand(contacts).execute("").message


def test_show_renders_a_table(contacts: ContactRepository) -> None:
    contacts.create("Jo", "jo@example.com", "4165551234")
    message = ShowContactsCommand(contacts).execute("").message
    assert "NAME" in message and "Jo" in message and "1 contact(s)" in message


def test_find_matches_case_insensitively_across_fields(contacts: ContactRepository) -> None:
    contacts.create("Jo Patel", "jo@example.com", "(416) 555-1234")
    command = FindContactCommand(contacts)
    assert "Jo Patel" in command.execute("PATEL").message
    assert "Jo Patel" in command.execute("EXAMPLE.COM").message
    assert "Jo Patel" in command.execute("555").message


def test_find_reports_no_matches(contacts: ContactRepository) -> None:
    contacts.create("Jo", "jo@example.com", "4165551234")
    assert "No contacts match" in FindContactCommand(contacts).execute("zzz").message


def test_remove_deletes_the_record(contacts: ContactRepository) -> None:
    contacts.create("Jo", "jo@example.com", "4165551234")
    RemoveContactCommand(contacts).execute("1")
    assert contacts.all() == []


def test_remove_unknown_id_raises_not_found(contacts: ContactRepository) -> None:
    with pytest.raises(NotFoundError, match="no contact with id 99"):
        RemoveContactCommand(contacts).execute("99")


def test_remove_with_non_numeric_id_raises_usage_error(contacts: ContactRepository) -> None:
    with pytest.raises(UsageError, match="not a number"):
        RemoveContactCommand(contacts).execute("abc")


def test_contacts_survive_a_restart(tmp_path: Path) -> None:
    """The whole point of the persistence layer, asserted directly: a second
    repository over the same file sees the first one's writes."""
    path = tmp_path / "contacts.json"
    first = ContactRepository(JsonStore(path))
    first.create("Jo", "jo@example.com", "4165551234")
    first.create("Ann", "ann@example.com", "4165559999")

    second = ContactRepository(JsonStore(path))
    assert [contact.name for contact in second.all()] == ["Jo", "Ann"]
    assert second.next_id() == 3


def test_unusable_records_are_skipped_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "contacts.json"
    path.write_text(
        '[{"id": 1, "name": "Jo", "email": "jo@example.com", "phone": "1", '
        '"created_at": "2026-01-01T09:00:00"}, {"id": 2, "name": "broken"}]',
        encoding="utf-8",
    )
    repository = ContactRepository(JsonStore(path))
    assert [contact.name for contact in repository.all()] == ["Jo"]
    assert repository.discarded == 1
