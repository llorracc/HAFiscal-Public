#!/usr/bin/env python3
"""Generated tables in the revision memo: marker injection + drift check (C6 of
plans/20260828-1130h_infrastructure-lessons-implementation_plan.md, as reshaped by the prior-art review of 2026-08-28:
generator + injector + drift guard, no style document -- the format rulings live in waterfall_table.py's docstring and
in the presenting plan's section 5e).

The memo carries every generated block between HTML-comment markers, invisible when rendered:

    <!-- BEGIN generated: chain-table -->
    ```text
    ...
    ```
    <!-- END generated: chain-table -->

`inject` regenerates each registered block from its inputs and rewrites the memo in place; `check` regenerates and
diffs without writing (exit 1 on drift) -- what test_memo_tables.py runs, so a changed input table without a
regenerated memo, or a hand edit inside the markers, fails the suite. Numbers inside the markers are never edited by
hand: change the inputs (or the generator's explicit tables) and inject.

Usage:
  python memo_tables.py check  [--memo FILE] [--tables DIR]
  python memo_tables.py inject [--memo FILE] [--tables DIR] [--dry-run]
Registered blocks (TABLES): chain-table = waterfall_table.memo_block (section 1.2 of the v3 memo).
"""
import argparse, difflib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import waterfall_table as wt  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MEMO_DEFAULT = os.path.join(REPO_ROOT, "conclusions_private", "2026-08-27_revision-memo_v3_original-code.md")
TABLES = {"chain-table": wt.memo_block}   # name -> generator(tables_dir=None) -> block text ending with a newline
MissingInputs = wt.MissingInputs


def markers(name):
    return f"<!-- BEGIN generated: {name} -->", f"<!-- END generated: {name} -->"


def _span(text, name):
    """(start, end) of the region between the markers: after the BEGIN line's newline, up to the END marker."""
    b, e = markers(name)
    nb, ne = text.count(b), text.count(e)
    if (nb, ne) != (1, 1):
        raise ValueError(f"expected exactly one {b!r} and one {e!r}; found {nb} and {ne}")
    i = text.index(b) + len(b)
    if text[i:i + 1] != "\n":
        raise ValueError(f"{b!r} must end its line")
    j = text.index(e)
    if j < i:
        raise ValueError(f"{e!r} precedes {b!r}")
    return i + 1, j


def extract(text, name):
    """The block currently between the markers (the END marker starts its own line, so the block ends with a newline)."""
    i, j = _span(text, name)
    return text[i:j]


def replace(text, name, block):
    """`text` with the region between the markers replaced by `block`; the markers themselves stay."""
    i, j = _span(text, name)
    if not block.endswith("\n"):
        block += "\n"
    return text[:i] + block + text[j:]


def read(path):
    return open(path, encoding="utf-8", newline="").read()


def drift(memo_path=MEMO_DEFAULT, tables_dir=None, names=None):
    """[(name, current, generated)] for the registered blocks whose memo text differs from the regenerated one
    (MissingInputs propagates: without the inputs there is nothing to compare)."""
    text = read(memo_path)
    out = []
    for name in names or TABLES:
        gen = TABLES[name](tables_dir)
        cur = extract(text, name)
        if cur != gen:
            out.append((name, cur, gen))
    return out


def unified(name, cur, gen, memo_path=MEMO_DEFAULT):
    return "".join(difflib.unified_diff(cur.splitlines(True), gen.splitlines(True),
                                        f"{memo_path} [{name}]", f"generated [{name}]"))


def inject(memo_path=MEMO_DEFAULT, tables_dir=None, dry_run=False):
    """Rewrite every registered block in place; returns whether the memo changed (nothing is written on --dry-run)."""
    text = read(memo_path)
    new = text
    for name, gen in TABLES.items():
        new = replace(new, name, gen(tables_dir))
    changed = new != text
    if changed and not dry_run:
        with open(memo_path, "w", encoding="utf-8", newline="") as f:
            f.write(new)
    return changed


def main(argv=None):
    ap = argparse.ArgumentParser(description="generated memo tables: inject between the markers, or check for drift")
    ap.add_argument("cmd", choices=("check", "inject"))
    ap.add_argument("--memo", default=MEMO_DEFAULT)
    ap.add_argument("--tables", default=None, help="Tables root holding the arms (waterfall_table.resolve_tables_dir)")
    ap.add_argument("--dry-run", action="store_true", help="inject: report whether the memo would change, write nothing")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        bad = drift(a.memo, a.tables)
        for name, cur, gen in bad:
            sys.stdout.write(unified(name, cur, gen, a.memo))
        print(f"{'DRIFT' if bad else 'OK'}: {len(TABLES) - len(bad)}/{len(TABLES)} generated block(s) in {a.memo} "
              f"match the generator")
        return 1 if bad else 0
    changed = inject(a.memo, a.tables, a.dry_run)
    print(f"{a.memo}: {'would change' if a.dry_run and changed else 'updated' if changed else 'unchanged'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
