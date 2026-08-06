"""YAML <-> HAFiscal-code consistency check as a pytest (wraps check_vs_hafiscal_code).

Solves a baseline single-cohort AggFiscalType (interpretation='ESC') with HAFiscal's
production solver, then re-solves the SAME calibration with the independent textbook
EGM that the dolo-plus YAML encodes, and compares the employed-state cFunc[0](m).

Both tests are @pytest.mark.slow (full AggFiscalType solve). They share one solved
agent via the session-scoped cache (equation-check grid density aXtraCount=192 —
see the 2026-06-12 addendum in FINDING_permgrofac_marginal_value_factor.md for why
the gate is evaluated there rather than at the production aXtraCount=48).

  - test_standard_factor_matches_production: spec/YAML/standard-HARK marginal-value
    factor (PermGroFac*psi)^(-rho) matches the post-BUG-047 production solver, rel<1e-3
    on probes within both solvers' grid support (m <= aXtraMax = 40).
  - test_legacy_factor_deviates: the legacy psi^(-rho)-only factor (pre-BUG-047 solver
    math) DEVIATES — the regression guard that the BUG-047 fix is active in the solver.
"""
import pytest

import check_vs_hafiscal_code as chk

pytestmark = pytest.mark.slow

PROBES_ON_GRID = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 40.0]


def _run(solved_agent_cache, factor_mode):
    solved = solved_agent_cache.get_solved(aXtraCount=chk.CHECK_AXTRA_COUNT)
    calib = chk.extract_calibration(solved)
    egm, _ = chk.solve_egm_from_calibration(
        calib, factor_mode=factor_mode, aCount=chk.CHECK_EGM_ACOUNT)
    return chk.compare_cfunc(calib, egm, probes=PROBES_ON_GRID, gate_m_max=chk.GATE_M_MAX)


def test_standard_factor_matches_production(solved_agent_cache):
    res = _run(solved_agent_cache, "standard")
    rows = "\n".join(
        f"  m={r['m']:>6.2f}  HAFiscal={r['c_hafiscal']:.6f}  EGM={r['c_egm']:.6f}  "
        f"rel={r['rel']:.2e}" for r in res["rows"])
    assert res["maxrel_gated"] < chk.GATE_REL, (
        f"YAML/standard EGM vs production cFunc[0]: max rel diff "
        f"{res['maxrel_gated']:.3e} >= {chk.GATE_REL} on m<={res['gate_m_max']:g}\n{rows}")


def test_legacy_factor_deviates(solved_agent_cache):
    res = _run(solved_agent_cache, "hafiscal_code")
    assert res["maxrel_gated"] > 1e-2, (
        "legacy psi^(-rho)-only EGM agrees with the production solver "
        f"(max rel diff {res['maxrel_gated']:.3e} <= 1e-2) — is the BUG-047 "
        "PermGroFac fix still active (HAFISCAL_PERMGROFAC_FIX)?")
