"""Web search behind a swappable provider interface.

The interface is not speculative architecture. While this project was being
built, Brave moved its Search API off a card-free free tier, Google closed its
Custom Search JSON API to new customers, and Microsoft retired the Bing Search
API. A search feature wired directly to one vendor is a feature that breaks.

Two providers ship:

* ``WikipediaSearchProvider`` needs no key, so ``search`` works on a fresh clone.
* ``TavilySearchProvider`` performs real web search and is selected
  automatically when ``TAVILY_API_KEY`` is set.

Adding a third is one class and one line in ``build_search_provider``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Protocol

from ..config import AppConfig
from ..errors import ApiError, ConfigurationError, ValidationError
from .http_client import HttpClient

WIKIPEDIA_URL = "https://en.wikipedia.org/w/api.php"
TAVILY_URL = "https://api.tavily.com/search"

_HTML_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class SearchResult:
    title: str
    snippet: str
    url: str


class SearchProvider(Protocol):
    """Structural interface for a search backend.

    A ``Protocol`` rather than an abstract base class: providers only need the
    right shape, not a shared ancestor.
    """

    name: str

    def search(self, query: str, limit: int) -> list[SearchResult]: ...


class WikipediaSearchProvider:
    """Keyless default, backed by the MediaWiki search API."""

    name = "Wikipedia"

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def search(self, query: str, limit: int) -> list[SearchResult]:
        payload = self._http.get_json(
            WIKIPEDIA_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
                "utf8": 1,
            },
        )
        hits = _dig(payload, "query", "search")
        if hits is None:
            raise ApiError("The Wikipedia response did not contain a result list.")

        results: list[SearchResult] = []
        for hit in hits[:limit]:
            if not isinstance(hit, dict):
                continue
            page_id = hit.get("pageid")
            results.append(
                SearchResult(
                    title=str(hit.get("title", "Untitled")),
                    # Snippets arrive as HTML with the matched terms wrapped in
                    # spans, which is noise in a terminal.
                    snippet=_strip_html(str(hit.get("snippet", ""))),
                    url=(
                        f"https://en.wikipedia.org/?curid={page_id}"
                        if page_id is not None
                        else "https://en.wikipedia.org"
                    ),
                )
            )
        return results


class TavilySearchProvider:
    """General web search. Enabled by setting ``TAVILY_API_KEY``."""

    name = "Tavily"

    def __init__(self, http: HttpClient, api_key: str) -> None:
        if not api_key:
            raise ConfigurationError(
                "TAVILY_API_KEY is empty. Remove it from .env to fall back to Wikipedia search."
            )
        self._http = http
        self._api_key = api_key

    def search(self, query: str, limit: int) -> list[SearchResult]:
        payload = self._http.post_json(
            TAVILY_URL,
            payload={"query": query, "max_results": limit},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ApiError("The Tavily response did not contain a result list.")

        results: list[SearchResult] = []
        for hit in payload["results"][:limit]:
            if not isinstance(hit, dict):
                continue
            results.append(
                SearchResult(
                    title=str(hit.get("title", "Untitled")),
                    snippet=_strip_html(str(hit.get("content", ""))),
                    url=str(hit.get("url", "")),
                )
            )
        return results


class SearchService:
    """Validates the query, delegates to a provider, and reports which one ran."""

    def __init__(self, provider: SearchProvider, *, limit: int = 5) -> None:
        self._provider = provider
        self._limit = limit

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def search(self, query: str) -> list[SearchResult]:
        cleaned = " ".join(query.split())
        if len(cleaned) < 2:
            raise ValidationError("Give me at least two characters to search for.")
        return self._provider.search(cleaned, self._limit)


def build_search_provider(http: HttpClient, config: AppConfig) -> SearchProvider:
    """Pick a provider from configuration: a key upgrades you, its absence does
    not break you."""
    if config.tavily_api_key:
        return TavilySearchProvider(http, config.tavily_api_key)
    return WikipediaSearchProvider(http)


def _strip_html(text: str) -> str:
    return " ".join(html.unescape(_HTML_TAG.sub("", text)).split())


def _dig(payload: Any, *keys: str) -> list[Any] | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, list) else None
