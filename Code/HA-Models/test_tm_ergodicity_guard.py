"""Unit tests for tm_methods.assert_mortality_inclusive_ergodicity (owner order
2026-07-25: halt when the calibration admits no mortality-inclusive ergodic).

These exercise the FALLBACK (direct-formula) path via stub agents without
EducType. The EXACT path (loader-convention boundary via
EstimParameters.gic_capped_beta) is integration-covered by the opt-in cap-atom
parity gate (toolmap/test_tm_ergodic_parity_cap.py), whose TM build runs the
guard on the real Baseline economy.
"""
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = [sys.argv[0]]
if os.path.join(_HERE, "FromPandemicCode") not in sys.path:
    sys.path.insert(0, os.path.join(_HERE, "FromPandemicCode"))

from tm_methods import assert_mortality_inclusive_ergodicity as guard  # noqa: E402


def _stub(beta, R=1.01, rho=2.0, L=0.99375, G=1.0049):
    """Fallback-path stub agent (no EducType). E[1/psi] = 1.000901 here."""
    d0 = SimpleNamespace(pmv=np.array([0.5, 0.5]),
                         atoms=np.array([[0.97, 1.03], [1.00, 1.00]]))
    return SimpleNamespace(DiscFac=beta, Rfree=R, CRRA=rho, LivPrb=[L],
                           PermGroFac=[G], IncShkDstn=[[d0]])


def test_guard_silent_for_impatient_atoms():
    guard([_stub(0.90), _stub(0.99)])  # GPF_out well below the warn band


def test_guard_halts_on_gpf_at_or_above_one():
    with pytest.raises(RuntimeError, match="MORTALITY-INCLUSIVE ERGODICITY"):
        guard([_stub(0.99), _stub(1.02)])  # second atom: GPF_out ≈ 1.0046


def test_guard_warns_in_near_boundary_band_without_halting():
    # beta chosen so GPF_out ≈ 0.9998 ∈ [0.9996, 1.0)
    with pytest.warns(UserWarning, match="near-boundary"):
        guard([_stub(1.0103)])


def test_guard_escape_hatch_env():
    os.environ["HAFISCAL_SKIP_ERGODICITY_GUARD"] = "1"
    try:
        guard([_stub(1.02)])  # would halt without the hatch
    finally:
        del os.environ["HAFISCAL_SKIP_ERGODICITY_GUARD"]


def test_guard_warns_not_halts_on_unevaluable_atom():
    bad = SimpleNamespace(DiscFac=0.95)  # missing everything else
    with pytest.warns(UserWarning, match="could not evaluate"):
        guard([bad])
