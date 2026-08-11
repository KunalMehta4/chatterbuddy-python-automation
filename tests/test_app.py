"""End-to-end tests over the real command set.

The application is built with fake weather and search services -- the two
components that would otherwise need a network -- and real repositories on
``tmp_path``. Everything else is the production wiring, so these tests would
catch a broken registration or a parser regression.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chatterbuddy.app import ChatterBuddy, create_app
from chatterbuddy.commands import build_registry
from chatterbuddy.config import AppConfig
from chatterbuddy.errors import ApiError
from chatterbuddy.parser import CommandParser
from chatterbuddy.repositories import AlarmRepository, ContactRepository, TaskRepository
from chatterbuddy.services.search_service import SearchResult
from chatterbuddy.services.storage import JsonStore
from chatterbuddy.services.weather_service import Location, WeatherReport


class FakeWeatherService:
    """Stands in for WeatherService. Raising on demand is how the failure path
    gets tested without pretending to be a network."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[str] = []

    def current(self, query: str) -> WeatherReport:
        self.queries.append(query)
        if self.error:
            raise self.error
        return WeatherReport(
            location=Location("Toronto", "Canada", "Ontario", 43.7, -79.4),
            temperature=24.0,
            feels_like=26.0,
            condition="Partly cloudy",
            humidity=60,
            wind_speed=12.0,
            temperature_unit="\u00b0C",
            wind_unit="km/h",
            observed_at="2026-08-11T14:00",
        )


class FakeSearchService:
    provider_name = "Fake"

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = (
            results
            if results is not None
            else [SearchResult("Hypothesis", "Property-based testing", "https://example.com")]
        )

    def search(self, query: str) -> list[SearchResult]:
        return self.results


@pytest.fixture
def app(tmp_path: Path) -> ChatterBuddy:
    return _build(tmp_path, FakeWeatherService(), FakeSearchService())


def _build(tmp_path: Path, weather, search) -> ChatterBuddy:
    registry = build_registry(
        weather_service=weather,
        search_service=search,
        contacts=ContactRepository(JsonStore(tmp_path / "contacts.json")),
        tasks=TaskRepository(JsonStore(tmp_path / "tasks.json")),
        alarms=AlarmRepository(JsonStore(tmp_path / "alarms.json")),
    )
    return ChatterBuddy(registry=registry, parser=CommandParser(registry))


def test_every_command_is_registered_exactly_once(app: ChatterBuddy) -> None:
    """Registration raises on duplicates, so reaching this point proves the real
    command set has no colliding names or aliases."""
    assert "weather" in app.handle("help").message
    assert "set alarm" in app.handle("help").message


def test_weather_command_reaches_the_service_and_formats_the_report(tmp_path: Path) -> None:
    weather = FakeWeatherService()
    app = _build(tmp_path, weather, FakeSearchService())

    message = app.handle("weather Toronto").message

    assert weather.queries == ["Toronto"]
    assert "Toronto, Ontario, Canada" in message
    assert "Partly cloudy" in message
    assert "24" in message and "60%" in message


def test_a_service_failure_is_shown_as_a_message_not_a_traceback(tmp_path: Path) -> None:
    app = _build(tmp_path, FakeWeatherService(ApiError("the sky is down")), FakeSearchService())
    result = app.handle("weather Toronto")
    assert result.message == "the sky is down"
    assert result.should_exit is False


def test_search_command_formats_results_with_the_provider_name(app: ChatterBuddy) -> None:
    message = app.handle("search property based testing").message
    assert "Hypothesis" in message
    assert "https://example.com" in message
    assert "via Fake" in message


def test_search_with_no_results_says_so(tmp_path: Path) -> None:
    app = _build(tmp_path, FakeWeatherService(), FakeSearchService(results=[]))
    assert "No results" in app.handle("search zzzzzz").message


def test_a_full_task_workflow_through_the_dispatcher(app: ChatterBuddy) -> None:
    assert "Added task 1" in app.handle("add task Finish Python project !high").message
    assert "Added task 2" in app.handle("add task Update resume").message
    assert "Completed task 2" in app.handle("complete task 2").message

    listing = app.handle("show tasks").message
    assert "[x]" in listing and "1 of 2 task(s) outstanding" in listing

    assert "Removed task 1" in app.handle("remove task 1").message


def test_a_full_contact_workflow_through_the_dispatcher(app: ChatterBuddy) -> None:
    added = app.handle("add contact John Smith john@email.com 4165551234")
    assert "contact 1" in added.message
    assert "John Smith" in app.handle("show contacts").message
    assert "John Smith" in app.handle("find contact smith").message
    assert "Removed contact 1" in app.handle("remove contact 1").message


def test_a_full_alarm_workflow_through_the_dispatcher(app: ChatterBuddy) -> None:
    assert "18:30" in app.handle("set alarm 6:30pm Study Python").message
    assert "paused" in app.handle("toggle alarm 1").message
    assert "Removed alarm 1" in app.handle("remove alarm 1").message


