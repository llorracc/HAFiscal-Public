#!/usr/bin/env python3
"""Equation-tag registry checker for the dolo-plus integration effort.

Binds three artifact families together, machine-checked:

  * the math-derive docs (history/20260331-mathematical-derivations-*.md),
    which carry LaTeX equation tags of the form \\tag{name};
  * the canonical YAML spec (HAFiscal-doloplus-draft.yaml, STATUS: CANONICAL);
  * the code, which cites doc tags in comments/docstrings using the grammar
    math-derive[-appendix|-harm] followed by the parenthesized tag.

Registry: eqn_registry.yaml (same directory) — a YAML list of entries keyed
by a namespaced id (main:<tag>, appendix:<tag>, harm:<tag>, yaml:<block>).
Code bindings use (file, symbol, cite-string) — never line numbers — and are
resolved by AST walk, so the checker is drift-robust under edits and alarms
loudly on symbol renames.

Modes:
  (default)            forward + reverse checks + coverage report
  --strict             unregistered in-code citations become errors
  --bootstrap [-o F]   scrape docs + code citations into a draft registry
  --assert-inert F...  prove a working-tree file differs from HEAD only in
                       comments/docstrings (docstring-stripped ast.dump)

Plan: plans/20260611_doloplus-eqn-tag-registry.md (phase P1).
Master: plans/20260611_doloplus-integration-master.md.
"""

import argparse
import ast
import re
import subprocess
import sys
import warnings
from pathlib import Path

import yaml


def parse_python(source):
    """ast.parse, silencing escape-sequence warnings from scanned legacy files."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
        return ast.parse(source)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]

DOC_PATHS = {
    "main": "history/20260331-mathematical-derivations-TM-MC-convergence.md",
    "appendix": "history/20260331-mathematical-derivations-appendix.md",
    "harm": "history/20260331-mathematical-derivations-harmenberg.md",
}
CANONICAL_YAML = "HAFiscal-doloplus-draft.yaml"
DEFAULT_REGISTRY = HERE / "eqn_registry.yaml"

# Directories whose *.py files are scanned for in-code citations (reverse check).
SCAN_GLOBS = [
    "Code/HA-Models/FromPandemicCode/*.py",
    "Code/HA-Models/dolo_plus_validation/*.py",
]

NS_ORDER = ["main", "appendix", "harm", "yaml"]
PREFIX_TO_NS = {None: "main", "-appendix": "appendix", "-harm": "harm"}
CITE_RE = re.compile(r"math-derive(-appendix|-harm)? \(([A-Za-z0-9-]+)\)")
TAG_RE = re.compile(r"\\tag\{([^}]+)\}")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
VALID_STATUSES = {"bound", "code-only", "doc-only", "pending-decision"}


# ---------------------------------------------------------------------------
# Doc scraping
# ---------------------------------------------------------------------------

def slugify(text):
    """GitHub-style markdown heading anchor: lowercase, drop punctuation,
    spaces to hyphens.  '5. Euler Equation and EGM' -> '5-euler-equation-and-egm'."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def scan_doc(relpath):
    """Return (tags, anchors) for a markdown doc.

    tags: dict tag-name -> anchor of the nearest preceding heading (or None).
    anchors: set of all heading anchors in the doc.
    """
    text = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    tags, anchors = {}, set()
    current = None
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            current = slugify(m.group(1))
            anchors.add(current)
            continue
        for tag in TAG_RE.findall(line):
            tags.setdefault(tag, current)
    return tags, anchors


# ---------------------------------------------------------------------------
# Code scraping (AST symbol spans + citation scan)
# ---------------------------------------------------------------------------

