"""Pytest plumbing for the dolo-plus validation harness.

Key constraints encoded here (see CLAUDE.md and the module docstrings):
  - EstimParameters parses sys.argv AT IMPORT TIME (argv[1..4] = Rfree, CRRA,
    IncUnemp, IncUnempNoBenefits) and reads calibration files relative to cwd,
    so sys.argv must be patched and cwd moved to FromPandemicCode/ BEFORE the
    first `import Parameters`. The session fixture below does both for the whole
    session, before any test imports the production modules.
  - Env flags are pinned per test (restored afterwards) so regime-parameterized
    tests cannot leak flag state into each other.
  - Solving an AggFiscalType takes O(10s); tests share solved agents through a
    session-scoped cache with EXPLICIT keys (parametrization + interpretation +
    PermGroFac regime + grid overrides), so a test under one regime can never
    silently receive an agent solved under another.
"""
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FPC_DIR = HERE.parents[0] / "FromPandemicCode"

sys.path.insert(0, str(HERE))  # make check_vs_hafiscal_code importable from tests

# Pinned argv that EstimParameters parses at import time (CLI defaults of the harness).
PINNED_ARGV = ["dolo_plus_validation", "1.01", "2.0", "0.7", "0.5"]

# Env flags pinned for every test in this directory (today's production defaults).
PINNED_ENV = {
    "HAFISCAL_INTERPRETATION": "ESC",
    "HAFISCAL_PERMGROFAC_FIX": "1",
}


@pytest.fixture(scope="session", autouse=True)
def hafiscal_import_guard():
    """Patch sys.argv and chdir to FromPandemicCode/ for the whole session.

    Must run before any test (or fixture) imports Parameters/EstimParameters —
    session-scoped + autouse guarantees that within this directory.
    """
    saved_argv, saved_cwd = sys.argv, os.getcwd()
    sys.argv = list(PINNED_ARGV)
    os.chdir(FPC_DIR)
    if str(FPC_DIR) not in sys.path:
        sys.path.insert(0, str(FPC_DIR))
    try:
        yield
    finally:
        sys.argv = saved_argv
        os.chdir(saved_cwd)


@pytest.fixture(autouse=True)
def pinned_env():
    """Pin the harness env flags for each test; restore the prior values after."""
    saved = {k: os.environ.get(k) for k in PINNED_ENV}
    os.environ.update(PINNED_ENV)
    try:
        yield dict(PINNED_ENV)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class SolvedAgentCache:
    """Session cache of solved AggFiscalType agents, keyed explicitly.

    Key = (parametrization, interpretation, permgrofac_regime, aXtraCount, aXtraMax).
    The regime component is read from the env AT SOLVE TIME, so a cached solve can
    never be served to a test running under a different PermGroFac regime.
    """

    def __init__(self):
        self._store = {}

    @staticmethod
    def make_key(parametrization="Reduced_Run", aXtraCount=None, aXtraMax=None):
        return (
            parametrization,
            os.environ.get("HAFISCAL_INTERPRETATION", "ESC"),
            "pgfFix" if os.environ.get("HAFISCAL_PERMGROFAC_FIX", "1") != "0" else "pgfLegacy",
            aXtraCount,
            aXtraMax,
        )

    def get_solved(self, parametrization="Reduced_Run", aXtraCount=None, aXtraMax=None):
        key = self.make_key(parametrization, aXtraCount, aXtraMax)
        if key not in self._store:
            import check_vs_hafiscal_code as chk
            assert parametrization == "Reduced_Run", (
                "only the Reduced_Run baseline build is wired into the harness")
            self._store[key] = chk.build_and_solve_agent(
                aXtraCount=aXtraCount, aXtraMax=aXtraMax)
        return self._store[key]


@pytest.fixture(scope="session")
def solved_agent_cache():
    return SolvedAgentCache()