def test_aliases_work_through_the_dispatcher(app: ChatterBuddy) -> None:
    app.handle("add task Something")
    assert "Something" in app.handle("todo").message
    assert "Something" in app.handle("tasks").message


def test_unknown_command_returns_a_suggestion(app: ChatterBuddy) -> None:
    """The real registry has no bare 'show', so a mistyped second word reaches
    the suggestion path rather than falling through."""
    message = app.handle("show contancts").message
    assert "Unknown command" in message
    assert "show contacts" in message


def test_missing_arguments_return_the_usage_line(app: ChatterBuddy) -> None:
    assert app.handle("weather").message == "Usage: weather <location>"
    assert "Usage: add contact" in app.handle("add contact John").message


def test_an_unexpected_exception_does_not_escape_handle(app: ChatterBuddy, monkeypatch) -> None:
    """A bug in one command must not end the session."""

    def explode(self, args: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("chatterbuddy.commands.tasks.ShowTasksCommand.execute", explode)

    result = app.handle("show tasks")
    assert "Something went wrong" in result.message
    assert result.should_exit is False
    # The session is still usable afterwards.
    assert "Added task 1" in app.handle("add task Still working").message


def test_exit_signals_the_loop_to_stop(app: ChatterBuddy) -> None:
    result = app.handle("exit")
    assert result.should_exit is True

    for alias in ("quit", "bye"):
        assert app.handle(alias).should_exit is True


def test_help_for_a_single_command(app: ChatterBuddy) -> None:
    message = app.handle("help set alarm").message
    assert "Usage: set alarm <HH:MM> <message>" in message


def test_help_for_a_command_that_does_not_exist(app: ChatterBuddy) -> None:
    assert "no command called" in app.handle("help nonsense").message


def test_run_prints_the_banner_and_stops_on_exit(tmp_path: Path) -> None:
    registry = build_registry(
        weather_service=FakeWeatherService(),
        search_service=FakeSearchService(),
        contacts=ContactRepository(JsonStore(tmp_path / "contacts.json")),
        tasks=TaskRepository(JsonStore(tmp_path / "tasks.json")),
        alarms=AlarmRepository(JsonStore(tmp_path / "alarms.json")),
    )
    lines = iter(["", "   ", "add task From the loop", "show tasks", "exit"])
    written: list[str] = []

    ChatterBuddy(
        registry=registry,
        parser=CommandParser(registry),
        output=written.append,
        read_input=lambda prompt: next(lines),
    ).run()

    transcript = "\n".join(written)
    assert "CHATTERBUDDY" in transcript
    assert "From the loop" in transcript
    assert "Goodbye!" in transcript


def test_run_exits_cleanly_on_ctrl_d(tmp_path: Path) -> None:
    registry = build_registry(
        weather_service=FakeWeatherService(),
        search_service=FakeSearchService(),
        contacts=ContactRepository(JsonStore(tmp_path / "contacts.json")),
        tasks=TaskRepository(JsonStore(tmp_path / "tasks.json")),
        alarms=AlarmRepository(JsonStore(tmp_path / "alarms.json")),
    )
    written: list[str] = []

    def eof(prompt: str) -> str:
        raise EOFError

    ChatterBuddy(
        registry=registry,
        parser=CommandParser(registry),
        output=written.append,
        read_input=eof,
    ).run()

    assert "Goodbye!" in "\n".join(written)


def test_create_app_wires_a_working_application(tmp_path: Path) -> None:
    """Covers the composition root itself, which nothing else touches."""
    written: list[str] = []
    app = create_app(AppConfig(data_dir=tmp_path), output=written.append)

    assert "Added task 1" in app.handle("add task Built by create_app").message
    assert (tmp_path / "tasks.json").exists()


def test_create_app_reports_the_active_search_provider(tmp_path: Path) -> None:
    notices = create_app(AppConfig(data_dir=tmp_path)).notices
    assert any("Search provider: Wikipedia" in notice for notice in notices)
    assert any("TAVILY_API_KEY" in notice for notice in notices)


def test_create_app_warns_about_a_quarantined_data_file(tmp_path: Path) -> None:
    """A file the user broke by hand should produce a warning, not a crash."""
    (tmp_path / "tasks.json").write_text("{ broken", encoding="utf-8")

    app = create_app(AppConfig(data_dir=tmp_path))

    assert any("moved to" in notice for notice in app.notices)
    # And the application is fully usable afterwards.
    assert "Added task 1" in app.handle("add task Recovered").message


def test_create_app_warns_about_individually_unusable_records(tmp_path: Path) -> None:
    (tmp_path / "tasks.json").write_text('[{"id": 1, "nope": true}]', encoding="utf-8")
    app = create_app(AppConfig(data_dir=tmp_path))
    assert any("skipped 1 unusable task record" in notice for notice in app.notices)