def symbol_spans(tree):
    """Map dotted qualname -> (start_line, end_line) for every def/class."""
    spans = {}

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = prefix + child.name
                spans.setdefault(qual, (child.lineno, child.end_lineno))
                visit(child, qual + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    return spans


def enclosing_symbol(spans, lineno):
    """Innermost def/class containing a line; '<module>' if none."""
    best, best_size = "<module>", None
    for qual, (a, b) in spans.items():
        if a <= lineno <= b and (best_size is None or (b - a) < best_size):
            best, best_size = qual, b - a
    return best


def parse_file(relpath, cache):
    """Return (source_text, spans) for a repo-relative path, memoized.
    spans is None if the file does not parse as Python."""
    if relpath not in cache:
        source = (REPO_ROOT / relpath).read_text(encoding="utf-8")
        try:
            spans = symbol_spans(parse_python(source))
        except SyntaxError:
            spans = None
        cache[relpath] = (source, spans)
    return cache[relpath]


def scan_code_citations():
    """All in-code citations under SCAN_GLOBS.

    Returns a list of dicts: file (repo-relative), line, ns, tag, cite
    (the exact matched text), symbol (innermost enclosing def/class).
    """
    out = []
    cache = {}
    for pattern in SCAN_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            rel = path.relative_to(REPO_ROOT).as_posix()
            source, spans = parse_file(rel, cache)
            for lineno, line in enumerate(source.splitlines(), 1):
                for m in CITE_RE.finditer(line):
                    out.append({
                        "file": rel,
                        "line": lineno,
                        "ns": PREFIX_TO_NS[m.group(1)],
                        "tag": m.group(2),
                        "cite": m.group(0),
                        "symbol": enclosing_symbol(spans or {}, lineno),
                    })
    return out


# ---------------------------------------------------------------------------
# Canonical YAML helpers
# ---------------------------------------------------------------------------

def load_canonical_yaml():
    return yaml.safe_load((REPO_ROOT / CANONICAL_YAML).read_text(encoding="utf-8"))


def yaml_equation_blocks(data):
    """Dotted paths of every equation block (string leaf) under 'equations'."""
    blocks = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, val in node.items():
                walk(val, "%s.%s" % (path, key))
        elif isinstance(node, str):
            blocks.append(path)

    walk(data.get("equations", {}), "equations")
    return blocks


def resolve_yaml_ref(data, dotted):
    """Resolve a dotted path in the parsed canonical YAML; raise KeyError if absent."""
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(dotted)
        node = node[part]
    return node


# ---------------------------------------------------------------------------
# Forward + reverse checks
# ---------------------------------------------------------------------------

def load_registry(path):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("registry %s must be a YAML list of entries" % path)
    return data


def check_entry(entry, docs, canon, cache, errors):
    """Forward-check one registry entry; append messages to errors."""
    eid = entry.get("id")
    if not eid or ":" not in eid:
        errors.append("entry with missing/malformed id: %r" % (eid,))
        return
    ns, tag = eid.split(":", 1)
    if ns not in NS_ORDER:
        errors.append("%s: unknown namespace %r" % (eid, ns))
        return

    expected_doc = CANONICAL_YAML if ns == "yaml" else DOC_PATHS[ns]
    if entry.get("doc") != expected_doc:
        errors.append("%s: doc is %r, expected %r" % (eid, entry.get("doc"), expected_doc))

    status = entry.get("status")
    if status not in VALID_STATUSES:
        errors.append("%s: invalid status %r" % (eid, status))
    code = entry.get("code") or []
    anchor = entry.get("anchor")
    yaml_ref = entry.get("yaml_ref")

    if ns == "yaml":
        if not yaml_ref:
            errors.append("%s: yaml-namespace entry must carry a yaml_ref" % eid)
    else:
        doc_tags, doc_anchors = docs[ns]
        tag_in_doc = tag in doc_tags
        anchor_ok = False
        if anchor is not None:
            anchor_ok = anchor.lstrip("#") in doc_anchors
            if not anchor_ok:
                errors.append("%s: anchor %r not found among headings of %s"
                              % (eid, anchor, entry.get("doc")))
        # code-only means the cited tag has no doc-side counterpart (yet);
        # every other status must anchor into the doc somehow.
        if status != "code-only" and not tag_in_doc and not anchor_ok:
            errors.append("%s: tag not in doc and no resolving anchor" % eid)

        # Status consistency (honesty checks).
        if status == "bound":
            if not code:
                errors.append("%s: status bound but no code bindings" % eid)
            if not tag_in_doc:
                errors.append("%s: status bound but tag absent from doc" % eid)
        elif status == "code-only":
            if not code:
                errors.append("%s: status code-only but no code bindings" % eid)
            if tag_in_doc:
                errors.append("%s: status code-only but tag IS in doc (should be bound)" % eid)
        elif status == "doc-only" and code:
            errors.append("%s: status doc-only but has code bindings" % eid)

    if status == "pending-decision" and not entry.get("decision"):
        errors.append("%s: status pending-decision requires a decision id (D-NN)" % eid)

    if yaml_ref:
        try:
            resolve_yaml_ref(canon, yaml_ref)
        except KeyError:
            errors.append("%s: yaml_ref %r does not resolve in %s"
                          % (eid, yaml_ref, CANONICAL_YAML))

    for binding in code:
        bfile, bsym, bcite = binding.get("file"), binding.get("symbol"), binding.get("cite")
        if not bfile or not bcite:
            errors.append("%s: code binding missing file/cite: %r" % (eid, binding))
            continue
        if not (REPO_ROOT / bfile).is_file():
            errors.append("%s: bound file %s does not exist" % (eid, bfile))
            continue
        source, spans = parse_file(bfile, cache)
        if spans is None:
            errors.append("%s: bound file %s does not parse as Python" % (eid, bfile))
            continue
        if bsym in (None, "<module>"):
            span_text = source
        elif bsym in spans:
            a, b = spans[bsym]
            span_text = "\n".join(source.splitlines()[a - 1:b])
        else:
            suffix = [q for q in spans if q.split(".")[-1] == bsym]
            if len(suffix) == 1:
                a, b = spans[suffix[0]]
                span_text = "\n".join(source.splitlines()[a - 1:b])
            elif suffix:
                errors.append("%s: symbol %r ambiguous in %s (%s)"
                              % (eid, bsym, bfile, ", ".join(sorted(suffix))))
                continue
            else:
                errors.append("%s: symbol %r not found in %s (renamed?)" % (eid, bsym, bfile))
                continue
        if bcite not in span_text:
            errors.append("%s: cite %r not found within %s:%s"
                          % (eid, bcite, bfile, bsym or "<module>"))


def coverage_report(registry, docs, canon):
    """Print coverage; return the report lines."""
    lines = ["", "Coverage report:"]
    entries_by_ns = {ns: [] for ns in NS_ORDER}
    for entry in registry:
        eid = entry.get("id") or ""
        if ":" in eid:
            ns = eid.split(":", 1)[0]
            if ns in entries_by_ns:
                entries_by_ns[ns].append(entry)

    total_tags = total_bound = 0
    for ns in ("main", "appendix", "harm"):
        doc_tags = set(docs[ns][0])
        bound = {e["id"].split(":", 1)[1] for e in entries_by_ns[ns]
                 if e.get("code") and e["id"].split(":", 1)[1] in doc_tags}
        total_tags += len(doc_tags)
        total_bound += len(bound)
        pct = 100.0 * len(bound) / len(doc_tags) if doc_tags else 0.0
        lines.append("  %-9s %3d/%3d doc tags bound to code (%5.1f%%)"
                     % (ns + ":", len(bound), len(doc_tags), pct))
    pct = 100.0 * total_bound / total_tags if total_tags else 0.0
    lines.append("  %-9s %3d/%3d doc tags bound to code (%5.1f%%)"
                 % ("all docs:", total_bound, total_tags, pct))

    blocks = set(yaml_equation_blocks(canon))
    bound_blocks = {e.get("yaml_ref") for ns in ("main", "appendix", "harm")
                    for e in entries_by_ns[ns] if e.get("yaml_ref")} & blocks
    pct = 100.0 * len(bound_blocks) / len(blocks) if blocks else 0.0
    lines.append("  YAML:     %3d/%3d equation blocks bound to doc tags (%5.1f%%)"
                 % (len(bound_blocks), len(blocks), pct))
    print("\n".join(lines))
    return lines


def run_checks(registry_path, strict):
    registry = load_registry(registry_path)
    docs = {ns: scan_doc(p) for ns, p in DOC_PATHS.items()}
    canon = load_canonical_yaml()
    cache = {}
    errors, warnings = [], []

    seen = set()
    for entry in registry:
        eid = entry.get("id")
        if eid in seen:
            errors.append("duplicate id: %s" % eid)
        seen.add(eid)
        check_entry(entry, docs, canon, cache, errors)

    citations = scan_code_citations()
    unregistered = {}
    for c in citations:
        eid = "%s:%s" % (c["ns"], c["tag"])
        if eid not in seen:
            unregistered.setdefault(eid, []).append("%s:%d" % (c["file"], c["line"]))
    for eid, sites in sorted(unregistered.items()):
        msg = "citation %s not in registry (%s)" % (eid, "; ".join(sites))
        (errors if strict else warnings).append(msg)

    for msg in errors:
        print("ERROR: %s" % msg)
    for msg in warnings:
        print("WARNING: %s" % msg)
    print("\nChecked %d registry entries against %d in-code citation occurrences "
          "(%d unique namespaced tags cited)."
          % (len(registry), len(citations),
             len({(c["ns"], c["tag"]) for c in citations})))
    coverage_report(registry, docs, canon)
    if errors:
        print("\nFAIL: %d error(s), %d warning(s)." % (len(errors), len(warnings)))
        return 1
    print("\nOK: 0 errors, %d warning(s)." % len(warnings))
    return 0


# ---------------------------------------------------------------------------
# --bootstrap
# ---------------------------------------------------------------------------

def bootstrap(out_path):
    entries = {}
    tag_counts = {}
    for ns in ("main", "appendix", "harm"):
        tags, _anchors = scan_doc(DOC_PATHS[ns])
        tag_counts[ns] = len(tags)
        for tag, anchor in tags.items():
            entries["%s:%s" % (ns, tag)] = {
                "id": "%s:%s" % (ns, tag),
                "doc": DOC_PATHS[ns],
                "anchor": ("#" + anchor) if anchor else None,
                "yaml_ref": None,
                "code": [],
                "status": "doc-only",
                "decision": None,
            }

    citations = scan_code_citations()
    for c in citations:
        eid = "%s:%s" % (c["ns"], c["tag"])
        entry = entries.get(eid)
        if entry is None:
            entry = entries[eid] = {
                "id": eid,
                "doc": DOC_PATHS[c["ns"]],
                "anchor": None,
                "yaml_ref": None,
                "code": [],
                "status": "code-only",
                "decision": None,
            }
        binding = {"file": c["file"], "symbol": c["symbol"], "cite": c["cite"]}
        if binding not in entry["code"]:
            entry["code"].append(binding)
        if entry["status"] == "doc-only":
            entry["status"] = "bound"

    ordered = sorted(
        entries.values(),
        key=lambda e: (NS_ORDER.index(e["id"].split(":", 1)[0]), e["id"]),
    )
    text = yaml.safe_dump(ordered, sort_keys=False, width=110, allow_unicode=True)
    header = (
        "# Equation-tag registry: math-derive docs <-> canonical YAML <-> code.\n"
        "# Maintained by hand on top of a --bootstrap scrape; checked by\n"
        "# check_eqn_registry.py (run with --strict in CI / pytest).\n"
        "# Schema: plans/20260611_doloplus-eqn-tag-registry.md\n"
    )
    Path(out_path).write_text(header + text, encoding="utf-8")

    by_status = {}
    for e in ordered:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
    print("Bootstrap: scraped doc tags: %s" % tag_counts)
    print("Bootstrap: %d citation occurrences in code (%d unique namespaced tags)."
          % (len(citations), len({(c["ns"], c["tag"]) for c in citations})))
    print("Bootstrap: wrote %d entries to %s (by status: %s)"
          % (len(ordered), out_path, by_status))
    return 0


# ---------------------------------------------------------------------------
# --assert-inert
# ---------------------------------------------------------------------------

def strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:]
    return tree


