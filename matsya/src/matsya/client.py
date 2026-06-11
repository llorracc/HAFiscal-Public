"""Zero-dependency HTTP client for the Matsya API.

Uses only :mod:`urllib.request` — no ``requests``, ``httpx``, or other
third-party libraries.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

_TIMEOUT = 620  # LLM calls can be slow (server kills at 600s / 10 min)


class MatsyaError(Exception):
    """Base exception for Matsya API errors."""


class AuthenticationError(MatsyaError):
    """Raised on 401 — invalid or revoked token."""


class RateLimitError(MatsyaError):
    """Raised on 429 — rate limit exceeded."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ServerError(MatsyaError):
    """Raised on 5xx server errors."""


class ContextTooLargeError(MatsyaError):
    """Raised on 413 — prompt too large for the server to process."""


class MatsyaClient:
    """HTTP client for the Matsya RAG API.

    Parameters
    ----------
    token : str
        Personal access token (``msy_…``).
    server_url : str
        Base URL of the Matsya server.
    anthropic_key : str | None
        Optional BYOK Anthropic API key — sent via ``X-Anthropic-Key``
        header so the server uses it instead of its own key.
    """

    def __init__(
        self,
        token: str,
        server_url: str,
        anthropic_key: str | None = None,
    ) -> None:
        self.token = token
        self.server_url = server_url.rstrip("/")
        self.anthropic_key = anthropic_key

    # -- low-level request --------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Issue an HTTP request and return parsed JSON."""
        url = f"{self.server_url}{path}"
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if self.anthropic_key:
            headers["X-Anthropic-Key"] = self.anthropic_key

        data: bytes | None = None
        if body is not None:
            data = json.dumps(body).encode()

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            self._handle_http_error(exc)
        except urllib.error.URLError as exc:
            raise MatsyaError(
                f"Could not connect to {self.server_url}: {exc.reason}"
            ) from exc

        return {}  # unreachable, keeps mypy happy

    def _handle_http_error(self, exc: urllib.error.HTTPError) -> None:
        """Translate HTTP status codes into typed exceptions."""
        body = ""
        try:
            body = exc.read().decode()
        except Exception:
            pass

        detail = ""
        try:
            detail = json.loads(body).get("detail", body)
        except (json.JSONDecodeError, AttributeError):
            detail = body

        if exc.code == 401:
            raise AuthenticationError(
                "Authentication failed — check that your Matsya token is "
                "valid and has not been revoked.\n"
                "Run `matsya configure` to set a new token."
            ) from exc

        if exc.code == 413:
            raise ContextTooLargeError(
                f"Context too large:\n\n{detail}"
            ) from exc

        if exc.code == 429:
            retry_after: int | None = None
            ra_header = exc.headers.get("Retry-After") if exc.headers else None
            if ra_header:
                try:
                    retry_after = int(ra_header)
                except ValueError:
                    pass
            msg = "Rate limit exceeded."
            if retry_after:
                msg += f" Try again in {retry_after} seconds."
            raise RateLimitError(msg, retry_after=retry_after) from exc

        if exc.code >= 500:
            raise ServerError(
                f"Server error ({exc.code}): {detail or 'internal error'}"
            ) from exc

        raise MatsyaError(
            f"HTTP {exc.code}: {detail or exc.reason}"
        ) from exc

    # -- public API ---------------------------------------------------------

    def search(
        self,
        query: str,
        k: int = 15,
        group: str = "Bellman-DDSL",
        boost: dict[str, float] | None = None,
        balanced: bool = False,
    ) -> list[dict[str, Any]]:
        """Vector search — no LLM."""
        payload: dict[str, Any] = {
            "query": query,
            "k": k,
            "group": group,
            "balanced": balanced,
        }
        if boost:
            payload["boost"] = boost
        resp = self._request("POST", "/search", payload)
        return resp.get("results", [])

    def chat(
        self,
        messages: list[dict[str, str]],
        k: int = 15,
        group: str = "Bellman-DDSL",
        model: str = "claude-opus-4-7",
        boost: dict[str, float] | None = None,
        balanced: bool = False,
        think: bool = False,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Stateless chat — client sends full message history."""
        payload: dict[str, Any] = {
            "messages": messages,
            "k": k,
            "group": group,
            "model": model,
            "balanced": balanced,
            "think": think,
            "temperature": temperature,
        }
        if boost:
            payload["boost"] = boost
        return self._request("POST", "/chat", payload)

    def session_chat(
        self,
        session_name: str,
        query: str,
        k: int = 15,
        group: str = "Bellman-DDSL",
        model: str = "claude-opus-4-7",
        boost: dict[str, float] | None = None,
        think: bool = False,
        temperature: float = 0.2,
        context_turns: int = 5,
    ) -> dict[str, Any]:
        """Stateful session chat — server manages conversation history."""
        payload: dict[str, Any] = {
            "query": query,
            "k": k,
            "group": group,
            "model": model,
            "think": think,
            "temperature": temperature,
            "context_turns": context_turns,
        }
        if boost:
            payload["boost"] = boost
        path = f"/sessions/{urllib.parse.quote(session_name, safe='')}/chat"
        return self._request("POST", path, payload)

    def refine(
        self,
        query: str,
        k: int = 15,
        group: str = "Bellman-DDSL",
        model: str = "claude-opus-4-7",
        max_iter: int = 3,
        session: str | None = None,
    ) -> dict[str, Any]:
        """YAML<->MDP round-trip refinement."""
        payload: dict[str, Any] = {
            "query": query,
            "k": k,
            "group": group,
            "model": model,
            "max_iter": max_iter,
        }
        if session:
            payload["session"] = session
        return self._request("POST", "/refine", payload)

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return the authenticated principal's sessions."""
        return cast(list[dict[str, Any]], self._request("GET", "/sessions"))

    def get_session(self, name: str) -> dict[str, Any]:
        """Return the full Q&A history for a named session."""
        path = f"/sessions/{urllib.parse.quote(name, safe='')}"
        return self._request("GET", path)
