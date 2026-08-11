"""Application settings, resolved once at start-up.

``AppConfig`` is the only place that reads environment variables. Everything
else receives its settings through a constructor, which keeps the rest of the
codebase free of hidden global state and trivial to test.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_VALID_UNITS = frozenset({"metric", "imperial"})


@dataclass(frozen=True)
class AppConfig:
    """Immutable snapshot of the settings the application runs with."""

    data_dir: Path
    tavily_api_key: str | None = None
    http_timeout: float = 8.0
    search_results: int = 5
    alarm_poll_seconds: float = 15.0
    units: str = "metric"

    @property
    def temperature_unit(self) -> str:
        return "celsius" if self.units == "metric" else "fahrenheit"

    @property
    def wind_speed_unit(self) -> str:
        return "kmh" if self.units == "metric" else "mph"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AppConfig:
        """Build a config from a mapping, defaulting to the real environment.

        Accepting the mapping as an argument is what lets the tests exercise
        every branch below without mutating ``os.environ``.
        """
        source = os.environ if env is None else env

        raw_dir = source.get("CHATTERBUDDY_DATA_DIR", "").strip()
        data_dir = Path(raw_dir).expanduser() if raw_dir else PROJECT_ROOT / "data"

        units = source.get("CHATTERBUDDY_UNITS", "metric").strip().lower() or "metric"
        if units not in _VALID_UNITS:
            raise ConfigurationError(
                f"CHATTERBUDDY_UNITS must be one of {sorted(_VALID_UNITS)}, got {units!r}."
            )

        key = source.get("TAVILY_API_KEY", "").strip()

        return cls(
            data_dir=data_dir,
            tavily_api_key=key or None,
            http_timeout=_positive_float(source, "CHATTERBUDDY_HTTP_TIMEOUT", 8.0),
            search_results=_positive_int(source, "CHATTERBUDDY_SEARCH_RESULTS", 5),
            alarm_poll_seconds=_positive_float(source, "CHATTERBUDDY_ALARM_POLL_SECONDS", 15.0),
            units=units,
        )


def _positive_float(source: Mapping[str, str], key: str, default: float) -> float:
    raw = source.get(key, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be a number, got {raw!r}.") from exc
    if value <= 0:
        raise ConfigurationError(f"{key} must be greater than zero, got {value}.")
    return value


def _positive_int(source: Mapping[str, str], key: str, default: int) -> int:
    raw = source.get(key, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be a whole number, got {raw!r}.") from exc
    if value <= 0:
        raise ConfigurationError(f"{key} must be greater than zero, got {value}.")
    return value
