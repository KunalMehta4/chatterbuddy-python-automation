"""The registry is the dispatch table, so its guarantees matter: no silent
shadowing, working aliases, and an accurate longest-name width for the parser."""

from __future__ import annotations

import pytest

from chatterbuddy.commands.base import Command, CommandResult
from chatterbuddy.registry import CommandRegistry


class Fake(Command):
    def __init__(self, name: str, aliases: tuple[str, ...] = (), category: str = "General"):
        self.name = name
        self.aliases = aliases
        self.category = category
        self.usage = name
        self.description = f"does {name}"

    def execute(self, args: str) -> CommandResult:
        return CommandResult(f"{self.name}:{args}")


def test_registers_and_retrieves(registry: CommandRegistry) -> None:
    registry.register(Fake("weather"))
    assert registry.get("weather").execute("Toronto").message == "weather:Toronto"
    assert "weather" in registry
    assert len(registry) == 1


def test_lookup_is_case_insensitive(registry: CommandRegistry) -> None:
    registry.register(Fake("weather"))
    assert registry.resolve("WEATHER") == "weather"


def test_alias_resolves_to_canonical_name(registry: CommandRegistry) -> None:
    registry.register(Fake("exit", aliases=("quit", "bye")))
    assert registry.resolve("quit") == "exit"
    assert registry.resolve("bye") == "exit"


def test_duplicate_name_is_rejected(registry: CommandRegistry) -> None:
    registry.register(Fake("weather"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Fake("weather"))


def test_alias_colliding_with_existing_name_is_rejected(registry: CommandRegistry) -> None:
    registry.register(Fake("weather"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Fake("forecast", aliases=("weather",)))


def test_max_name_words_tracks_the_longest_registration(registry: CommandRegistry) -> None:
    registry.register(Fake("help"))
    assert registry.max_name_words == 1
    registry.register(Fake("add contact"))
    assert registry.max_name_words == 2
    registry.register(Fake("remove", aliases=("delete task record",)))
    assert registry.max_name_words == 3


def test_suggest_finds_close_matches(registry: CommandRegistry) -> None:
    registry.register(Fake("show contacts"))
    assert "show contacts" in registry.suggest("show contancts")


def test_suggest_returns_nothing_for_gibberish(registry: CommandRegistry) -> None:
    registry.register(Fake("weather"))
    assert registry.suggest("zzzzzzzz") == []


def test_grouped_buckets_by_category(registry: CommandRegistry) -> None:
    registry.register(Fake("show tasks", category="Tasks"))
    registry.register(Fake("add task", category="Tasks"))
    registry.register(Fake("help"))
    grouped = registry.grouped()
    assert [command.name for command in grouped["Tasks"]] == ["add task", "show tasks"]
    assert list(grouped) == ["Tasks", "General"] or set(grouped) == {"Tasks", "General"}
