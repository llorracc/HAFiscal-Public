"""Validation for the opt-in Step-1 FTI wiring (``fti_step1.py``).

Independent of the heavy ``Estimation_BetaNablaSplurge.py`` script (which runs on
import): reconstructs Step-1's NOR ``base_params`` and tapered discount-factor ladder
(mirroring the PoC ``poc_hafiscal_step1_fti.py``) and checks the clean-pattern
transplant per type:

  (a) the FTI (NAM) solve converges and yields a finite, increasing policy for ALL
      seven types — including the patient GIC-edge type (needs autoExtend);
  (b) the transplanted NAM policy is at least as accurate as the host KinkedR-EGM
      policy by the Euler-error metric, and agrees with it on the resolved region for
      the moderately-patient types (shared-region cFunc parity);
  (c) the opt-in switch defaults to OFF.

Run:
  PYTHONPATH=../FromPandemicCode .../python -m pytest test_fti_step1.py -q
"""
import os
import sys
from copy import deepcopy

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.normpath(os.path.join(_HERE, "..", "FromPandemicCode"))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from HARK.distributions import Uniform
from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
from SetupParamsCSTW import init_infinite

try:
    import fti_step1
except ModuleNotFoundError as _e:
    # The opt-in FTI solvers live in the external (sibling) fast-time-iteration repo.
    # Skip this opt-in wiring test when that package is not available.
    pytest.skip(
        f"fast-time-iteration `hark_fti` not available ({_e}); skipping opt-in Step-1 FTI tests",
        allow_module_level=True,
    )


def _base_params():
    """Step-1 NOR base_params (mirrors Estimation_BetaNablaSplurge.py lines 167-202)."""
    b = deepcopy(init_infinite)
    b["LivPrb"] = [1 - 1 / 160]
    b["Rfree"] = 1.02 ** 0.25
    b["Rsave"] = 1.02 ** 0.25
    b["Rboro"] = 1.137 ** 0.25
    b["pLogInitMean"] = 0
    b["UnempPrb"] = 0.044
    b["IncUnemp"] = 0.60
    b["PermShkStd"] = [0.001 ** 0.5]
    b["TranShkStd"] = [0.132 ** 0.5]
    b["BoroCnstArt"] = 0
    b["PermGroFacAgg"] = 1.01 ** 0.25
    b["CRRA"] = 2.0
    b["T_age"] = None
    return b


def _tapered_betas(base, center=0.9608076235664129, spread=0.07128652461546793, TypeCount=7):
    beta_set = Uniform(bot=center - spread, top=center + spread).discretize(TypeCount).atoms[0]
    # Mirror Estimation_BetaNablaSplurge.py: corrected GPF_out cap (BUG-060 fix, default)
    # = (Gamma_ind/(L*E[1/psi]))^rho / R with individual PermGroFac; legacy = old additive.
    if os.environ.get("HAFISCAL_STEP1_GIC_LEGACY", "0") == "1":
        GICmaxBeta = (1 - base["LivPrb"][0]) + (base["PermGroFacAgg"] ** base["CRRA"]) / base["Rfree"]
    else:
        _E_inv_psi = float(np.exp(base["PermShkStd"][0] ** 2))
        GICmaxBeta = (base["PermGroFac"][0] / (base["LivPrb"][0] * _E_inv_psi)) ** base["CRRA"] / base["Rfree"]
    tt, minBeta = 0.01, 0.01
    out = np.array(beta_set, dtype=float)
    for j in range(TypeCount):
        if out[j] > GICmaxBeta - tt:
            out[j] = GICmaxBeta - tt + np.arctan((out[j] - GICmaxBeta + tt) / tt) * tt / np.pi * 2
        elif out[j] < minBeta:
            out[j] = minBeta
    return out


