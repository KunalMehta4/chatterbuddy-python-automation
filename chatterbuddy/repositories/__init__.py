"""Repositories turn a JSON file into a collection of domain objects.

Commands ask a repository for records; the repository decides how they are
stored. Swapping JSON for SQLite means rewriting this package and nothing else.
"""

from .alarms import AlarmRepository
from .base import JsonRepository
from .contacts import ContactRepository
from .tasks import TaskRepository

__all__ = ["AlarmRepository", "ContactRepository", "JsonRepository", "TaskRepository"]
