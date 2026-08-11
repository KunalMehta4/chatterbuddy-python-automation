"""Alarm commands: set, list, toggle, remove."""

from __future__ import annotations

from ..errors import UsageError
from ..models import Alarm
from ..repositories import AlarmRepository
from ..utils.formatting import render_table, truncate
from ..utils.validators import parse_time, require_text
from .base import Command, CommandResult

CATEGORY = "Alarms"
MESSAGE_WIDTH = 40


class SetAlarmCommand(Command):
    name = "set alarm"
    usage = "set alarm <HH:MM> <message>"
    description = "Schedule a daily reminder. 18:30 and 6:30pm both work."
    category = CATEGORY

    def __init__(self, repository: AlarmRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        parts = self.require_args(args).split(" ", 1)
        if len(parts) < 2:
            raise UsageError(f"Usage: {self.usage}")

        at = parse_time(parts[0])
        message = require_text(parts[1], field="Alarm message", max_length=120)
        alarm = self._repository.create(at, message)
        return CommandResult(f"Alarm {alarm.id} set for {alarm.label} daily: {alarm.message}")


class ShowAlarmsCommand(Command):
    name = "show alarms"
    usage = "show alarms"
    description = "List every alarm and whether it is active."
    category = CATEGORY
    aliases = ("alarms",)

    def __init__(self, repository: AlarmRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        alarms = sorted(self._repository.all(), key=lambda alarm: (alarm.at, alarm.id))
        if not alarms:
            return CommandResult("No alarms set. Add one with: set alarm 18:30 Study Python")

        rows = [
            (
                alarm.id,
                alarm.label,
                "active" if alarm.active else "paused",
                truncate(alarm.message, MESSAGE_WIDTH),
                alarm.last_triggered.isoformat() if alarm.last_triggered else "never",
            )
            for alarm in alarms
        ]
        table = render_table(("ID", "TIME", "STATUS", "MESSAGE", "LAST FIRED"), rows)
        active = sum(1 for alarm in alarms if alarm.active)
        return CommandResult(f"{table}\n\n{active} of {len(alarms)} alarm(s) active.")


class ToggleAlarmCommand(Command):
    name = "toggle alarm"
    usage = "toggle alarm <id>"
    description = "Pause or resume an alarm without deleting it."
    category = CATEGORY

    def __init__(self, repository: AlarmRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        alarm = self._repository.toggle(self.require_id(args))
        state = "active" if alarm.active else "paused"
        return CommandResult(f"Alarm {alarm.id} ({alarm.label}) is now {state}.")


class RemoveAlarmCommand(Command):
    name = "remove alarm"
    usage = "remove alarm <id>"
    description = "Delete an alarm by id."
    category = CATEGORY
    aliases = ("cancel alarm",)

    def __init__(self, repository: AlarmRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        alarm = self._repository.remove(self.require_id(args))
        return CommandResult(f"Removed alarm {alarm.id} ({alarm.label}).")


def format_notification(alarm: Alarm) -> str:
    """How a firing alarm interrupts the prompt."""
    return f"\n*** ALARM {alarm.label} *** {alarm.message}"