def _make_kinkedR_host(base, DiscFac):
    """KinkedR EGM host on Step-1's own grid (as the estimation builds it)."""
    p = fti_step1._solve_params(base, DiscFac)
    p.pop("Rfree", None)  # KinkedR derives the kink from Rboro/Rsave
    p.update(Rboro=base["Rboro"], Rsave=base["Rsave"])
    host = KinkedRconsumerType(**p)
    host.cycles = 0
    host.solve()
    return host


def _euler_errors(agent, m_vals):
    sol = agent.solution[0]
    cFunc = sol.cFunc
    R = float(np.asarray(agent.Rfree).reshape(-1)[0])
    G = float(np.asarray(agent.PermGroFac).reshape(-1)[0])
    rho = float(agent.CRRA)
    DiscFacEff = float(agent.DiscFac) * float(np.asarray(agent.LivPrb).reshape(-1)[0])
    dstn = agent.IncShkDstn[0]
    probs = np.asarray(dstn.pmv, dtype=float)
    perm = np.asarray(dstn.atoms[0], dtype=float)
    tran = np.asarray(dstn.atoms[1], dtype=float)
    m = np.asarray(m_vals, dtype=float)
    c = np.asarray(cFunc(m), dtype=float)
    a = m - c
    mNext = (R / (G * perm))[None, :] * a[:, None] + tran[None, :]
    cNext = np.asarray(cFunc(mNext.ravel()), dtype=float).reshape(mNext.shape)
    EndOfPrdvP = DiscFacEff * R * G ** (-rho) * (
        probs[None, :] * perm[None, :] ** (-rho) * cNext ** (-rho)
    ).sum(axis=1)
    c_opt = EndOfPrdvP ** (-1.0 / rho)
    return (c - c_opt) / c_opt


BASE = _base_params()
BETAS = _tapered_betas(BASE)
# Unconstrained, ergodic-relevant region (above the borrowing constraint at mNrmMin=0;
# the Euler equation holds here, unlike the constrained m≈mNrmMin point).
M_ERGODIC = np.linspace(1.0, 8.0, 40)
MODERATE = [0, 1, 2, 3, 4]   # NAM converges fast and matches EGM-on-grid here
GIC_EDGE = 6                 # most-patient: plain NAM hits the iter cap (Phase-4 territory)


def test_opt_in_defaults_off():
    # The harness must not have it forced on; the module default is OFF.
    assert os.environ.get("HAFISCAL_STEP1_FTI", "0") != "1"
    assert fti_step1.STEP1_FTI_ON is False
    assert fti_step1.FTI_METHOD in ("NAM", "ATI")


@pytest.mark.parametrize("j", MODERATE)
def test_nam_converges_and_is_accurate_for_moderate_types(j):
    """NAM converges to a finite, increasing, Euler-accurate policy on the ergodic region."""
    fti = fti_step1.make_fti_type(BASE, float(BETAS[j]), method="NAM")
    fti.solve()
    iters = int(getattr(fti, "completed_cycles", -1))
    assert 1 <= iters < fti_step1.GRAFT_MAX_ITERS, f"type {j}: NAM did not converge (iters={iters})"
    c = np.asarray(fti.solution[0].cFunc(M_ERGODIC), dtype=float)
    assert np.all(np.isfinite(c)) and np.all(np.diff(c) > 0), f"type {j}: bad policy"
    ee = float(np.max(np.abs(_euler_errors(fti, M_ERGODIC))))
    assert ee < 1e-2, f"type {j}: NAM Euler error too large on ergodic region ({ee:.2e})"


@pytest.mark.parametrize("j", MODERATE)
def test_safe_graft_replaces_with_egm_equivalent_policy(j):
    """The safe graft fires for moderate types and the grafted policy matches EGM where mass lives."""
    host = _make_kinkedR_host(BASE, float(BETAS[j]))
    c_before = np.asarray(host.solution[0].cFunc(M_ERGODIC), dtype=float)
    fti_step1.transplant_fti_cfunc(host, BASE)
    assert host._fti_grafted is True, f"type {j}: expected graft, got fallback ({host._fti_reason})"
    c_after = np.asarray(host.solution[0].cFunc(M_ERGODIC), dtype=float)
    max_dc = float(np.max(np.abs(c_after - c_before)))
    assert max_dc < 2e-2, f"type {j}: grafted policy vs EGM gap too large on ergodic region ({max_dc:.2e})"


