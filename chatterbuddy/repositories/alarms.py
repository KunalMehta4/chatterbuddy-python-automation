"""Alarm storage, including the mutations the scheduler thread performs."""

from __future__ import annotations

from datetime import date, time

from ..models import Alarm
from ..services.storage import JsonStore
from .base import JsonRepository


class AlarmRepository(JsonRepository[Alarm]):
    entity_name = "alarm"

    def __init__(self, store: JsonStore) -> None:
        super().__init__(store, Alarm)

    def create(self, at: time, message: str) -> Alarm:
        with self._lock:
            return self.add(Alarm(id=self.next_id(), at=at, message=message))

    def toggle(self, alarm_id: int) -> Alarm:
        with self._lock:
            alarm = self.get(alarm_id)
            alarm.active = not alarm.active
            self.save()
            return alarm

    def mark_triggered(self, alarms: list[Alarm], on: date) -> None:
        """Record that a batch of alarms has fired, with a single write.

        Called from the scheduler thread; the base class lock is what makes it
        safe to do while the user is typing a command.
        """
        if not alarms:
            return
        with self._lock:
            for alarm in alarms:
                alarm.last_triggered = on
            self.save()

    def active(self) -> list[Alarm]:
        return [alarm for alarm in self.all() if alarm.active]
