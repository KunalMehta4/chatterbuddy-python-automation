"""Commands about the application itself: ``help`` and ``exit``.

``help`` reads the registry, so it can never drift out of date with the set of
commands that actually exist.
"""

from __future__ import annotations

from ..errors import NotFoundError
from ..registry import CommandRegistry
from .base import Command, CommandResult

CATEGORY_ORDER = ("Lookups", "Contacts", "Tasks", "Alarms", "General")


class HelpCommand(Command):
    name = "help"
    usage = "help [command]"
    description = "List commands, or explain one in detail."
    category = "General"
    aliases = ("?", "commands")

    def __init__(self, registry: CommandRegistry) -> None:
        self._registry = registry

    def execute(self, args: str) -> CommandResult:
        requested = args.strip().lower()
        if requested:
            return CommandResult(self._detail(requested))
        return CommandResult(self._overview())

    def _detail(self, requested: str) -> str:
        resolved = self._registry.resolve(requested)
        if resolved is None:
            raise NotFoundError(f"There is no command called {requested!r}.")
        command = self._registry.get(resolved)
        lines = [f"{command.name} -- {command.description}", f"  Usage: {command.usage}"]
        if command.aliases:
            lines.append(f"  Also:  {', '.join(command.aliases)}")
        return "\n".join(lines)

    def _overview(self) -> str:
        groups = self._registry.grouped()
        ordered = [name for name in CATEGORY_ORDER if name in groups]
        ordered += [name for name in sorted(groups) if name not in CATEGORY_ORDER]

        lines = ["Available commands:"]
        for category in ordered:
            lines.append("")
            lines.append(f"{category}:")
            for command in groups[category]:
                lines.append(f"  {command.usage:<58} {command.description}")
        lines.append("")
        lines.append("Type 'help <command>' for detail on one command.")
        return "\n".join(lines)


class ExitCommand(Command):
    name = "exit"
    usage = "exit"
    description = "Save everything and close ChatterBuddy."
    category = "General"
    aliases = ("quit", "bye")

    def execute(self, args: str) -> CommandResult:
        return CommandResult("Goodbye!", should_exit=True)
