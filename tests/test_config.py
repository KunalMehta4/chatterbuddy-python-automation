"""Configuration parsing, exercised without touching os.environ."""

from __future__ import annotations

from pathlib import Path

import pytest

from chatterbuddy.config import PROJECT_ROOT, AppConfig
from chatterbuddy.errors import ConfigurationError


def test_defaults_apply_when_nothing_is_set() -> None:
    config = AppConfig.from_env({})
    assert config.data_dir == PROJECT_ROOT / "data"
    assert config.tavily_api_key is None
    assert config.units == "metric"
    assert config.search_results == 5


def test_values_are_read_from_the_environment() -> None:
    config = AppConfig.from_env(
        {
            "CHATTERBUDDY_DATA_DIR": "/tmp/cb",
            "TAVILY_API_KEY": "tvly-secret",
            "CHATTERBUDDY_UNITS": "IMPERIAL",
            "CHATTERBUDDY_SEARCH_RESULTS": "3",
            "CHATTERBUDDY_HTTP_TIMEOUT": "2.5",
        }
    )
    assert config.data_dir == Path("/tmp/cb")
    assert config.tavily_api_key == "tvly-secret"
    assert config.units == "imperial"
    assert config.search_results == 3
    assert config.http_timeout == 2.5


def test_a_blank_api_key_is_treated_as_absent() -> None:
    """Otherwise an empty line in .env would select a provider that cannot work."""
    assert AppConfig.from_env({"TAVILY_API_KEY": "   "}).tavily_api_key is None


def test_units_drive_the_api_unit_parameters() -> None:
    assert AppConfig.from_env({}).temperature_unit == "celsius"
    imperial = AppConfig.from_env({"CHATTERBUDDY_UNITS": "imperial"})
    assert (imperial.temperature_unit, imperial.wind_speed_unit) == ("fahrenheit", "mph")


def test_an_unknown_unit_system_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="CHATTERBUDDY_UNITS"):
        AppConfig.from_env({"CHATTERBUDDY_UNITS": "kelvin"})


def test_a_non_numeric_timeout_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="must be a number"):
        AppConfig.from_env({"CHATTERBUDDY_HTTP_TIMEOUT": "soon"})


def test_a_zero_or_negative_setting_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="greater than zero"):
        AppConfig.from_env({"CHATTERBUDDY_SEARCH_RESULTS": "0"})
