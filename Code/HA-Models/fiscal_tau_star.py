"""The shared derived steady-state tax rate tau* (BUG-077, stage B).

Owner design (2026-08-10, the tax-alignment program,
plans/20260810-1030h_pe-hank-tax-alignment_plan.md): instead of the
historical ARBITRARY tau_ss = 0.3 (which implicitly financed a
G_ss ~ 27%-of-output residual that entered no agent's budget or
utility), the model government's tax rate is DERIVED as the rate that
funds exactly its modeled obligations at the steady state:

    tau* * w * N  =  0.7 * (1 - tau*) * w * U12  +  r * qb*B

- 0.7*(1-tau*)*w per benefit-eligible unemployed (U12 = duration
  quarters 1-2): the PE income spec's UI program booked IN FULL on the
  government ledger (owner 2026-08-10, reversing the historical
  0.5-core booking whose implied "private top-up to the eligible" had
  no economic reading). Only the exhausted households' 0.5 floor
  remains private income (Y_priv). Benefits are net-indexed, hence the
  fixed-point form.
- r*qb*B: interest on the data-anchored household-held government debt,
  qb*B = 1.4324029855872642 (~31% of annual GDP; RECONCILED-003), at
  the quarterly real rate r = 0.01.
- G == 0: the minimal government — exactly as big as its two jobs in
  the model (servicing the debt the asset market is calibrated to and
  paying the UI the experiments extend).
- N, U12: the education-weighted ergodic employment/eligible shares of
  the UNIFIED per-education chains (BUG-076 fixed;
  Urate_normal_{d,h,c} = 0.085/0.044/0.027, data_EducShares weights),
  which is what makes tau* a SINGLE number shared by the PE model and
  the HANK-SAM block. N = 0.958647, U12 = 0.036758222.

TAU_STAR below is the frozen value of that computation;
derive_tau_star() re-runs it from the live chains and a guard test
(test_step4_engine.test_tau_star_literal_matches_derivation) keeps the
two from drifting. Recorded alternative: the historical 0.5-core
basket would give 0.033472 — the basket choice moves tau* by ~0.7pp
and multipliers by ~0.1% (immaterial; the PE-first basket is the
owner-ruled spec).
"""

TAU_STAR = 0.04069046175146683

# The historical arbitrary rate (the "legacy" escape of
# HAFISCAL_TAU_SS; also the frozen monolith's hardcode).
TAU_LEGACY = 0.3


def derive_tau_star():
    """Recompute tau* from the live unified chains (guard-test target).

    Chains and shares come from step4.hh_setup.unemployment_chains()
    (the BUG-076 single source); the ergodics are calibration-file
    independent, so this is cwd-robust.
    """
    import numpy as np
    import scipy.sparse.linalg as spla
    from step4.hh_setup import unemployment_chains

    uc = unemployment_chains()
    dstns = []
    for m in uc["chains_cs"]:
        _w, _v = spla.eigs(m, k=1, which='LM')
        dstns.append((_v[:, 0] / _v[:, 0].sum()).real)
    agg = sum(w * v for w, v in zip(uc["shares"], dstns))
    N, U12 = agg[0], agg[1] + agg[2]
    r = 0.01
    qbB = 1.4324029855872642
    wage = 1.0
    return (0.7 * U12 * wage + r * qbB) / (N * wage + 0.7 * U12 * wage)
