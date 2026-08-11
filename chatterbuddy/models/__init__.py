"""Domain objects. These know their own shape and how to survive a round-trip
through JSON, and nothing else."""

from .alarm import Alarm
from .contact import Contact
from .task import Priority, Task

__all__ = ["Alarm", "Contact", "Priority", "Task"]
