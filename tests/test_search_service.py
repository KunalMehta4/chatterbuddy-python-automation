"""Search has two interchangeable backends, so the tests cover both providers and
the rule that decides between them."""

from __future__ import annotations

import pytest
import responses

from chatterbuddy.config import AppConfig
from chatterbuddy.errors import ApiError, ConfigurationError, ValidationError
from chatterbuddy.services.search_service import (
    TAVILY_URL,
    WIKIPEDIA_URL,
    SearchService,
    TavilySearchProvider,
    WikipediaSearchProvider,
    build_search_provider,
)

WIKIPEDIA_HIT = {
    "query": {
        "search": [
            {
                "pageid": 4321,
                "title": "Property testing",
                # Wikipedia returns HTML with the matched terms marked up.
                "snippet": 'A <span class="searchmatch">property</span> &amp; its invariants',
            },
            {"pageid": 8765, "title": "Hypothesis (software)", "snippet": "A testing library"},
        ]
    }
}

TAVILY_HIT = {
    "results": [
        {
            "title": "Hypothesis documentation",
            "content": "Property-based testing for Python",
            "url": "https://hypothesis.readthedocs.io",
        }
    ]
}


@responses.activate
def test_wikipedia_provider_parses_results(http) -> None:
    responses.add(responses.GET, WIKIPEDIA_URL, json=WIKIPEDIA_HIT)

    results = WikipediaSearchProvider(http).search("property testing", 5)

    assert len(results) == 2
    assert results[0].title == "Property testing"
    assert results[0].url == "https://en.wikipedia.org/?curid=4321"


@responses.activate
def test_wikipedia_snippets_are_stripped_of_markup_and_entities(http) -> None:
    responses.add(responses.GET, WIKIPEDIA_URL, json=WIKIPEDIA_HIT)
    snippet = WikipediaSearchProvider(http).search("property testing", 5)[0].snippet
    assert snippet == "A property & its invariants"
    assert "<" not in snippet


@responses.activate
def test_wikipedia_request_carries_the_query_and_limit(http) -> None:
    responses.add(responses.GET, WIKIPEDIA_URL, json=WIKIPEDIA_HIT)
    WikipediaSearchProvider(http).search("property testing", 3)
    params = responses.calls[0].request.params
    assert params["srsearch"] == "property testing"
    assert params["srlimit"] == "3"


@responses.activate
def test_wikipedia_honours_the_limit_even_if_the_api_overshoots(http) -> None:
    responses.add(responses.GET, WIKIPEDIA_URL, json=WIKIPEDIA_HIT)
    assert len(WikipediaSearchProvider(http).search("property testing", 1)) == 1


@responses.activate
def test_no_matches_returns_an_empty_list(http) -> None:
    responses.add(responses.GET, WIKIPEDIA_URL, json={"query": {"search": []}})
    assert WikipediaSearchProvider(http).search("zzzzzz", 5) == []


@responses.activate
def test_an_unexpected_wikipedia_shape_becomes_an_api_error(http) -> None:
    responses.add(responses.GET, WIKIPEDIA_URL, json={"batchcomplete": ""})
    with pytest.raises(ApiError, match="result list"):
        WikipediaSearchProvider(http).search("anything", 5)


@responses.activate
def test_tavily_provider_parses_results_and_sends_the_key(http) -> None:
    responses.add(responses.POST, TAVILY_URL, json=TAVILY_HIT)

    results = TavilySearchProvider(http, "tvly-secret").search("hypothesis", 5)

    assert results[0].url == "https://hypothesis.readthedocs.io"
    assert responses.calls[0].request.headers["Authorization"] == "Bearer tvly-secret"


@responses.activate
def test_tavily_rejecting_the_key_becomes_a_readable_api_error(http) -> None:
    responses.add(responses.POST, TAVILY_URL, json={"detail": "unauthorized"}, status=401)
    with pytest.raises(ApiError, match="API key in your .env"):
        TavilySearchProvider(http, "wrong-key").search("hypothesis", 5)


def test_tavily_refuses_to_be_built_without_a_key(http) -> None:
    with pytest.raises(ConfigurationError, match="TAVILY_API_KEY"):
        TavilySearchProvider(http, "")


def test_provider_selection_defaults_to_wikipedia(http, tmp_path) -> None:
    """A fresh clone with no .env must still have a working search command."""
    provider = build_search_provider(http, AppConfig(data_dir=tmp_path))
    assert provider.name == "Wikipedia"


def test_provider_selection_prefers_tavily_when_a_key_is_present(http, tmp_path) -> None:
    config = AppConfig(data_dir=tmp_path, tavily_api_key="tvly-secret")
    assert build_search_provider(http, config).name == "Tavily"


def test_service_rejects_a_query_that_is_too_short(http) -> None:
    service = SearchService(WikipediaSearchProvider(http))
    with pytest.raises(ValidationError, match="two characters"):
        service.search("a")


@responses.activate
def test_service_collapses_whitespace_in_the_query(http) -> None:
    responses.add(responses.GET, WIKIPEDIA_URL, json=WIKIPEDIA_HIT)
    SearchService(WikipediaSearchProvider(http)).search("  property    testing  ")
    assert responses.calls[0].request.params["srsearch"] == "property testing"


@responses.activate
def test_service_passes_its_configured_limit_through(http) -> None:
    responses.add(responses.GET, WIKIPEDIA_URL, json=WIKIPEDIA_HIT)
    SearchService(WikipediaSearchProvider(http), limit=2).search("property testing")
    assert responses.calls[0].request.params["srlimit"] == "2"