def assert_inert(files):
    """Exit nonzero unless each file differs from HEAD only in comments/docstrings."""
    failures = 0
    for f in files:
        path = Path(f).resolve()
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            print("ERROR: %s is outside the repo root %s" % (f, REPO_ROOT))
            failures += 1
            continue
        head = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", "HEAD:%s" % rel],
            capture_output=True, text=True)
        if head.returncode != 0:
            print("ERROR: %s: cannot read HEAD version (%s)"
                  % (rel, head.stderr.strip()))
            failures += 1
            continue
        try:
            work_dump = ast.dump(strip_docstrings(parse_python(path.read_text(encoding="utf-8"))))
            head_dump = ast.dump(strip_docstrings(parse_python(head.stdout)))
        except SyntaxError as exc:
            print("ERROR: %s: does not parse: %s" % (rel, exc))
            failures += 1
            continue
        if work_dump == head_dump:
            print("INERT: %s (AST identical to HEAD after docstring strip)" % rel)
        else:
            print("NOT INERT: %s (AST differs from HEAD beyond comments/docstrings)" % rel)
            failures += 1
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true",
                        help="unregistered in-code citations become errors")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY),
                        help="registry path (default: %(default)s)")
    parser.add_argument("--bootstrap", action="store_true",
                        help="scrape docs + code into a draft registry")
    parser.add_argument("-o", "--out", default=str(DEFAULT_REGISTRY),
                        help="output path for --bootstrap (default: %(default)s)")
    parser.add_argument("--assert-inert", nargs="+", metavar="FILE",
                        help="AST comment-only proof vs HEAD for FILE(s)")
    args = parser.parse_args(argv)

    if args.assert_inert:
        return assert_inert(args.assert_inert)
    if args.bootstrap:
        return bootstrap(args.out)
    return run_checks(args.registry, args.strict)


if __name__ == "__main__":
    sys.exit(main())
