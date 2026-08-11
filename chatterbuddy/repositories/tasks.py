"""Task storage and the completion state transition."""

from __future__ import annotations

from datetime import date

from ..models import Priority, Task
from ..services.storage import JsonStore
from ..utils import now
from .base import JsonRepository


class TaskRepository(JsonRepository[Task]):
    entity_name = "task"

    def __init__(self, store: JsonStore) -> None:
        super().__init__(store, Task)

    def create(
        self,
        description: str,
        *,
        priority: Priority = Priority.NORMAL,
        due_date: date | None = None,
    ) -> Task:
        with self._lock:
            return self.add(
                Task(
                    id=self.next_id(),
                    description=description,
                    priority=priority,
                    due_date=due_date,
                )
            )

    def complete(self, task_id: int) -> tuple[Task, bool]:
        """Mark a task done. Returns the task and whether this call changed it.

        Completing an already-complete task is not an error -- the user's
        intent is satisfied either way -- so the caller gets a flag instead of
        an exception and can word the response accordingly.
        """
        with self._lock:
            task = self.get(task_id)
            if task.is_complete:
                return task, False
            task.completed_at = now()
            self.save()
            return task, True

    def reopen(self, task_id: int) -> Task:
        with self._lock:
            task = self.get(task_id)
            task.completed_at = None
            self.save()
            return task

    def pending(self) -> list[Task]:
        return [task for task in self.all() if not task.is_complete]

    def sorted_for_display(self) -> list[Task]:
        """Unfinished tasks first, highest priority first, then by id."""
        rank = {Priority.HIGH: 0, Priority.NORMAL: 1, Priority.LOW: 2}
        return sorted(
            self.all(),
            key=lambda task: (task.is_complete, rank[task.priority], task.id),
        )
