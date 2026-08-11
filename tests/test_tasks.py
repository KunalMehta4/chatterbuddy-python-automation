"""Tasks cover the state-machine path: creation, an inline flag parser, and a
transition that must be idempotent."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from chatterbuddy.commands.tasks import (
    AddTaskCommand,
    CompleteTaskCommand,
    RemoveTaskCommand,
    ShowTasksCommand,
)
from chatterbuddy.errors import NotFoundError, UsageError, ValidationError
from chatterbuddy.models import Priority
from chatterbuddy.repositories import TaskRepository
from chatterbuddy.services.storage import JsonStore


def test_add_stores_the_description(tasks: TaskRepository) -> None:
    AddTaskCommand(tasks).execute("Finish Python project")
    task = tasks.all()[0]
    assert task.description == "Finish Python project"
    assert task.priority is Priority.NORMAL
    assert not task.is_complete


def test_add_without_a_description_raises_usage_error(tasks: TaskRepository) -> None:
    with pytest.raises(UsageError):
        AddTaskCommand(tasks).execute("   ")


def test_priority_flag_is_applied_and_stripped(tasks: TaskRepository) -> None:
    AddTaskCommand(tasks).execute("Ship the resume !high")
    task = tasks.all()[0]
    assert task.priority is Priority.HIGH
    assert task.description == "Ship the resume"


def test_priority_flag_works_anywhere_in_the_input(tasks: TaskRepository) -> None:
    AddTaskCommand(tasks).execute("!low Water the plants")
    assert tasks.all()[0].description == "Water the plants"


def test_due_date_flag_accepts_an_iso_date(tasks: TaskRepository) -> None:
    AddTaskCommand(tasks).execute("Renew passport due:2026-12-01")
    task = tasks.all()[0]
    assert task.due_date == date(2026, 12, 1)
    assert task.description == "Renew passport"


def test_due_date_flag_accepts_tomorrow(tasks: TaskRepository) -> None:
    AddTaskCommand(tasks).execute("Standup prep due:tomorrow")
    assert tasks.all()[0].due_date == date.today() + timedelta(days=1)


def test_unparseable_due_date_is_rejected(tasks: TaskRepository) -> None:
    with pytest.raises(ValidationError, match="not a date"):
        AddTaskCommand(tasks).execute("Do a thing due:next-thursday")


def test_a_flag_alone_is_not_a_description(tasks: TaskRepository) -> None:
    with pytest.raises(ValidationError, match="cannot be empty"):
        AddTaskCommand(tasks).execute("!high")


def test_complete_marks_the_task_done(tasks: TaskRepository) -> None:
    tasks.create("Write tests")
    message = CompleteTaskCommand(tasks).execute("1").message
    assert "Completed task 1" in message
    assert tasks.all()[0].is_complete


def test_completing_twice_is_reported_not_an_error(tasks: TaskRepository) -> None:
    """The user's intent is satisfied either way, so this is a message rather
    than an exception."""
    tasks.create("Write tests")
    CompleteTaskCommand(tasks).execute("1")
    assert "already complete" in CompleteTaskCommand(tasks).execute("1").message


def test_complete_unknown_id_raises_not_found(tasks: TaskRepository) -> None:
    with pytest.raises(NotFoundError, match="no task with id 42"):
        CompleteTaskCommand(tasks).execute("42")


def test_remove_deletes_the_task(tasks: TaskRepository) -> None:
    tasks.create("Temporary")
    RemoveTaskCommand(tasks).execute("1")
    assert tasks.all() == []


def test_show_is_helpful_when_empty(tasks: TaskRepository) -> None:
    assert "No tasks yet" in ShowTasksCommand(tasks).execute("").message


def test_show_distinguishes_complete_from_incomplete(tasks: TaskRepository) -> None:
    tasks.create("Done one")
    tasks.create("Open one")
    tasks.complete(1)
    message = ShowTasksCommand(tasks).execute("").message
    assert "[x]" in message and "[ ]" in message
    assert "1 of 2 task(s) outstanding" in message


def test_display_order_puts_unfinished_high_priority_first(tasks: TaskRepository) -> None:
    tasks.create("Low", priority=Priority.LOW)
    tasks.create("High", priority=Priority.HIGH)
    tasks.create("Normal")
    tasks.complete(2)
    order = [task.description for task in tasks.sorted_for_display()]
    assert order == ["Normal", "Low", "High"]


def test_overdue_is_flagged_in_the_listing(tasks: TaskRepository) -> None:
    tasks.create("Late thing", due_date=date.today() - timedelta(days=3))
    assert "overdue" in ShowTasksCommand(tasks).execute("").message


def test_completed_tasks_are_never_overdue(tasks: TaskRepository) -> None:
    tasks.create("Late thing", due_date=date.today() - timedelta(days=3))
    tasks.complete(1)
    assert "overdue" not in ShowTasksCommand(tasks).execute("").message


def test_ids_do_not_repeat_within_a_session(tasks: TaskRepository) -> None:
    tasks.create("One")
    tasks.create("Two")
    tasks.remove(2)
    assert tasks.create("Three").id == 3


def test_tasks_and_completion_state_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "tasks.json"
    first = TaskRepository(JsonStore(path))
    first.create("Persisted", priority=Priority.HIGH, due_date=date(2026, 9, 1))
    first.complete(1)

    second = TaskRepository(JsonStore(path))
    restored = second.all()[0]
    assert restored.description == "Persisted"
    assert restored.is_complete
    assert restored.priority is Priority.HIGH
    assert restored.due_date == date(2026, 9, 1)
