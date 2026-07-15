"""Guard test: every HAFISCAL_* env flag in the code has a registry entry.

Keeps ``Code/HA-Models/docs/ENV_FLAGS.md`` complete forever (plan:
``plans/20260611_env-flag-registry.md``). Pure-stdlib regex scan — imports no
repo code, runs in well under a second.

Scan design (decided during the env-flag-registry plan's Phase-A inventory, 2026-06-11):
    The scan matches **any quoted ``HAFISCAL_[A-Z0-9_]+`` string literal** in
    the scanned files, NOT only literals adjacent to an ``os.environ`` /
    ``os.getenv`` call. Rationale: adjacency regexes miss real read sites that
    go through indirection —

      * ``do_all.py``'s ``_env_run('HAFISCAL_RUN_STEP_1', ...)`` wrapper (the
        ``os.environ.get`` lives inside ``_env_run``; five RUN_STEP flags have
        no direct-pattern read site at all);
      * module-constant indirection such as ``solution_cache/cache.py``'s
        ``USE_CACHE_ENV_VAR = "HAFISCAL_USE_SOLUTION_CACHE"`` read later via
        ``os.environ.get(USE_CACHE_ENV_VAR, "0")``;
      * flag-list tuples (``solution_cache/keys.py`` cache-key whitelist,
        ``welfare6_tm_vs_mc_guard_test.py`` save/restore harness) consumed by
        comprehensions elsewhere in the module.

    Quoted-literal matching is also os-alias-agnostic for free (the codebase
    uses ``import os as _os`` / ``_os_early`` / ``_os_aggsh`` etc., so no
    pattern may anchor on ``os.``). The cost is potential over-matching
    (write-only / mention-only literals look like reads); as of 2026-06-11 the
    quoted-literal scan finds exactly the 118 inventoried flags with zero
    false positives, so ``IGNORE_LITERALS`` starts empty. If a quoted
    HAFISCAL_* literal that is genuinely not an env flag ever appears (e.g. a
    log label), add it to ``IGNORE_LITERALS`` with a comment instead of
    weakening the pattern.

Assertions:
    1. completeness — every scanned flag has a ``### HAFISCAL_<NAME>`` heading
       in the registry (a new flag without an entry fails the suite);
    2. no zombies — every heading with Status ``live`` or ``diagnostic``
       appears in the scan (``deprecated`` / ``archived-only`` exempt, e.g.
       the two write-/print-only zombies HAFISCAL_RUN_ONLY_SHOCK and
       HAFISCAL_STEP5_SCOPE), unless listed in ``ALLOWED_DYNAMIC``;
    3. structure — every entry carries the required fields and a valid Status,
       and no flag has two headings.

Scope: ``Code/HA-Models/**/*.py`` excluding ``*_archive/`` directories,
``__pycache__``, and this file itself (it names flags in its own docstring
and would otherwise have to registry-document its examples).
"""

import re
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
HA_MODELS = THIS_FILE.parent
REGISTRY = HA_MODELS / "docs" / "ENV_FLAGS.md"

# Flags whose names are constructed dynamically (f-strings/concat) and are
# therefore invisible to the literal scan, yet legitimately Status live.
# None known today (Phase-A inventory found no dynamic construction) — the
# hook must exist per the plan. Entries here are exempted from assertion 2.
ALLOWED_DYNAMIC = []

# Quoted HAFISCAL_* literals that are NOT environment flags (none today; see
# module docstring before adding anything here).
IGNORE_LITERALS = set()

_FLAG_LITERAL = re.compile(r"""['"](HAFISCAL_[A-Z0-9_]+)['"]""")
_HEADING = re.compile(r"^### (HAFISCAL_[A-Z0-9_]+)\s*$", re.MULTILINE)
_STATUS = re.compile(r"\*\*Status:\*\*\s*(\S+)")

VALID_STATUS = {"live", "diagnostic", "deprecated", "archived-only"}
REQUIRED_FIELDS = (
    "**Default:**",
    "**Values:**",
    "**Status:**",
    "**Read by:**",
    "**Purpose:**",
    "**Refs:**",
)


def _scan_code_flags():
    """Return {flag_name: sorted list of relative file paths} from the scan."""
    found = {}
    for path in HA_MODELS.rglob("*.py"):
        rel = path.relative_to(HA_MODELS)
        parts = rel.parts
        if any(d == "__pycache__" or d.endswith("_archive") for d in parts[:-1]):
            continue
        if path.resolve() == THIS_FILE:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _FLAG_LITERAL.finditer(text):
            name = match.group(1)
            if name in IGNORE_LITERALS:
                continue
            found.setdefault(name, set()).add(str(rel))
    return {name: sorted(files) for name, files in found.items()}


def _parse_registry():
    """Return ordered list of (flag_name, entry_block_text) from ENV_FLAGS.md."""
    assert REGISTRY.is_file(), f"registry file missing: {REGISTRY}"
    text = REGISTRY.read_text(encoding="utf-8")
    headings = list(_HEADING.finditer(text))
    entries = []
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        # An entry block ends at the next ### heading or the next ## section.
        # (r"\n## " cannot match a "\n### " heading: the char after "##" there
        # is "#", not a space.)
        block = text[match.start():end]
        section_break = re.search(r"\n## ", block)
        if section_break:
            block = block[: section_break.start() + 1]
        entries.append((match.group(1), block))
    return entries


def test_registry_completeness_no_zombies_and_structure():
    scanned = _scan_code_flags()
    entries = _parse_registry()
    registered = [name for name, _ in entries]
    registered_set = set(registered)

    problems = []

    # 3a. no duplicate headings
    dupes = sorted({n for n in registered if registered.count(n) > 1})
    if dupes:
        problems.append(f"duplicate registry headings: {dupes}")

    # 3b. required fields + valid Status per entry
    status_by_flag = {}
    for name, block in entries:
        missing = [f for f in REQUIRED_FIELDS if f not in block]
        if missing:
            problems.append(f"{name}: missing required field(s) {missing}")
        m = _STATUS.search(block)
        status = m.group(1) if m else None
        status_by_flag[name] = status
        if status not in VALID_STATUS:
            problems.append(
                f"{name}: Status {status!r} not in {sorted(VALID_STATUS)}")

    # 1. completeness: every scanned flag is registered
    unregistered = sorted(set(scanned) - registered_set)
    for name in unregistered:
        problems.append(
            f"flag {name} found in code ({', '.join(scanned[name][:3])}"
            f"{', ...' if len(scanned[name]) > 3 else ''}) but has no "
            f"'### {name}' entry in {REGISTRY.name} — add one (see the "
            f"format legend at the top of the registry)")

    # 2. no zombies: live|diagnostic entries must appear in the scan
    for name, status in status_by_flag.items():
        if status in ("live", "diagnostic") and name not in scanned \
                and name not in ALLOWED_DYNAMIC:
            problems.append(
                f"registry entry {name} has Status {status!r} but no quoted "
                f"literal in scanned code — flip its Status to 'deprecated'/"
                f"'archived-only', delete the entry, or (if the name is "
                f"dynamically constructed) add it to ALLOWED_DYNAMIC")

    assert not problems, (
        f"{len(problems)} env-flag registry problem(s):\n  - "
        + "\n  - ".join(problems)
    )
    # Sanity floor: the 2026-06-11 inventory registered 118 flags; a scan
    # suddenly finding almost nothing means the scan itself broke.
    assert len(scanned) >= 100, (
        f"scan found only {len(scanned)} flags — scan scope/pattern broken?")
