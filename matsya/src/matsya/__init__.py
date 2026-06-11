"""Matsya — CLI and Python API for the Matsya research RAG.

Public API
----------
.. autofunction:: ask
.. autofunction:: search
.. autofunction:: sessions
.. autofunction:: session_history
"""

from __future__ import annotations

import os
from typing import Any

from matsya.client import MatsyaClient
from matsya.config import load_config

__version__ = "0.1.0"

__all__ = ["ask", "search", "sessions", "session_history"]


def _make_client() -> MatsyaClient:
    """Build a :class:`MatsyaClient` from config file + env vars."""
    cfg = load_config()
    token = cfg["token"]
    if not token:
        raise RuntimeError(
            "No Matsya token found.  Run `matsya configure` or set "
            "the MATSYA_TOKEN environment variable."
        )
    return MatsyaClient(
        token=token,
        server_url=cfg["server"],
        anthropic_key=os.environ.get("MATSYA_ANTHROPIC_KEY"),
    )


def ask(
    query: str,
    *,
    session: str | None = None,
    bst: bool = False,
    boost: dict[str, float] | None = None,
    k: int = 15,
    group: str = "Bellman-DDSL",
    model: str = "claude-opus-4-7",
    think: bool = False,
    temperature: float = 0.2,
    context_turns: int = 5,
    messages: list[dict[str, str]] | None = None,
) -> str:
    """Ask Matsya a question and get an LLM-generated answer.

    Parameters
    ----------
    query : str
        The question to ask.
    session : str, optional
        Named session for stateful multi-turn conversation.
    bst : bool
        Shorthand for ``boost={"BufferStockTheory": 100}, think=True``.
    boost : dict, optional
        Mapping of repository names to retrieval weight multipliers.
    k : int
        Number of chunks to retrieve (default 15).
    group : str
        Repository group to search (default ``"Bellman-DDSL"``).
    model : str
        LLM model identifier.
    think : bool
        Enable extended thinking (Claude only).
    temperature : float
        Sampling temperature 0–1 (default 0.2).
    context_turns : int
        Max prior turns to include in session context (default 5).
    messages : list[dict], optional
        Full message history for stateless multi-turn chat.  Each dict
        must have ``"role"`` and ``"content"`` keys.

    Returns
    -------
    str
        The LLM answer text.
    """
    if bst:
        boost = boost or {}
        boost["BufferStockTheory"] = 100
        think = True

    client = _make_client()

    if session:
        resp = client.session_chat(
            session_name=session,
            query=query,
            k=k,
            group=group,
            model=model,
            boost=boost,
            think=think,
            temperature=temperature,
            context_turns=context_turns,
        )
        return resp.get("answer", "")

    if messages is not None:
        msgs = list(messages)
    else:
        msgs = [{"role": "user", "content": query}]

    resp = client.chat(
        messages=msgs,
        k=k,
        group=group,
        model=model,
        boost=boost,
        think=think,
        temperature=temperature,
    )
    return resp.get("answer", "")


def search(
    query: str,
    *,
    k: int = 15,
    group: str = "Bellman-DDSL",
    boost: dict[str, float] | None = None,
    balanced: bool = False,
) -> list[dict[str, Any]]:
    """Run a vector search and return matching chunks (no LLM).

    Returns a list of dicts with keys ``text``, ``score``, ``path``,
    ``repo``.
    """
    client = _make_client()
    return client.search(query, k=k, group=group, boost=boost, balanced=balanced)


def sessions() -> list[dict[str, Any]]:
    """List the authenticated user's sessions."""
    client = _make_client()
    return client.list_sessions()


def session_history(name: str) -> list[dict[str, Any]]:
    """Return the turns for a named session."""
    client = _make_client()
    resp = client.get_session(name)
    return resp.get("turns", [])
