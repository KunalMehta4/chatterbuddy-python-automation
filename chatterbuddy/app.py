"""The application shell and its composition root.

``ChatterBuddy.handle`` is the whole of the request lifecycle: parse, dispatch,
convert failures into readable text. It returns a ``CommandResult`` instead of
printing, which is what makes the loop testable without a terminal.

``create_app`` is the only function that wires concrete implementations
together. Nothing below it reaches for a global or constructs its own
dependencies, so any part of the system can be exercised with a substitute.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from .commands import build_registry
from .commands.alarms import format_notification
from .commands.base import CommandResult
from .config import AppConfig
from .errors import ChatterBuddyError
from .parser import CommandParser
from .registry import CommandRegistry
from .repositories import AlarmRepository, ContactRepository, TaskRepository
from .services.http_client import HttpClient
from .services.scheduler import AlarmScheduler
from .services.search_service import SearchService, build_search_provider
from .services.storage import JsonStore
from .services.weather_service import WeatherService
from .utils.formatting import BANNER

logger = logging.getLogger(__name__)

PROMPT = "chatterbuddy> "


class ChatterBuddy:
    """Reads lines, dispatches commands, prints results."""

    def __init__(
        self,
        *,
        registry: CommandRegistry,
        parser: CommandParser,
        scheduler: AlarmScheduler | None = None,
        notices: Sequence[str] = (),
        output: Callable[[str], None] = print,
        read_input: Callable[[str], str] = input,
    ) -> None:
        self._registry = registry
        self._parser = parser
        self._scheduler = scheduler
        self._notices = list(notices)
        self._output = output
        self._read_input = read_input

    @property
    def notices(self) -> list[str]:
        """Messages shown once, under the banner, before the first prompt."""
        return list(self._notices)

    def handle(self, raw: str) -> CommandResult:
        """Run one line of input and always return something printable.

        Two layers of catching, for two different audiences. Expected failures
        carry a message written for the user. Anything else is a bug: the user
        gets an apology, and the traceback goes to the log rather than the
        screen.
        """
        try:
            parsed = self._parser.parse(raw)
            return self._registry.get(parsed.name).execute(parsed.args)
        except ChatterBuddyError as error:
            return CommandResult(str(error))
        except Exception:
            logger.exception("Unhandled error while running %r", raw)
            return CommandResult(
                "Something went wrong running that command. "
                "Your saved data is untouched -- please try again."
            )

    def run(self) -> None:
        self._output(BANNER)
        for notice in self._notices:
            self._output(notice)

        if self._scheduler is not None:
            self._scheduler.start()

        try:
            while True:
                try:
                    raw = self._read_input(PROMPT)
                except (EOFError, KeyboardInterrupt):
                    # Ctrl-C and Ctrl-D are how people actually leave a REPL.
                    self._output("\nGoodbye!")
                    return

                if not raw.strip():
                    continue

                result = self.handle(raw)
                if result.message:
                    self._output(result.message)
                if result.should_exit:
                    return
        finally:
            if self._scheduler is not None:
                self._scheduler.stop()


def create_app(config: AppConfig, *, output: Callable[[str], None] = print) -> ChatterBuddy:
    """Build a fully wired application from configuration."""
    http = HttpClient(timeout=config.http_timeout)

    weather_service = WeatherService(
        http,
        temperature_unit=config.temperature_unit,
        wind_speed_unit=config.wind_speed_unit,
    )
    search_service = SearchService(build_search_provider(http, config), limit=config.search_results)

    contacts = ContactRepository(JsonStore(config.data_dir / "contacts.json"))
    tasks = TaskRepository(JsonStore(config.data_dir / "tasks.json"))
    alarms = AlarmRepository(JsonStore(config.data_dir / "alarms.json"))

    # Load eagerly so storage problems surface at start-up, with the banner,
    # rather than in the middle of the user's first command.
    for repository in (contacts, tasks, alarms):
        repository.load()

    registry = build_registry(
        weather_service=weather_service,
        search_service=search_service,
        contacts=contacts,
        tasks=tasks,
        alarms=alarms,
    )

    scheduler = AlarmScheduler(
        alarms,
        notify=lambda alarm: output(format_notification(alarm)),
        poll_seconds=config.alarm_poll_seconds,
    )

    return ChatterBuddy(
        registry=registry,
        parser=CommandParser(registry),
        scheduler=scheduler,
        notices=_startup_notices(search_service, (contacts, tasks, alarms)),
        output=output,
    )


def _startup_notices(
    search_service: SearchService,
    repositories: Sequence[ContactRepository | TaskRepository | AlarmRepository],
) -> list[str]:
    """Things the user should know before their first command."""
    notices = [f"Search provider: {search_service.provider_name}"]
    if search_service.provider_name == "Wikipedia":
        notices.append("  (set TAVILY_API_KEY in .env for general web search)")

    for repository in repositories:
        quarantined = repository.store.last_quarantine
        if quarantined is not None:
            notices.append(
                f"Warning: {repository.store.path.name} was unreadable and has been "
                f"moved to {quarantined.name}. Starting with an empty list."
            )
        if repository.discarded:
            notices.append(
                f"Warning: skipped {repository.discarded} unusable "
                f"{repository.entity_name} record(s) in {repository.store.path.name}."
            )
    return notices
