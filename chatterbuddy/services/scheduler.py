"""Firing alarms while the user is typing.

The scheduling decision is a pure function -- ``due_alarms`` -- and the thread
is a thin loop around it. That split is deliberate: the interesting logic
(including the midnight boundary) is testable by passing in two timestamps,
with no clock patching and no sleeping in the test suite.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from datetime import date, datetime

from ..models import Alarm
from ..repositories import AlarmRepository

logger = logging.getLogger(__name__)


def due_alarms(alarms: Iterable[Alarm], previous_check: datetime, now: datetime) -> list[Alarm]:
    """Alarms whose scheduled moment falls in the half-open window
    ``(previous_check, now]``.

    Using a window rather than "is it within N minutes of the alarm time" means
    an alarm fires exactly once and is never missed, and starting the program at
    20:00 does not immediately fire an 18:30 reminder.
    """
    if now <= previous_check:
        return []

    days = _candidate_days(previous_check, now)
    due: list[Alarm] = []
    for alarm in alarms:
        if not alarm.active:
            continue
        for day in days:
            occurrence = alarm.occurrence_on(day)
            if previous_check < occurrence <= now:
                due.append(alarm)
                break
    return due


def _candidate_days(previous_check: datetime, now: datetime) -> list[date]:
    """Both dates spanned by the window, so a poll across midnight still fires.

    Polling happens every few seconds, so the window never spans more than two
    calendar days in practice.
    """
    if previous_check.date() == now.date():
        return [now.date()]
    return [previous_check.date(), now.date()]


class AlarmScheduler:
    """Polls for due alarms on a background daemon thread."""

    def __init__(
        self,
        repository: AlarmRepository,
        notify: Callable[[Alarm], None],
        *,
        poll_seconds: float = 15.0,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._repository = repository
        self._notify = notify
        self._poll_seconds = poll_seconds
        self._clock = clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        # A daemon thread dies with the interpreter, so a hung poll can never
        # keep the program alive after the user types 'exit'.
        self._thread = threading.Thread(target=self._run, name="alarm-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_seconds + 1)
            self._thread = None

    def poll_once(self, previous_check: datetime, now: datetime) -> list[Alarm]:
        """One scheduling pass. Public so tests can drive it directly."""
        fired = due_alarms(self._repository.all(), previous_check, now)
        self._repository.mark_triggered(fired, now.date())
        for alarm in fired:
            self._notify(alarm)
        return fired

    def _run(self) -> None:
        previous_check = self._clock()
        # Event.wait doubles as the sleep and the shutdown signal, so stopping
        # is immediate instead of waiting out the remainder of a sleep.
        while not self._stop.wait(self._poll_seconds):
            now = self._clock()
            try:
                self.poll_once(previous_check, now)
            except Exception:
                # A background thread must not take the session down, but the
                # failure still belongs in the log rather than nowhere. The next
                # tick will try again.
                logger.exception("Alarm poll failed")
            previous_check = now
