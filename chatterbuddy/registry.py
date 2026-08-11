"""The command registry: one dictionary, and the reason there is no if/elif chain.

Registering a command makes it dispatchable, discoverable in ``help``, and
resolvable by alias. Adding a feature never means editing this file.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    # Import for typing only. The registry stores commands but has no runtime
    # need of the class, and keeping it out of the import graph makes the
    # dependency strictly one-way: commands import the registry, never the
    # reverse. That is what removes the import cycle rather than working around
    # it.
    from .commands.base import Command


class CommandRegistry:
    """Maps canonical command names, and their aliases, to command objects."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._aliases: dict[str, str] = {}
        self._max_name_words = 1

    def register(self, command: Command) -> None:
        """Add a command, refusing to silently shadow an existing name.

        Two commands answering to the same word is a programming mistake that is
        miserable to debug at runtime, so it fails loudly at start-up instead.
        """
        name = command.name.lower()
        if name in self._commands or name in self._aliases:
            raise ValueError(f"Command name {name!r} is already registered.")
        self._commands[name] = command

        for alias in command.aliases:
            key = alias.lower()
            if key in self._commands or key in self._aliases:
                raise ValueError(f"Alias {key!r} is already registered.")
            self._aliases[key] = name

        self._max_name_words = max(
            self._max_name_words,
            *(len(key.split()) for key in (name, *(a.lower() for a in command.aliases))),
        )

    @property
    def max_name_words(self) -> int:
        """Longest registered name in words.

        The parser uses this as its starting window size, so multi-word commands
        keep working without the parser hard-coding a number.
        """
        return self._max_name_words

    @property
    def names(self) -> list[str]:
        return sorted(self._commands)

    def resolve(self, text: str) -> str | None:
        """Canonical name for an exact name or alias match, else ``None``."""
        key = text.lower()
        if key in self._commands:
            return key
        return self._aliases.get(key)

    def get(self, name: str) -> Command:
        return self._commands[name.lower()]

    def suggest(self, text: str, *, limit: int = 3) -> list[str]:
        """Close matches for a typo, so an unknown command is still helpful."""
        candidates = [*self._commands, *self._aliases]
        return difflib.get_close_matches(text.lower(), candidates, n=limit, cutoff=0.6)

    def grouped(self) -> dict[str, list[Command]]:
        """Commands by category, for a readable ``help`` screen."""
        groups: dict[str, list[Command]] = {}
        for command in self._commands.values():
            groups.setdefault(command.category, []).append(command)
        for commands in groups.values():
            commands.sort(key=lambda command: command.name)
        return groups

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self.resolve(name) is not None

    def __iter__(self) -> Iterator[Command]:
        return iter(self._commands.values())

    def __len__(self) -> int:
        return len(self._commands)
