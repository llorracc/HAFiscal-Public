"""Fresh-interpreter isolation for order-sensitive knife-edge test gates.

2026-08-12 certified-net finding (night-log, cleanup wave): three numeric
gates (jax2b tail-quality, step5-ATI cross-formulation, pf-asymptote
large-m tracking) pass standalone but fail marginally inside a long pytest
session — the channel is in-process module/global state (which module first
imported EstimParameters and under what grid regime, JAX global config,
numba state), NOT os.environ (the env polluters were fixed separately the
same day). The honest fix is to run each such gate in a fresh interpreter
with a scrubbed HAFISCAL_* environment — the same isolation philosophy as
test_fti_tail_guard's per-case subprocesses.

Usage in a test module::

    import fresh_interp

    @pytest.mark.skipif(not fresh_interp.is_inner(), reason=fresh_interp.SKIP_REASON)
    def test_my_gate(...):            # the real body, unchanged
        ...

    def test_my_gate_fresh_interpreter():
        fresh_interp.run_fresh(__file__, "test_my_gate")

In-session, the real body is skipped and the wrapper runs it in a clean
subprocess; standalone debugging of the body directly is
``HAFISCAL_FRESH_INTERP_INNER=1 pytest <file>::<test>``.
"""
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
INNER_FLAG = "HAFISCAL_FRESH_INTERP_INNER"
SKIP_REASON = ("knife-edge numeric gate: order-sensitive in a long session; "
               "runs via its *_fresh_interpreter wrapper test "
               "(set HAFISCAL_FRESH_INTERP_INNER=1 to run the body directly)")


def is_inner():
    return os.environ.get(INNER_FLAG) == "1"


def run_fresh(test_file, test_name, timeout=1800):
    """Run ``<test_file>::<test_name>`` in a fresh interpreter; assert green.

    The child env drops every HAFISCAL_* variable (canonical defaults; the
    module under test applies its own pins) and sets the inner marker so the
    real body executes there.
    """
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HAFISCAL_")}
    env[INNER_FLAG] = "1"
    r = subprocess.run(
        [sys.executable, "-m", "pytest", f"{test_file}::{test_name}",
         "-x", "-q", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=env, cwd=str(_REPO_ROOT),
        timeout=timeout)
    assert r.returncode == 0, (
        f"fresh-interpreter run of {test_name} FAILED (rc={r.returncode}):\n"
        f"--- stdout tail ---\n{r.stdout[-3000:]}\n"
        f"--- stderr tail ---\n{r.stderr[-2000:]}")
