"""Task commands: add, list, complete, remove.

``add task`` accepts two optional inline flags, ``!high`` / ``!low`` and
``due:<date>``, which are stripped out before the rest becomes the description.
Flags are parsed here rather than in the central parser because they are
specific to this one command -- the parser's job ends at routing.
"""

from __future__ import annotations

from datetime import date

from ..models import Priority
from ..repositories import TaskRepository
from ..utils.formatting import render_table, truncate
from ..utils.validators import parse_date, require_text
from .base import Command, CommandResult

CATEGORY = "Tasks"
DESCRIPTION_WIDTH = 48

_PRIORITY_FLAGS = {"!high": Priority.HIGH, "!low": Priority.LOW, "!normal": Priority.NORMAL}


class AddTaskCommand(Command):
    name = "add task"
    usage = "add task <description> [!high|!low] [due:DATE]"
    description = "Add a task. DATE accepts 2026-08-20, today, or tomorrow."
    category = CATEGORY

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        raw = self.require_args(args)
        priority = Priority.NORMAL
        due_date: date | None = None
        words: list[str] = []

        for word in raw.split(" "):
            lowered = word.lower()
            if lowered in _PRIORITY_FLAGS:
                priority = _PRIORITY_FLAGS[lowered]
            elif lowered.startswith("due:"):
                due_date = parse_date(word[4:])
            else:
                words.append(word)

        description = require_text(" ".join(words), field="Task description")
        task = self._repository.create(description, priority=priority, due_date=due_date)

        message = f"Added task {task.id}: {task.description}"
        extras = []
        if task.priority is not Priority.NORMAL:
            extras.append(f"priority {task.priority}")
        if task.due_date:
            extras.append(f"due {task.due_date.isoformat()}")
        if extras:
            message += " (" + ", ".join(extras) + ")"
        return CommandResult(message)


class ShowTasksCommand(Command):
    name = "show tasks"
    usage = "show tasks"
    description = "List tasks, unfinished ones first."
    category = CATEGORY
    aliases = ("tasks", "todo")

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        tasks = self._repository.sorted_for_display()
        if not tasks:
            return CommandResult("No tasks yet. Add one with: add task <description>")

        today = date.today()
        rows = []
        for task in tasks:
            due = task.due_date.isoformat() if task.due_date else "-"
            if task.is_overdue(today=today):
                due += " (overdue)"
            rows.append(
                (
                    task.id,
                    "[x]" if task.is_complete else "[ ]",
                    task.priority.value,
                    truncate(task.description, DESCRIPTION_WIDTH),
                    due,
                )
            )

        table = render_table(("ID", "DONE", "PRIORITY", "DESCRIPTION", "DUE"), rows)
        outstanding = sum(1 for task in tasks if not task.is_complete)
        return CommandResult(f"{table}\n\n{outstanding} of {len(tasks)} task(s) outstanding.")


class CompleteTaskCommand(Command):
    name = "complete task"
    usage = "complete task <id>"
    description = "Mark a task as done."
    category = CATEGORY
    aliases = ("done",)

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        task, changed = self._repository.complete(self.require_id(args))
        if not changed:
            return CommandResult(f"Task {task.id} was already complete.")
        return CommandResult(f"Completed task {task.id}: {task.description}")


class RemoveTaskCommand(Command):
    name = "remove task"
    usage = "remove task <id>"
    description = "Delete a task by id."
    category = CATEGORY

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    def execute(self, args: str) -> CommandResult:
        task = self._repository.remove(self.require_id(args))
        return CommandResult(f"Removed task {task.id} ({task.description}).")