def test_safe_graft_falls_back_to_egm_at_gic_edge():
    """Plain NAM cannot solve the patient GIC-edge type → graft must transparently keep EGM."""
    host = _make_kinkedR_host(BASE, float(BETAS[GIC_EDGE]))
    c_egm = np.asarray(host.solution[0].cFunc(M_ERGODIC), dtype=float)
    cfunc_egm_obj = host.solution[0].cFunc
    fti_step1.transplant_fti_cfunc(host, BASE)
    assert host._fti_grafted is False, f"type {GIC_EDGE}: expected EGM fallback, but grafted ({host._fti_reason})"
    # cFunc object is untouched on fallback → behavior byte-identical to EGM for this type.
    assert host.solution[0].cFunc is cfunc_egm_obj
    c_after = np.asarray(host.solution[0].cFunc(M_ERGODIC), dtype=float)
    assert np.array_equal(c_after, c_egm)


def test_namg_solves_gic_edge_far_faster_than_egm():
    """NAMG converges the patient GIC-edge type in O(10s) of steps; EGM needs ~1000s.

    This is the point of #4: plain NAM/ATI fall back to (slow) EGM at the GIC edge,
    but the global-Newton NAMG type converges grid-independently. It also auto-sizes
    its own grid top (no hand-tuned aXtraMax).
    """
    fti = fti_step1.make_fti_type(BASE, float(BETAS[GIC_EDGE]), method="NAMG")
    fti.solve()
    iters = int(getattr(fti, "completed_cycles", -1))
    assert 1 <= iters < 120, f"NAMG did not converge fast at the GIC edge (iters={iters})"
    assert getattr(fti, "namg_gpf_mod", 0.0) > 0.998, "expected a GIC-edge GPF-Mod"
    assert fti.aXtraMax > 1000.0, f"NAMG auto-grid did not grow the top ({fti.aXtraMax})"
    c = np.asarray(fti.solution[0].cFunc(M_ERGODIC), dtype=float)
    assert np.all(np.isfinite(c)) and np.all(np.diff(c) > 0), "bad NAMG policy"
    # NAMG must be much cheaper than the EGM host it replaces.
    host = _make_kinkedR_host(BASE, float(BETAS[GIC_EDGE]))
    assert iters < int(host.completed_cycles) / 10, (
        f"NAMG ({iters}) not >>10x cheaper than EGM ({host.completed_cycles})"
    )


def test_namg_grafts_at_gic_edge_where_nam_falls_back():
    """With method='NAMG' the safe graft FIRES for the GIC-edge type (vs NAM fallback)."""
    host = _make_kinkedR_host(BASE, float(BETAS[GIC_EDGE]))
    c_egm = np.asarray(host.solution[0].cFunc(M_ERGODIC), dtype=float)
    fti_step1.transplant_fti_cfunc(host, BASE, method="NAMG")
    assert host._fti_grafted is True, (
        f"NAMG should graft the GIC-edge type, got fallback ({host._fti_reason})"
    )
    c_after = np.asarray(host.solution[0].cFunc(M_ERGODIC), dtype=float)
    max_dc = float(np.max(np.abs(c_after - c_egm)))
    assert max_dc < 5e-2, f"grafted NAMG policy vs EGM gap too large on ergodic region ({max_dc:.2e})"


