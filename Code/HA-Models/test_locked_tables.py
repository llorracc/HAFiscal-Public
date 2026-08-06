"""Working-tree integrity check for the frozen QE-baseline result files.

Asserts that every file listed in LOCKED_TABLES.manifest exists and that its
current SHA-256 matches the manifest row — catching accidental clobbering of
frozen results BEFORE commit (the pre-commit hook is the commit-time guard).

A normal pipeline run writes `_candidate` siblings (see
FromPandemicCode/generated_output.py) and therefore never trips this test.

Run: pytest Code/HA-Models/test_locked_tables.py
Plan: plans/20260611_qe-baseline-freeze-and-candidate-lock_plan.md
"""

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "reproduce"))

from locked_manifest import MANIFEST_PATH, parse_manifest, sha256_file  # noqa: E402

ROWS = parse_manifest()


def test_manifest_exists():
    assert MANIFEST_PATH.exists(), f"missing {MANIFEST_PATH}"


@pytest.mark.parametrize(
    "row", ROWS, ids=[r["path"] for r in ROWS] if ROWS else [])
def test_frozen_file_matches_manifest(row):
    path = os.path.join(_REPO_ROOT, row["path"])
    assert os.path.exists(path), (
        f"frozen file missing from working tree: {row['path']}")
    actual = sha256_file(path)
    assert actual == row["sha256"], (
        f"FROZEN FILE DRIFTED: {row['path']}\n"
        f"  manifest sha256: {row['sha256']}\n"
        f"  current  sha256: {actual}\n"
        f"Frozen results change ONLY via reproduce/promote_candidates.py "
        f"(make promote-tables) under HAFISCAL_UNLOCK=1.")
