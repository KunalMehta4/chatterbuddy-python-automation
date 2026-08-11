"""Composition of the command set.

``build_registry`` is the single place that knows which commands exist and what
each one depends on. A new feature is a new command class plus one line here --
the parser, the registry, the REPL, and ``help`` all pick it up for free.
"""

from __future__ import annotations

from ..registry import CommandRegistry
from ..repositories import AlarmRepository, ContactRepository, TaskRepository
from ..services.search_service import SearchService
from ..services.weather_service import WeatherService
from .alarms import (
    RemoveAlarmCommand,
    SetAlarmCommand,
    ShowAlarmsCommand,
    ToggleAlarmCommand,
)
from .base import Command, CommandResult
from .contacts import (
    AddContactCommand,
    FindContactCommand,
    RemoveContactCommand,
    ShowContactsCommand,
)
from .meta import ExitCommand, HelpCommand
from .search import SearchCommand
from .tasks import (
    AddTaskCommand,
    CompleteTaskCommand,
    RemoveTaskCommand,
    ShowTasksCommand,
)
from .weather import WeatherCommand

__all__ = ["Command", "CommandResult", "build_registry"]


def build_registry(
    *,
    weather_service: WeatherService,
    search_service: SearchService,
    contacts: ContactRepository,
    tasks: TaskRepository,
    alarms: AlarmRepository,
) -> CommandRegistry:
    registry = CommandRegistry()

    for command in (
        WeatherCommand(weather_service),
        SearchCommand(search_service),
        AddContactCommand(contacts),
        ShowContactsCommand(contacts),
        FindContactCommand(contacts),
        RemoveContactCommand(contacts),
        AddTaskCommand(tasks),
        ShowTasksCommand(tasks),
        CompleteTaskCommand(tasks),
        RemoveTaskCommand(tasks),
        SetAlarmCommand(alarms),
        ShowAlarmsCommand(alarms),
        ToggleAlarmCommand(alarms),
        RemoveAlarmCommand(alarms),
        ExitCommand(),
    ):
        registry.register(command)

    # Registered last because it needs the finished registry to document itself.
    registry.register(HelpCommand(registry))
    return registry
