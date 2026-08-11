"""The command contract.

Commands receive their dependencies through ``__init__`` and return a
``CommandResult`` rather than printing. Both choices exist for the same reason:
a command can be constructed with a fake repository, executed, and asserted on,
with no terminal and no network anywhere in the test.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from ..errors import UsageError


@dataclass(frozen=True)
class CommandResult:
    """What a command produced: text to show, and whether to stop the loop."""

    message: str
    should_exit: bool = False


class Command(ABC):
    """Base class for every command.

    Subclasses set the class-level metadata, which the registry uses for
    dispatch and ``help`` uses to document itself. There is no separate list of
    commands to keep in sync.
    """

    name: ClassVar[str]
    usage: ClassVar[str]
    description: ClassVar[str]
    category: ClassVar[str] = "General"
    aliases: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def execute(self, args: str) -> CommandResult:
        """Run the command against the argument string the parser extracted."""

    def require_args(self, args: str) -> str:
        """Argument text, or a usage error naming the correct form."""
        cleaned = args.strip()
        if not cleaned:
            raise UsageError(f"Usage: {self.usage}")
        return cleaned

    def require_id(self, args: str) -> int:
        """Parse a leading integer id, or explain what was expected."""
        first = self.require_args(args).split(" ")[0]
        try:
            record_id = int(first)
        except ValueError:
            raise UsageError(f"{first!r} is not a number. Usage: {self.usage}") from None
        if record_id < 1:
            raise UsageError(f"Ids start at 1. Usage: {self.usage}")
        return record_id