@pytest.mark.parametrize("j", MODERATE)
def test_anderson_egm_matches_egm_for_moderate_types(j):
    """AndersonEGM reaches the same EGM policy on the ergodic region for moderate types.

    Unlike NAM (a different algorithm), AndersonEGM just accelerates the EGM contraction,
    so on the host's grid it must agree with the KinkedR-EGM host to solver tolerance.
    """
    fti = fti_step1.make_fti_type(BASE, float(BETAS[j]), method="AndersonEGM")
    fti.solve()
    iters = int(getattr(fti, "completed_cycles", -1))
    assert 1 <= iters < fti_step1.GRAFT_MAX_ITERS, f"type {j}: AndersonEGM did not converge (iters={iters})"
    c = np.asarray(fti.solution[0].cFunc(M_ERGODIC), dtype=float)
    assert np.all(np.isfinite(c)) and np.all(np.diff(c) > 0), f"type {j}: bad policy"
    host = _make_kinkedR_host(BASE, float(BETAS[j]))
    c_egm = np.asarray(host.solution[0].cFunc(M_ERGODIC), dtype=float)
    max_dc = float(np.max(np.abs(c - c_egm)))
    assert max_dc < 2e-2, f"type {j}: AndersonEGM vs EGM gap too large on ergodic region ({max_dc:.2e})"


def test_anderson_egm_solves_and_grafts_at_gic_edge():
    """AndersonEGM solves the patient GIC-edge type (where plain NAM falls back) and grafts.

    Same fixed point as EGM, far fewer sweeps; the safe graft therefore FIRES (the
    AndersonEGM policy agrees with the EGM host), in contrast to the NAM fallback.
    """
    fti = fti_step1.make_fti_type(BASE, float(BETAS[GIC_EDGE]), method="AndersonEGM")
    fti.solve()
    iters = int(getattr(fti, "completed_cycles", -1))
    assert 1 <= iters < fti_step1.GRAFT_MAX_ITERS, f"AndersonEGM did not converge at the GIC edge (iters={iters})"
    c = np.asarray(fti.solution[0].cFunc(M_ERGODIC), dtype=float)
    assert np.all(np.isfinite(c)) and np.all(np.diff(c) > 0), "bad AndersonEGM policy at GIC edge"
    # Accelerated: strictly fewer sweeps than the plain-EGM host on the same grid.
    host = _make_kinkedR_host(BASE, float(BETAS[GIC_EDGE]))
    assert iters < int(host.completed_cycles), (
        f"AndersonEGM ({iters}) not fewer sweeps than EGM ({host.completed_cycles})"
    )
    # And the graft fires (policy matches EGM where the mass lives).
    host2 = _make_kinkedR_host(BASE, float(BETAS[GIC_EDGE]))
    c_egm = np.asarray(host2.solution[0].cFunc(M_ERGODIC), dtype=float)
    fti_step1.transplant_fti_cfunc(host2, BASE, method="AndersonEGM")
    assert host2._fti_grafted is True, (
        f"AndersonEGM should graft the GIC-edge type, got fallback ({host2._fti_reason})"
    )
    c_after = np.asarray(host2.solution[0].cFunc(M_ERGODIC), dtype=float)
    assert float(np.max(np.abs(c_after - c_egm))) < 5e-2


def test_solve_types_fti_end_to_end():
    """solve_types_fti solves + (safely) grafts onto a list of KinkedR hosts; all policies sane."""
    hosts = []
    for j in (1, GIC_EDGE):  # a moderate type and the GIC-edge type
        p = fti_step1._solve_params(BASE, float(BETAS[j]))
        p.pop("Rfree", None)
        p.update(Rboro=BASE["Rboro"], Rsave=BASE["Rsave"])
        h = KinkedRconsumerType(**p)
        h.cycles = 0
        hosts.append(h)
    fti_step1.solve_types_fti(hosts, BASE)
    for j, h in zip((1, GIC_EDGE), hosts):
        c = np.asarray(h.solution[0].cFunc(M_ERGODIC), dtype=float)
        assert np.all(np.isfinite(c)) and np.all(np.diff(c) > 0), f"type {j}: bad grafted policy"
    assert hosts[0]._fti_grafted is True       # moderate type grafted
    assert hosts[1]._fti_grafted is False      # GIC-edge type fell back to EGM
