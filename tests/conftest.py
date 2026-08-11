"""Shared fixtures.

Repositories are built on ``tmp_path`` so every test gets its own filesystem and
nothing leaks between tests. Services are built on a real ``HttpClient`` whose
traffic is intercepted by ``responses``, which means the tests exercise the
actual URL and parameter construction rather than a mock of it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chatterbuddy.registry import CommandRegistry
from chatterbuddy.repositories import AlarmRepository, ContactRepository, TaskRepository
from chatterbuddy.services.http_client import HttpClient
from chatterbuddy.services.storage import JsonStore
from chatterbuddy.services.weather_service import WeatherService


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(tmp_path / "records.json")


@pytest.fixture
def contacts(tmp_path: Path) -> ContactRepository:
    return ContactRepository(JsonStore(tmp_path / "contacts.json"))


@pytest.fixture
def tasks(tmp_path: Path) -> TaskRepository:
    return TaskRepository(JsonStore(tmp_path / "tasks.json"))


@pytest.fixture
def alarms(tmp_path: Path) -> AlarmRepository:
    return AlarmRepository(JsonStore(tmp_path / "alarms.json"))


@pytest.fixture
def http() -> HttpClient:
    return HttpClient(timeout=1.0)


@pytest.fixture
def weather_service(http: HttpClient) -> WeatherService:
    return WeatherService(http)


@pytest.fixture
def registry() -> CommandRegistry:
    return CommandRegistry()
