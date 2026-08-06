"""Guard tests for the opt-in Step-5a ConsumedATI-Markov solver wiring (HAFISCAL_STEP5_ATI).

P4b of the power-law-tail meld (plans/20260723_powerlaw-tail-meld-execution_plan.md
section 5; GO verdict: conclusions_private/2026-07-23_meld_p4a_recession_scale_verdict.md).
The wiring under test is ``AggregateDemandEconomy.solve`` ->
``_try_solve_ati_markov`` in Code/HA-Models/FromPandemicCode/AggFiscalModel.py.

Tests (one shared HS_Only base economy, built once via the P4a harness's
construction-only path — ~1-2 min):

1. default-off byte-identity — a base-economy solve with the flag UNSET and with
   ``HAFISCAL_STEP5_ATI=0`` produce EXACTLY equal policies (``==`` on probe-grid
   evaluations, not allclose: both are the stock path and the solve is
   deterministic, so any difference at all would mean the flag read perturbs the
   default path).
2. flag-on smoke — with ``HAFISCAL_STEP5_ATI=1`` (threshold lowered so the
   HS atom qualifies) the solve routes through ConsumedATI (``_step5_ati_used``)
   and the routed solution certifies at BOTH parity tiers:
   (i) same-fixed-point WITHIN the consumed(a) formulation — consumed(a) vs a
       deep power-law Picard reference on the same inputs <= 1e-8 (the P4a
       pre-registered class; recession cells measured 3.4e-11-8.4e-10) and the
       solver's FULL Euler residual (fnorm) <= 1e-8;
   (ii) ACROSS formulations vs a DEEP (tolerance 1e-11) production-EGM solve —
       cFunc sup-diff <= 5e-4 ergodic / 1e-3 wide-grid (measured ~1.8e-4 /
       2.2e-4 after the wiring's a=0 grid prepend, which removes the ~1e-3 =
       aXtraGrid[0] constrained-region segment error; the residual is
       kink-adjacent discretization + the chain-Q vs measured-Q tail
       convention, NOT stopping noise).
3. forced-error fallback — with the FTI solver monkeypatched to raise, the solve
   completes via the EGM fallback and reproduces the stock policy EXACTLY.
4. default-threshold refusal — with the flag ON but the threshold at its default
   (0.97), the HS atom (beta=0.935) is refused by patience routing and the
   stock policy is reproduced EXACTLY.

Runtime escape hatch: ``HAFISCAL_SKIP_STEP5_ATI_ITEST=1`` skips the economy
fixture and everything that needs it (mirrors HAFISCAL_SKIP_STEP2_NAMG_ITEST).
Requires a resolvable ``fast-time-iteration`` checkout (``_hark_fti_path``);
tests 2/3 are skipped cleanly if it is absent.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import numpy as np
import pytest

HA_MODELS = os.path.dirname(os.path.abspath(__file__))
FPC = os.path.join(HA_MODELS, "FromPandemicCode")

_SKIP = os.environ.get("HAFISCAL_SKIP_STEP5_ATI_ITEST", "") == "1"
pytestmark = pytest.mark.skipif(
    _SKIP, reason="HAFISCAL_SKIP_STEP5_ATI_ITEST=1: heavy build-the-economy tests skipped")


def _load_poc():
    """Load the P4a harness module by path (fti_diagnostics is not a package)."""
    if FPC not in sys.path:
        sys.path.insert(0, FPC)
    spec = importlib.util.spec_from_file_location(
        "_poc_mm5_for_ati_test",
        os.path.join(FPC, "fti_diagnostics", "_poc_mm5_aggfiscal_parity.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_poc_mm5_for_ati_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _fti_available():
    try:
        if FPC not in sys.path:
            sys.path.insert(0, FPC)
        import _hark_fti_path  # noqa: F401
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def base_eco():
    """One HS_Only base economy (constructed, NOT solved), shared by all tests.

    HS_Only = a single HS cohort (DiscFac 0.935184) on the 6-state base Markov
    structure — the cheapest real AggFiscalType economy. Each test performs its
    own cold ``solve(warm_start=False)`` under its own env, so sharing the
    constructed object is safe (solves fully overwrite ``agent.solution``)."""
    cwd = os.getcwd()
    argv = sys.argv
    # EstimParameters reads sys.argv POSITIONALLY (argv[1]=Rfree, ...); under
    # pytest argv[1] is the test path -> patch it for the import/build window
    # (the CLAUDE.md-documented convention for importing in tests).
    sys.argv = [argv[0]]
    os.chdir(FPC)
    try:
        poc = _load_poc()
        eco = poc._build_economy_no_solve("HS_Only")
    finally:
        os.chdir(cwd)
        sys.argv = argv
    return eco


def _policy_snapshot(eco, m_grid):
    """Evaluate every agent's per-state cFunc(m, Cratio=1) on m_grid -> list of (S, M) arrays."""
    out = []
    for agent in eco.agents:
        S = int(np.asarray(agent.MrkvArray[0]).shape[0])
        ones = np.ones_like(m_grid)
        sol = agent.solution[0]
        out.append(np.array([
            np.asarray(sol.cFunc[j](m_grid, ones), dtype=float) for j in range(S)]))
    return out


