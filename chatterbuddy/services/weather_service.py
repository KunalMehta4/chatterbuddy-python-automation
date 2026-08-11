"""Current-conditions lookup, built on two chained Open-Meteo calls.

Open-Meteo was chosen because it needs no API key, which means the weather
command works the moment someone clones this repository. Coverage is a property
of the geocoding index (GeoNames), not of a hard-coded city list, so there is
nothing in this file that limits which places can be looked up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ApiError, NotFoundError, ValidationError
from .http_client import HttpClient

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO 4677 weather codes, which is what Open-Meteo reports.
WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Light snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with light hail",
    99: "Thunderstorm with heavy hail",
}


@dataclass(frozen=True)
class Location:
    name: str
    country: str
    region: str
    latitude: float
    longitude: float

    @property
    def display_name(self) -> str:
        parts = [self.name, self.region, self.country]
        return ", ".join(part for part in parts if part)


@dataclass(frozen=True)
class WeatherReport:
    location: Location
    temperature: float
    feels_like: float
    condition: str
    humidity: int
    wind_speed: float
    temperature_unit: str
    wind_unit: str
    observed_at: str


class WeatherService:
    """Resolves a place name to coordinates, then coordinates to conditions."""

    def __init__(
        self,
        http: HttpClient,
        *,
        temperature_unit: str = "celsius",
        wind_speed_unit: str = "kmh",
    ) -> None:
        self._http = http
        self._temperature_unit = temperature_unit
        self._wind_speed_unit = wind_speed_unit

    def geocode(self, query: str) -> Location:
        """Turn a place name into coordinates.

        The geocoder ignores single-character searches, so that is rejected here
        with a useful message instead of being sent as a request that cannot
        succeed.
        """
        cleaned = " ".join(query.split())
        if len(cleaned) < 2:
            raise ValidationError("Give me at least two characters of a place name.")

        payload = self._http.get_json(
            GEOCODE_URL,
            params={"name": cleaned, "count": 1, "language": "en", "format": "json"},
        )
        results = _expect_dict(payload, GEOCODE_URL).get("results") or []
        if not results:
            raise NotFoundError(
                f"I could not find anywhere called {cleaned!r}. "
                "Try adding a country, for example 'weather London, CA'."
            )

        first = results[0]
        try:
            return Location(
                name=str(first["name"]),
                country=str(first.get("country", "")),
                region=str(first.get("admin1", "")),
                latitude=float(first["latitude"]),
                longitude=float(first["longitude"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError("The geocoding response was missing expected fields.") from exc

    def current(self, query: str) -> WeatherReport:
        location = self.geocode(query)
        payload = self._http.get_json(
            FORECAST_URL,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": ",".join(
                    (
                        "temperature_2m",
                        "apparent_temperature",
                        "relative_humidity_2m",
                        "weather_code",
                        "wind_speed_10m",
                    )
                ),
                "temperature_unit": self._temperature_unit,
                "wind_speed_unit": self._wind_speed_unit,
                "timezone": "auto",
            },
        )
        body = _expect_dict(payload, FORECAST_URL)
        current = body.get("current")
        if not isinstance(current, dict):
            raise ApiError("The forecast response did not include current conditions.")

        units = body.get("current_units") or {}
        try:
            return WeatherReport(
                location=location,
                temperature=float(current["temperature_2m"]),
                feels_like=float(current["apparent_temperature"]),
                condition=WEATHER_CODES.get(int(current["weather_code"]), "Unknown conditions"),
                humidity=int(current["relative_humidity_2m"]),
                wind_speed=float(current["wind_speed_10m"]),
                temperature_unit=str(units.get("temperature_2m", "")),
                wind_unit=str(units.get("wind_speed_10m", "")),
                observed_at=str(current.get("time", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError("The forecast response was missing expected fields.") from exc


def _expect_dict(payload: Any, url: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ApiError(f"{url} returned JSON in an unexpected shape.")
    return payload
