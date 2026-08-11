"""The ``weather`` command: argument handling and presentation only.

Every HTTP concern lives in ``WeatherService``. This class would work unchanged
against a different weather provider.
"""

from __future__ import annotations

from ..services.weather_service import WeatherReport, WeatherService
from .base import Command, CommandResult


class WeatherCommand(Command):
    name = "weather"
    usage = "weather <location>"
    description = "Show current conditions for any town, city, or region."
    category = "Lookups"
    aliases = ("forecast",)

    def __init__(self, service: WeatherService) -> None:
        self._service = service

    def execute(self, args: str) -> CommandResult:
        location = self.require_args(args)
        return CommandResult(format_report(self._service.current(location)))


def format_report(report: WeatherReport) -> str:
    lines = [
        f"Weather for {report.location.display_name}",
        f"  Condition   {report.condition}",
        f"  Temperature {report.temperature:g}{report.temperature_unit}"
        f" (feels like {report.feels_like:g}{report.temperature_unit})",
        f"  Humidity    {report.humidity}%",
        f"  Wind        {report.wind_speed:g} {report.wind_unit}",
    ]
    if report.observed_at:
        lines.append(f"  Observed    {report.observed_at.replace('T', ' ')} local time")
    return "\n".join(lines)
