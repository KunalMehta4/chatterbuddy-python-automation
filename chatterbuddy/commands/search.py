"""The ``search`` command."""

from __future__ import annotations

from ..services.search_service import SearchResult, SearchService
from ..utils.formatting import truncate
from .base import Command, CommandResult

SNIPPET_WIDTH = 150


class SearchCommand(Command):
    name = "search"
    usage = "search <query>"
    description = "Search the web and print the top results."
    category = "Lookups"
    aliases = ("find",)

    def __init__(self, service: SearchService) -> None:
        self._service = service

    def execute(self, args: str) -> CommandResult:
        query = self.require_args(args)
        results = self._service.search(query)
        if not results:
            return CommandResult(f"No results for {query!r}.")
        return CommandResult(format_results(query, self._service.provider_name, results))


def format_results(query: str, provider: str, results: list[SearchResult]) -> str:
    blocks = [f"Results for {query!r} (via {provider})", ""]
    for position, result in enumerate(results, start=1):
        blocks.append(f"{position}. {result.title}")
        if result.snippet:
            blocks.append(f"   {truncate(result.snippet, SNIPPET_WIDTH)}")
        blocks.append(f"   {result.url}")
        blocks.append("")
    return "\n".join(blocks).rstrip()
