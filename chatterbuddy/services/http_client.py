"""A thin wrapper over ``requests`` that owns two responsibilities.

First, sensible defaults in one place: a shared session for connection reuse, a
timeout on every call (a request without a timeout can hang forever), and a
descriptive User-Agent, which the Wikipedia API asks for.

Second, and more importantly, translation. Everything that can go wrong on the
wire leaves this class as a ``ServiceError`` subclass, so no ``requests``
exception type ever reaches a command handler.
"""

from __future__ import annotations

from typing import Any

import requests

from .. import __version__
from ..errors import ApiError, NetworkError

DEFAULT_USER_AGENT = (
    f"ChatterBuddy/{__version__} (+https://github.com/KunalMehta4/chatterbuddy-python-automation)"
)


class HttpClient:
    """Performs JSON-over-HTTP requests and normalises the failure modes."""

    def __init__(
        self,
        *,
        timeout: float = 8.0,
        user_agent: str = DEFAULT_USER_AGENT,
        session: requests.Session | None = None,
    ) -> None:
        self._timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self._request("GET", url, params=params, headers=headers)

    def post_json(
        self,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self._request("POST", url, json=payload, headers=headers)

    def close(self) -> None:
        self._session.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        try:
            response = self._session.request(method, url, timeout=self._timeout, **kwargs)
        except requests.Timeout as exc:
            raise NetworkError(
                f"{_host(url)} did not respond within {self._timeout:g} seconds."
            ) from exc
        except requests.ConnectionError as exc:
            raise NetworkError(
                f"Could not reach {_host(url)}. Check your internet connection."
            ) from exc
        except requests.RequestException as exc:
            raise NetworkError(f"Request to {_host(url)} failed: {exc}") from exc

        self._raise_for_status(response, url)

        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(f"{_host(url)} returned a response that was not valid JSON.") from exc

    @staticmethod
    def _raise_for_status(response: requests.Response, url: str) -> None:
        code = response.status_code
        if 200 <= code < 300:
            return
        host = _host(url)
        if code == 429:
            raise ApiError(f"{host} is rate limiting requests. Wait a moment and try again.")
        if code == 401:
            raise ApiError(
                f"{host} rejected the credentials it was sent. Check the API key in your .env file."
            )
        if code == 403:
            # Worth separating from 401: a 403 on a keyless API almost always
            # means a proxy or firewall in the way, not a bad key. Discovered by
            # running this against a sandboxed network.
            raise ApiError(
                f"{host} refused the request (HTTP 403). If that API needs a key, check "
                "your .env file; a network proxy or firewall can also cause this."
            )
        if code == 404:
            raise ApiError(f"{host} has no endpoint at {url}.")
        if code >= 500:
            raise ApiError(f"{host} is having server trouble (HTTP {code}). Try again shortly.")
        raise ApiError(f"{host} returned an unexpected HTTP {code}.")


def _host(url: str) -> str:
    """Best-effort hostname for error messages, without importing urllib."""
    without_scheme = url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0] or url
