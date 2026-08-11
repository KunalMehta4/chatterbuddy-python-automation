"""Alarms cover time parsing and the scheduling window, which is the one piece of
genuinely tricky logic in the project."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from chatterbuddy.commands.alarms import (
    RemoveAlarmCommand,
    SetAlarmCommand,
    ShowAlarmsCommand,
    ToggleAlarmCommand,
    format_notification,
)
from chatterbuddy.errors import NotFoundError, UsageError, ValidationError
from chatterbuddy.models import Alarm
from chatterbuddy.repositories import AlarmRepository
from chatterbuddy.services.scheduler import AlarmScheduler, due_alarms
from chatterbuddy.services.storage import JsonStore


def test_set_accepts_24_hour_time(alarms: AlarmRepository) -> None:
    message = SetAlarmCommand(alarms).execute("18:30 Study Python").message
    assert "18:30" in message
    stored = alarms.all()[0]
    assert stored.at == time(18, 30)
    assert stored.message == "Study Python"


def test_set_accepts_12_hour_time(alarms: AlarmRepository) -> None:
    SetAlarmCommand(alarms).execute("6:30pm Study Python")
    assert alarms.all()[0].at == time(18, 30)


def test_set_rejects_an_impossible_time(alarms: AlarmRepository) -> None:
    with pytest.raises(ValidationError, match="not a time"):
        SetAlarmCommand(alarms).execute("25:99 nope")


def test_set_without_a_message_raises_usage_error(alarms: AlarmRepository) -> None:
    with pytest.raises(UsageError):
        SetAlarmCommand(alarms).execute("18:30")


def test_show_lists_status_and_last_fired(alarms: AlarmRepository) -> None:
    alarms.create(time(7, 0), "Wake up")
    message = ShowAlarmsCommand(alarms).execute("").message
    assert "07:00" in message and "active" in message and "never" in message


def test_show_is_helpful_when_empty(alarms: AlarmRepository) -> None:
    assert "No alarms set" in ShowAlarmsCommand(alarms).execute("").message


def test_toggle_pauses_and_resumes(alarms: AlarmRepository) -> None:
    alarms.create(time(7, 0), "Wake up")
    command = ToggleAlarmCommand(alarms)
    assert "paused" in command.execute("1").message
    assert alarms.all()[0].active is False
    assert "active" in command.execute("1").message
    assert alarms.all()[0].active is True


def test_remove_deletes_the_alarm(alarms: AlarmRepository) -> None:
    alarms.create(time(7, 0), "Wake up")
    RemoveAlarmCommand(alarms).execute("1")
    assert alarms.all() == []


def test_remove_unknown_id_raises_not_found(alarms: AlarmRepository) -> None:
    with pytest.raises(NotFoundError, match="no alarm with id 5"):
        RemoveAlarmCommand(alarms).execute("5")


def test_alarms_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "alarms.json"
    first = AlarmRepository(JsonStore(path))
    first.create(time(18, 30), "Study Python")
    first.toggle(1)

    second = AlarmRepository(JsonStore(path))
    restored = second.all()[0]
    assert restored.at == time(18, 30)
    assert restored.active is False


def test_notification_includes_time_and_message() -> None:
    assert "18:30" in format_notification(Alarm(1, time(18, 30), "Study"))


# --- The scheduling window ---------------------------------------------------
# due_alarms is pure, so every case below is exact and instant: no sleeping, no
# patched clock, just two timestamps.

ALARM = Alarm(1, time(18, 30), "Study Python")


def test_fires_when_the_moment_falls_inside_the_window() -> None:
    fired = due_alarms([ALARM], datetime(2026, 8, 11, 18, 29, 50), datetime(2026, 8, 11, 18, 30, 5))
    assert [alarm.id for alarm in fired] == [1]


def test_does_not_fire_before_the_window() -> None:
    assert due_alarms([ALARM], datetime(2026, 8, 11, 18, 0), datetime(2026, 8, 11, 18, 15)) == []


def test_does_not_fire_after_the_window_has_passed() -> None:
    """Starting the program at 20:00 must not replay an 18:30 reminder."""
    assert due_alarms([ALARM], datetime(2026, 8, 11, 20, 0), datetime(2026, 8, 11, 20, 15)) == []


def test_the_exact_boundary_fires_once_and_only_once() -> None:
    moment = datetime(2026, 8, 11, 18, 30)
    assert due_alarms([ALARM], moment - timedelta(seconds=10), moment)
    assert due_alarms([ALARM], moment, moment + timedelta(seconds=10)) == []


def test_paused_alarms_never_fire() -> None:
    paused = Alarm(2, time(18, 30), "Study", active=False)
    assert due_alarms([paused], datetime(2026, 8, 11, 18, 29), datetime(2026, 8, 11, 18, 31)) == []


def test_a_window_spanning_midnight_still_fires() -> None:
    midnight = Alarm(3, time(0, 0), "New day")
    fired = due_alarms(
        [midnight], datetime(2026, 8, 11, 23, 59, 50), datetime(2026, 8, 12, 0, 0, 10)
    )
    assert [alarm.id for alarm in fired] == [3]


def test_several_alarms_in_one_window_all_fire() -> None:
    fired = due_alarms(
        [Alarm(1, time(9, 0), "a"), Alarm(2, time(9, 5), "b"), Alarm(3, time(11, 0), "c")],
        datetime(2026, 8, 11, 8, 59),
        datetime(2026, 8, 11, 9, 30),
    )
    assert [alarm.id for alarm in fired] == [1, 2]


def test_a_backwards_window_fires_nothing() -> None:
    """Defensive: a clock adjustment must not cause a replay."""
    assert due_alarms([ALARM], datetime(2026, 8, 11, 19, 0), datetime(2026, 8, 11, 18, 0)) == []


def test_poll_once_notifies_and_records_the_trigger(alarms: AlarmRepository) -> None:
    alarms.create(time(18, 30), "Study Python")
    seen: list[str] = []
    scheduler = AlarmScheduler(alarms, notify=lambda alarm: seen.append(alarm.message))

    fired = scheduler.poll_once(datetime(2026, 8, 11, 18, 29, 50), datetime(2026, 8, 11, 18, 30, 5))

    assert seen == ["Study Python"]
    assert [alarm.id for alarm in fired] == [1]
    assert alarms.all()[0].last_triggered == date(2026, 8, 11)
    # The trigger was persisted, not just held in memory.
    assert AlarmRepository(alarms.store).all()[0].last_triggered == date(2026, 8, 11)


def test_the_scheduler_thread_starts_and_stops_cleanly(alarms: AlarmRepository) -> None:
    scheduler = AlarmScheduler(alarms, notify=lambda alarm: None, poll_seconds=0.01)
    scheduler.start()
    scheduler.start()  # idempotent
    scheduler.stop()
    scheduler.stop()  # safe to call twice
