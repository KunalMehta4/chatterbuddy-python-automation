"""Raw text in, a routed command out.

The only non-obvious part is how multi-word commands such as ``add contact`` are
recognised. The parser takes the longest registered command name (in words) and
walks down: try the first three tokens, then two, then one, and take the first
match. That is at most three dictionary lookups, it lets ``show`` and
``show contacts`` coexist without ambiguity, and it needs no changes when a new
command is registered.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import UnknownCommandError, UsageError
from .registry import CommandRegistry


@dataclass(frozen=True)
class ParsedCommand:
    """A resolved command name and the untouched remainder of the input."""

    name: str
    args: str


class CommandParser:
    def __init__(self, registry: CommandRegistry) -> None:
        self._registry = registry

    def parse(self, raw: str) -> ParsedCommand:
        # Collapse runs of whitespace so "add   contact" behaves like
        # "add contact", but do not change case yet: the command name is
        # case-insensitive while the arguments are not. "weather Toronto" and
        # "add task Call Dr Chen" both depend on the original casing surviving.
        text = " ".join(raw.split())
        if not text:
            raise UsageError("Type a command, or 'help' to see what I can do.")

        tokens = text.split(" ")
        window = min(self._registry.max_name_words, len(tokens))
        for size in range(window, 0, -1):
            candidate = " ".join(tokens[:size]).lower()
            resolved = self._registry.resolve(candidate)
            if resolved is not None:
                return ParsedCommand(name=resolved, args=" ".join(tokens[size:]))

        attempted = " ".join(tokens[: self._registry.max_name_words])
        raise UnknownCommandError(attempted, self._registry.suggest(attempted))