def _solve_cold(eco, monkeypatch, env):
    """economy.solve(warm_start=False) under exactly the given HAFISCAL_STEP5_ATI* env."""
    for var in ("HAFISCAL_STEP5_ATI", "HAFISCAL_STEP5_ATI_MIN_DISCFAC"):
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    for agent in eco.agents:
        agent._step5_ati_used = False
    eco.solve(warm_start=False)
    return [bool(getattr(a, "_step5_ati_used", False)) for a in eco.agents]


# Probe grids: ergodic region (the P4a base-PoC parity convention) + a wide
# in-sample grid up to the HS solve top (aMax=551-class -> stay below it).
M_ERG = np.linspace(0.5, 12.0, 60)
M_FULL = np.concatenate([np.array([1e-4, 1e-3, 1e-2]), np.linspace(0.05, 500.0, 400)])


def test_default_off_byte_identity(base_eco, monkeypatch):
    """Flag unset vs '0': the two stock solves must be EXACTLY equal (and unrouted)."""
    routed_unset = _solve_cold(base_eco, monkeypatch, {})
    snap_unset = _policy_snapshot(base_eco, M_FULL)
    routed_zero = _solve_cold(base_eco, monkeypatch, {"HAFISCAL_STEP5_ATI": "0"})
    snap_zero = _policy_snapshot(base_eco, M_FULL)
    assert not any(routed_unset) and not any(routed_zero)
    for a, b in zip(snap_unset, snap_zero):
        assert np.array_equal(a, b), (
            "flag unset vs '0' changed the solve — default path is not byte-identical")


