"""Exception hierarchy for ChatterBuddy.

Every error the user could plausibly cause inherits from ``ChatterBuddyError``.
The REPL catches that base class and prints ``str(error)``, which is why each
subclass is responsible for carrying a message a non-technical user can act on.
Anything that escapes this hierarchy is a genuine bug, and the REPL reports it
differently on purpose.
"""

from __future__ import annotations

from collections.abc import Sequence


class ChatterBuddyError(Exception):
    """Base class for all expected, user-facing failures."""


class UsageError(ChatterBuddyError):
    """A command was called with missing or malformed arguments."""


class ValidationError(ChatterBuddyError):
    """A value failed validation (bad email, unparseable time, and so on)."""


class NotFoundError(ChatterBuddyError):
    """A requested record or location does not exist."""


class StorageError(ChatterBuddyError):
    """A data file could not be read or written."""


class UnknownCommandError(ChatterBuddyError):
    """The input did not match any registered command."""

    def __init__(self, attempted: str, suggestions: Sequence[str] = ()) -> None:
        self.attempted = attempted
        self.suggestions = list(suggestions)
        message = f"Unknown command: {attempted!r}."
        if self.suggestions:
            message += " Did you mean: " + ", ".join(self.suggestions) + "?"
        else:
            message += " Type 'help' to see everything I can do."
        super().__init__(message)


class ServiceError(ChatterBuddyError):
    """Base class for failures that originate outside the application."""


class ConfigurationError(ServiceError):
    """A required setting (such as an API key) is missing or invalid."""


class NetworkError(ServiceError):
    """The request never reached the remote service."""


class ApiError(ServiceError):
    """The remote service replied, but not with something usable."""
