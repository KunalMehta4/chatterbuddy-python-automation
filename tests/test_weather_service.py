"""Weather is the API-dependent feature, so the tests replace the network rather
than the service.

``responses`` intercepts at the ``requests`` adapter, which means these tests
assert on the real URL and query string the service builds. A hand-rolled mock of
``WeatherService`` would pass even if the parameters were wrong.
"""

from __future__ import annotations

import pytest
import requests
import responses

from chatterbuddy.errors import ApiError, NetworkError, NotFoundError, ValidationError
from chatterbuddy.services.weather_service import (
    FORECAST_URL,
    GEOCODE_URL,
    WeatherService,
)

GEOCODE_HIT = {
    "results": [
        {
            "name": "Toronto",
            "country": "Canada",
            "admin1": "Ontario",
            "latitude": 43.70011,
            "longitude": -79.4163,
        }
    ]
}

FORECAST_HIT = {
    "current": {
        "time": "2026-08-11T14:00",
        "temperature_2m": 24.3,
        "apparent_temperature": 26.1,
        "relative_humidity_2m": 61,
        "weather_code": 2,
        "wind_speed_10m": 13.7,
    },
    "current_units": {"temperature_2m": "\u00b0C", "wind_speed_10m": "km/h"},
}


def _register_geocode(payload: dict, status: int = 200) -> None:
    responses.add(responses.GET, GEOCODE_URL, json=payload, status=status)


def _register_forecast(payload: dict, status: int = 200) -> None:
    responses.add(responses.GET, FORECAST_URL, json=payload, status=status)


@responses.activate
def test_current_returns_a_populated_report(weather_service: WeatherService) -> None:
    _register_geocode(GEOCODE_HIT)
    _register_forecast(FORECAST_HIT)

    report = weather_service.current("Toronto")

    assert report.location.display_name == "Toronto, Ontario, Canada"
    assert report.temperature == 24.3
    assert report.feels_like == 26.1
    assert report.condition == "Partly cloudy"
    assert report.humidity == 61
    assert report.wind_speed == 13.7
    assert report.temperature_unit == "\u00b0C"


@responses.activate
def test_coordinates_from_geocoding_are_passed_to_the_forecast(
    weather_service: WeatherService,
) -> None:
    """The chaining between the two calls is the part worth pinning down."""
    _register_geocode(GEOCODE_HIT)
    _register_forecast(FORECAST_HIT)

    weather_service.current("Toronto")

    geocode_query, forecast_query = (call.request.params for call in responses.calls)
    assert geocode_query["name"] == "Toronto"
    assert geocode_query["count"] == "1"
    assert forecast_query["latitude"] == "43.70011"
    assert forecast_query["longitude"] == "-79.4163"
    assert "temperature_2m" in forecast_query["current"]


@responses.activate
def test_unit_configuration_reaches_the_request(http) -> None:
    _register_geocode(GEOCODE_HIT)
    _register_forecast(FORECAST_HIT)

    WeatherService(http, temperature_unit="fahrenheit", wind_speed_unit="mph").current("Toronto")

    forecast_query = responses.calls[1].request.params
    assert forecast_query["temperature_unit"] == "fahrenheit"
    assert forecast_query["wind_speed_unit"] == "mph"


@responses.activate
def test_unknown_location_raises_not_found(weather_service: WeatherService) -> None:
    _register_geocode({"generationtime_ms": 0.2})  # no "results" key at all
    with pytest.raises(NotFoundError, match="could not find anywhere"):
        weather_service.current("Nowherecity")


@responses.activate
def test_empty_result_list_raises_not_found(weather_service: WeatherService) -> None:
    _register_geocode({"results": []})
    with pytest.raises(NotFoundError):
        weather_service.current("Nowherecity")


def test_a_one_character_query_is_rejected_before_any_request(
    weather_service: WeatherService,
) -> None:
    """The geocoder ignores single-character searches, so there is no point
    spending a request to find out."""
    with pytest.raises(ValidationError, match="two characters"):
        weather_service.current("x")


@responses.activate
def test_server_error_becomes_an_api_error(weather_service: WeatherService) -> None:
    _register_geocode(GEOCODE_HIT)
    _register_forecast({"error": True}, status=500)
    with pytest.raises(ApiError, match="server trouble"):
        weather_service.current("Toronto")


@responses.activate
def test_rate_limiting_is_reported_as_such(weather_service: WeatherService) -> None:
    _register_geocode({}, status=429)
    with pytest.raises(ApiError, match="rate limiting"):
        weather_service.current("Toronto")


@responses.activate
def test_a_timeout_becomes_a_network_error(weather_service: WeatherService) -> None:
    responses.add(responses.GET, GEOCODE_URL, body=requests.Timeout("too slow"))
    with pytest.raises(NetworkError, match="did not respond"):
        weather_service.current("Toronto")


@responses.activate
def test_a_connection_failure_becomes_a_network_error(weather_service: WeatherService) -> None:
    responses.add(responses.GET, GEOCODE_URL, body=requests.ConnectionError("no route"))
    with pytest.raises(NetworkError, match="Could not reach"):
        weather_service.current("Toronto")


@responses.activate
def test_a_non_json_body_becomes_an_api_error(weather_service: WeatherService) -> None:
    responses.add(responses.GET, GEOCODE_URL, body="<html>maintenance</html>", status=200)
    with pytest.raises(ApiError, match="not valid JSON"):
        weather_service.current("Toronto")


@responses.activate
def test_a_forecast_without_current_conditions_becomes_an_api_error(
    weather_service: WeatherService,
) -> None:
    _register_geocode(GEOCODE_HIT)
    _register_forecast({"hourly": {}})
    with pytest.raises(ApiError, match="current conditions"):
        weather_service.current("Toronto")


@responses.activate
def test_missing_fields_in_current_conditions_become_an_api_error(
    weather_service: WeatherService,
) -> None:
    _register_geocode(GEOCODE_HIT)
    _register_forecast({"current": {"time": "2026-08-11T14:00"}})
    with pytest.raises(ApiError, match="missing expected fields"):
        weather_service.current("Toronto")


@responses.activate
def test_an_unrecognised_weather_code_does_not_crash(weather_service: WeatherService) -> None:
    _register_geocode(GEOCODE_HIT)
    _register_forecast({**FORECAST_HIT, "current": {**FORECAST_HIT["current"], "weather_code": 7}})
    assert weather_service.current("Toronto").condition == "Unknown conditions"