@pytest.mark.skipif(not _fti_available(), reason="fast-time-iteration checkout not resolvable")
def test_flag_on_routes_and_matches_deep_egm(base_eco, monkeypatch):
    """Routed ATI solution certifies at both parity tiers (see module docstring)."""
    routed = _solve_cold(base_eco, monkeypatch,
                         {"HAFISCAL_STEP5_ATI": "1",
                          "HAFISCAL_STEP5_ATI_MIN_DISCFAC": "0"})
    assert any(routed), "no agent routed through ConsumedATI with the threshold at 0"
    agent = base_eco.agents[0]
    info = agent._step5_ati_info
    snap_ati = _policy_snapshot(base_eco, M_ERG)
    snap_ati_full = _policy_snapshot(base_eco, M_FULL)

    # --- Tier (i): same-fixed-point WITHIN the consumed(a) formulation ---
    # Solver certificate: FULL Euler residual sup-norm (the masking-bug guard).
    assert info["fnorm"] <= 1e-8, f"ATI fnorm {info['fnorm']:.3e} not machine-class"
    # Deep power-law Picard reference on the SAME inputs + solve grid (the P4a
    # parity convention, harness _picard_powerlaw_arm; rho~0.79 at HS -> fast).
    poc = sys.modules["_poc_mm5_for_ati_test"]
    S = info["S"]
    inp = dict(
        S=S, MrkvArray=np.asarray(agent.MrkvArray[0], float),
        IncShkDstn=list(agent.IncShkDstn[0]),
        LivPrb=np.full(S, float(np.asarray(agent.LivPrb[0]).reshape(-1)[0])),
        Rfree=np.full(S, float(np.asarray(agent.Rfree).reshape(-1)[0])),
        PermGroFac=np.asarray(agent.PermGroFac[0], float).reshape(-1)[:S],
        CRRA=float(agent.CRRA), aXtraGrid=info["solve_grid"].copy(),
    )
    beta = float(np.asarray(agent.DiscFac).reshape(-1)[0])
    pic = poc._picard_powerlaw_arm(inp, beta, move_tol=1e-13, wall_cap_s=600,
                                   log_every=0)
    assert pic["converged"], "deep Picard reference did not converge"
    parity_consumed = float(np.max(np.abs(info["consumed_a"] - pic["X_ref"])))
    print(f"\n[step5-ati test] tier-i consumed(a) vs deep Picard: {parity_consumed:.3e} "
          f"(fnorm {info['fnorm']:.2e})")
    assert parity_consumed <= 1e-8, (
        f"consumed(a) parity {parity_consumed:.3e} > 1e-8 (P4a class)")

    # --- Tier (ii): ACROSS formulations vs deep production EGM ---
    # Deep reference: same agents, flag off, HARK tolerance tightened to 1e-11
    # so the reference's own stopping distance (~tol*rho/(1-rho) ~ 4e-11) is
    # negligible; what remains is the genuine formulation difference.
    old_tol = [a.tolerance for a in base_eco.agents]
    for a in base_eco.agents:
        a.tolerance = 1e-11
    try:
        routed_ref = _solve_cold(base_eco, monkeypatch, {})
    finally:
        for a, t in zip(base_eco.agents, old_tol):
            a.tolerance = t
    assert not any(routed_ref)
    snap_ref = _policy_snapshot(base_eco, M_ERG)
    snap_ref_full = _policy_snapshot(base_eco, M_FULL)

    worst_erg = max(float(np.max(np.abs(a - b))) for a, b in zip(snap_ati, snap_ref))
    worst_full = max(float(np.max(np.abs(a - b)))
                     for a, b in zip(snap_ati_full, snap_ref_full))
    print(f"[step5-ati test] tier-ii cFunc vs deep production EGM: "
          f"ergodic {worst_erg:.3e}  wide {worst_full:.3e}")
    # Measured 2026-07-23 (HS base, a=0 prepend ON): 1.8e-4 ergodic / 2.2e-4
    # wide — kink-adjacent discretization + chain-Q-vs-measured-Q tail feedback.
    # Without the a=0 prepend this is ~1e-3 (= aXtraGrid[0], the constrained-
    # region segment error) — the 5e-4 bound would catch a prepend regression.
    assert worst_erg <= 5e-4, f"ergodic cross-formulation gap {worst_erg:.3e} > 5e-4"
    assert worst_full <= 1e-3, f"wide-grid cross-formulation gap {worst_full:.3e} > 1e-3"


@pytest.mark.skipif(not _fti_available(), reason="fast-time-iteration checkout not resolvable")
def test_forced_error_falls_back_cleanly(base_eco, monkeypatch):
    """A raising FTI solver must produce the EXACT stock solve via the fallback."""
    routed_stock = _solve_cold(base_eco, monkeypatch, {})
    assert not any(routed_stock)
    snap_stock = _policy_snapshot(base_eco, M_FULL)

    import _hark_fti_path  # noqa: F401
    import hark_fti.consumed_ati_markov as cam

    def _boom(*a, **kw):
        raise RuntimeError("forced test error (test_step5_ati_wiring)")

    monkeypatch.setattr(cam, "solve_stationary_ConsumedATI_markov", _boom)
    routed = _solve_cold(base_eco, monkeypatch,
                         {"HAFISCAL_STEP5_ATI": "1",
                          "HAFISCAL_STEP5_ATI_MIN_DISCFAC": "0"})
    assert not any(routed), "_step5_ati_used set even though the solver raised"
    snap_fallback = _policy_snapshot(base_eco, M_FULL)
    for a, b in zip(snap_stock, snap_fallback):
        assert np.array_equal(a, b), (
            "fallback-after-exception solve differs from the stock solve")


@pytest.mark.skipif(not _fti_available(), reason="fast-time-iteration checkout not resolvable")
def test_default_threshold_refuses_impatient_atom(base_eco, monkeypatch):
    """Flag ON + default threshold (0.97): the HS atom (0.935) must stay on EGM."""
    beta = float(np.asarray(base_eco.agents[0].DiscFac).reshape(-1)[0])
    assert beta < 0.97, f"fixture atom beta={beta} unexpectedly above the default threshold"
    routed_stock = _solve_cold(base_eco, monkeypatch, {})
    snap_stock = _policy_snapshot(base_eco, M_FULL)
    routed = _solve_cold(base_eco, monkeypatch, {"HAFISCAL_STEP5_ATI": "1"})
    assert not any(routed), "patience routing failed: impatient atom was routed"
    snap_on = _policy_snapshot(base_eco, M_FULL)
    for a, b in zip(snap_stock, snap_on):
        assert np.array_equal(a, b), (
            "flag-on-but-refused solve differs from the stock solve")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
