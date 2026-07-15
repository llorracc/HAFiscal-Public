"""Tests for the reuse-fidelity VERIFY axis — thread-2 component 1 (flag surface + reader).

Two layers:
  1. the canonical reader (``verify_level.py``) — the real interpretation logic every
     entry point and every later component (2-5) calls; tested exhaustively in-process;
  2. the ``reproduce.sh`` surface — that ``--complete`` / ``--byte-identical`` parse, set
     ``HAFISCAL_VERIFY_LEVEL`` with strictest-requested-level-wins composition, respect a
     pre-set env, and stay silent at the default. Exercised by running the REAL script
     (a no-action run is ~0.3 s) and reading its post-parse stderr notice, plus static
     assertions that the bash wiring is present (regression tripwire).

Build plan: plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 1).
Spec:       plans/20260622_reuse-fidelity-verification-flag-taxonomy.md.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

HA_MODELS = Path(__file__).resolve().parent
REPO_ROOT = HA_MODELS.parent.parent
REPRODUCE = REPO_ROOT / "reproduce.sh"

sys.path.insert(0, str(HA_MODELS))
import verify_level as vl  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. the canonical reader
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("val,expect", [
    (None, "numeric"),          # unset -> default
    ("numeric", "numeric"),
    ("complete", "complete"),
    ("byte", "byte"),
    ("COMPLETE", "complete"),   # case-insensitive
    ("  byte ", "byte"),        # whitespace-tolerant
    ("Numeric", "numeric"),
    ("bogus", "numeric"),       # safe degradation, no raise
    ("", "numeric"),            # empty -> default
])
def test_get_verify_level(monkeypatch, val, expect):
    if val is None:
        monkeypatch.delenv(vl.ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(vl.ENV_VAR, val)
    assert vl.get_verify_level() == expect


def test_unrecognized_warns_once_then_degrades(monkeypatch, capsys):
    monkeypatch.setenv(vl.ENV_VAR, "totally-bogus-xyz")
    vl._warned_unrecognized.discard("totally-bogus-xyz")  # reset the once-guard
    assert vl.get_verify_level() == "numeric"
    first = capsys.readouterr().err
    assert "unrecognized" in first and "totally-bogus-xyz" in first
    # second call: degrades identically but does NOT re-warn (one-time guard)
    assert vl.get_verify_level() == "numeric"
    assert capsys.readouterr().err == ""


def test_rank_strictly_increasing():
    assert vl.verify_rank("numeric") < vl.verify_rank("complete") < vl.verify_rank("byte")
    assert (vl.verify_rank("numeric"), vl.verify_rank("complete"),
            vl.verify_rank("byte")) == (0, 1, 2)


def test_verify_rank_active_and_safe_default(monkeypatch):
    monkeypatch.setenv(vl.ENV_VAR, "byte")
    assert vl.verify_rank() == 2          # active level
    assert vl.verify_rank("not-a-level") == 0  # unknown name -> 0 (matches safe-degrade)


@pytest.mark.parametrize("active,at_least,expect", [
    ("numeric", "numeric", True),
    ("numeric", "complete", False),
    ("numeric", "byte", False),
    ("complete", "numeric", True),
    ("complete", "complete", True),
    ("complete", "byte", False),
    ("byte", "numeric", True),
    ("byte", "complete", True),
    ("byte", "byte", True),
])
def test_verify_at_least(monkeypatch, active, at_least, expect):
    monkeypatch.setenv(vl.ENV_VAR, active)
    assert vl.verify_at_least(at_least) is expect


def test_verify_at_least_rejects_bad_argument(monkeypatch):
    # a user's ENV typo safe-degrades, but a programmer passing an unknown level in
    # code is a bug and must raise.
    monkeypatch.setenv(vl.ENV_VAR, "numeric")
    with pytest.raises(ValueError):
        vl.verify_at_least("complete-ish")


# --------------------------------------------------------------------------- #
# 2. the reproduce.sh surface
# --------------------------------------------------------------------------- #
pytestmark_repro = pytest.mark.skipif(
    not REPRODUCE.is_file(), reason="reproduce.sh not found at repo root")


def _run_reproduce(args, level_env=None, timeout=60):
    """Run reproduce.sh with `args` (no action -> ~0.3 s), return (rc, stderr)."""
    env = None
    if level_env is not None:
        import os
        env = dict(os.environ)
        env[vl.ENV_VAR] = level_env
    p = subprocess.run(
        ["bash", str(REPRODUCE), *args],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, p.stderr


def _notice_level(stderr):
    """Extract the resolved level from reproduce.sh's post-parse stderr notice, or None."""
    import re
    m = re.search(r"verification level = '([a-z]+)'", stderr)
    return m.group(1) if m else None


@pytestmark_repro
def test_help_lists_both_flags():
    p = subprocess.run(["bash", str(REPRODUCE), "--help"],
                       cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)
    assert p.returncode == 0
    out = p.stdout + p.stderr
    assert "--complete" in out
    assert "--byte-identical" in out
    assert "HAFISCAL_VERIFY_LEVEL" in out


@pytestmark_repro
@pytest.mark.parametrize("args,env,expect", [
    ([], None, None),                                   # default -> SILENT (no notice)
    (["--complete"], None, "complete"),
    (["--byte-identical"], None, "byte"),
    (["--complete", "--byte-identical"], None, "byte"),  # strictest wins
    (["--byte-identical", "--complete"], None, "byte"),  # ...order-independent
    (["--complete"], "byte", "byte"),                    # stricter pre-set env not downgraded
    ([], "complete", "complete"),                        # pre-set env respected, no flag
    (["--complete", "--multiplier-engine", "tm"], None, "complete"),  # composes with METHOD axis
])
def test_reproduce_resolves_level(args, env, expect):
    rc, err = _run_reproduce(args, level_env=env)
    assert rc == 0, f"reproduce.sh {args} exited {rc}"
    assert _notice_level(err) == expect


@pytestmark_repro
def test_unknown_flag_still_errors():
    rc, _ = _run_reproduce(["--no-such-flag"])
    assert rc == 1


def test_reproduce_bash_wiring_present():
    """Static tripwire: the bash wiring exists (catches an accidental delete/regression
    even if the live tests are skipped)."""
    txt = REPRODUCE.read_text() if REPRODUCE.is_file() else ""
    if not txt:
        pytest.skip("reproduce.sh not found")
    for needle in (
        "--complete)",
        "--byte-identical)",
        'VERIFY_LEVEL="${HAFISCAL_VERIFY_LEVEL:-numeric}"',
        'if [[ "$VERIFY_LEVEL" != "byte" ]]; then',   # strictest-wins guard
        'export HAFISCAL_VERIFY_LEVEL="$VERIFY_LEVEL"',
    ):
        assert needle in txt, f"reproduce.sh missing VERIFY-axis wiring: {needle!r}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
