"""Parsing is where a CLI usually rots. These tests pin down the three things
that actually break: multi-word command names, argument casing, and what happens
when the user types something wrong."""

from __future__ import annotations

import pytest

from chatterbuddy.errors import UnknownCommandError, UsageError
from chatterbuddy.parser import CommandParser
from chatterbuddy.registry import CommandRegistry
from tests.test_registry import Fake


@pytest.fixture
def parser() -> CommandParser:
    registry = CommandRegistry()
    for command in (
        Fake("weather"),
        Fake("search"),
        Fake("show"),
        Fake("show contacts", aliases=("contacts",)),
        Fake("add contact"),
        Fake("add task"),
        Fake("complete task"),
        Fake("exit", aliases=("quit",)),
    ):
        registry.register(command)
    return CommandParser(registry)


def test_single_word_command(parser: CommandParser) -> None:
    parsed = parser.parse("weather Toronto")
    assert parsed.name == "weather"
    assert parsed.args == "Toronto"


def test_two_word_command(parser: CommandParser) -> None:
    parsed = parser.parse("add contact John john@email.com 4165551234")
    assert parsed.name == "add contact"
    assert parsed.args == "John john@email.com 4165551234"


def test_longest_prefix_wins_over_shorter_one(parser: CommandParser) -> None:
    """Both 'show' and 'show contacts' exist; the two-word name must win."""
    assert parser.parse("show contacts").name == "show contacts"
    assert parser.parse("show something else").name == "show"


def test_command_name_is_case_insensitive(parser: CommandParser) -> None:
    assert parser.parse("ADD Contact Jo a@b.co 4165551234").name == "add contact"


def test_argument_casing_is_preserved(parser: CommandParser) -> None:
    """'weather Toronto' and task descriptions both depend on this."""
    assert parser.parse("add task Call Dr Chen About X").args == "Call Dr Chen About X"


def test_extra_whitespace_is_collapsed(parser: CommandParser) -> None:
    parsed = parser.parse("   add    contact    Jo   a@b.co  4165551234  ")
    assert parsed.name == "add contact"
    assert parsed.args == "Jo a@b.co 4165551234"


def test_command_with_no_arguments(parser: CommandParser) -> None:
    parsed = parser.parse("exit")
    assert (parsed.name, parsed.args) == ("exit", "")


def test_alias_is_resolved_to_canonical_name(parser: CommandParser) -> None:
    assert parser.parse("quit").name == "exit"
    assert parser.parse("contacts").name == "show contacts"


def test_blank_input_raises_usage_error(parser: CommandParser) -> None:
    with pytest.raises(UsageError):
        parser.parse("   ")


def test_unknown_command_suggests_alternatives(parser: CommandParser) -> None:
    with pytest.raises(UnknownCommandError) as caught:
        parser.parse("shwo contacts")
    assert "show contacts" in str(caught.value)


def test_typo_after_a_valid_first_word_falls_through_to_it(parser: CommandParser) -> None:
    """This fixture registers a bare 'show', so 'show contancts' resolves to it
    with 'contancts' as the argument. The real application registers no bare
    'show', which is why a mistyped second word there reaches the suggestion
    path instead -- see test_app.py."""
    parsed = parser.parse("show contancts")
    assert (parsed.name, parsed.args) == ("show", "contancts")


def test_unknown_command_without_close_match_points_at_help(parser: CommandParser) -> None:
    with pytest.raises(UnknownCommandError) as caught:
        parser.parse("qqqqqq")
    assert "help" in str(caught.value)


def test_partial_multiword_command_is_unknown(parser: CommandParser) -> None:
    """'complete' alone is not a command, only 'complete task' is."""
    with pytest.raises(UnknownCommandError):
        parser.parse("complete 3")
