"""Command-line interface for Matsya.

Entry point registered as ``matsya`` in pyproject.toml.
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from typing import Any, NoReturn

from matsya.client import (
    AuthenticationError,
    ContextTooLargeError,
    MatsyaClient,
    MatsyaError,
    RateLimitError,
)
from matsya.config import load_config, save_config

DEFAULT_K = 15
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_GROUP = "Bellman-DDSL"
DEFAULT_TEMPERATURE = 0.2
RESULT_TEXT_LIMIT = 1000


# ── Output helpers ─────────────────────────────────────────────────


def _bar(width: int = 70) -> str:
    return "=" * width


def _print_search_results(
    results: list[dict[str, Any]], query: str
) -> None:
    print(f"Query: {query}")
    print(_bar())
    for i, r in enumerate(results, 1):
        score = r.get("score", 0.0)
        path = r.get("path", "?")
        print(f"\n--- Result {i} (score: {score:.3f}) ---")
        print(f"Source: {path}")
        print()
        text = r.get("text", "")
        print(text[:RESULT_TEXT_LIMIT] + "..." if len(text) > RESULT_TEXT_LIMIT else text)
        print()


def _print_chat_answer(
    answer: str,
    sources: list[dict[str, Any]],
    query: str,
) -> None:
    print(_bar())
    print(f"Query: {query}")
    print(_bar())
    print()
    print(answer)
    print()
    print(_bar())
    print(f"Sources ({len(sources)} chunks):")
    for r in sources:
        score = r.get("score", 0.0)
        path = r.get("path", "?")
        print(f"  [{score:.3f}] {path}")


def _print_session_list(sessions: list[dict[str, Any]]) -> None:
    if not sessions:
        print("No sessions found.")
        return
    name_w = max(len(s.get("name", "")) for s in sessions)
    name_w = max(name_w, 4)
    print(f"{'Name':<{name_w}}  {'Turns':>5}  Last active")
    print(f"{'-' * name_w}  {'-' * 5}  {'-' * 20}")
    for s in sessions:
        name = s.get("name", "?")
        turns = s.get("turn_count", 0)
        last = s.get("last_active", "—")
        print(f"{name:<{name_w}}  {turns:>5}  {last}")


def _print_session_history(data: dict[str, Any]) -> None:
    name = data.get("name", "?")
    turns = data.get("turns", [])
    print(_bar())
    print(f"Session: {name}  ({len(turns)} turns)")
    print(_bar())
    for t in turns:
        turn_num = t.get("turn", "?")
        ts = t.get("timestamp", "")
        query = t.get("query", "")
        answer = t.get("answer", "")
        print(f"\n--- Turn {turn_num}  {ts} ---")
        print(f"Q: {query}")
        print(f"A: {answer}")


def _print_refine_result(data: dict[str, Any], query: str) -> None:
    converged = data.get("converged", False)
    iterations = data.get("iterations", [])
    final_yaml = data.get("final_yaml", "")

    print(_bar())
    print(f"REFINE: '{query}'")
    print(f"Iterations: {len(iterations)}")
    print(_bar())

    for it in iterations:
        n = it.get("iteration", "?")
        print(f"\n--- Iteration {n} ---")
        if "yaml_to_mdp" in it:
            print(it["yaml_to_mdp"])
        if "mdp_to_yaml" in it:
            print(it["mdp_to_yaml"])

    print()
    print(_bar())
    if converged:
        print(f"CONVERGED after {len(iterations)} round-trip(s)")
    else:
        print(f"Did NOT converge after {len(iterations)} round-trip(s)")
    print(_bar())
    print("\n--- Final YAML ---")
    print(final_yaml)


# ── Configure flow ─────────────────────────────────────────────────


def _run_configure() -> None:
    """Interactive first-run token setup."""
    print("Matsya — configure access token\n")
    token = input("Enter your Matsya access token: ").strip()

    if not token.startswith("msy_"):
        print(
            "Error: token must start with 'msy_'. "
            "Check the token you received and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    path = save_config(token)
    print(f"Token saved to {path}")
    print()
    print(
        "Note: Session-backed queries and answers are logged on the "
        "server for research and product improvement."
    )
    print()
    print('Ready! Try: matsya "What is a stage?" --llm')


# ── Client construction ───────────────────────────────────────────


def _build_client(quiet: bool = False) -> MatsyaClient:
    cfg = load_config()
    token = cfg["token"]
    if not token:
        print(
            "No token configured. Run `matsya configure` first, or set "
            "the MATSYA_TOKEN environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)
    return MatsyaClient(
        token=token,
        server_url=cfg["server"],
        anthropic_key=os.environ.get("MATSYA_ANTHROPIC_KEY"),
    )


# ── Subcommand handlers ───────────────────────────────────────────


def _handle_sessions(args: argparse.Namespace) -> None:
    client = _build_client(args.quiet)
    if args.show:
        try:
            data = client.get_session(args.show)
        except MatsyaError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        _print_session_history(data)
    else:
        try:
            data = client.list_sessions()
        except MatsyaError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        _print_session_list(data)


def _handle_query(args: argparse.Namespace) -> None:
    client = _build_client(args.quiet)

    boost_dict: dict[str, float] = {}
    for item in args.boost:
        if ":" not in item:
            print(
                f"Error: --boost requires REPO:FACTOR format, got: {item}",
                file=sys.stderr,
            )
            sys.exit(1)
        repo, _, factor_str = item.partition(":")
        try:
            factor = float(factor_str)
        except ValueError:
            print(
                f"Error: --boost factor must be a number, got: {factor_str}",
                file=sys.stderr,
            )
            sys.exit(1)
        boost_dict[repo] = factor

    if args.BST:
        boost_dict["BufferStockTheory"] = 100
        args.think = True

    if args.balanced and args.k == DEFAULT_K:
        args.k = 30

    boost = boost_dict or None

    # --no-llm overrides the default --llm=True
    use_llm = args.llm and not args.no_llm
    # --no-think overrides the default --think=True
    args.think = args.think and not args.no_think

    try:
        if args.refine:
            _do_refine(client, args, boost)
        elif use_llm:
            _do_chat(client, args, boost)
        else:
            _do_search(client, args, boost)
    except AuthenticationError as exc:
        print(f"\n{exc}", file=sys.stderr)
        sys.exit(1)
    except RateLimitError as exc:
        print(f"\n{exc}", file=sys.stderr)
        sys.exit(1)
    except ContextTooLargeError as exc:
        print(f"\n⚠️  {exc}", file=sys.stderr)
        sys.exit(1)
    except MatsyaError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)


def _do_search(
    client: MatsyaClient,
    args: argparse.Namespace,
    boost: dict[str, float] | None,
) -> None:
    if not args.quiet:
        print("Searching...", file=sys.stderr)
    results = client.search(
        args.query,
        k=args.k,
        group=args.group,
        boost=boost,
        balanced=args.balanced,
    )
    _print_search_results(results, args.query)


def _do_chat(
    client: MatsyaClient,
    args: argparse.Namespace,
    boost: dict[str, float] | None,
) -> None:
    if args.session:
        if not args.quiet:
            print(
                f"Querying session '{args.session}'...", file=sys.stderr
            )
        resp = client.session_chat(
            session_name=args.session,
            query=args.query,
            k=args.k,
            group=args.group,
            model=args.model,
            boost=boost,
            think=args.think,
            temperature=args.temperature,
            context_turns=5,
        )
    else:
        if not args.quiet:
            print(f"Calling {args.model}...", file=sys.stderr)
        messages = [{"role": "user", "content": args.query}]
        resp = client.chat(
            messages=messages,
            k=args.k,
            group=args.group,
            model=args.model,
            boost=boost,
            balanced=args.balanced,
            think=args.think,
            temperature=args.temperature,
        )

    answer = resp.get("answer", "")
    sources = resp.get("sources", [])
    _print_chat_answer(answer, sources, args.query)


def _do_refine(
    client: MatsyaClient,
    args: argparse.Namespace,
    boost: dict[str, float] | None,
) -> None:
    if not args.quiet:
        print(
            f"Refining (max {args.max_iter} iterations)...",
            file=sys.stderr,
        )
    resp = client.refine(
        query=args.query,
        k=args.k,
        group=args.group,
        model=args.model,
        max_iter=args.max_iter,
        session=args.session,
    )
    _print_refine_result(resp, args.query)


# ── Argument parser ────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="matsya",
        description="Matsya — research copilot for modular dynamic programming.",
        epilog=textwrap.dedent("""\
            WHAT MATSYA IS
              A specialist oracle for modular dynamic programming, grounded
              in a curated knowledge base of DDSL theory, dolo-plus syntax,
              DP textbooks, canonical stage examples, formal MDPs, and
              research papers (including BufferStockTheory).

              Matsya is NOT a general-purpose chat or coding tool. Use it
              alongside a local coding agent (Claude Code, Cursor, etc.) —
              the local agent handles implementation, matsya provides the
              DP domain knowledge.

            TWO MODES
              1. Translate: convert between dolo-plus YAML and formal MDPs
                 matsya "Write the dolo-plus YAML for a consumption-savings stage"
                 matsya "Translate this stage YAML to a formal MDP: ..."

              2. Theory Q&A: ask about DP theory, DDSL concepts, perch/stage
                 structure, convergence conditions, or the indexed literature
                 matsya "What is a stage in DDSL?"
                 matsya "How do periods compose stages?"

            SESSIONS (multi-turn model development)
              Use --session to maintain context across queries:
                 matsya "Write cons_stage YAML" --session my-model
                 matsya "Now add portfolio choice" --session my-model
                 matsya sessions                    # list sessions
                 matsya sessions --show my-model    # view history

            NOTATION
              Matsya understands standard economics notation and modular-DDSL
              perch notation (prec/succ subscripts, operator composition).
              By default it uses whatever feels natural. To get strict
              modular-DDSL notation, add "please write your response using
              modular-DDSL notation" to your query. This produces:
                spaces:    X_prec, X, X_succ (sans-serif)
                elements:  x_prec, x, x_succ (italic)
                functions: v, g, r (upright roman)
                operators: B, I, T = I . B (blackboard bold)

            TIPS
              - Short, focused queries work best. Don't paste whole papers.
              - Break big questions into session turns.
              - Use --BST to surface BufferStockTheory content.
              - Use --no-llm for raw vector search (fast, no LLM cost).

            SETUP
              matsya configure          # paste your access token (one time)
              export MATSYA_TOKEN=...   # alternative: env variable

            EXAMPLES
              matsya "What is a stage?"
              matsya "explain growth impatience" --BST
              matsya "Write cons_stage YAML" --session my-model
              matsya "cons-savings IID" --refine
              matsya sessions --show my-model
              matsya configure

            Full docs: https://github.com/econ-ark/matsya
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # -- default: query mode (positional) -----------------------------------
    parser.add_argument(
        "query",
        nargs="?",
        help="Your question or search query (or 'configure' / 'sessions')",
    )
    parser.add_argument(
        "--llm", action="store_true", default=True,
        help="Generate an LLM answer (default: on). Use --no-llm for raw search.",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Return raw vector search results without calling an LLM",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"LLM model for --llm (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--k", type=int, default=DEFAULT_K,
        help=f"Number of chunks to retrieve (default: {DEFAULT_K})",
    )
    parser.add_argument(
        "--group", default=DEFAULT_GROUP,
        help=f"Repository group to search (default: {DEFAULT_GROUP})",
    )
    parser.add_argument(
        "--boost", action="append", default=[],
        metavar="REPO:FACTOR",
        help=(
            "Multiply retrieval weight for REPO by FACTOR. "
            "Repeatable. E.g. --boost BufferStockTheory:100"
        ),
    )
    parser.add_argument(
        "--BST", action="store_true",
        help="Shortcut for --boost BufferStockTheory:100 --think",
    )
    parser.add_argument(
        "--balanced", action="store_true",
        help="Balanced retrieval across indexed repos",
    )
    parser.add_argument(
        "--think", action="store_true", default=True,
        help="Extended thinking is on by default. Use --no-think to disable.",
    )
    parser.add_argument(
        "--no-think", action="store_true",
        help="Disable extended thinking.",
    )
    parser.add_argument(
        "--temperature", type=float, default=DEFAULT_TEMPERATURE,
        help=f"Sampling temperature 0-1 (default: {DEFAULT_TEMPERATURE})",
    )
    parser.add_argument(
        "--session", metavar="NAME",
        help="Use a named session for stateful conversation",
    )
    parser.add_argument(
        "--refine", action="store_true",
        help="YAML<->MDP round-trip refinement mode",
    )
    parser.add_argument(
        "--max-iter", type=int, default=3,
        help="Max refinement iterations for --refine (default: 3)",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress progress messages",
    )
    parser.add_argument(
        "--show", metavar="NAME",
        help="Show full history for a named session (use with 'sessions')",
    )

    return parser


# ── Entry point ────────────────────────────────────────────────────


def main() -> NoReturn | None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.query == "configure":
        _run_configure()
        return

    if args.query == "sessions":
        _handle_sessions(args)
        return

    if not args.query:
        parser.print_help()
        sys.exit(0)

    _handle_query(args)


if __name__ == "__main__":
    main()
