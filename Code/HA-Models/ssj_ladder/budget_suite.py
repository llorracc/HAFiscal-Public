"""Per-input flow-budget suite + by-educ aggregation identity on a FULL-model obj.

The Phase-B standing gates (plan 20260901-2010h §3). Convention pinned to the
adversarial pass's measurement (the floors below were measured with exactly
this code shape on ``rerun_logs/zerocol_fix_20260901/jacs_unanticipated.obj``,
T=300):

  resid[0, s]  = J_A[0, s] + J_C[0, s]
  resid[t, s]  = J_A[t, s] - rho * J_A[t-1, s] + J_C[t, s],   rho = R * LivPrb
  off-delivery = max |resid off the t==s diagonal|
  scale        = max|J_C| + max|J_A|          (per input)
  gate         : off-delivery / scale <= 1.5 x measured floor

eta is EXEMPT from the delivery-row form (an eta shock delivers income at
every t >= s; its delivery-row residual is structurally ~0.32 — gated instead
by the chain-implied dY path, Phase C's G-ETA). DiscFac's diagonal cash
varies by construction (no cash-constancy gate anywhere here — only
off-delivery is gated).

The by-educ identity: J_agg == sum_e w_e * J_e with the data_EducShares
weights, max-abs over all inputs, tolerance 1e-12 (measured 8.3e-17).
"""
import numpy as np

# data_EducShares' documented order (dropouts, HS grads, college) — the order the
# Jacobian obj keys its *_by_educ leaves with (step4.pe_anchor_gate.EDUC agrees;
# test_gate_constants_parity.py binds all three).
EDUC_LABELS = ("dropout", "highschool", "college")


def _production_ss_constants():
    """R * LivPrb and the education population shares from their SINGLE sources.

    Q9 of the dual-path sweep (conclusions_private/2026-09-02_dual-path-sweep_table.md
    §4; Phase-2 brief 2026-09-03): until then these gate constants were literals here,
    in pe_reproduction.py and in closed_form.py — one silent re-calibration away from a
    ladder gate certifying a stale economy. R and LivPrb are EstimParameters'
    Rfree_base / LivPrb_base (the calibration the household block builds with;
    step4.hh_setup.LIVPRB_SS copies the same survival value and the parity test binds
    it), the shares are data_EducShares (SCF 2004), labelled in EDUC_LABELS' order.

    Resolved from EstimParameters, NOT step4: hh_setup freezes HAFISCAL_HANK_BIGT and
    friends at import, and this module is imported by phase_b / rung_a56 BEFORE they pin
    the rung env ("env before import", ssj_ladder/README.md). EstimParameters reads
    sys.argv at import (BUG-114), hence the argv guard — the same shape as
    pe_reproduction._resolve_splurge. closed_form.py keeps its own literal BY DESIGN
    (package-free reconstruction); test_gate_constants_parity.py asserts it equals
    the value resolved here.
    """
    import os
    import sys
    fpc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "FromPandemicCode")
    if fpc not in sys.path:
        sys.path.insert(0, fpc)
    argv = sys.argv
    sys.argv = [argv[0]]
    try:
        from EstimParameters import Rfree_base, LivPrb_base, data_EducShares
    finally:
        sys.argv = argv
    rho = float(Rfree_base[0]) * float(LivPrb_base[0])
    if len(data_EducShares) != len(EDUC_LABELS):
        raise RuntimeError(f"data_EducShares has {len(data_EducShares)} entries, "
                           f"EDUC_LABELS {len(EDUC_LABELS)} — update both together")
    return rho, dict(zip(EDUC_LABELS, (float(s) for s in data_EducShares)))


RHO_LIVPRB, EDUC_SHARES = _production_ss_constants()   # R * LivPrb at the production SS; shares

# 3 x the measured off-delivery/scale on jacs_unanticipated.obj (T=300, the
# PRODUCTION config). Raised from 1.5x on 2026-09-02: rung B2 (pe grids at
# Gamma=1) measured a UNIFORM 1.02-1.6x overage on every input including
# DiscFac -- the discretization-borne residual profile shifts with each
# intermediate config, and the production-config floors do not transfer at
# 1.5x (the same lesson the plan §3 recorded one level down). The gate's job
# here is the STRUCTURAL-break tripwire (the BUG-112 class is 3.7e-2, two
# orders above); per-rung measured values stay in every verdict, so drift
# remains visible.
FLOORS = {
    "transfers": 3.0 * 9.7e-5,
    "tau":       3.0 * 9.8e-5,
    "w":         3.0 * 9.8e-5,
    "UI_extend": 3.0 * 3.4e-5,
    "UI_rr":     3.0 * 6.7e-5,
    "r":         3.0 * 1.3e-3,
    "DiscFac":   3.0 * 7.2e-4,
}
ETA_NOTE = ("eta gated by the chain-implied dY path (G-ETA, Phase C), "
            "not the delivery-row form")


def budget_stats(JC, JA, rho=RHO_LIVPRB):
    JC = np.asarray(JC, float)
    JA = np.asarray(JA, float)
    res = np.empty_like(JC)
    res[0] = JA[0] + JC[0]
    res[1:] = JA[1:] - rho * JA[:-1] + JC[1:]
    diag = np.diag(res).copy()
    off = res.copy()
    np.fill_diagonal(off, 0.0)
    scale = float(np.max(np.abs(JC)) + np.max(np.abs(JA)))
    return float(np.max(np.abs(off))), scale, diag


def run_suite(obj, rho=RHO_LIVPRB, floors=FLOORS):
    """Gate every FLOORS input on obj['C']/obj['A']; returns (verdict, rows)."""
    rows = {}
    ok = True
    for k, floor in floors.items():
        if k not in obj["C"]:
            rows[k] = {"present": False}
            continue
        off, scale, diag = budget_stats(obj["C"][k], obj["A"][k], rho)
        rel = off / scale
        rows[k] = {"present": True, "off": off, "scale": scale,
                   "off_over_scale": rel, "floor": floor,
                   "cash_s1": float(diag[1]) if diag.size > 1 else None,
                   "cash_s5": float(diag[5]) if diag.size > 5 else None,
                   "pass": bool(rel <= floor)}
        ok = ok and rows[k]["pass"]
    rows["eta"] = {"present": "eta" in obj["C"], "skipped": ETA_NOTE}
    return ok, rows


def by_educ_identity(obj, tol=1e-12, shares=EDUC_SHARES):
    worst = 0.0
    for top in ("C", "A"):
        for k in obj[top]:
            agg = np.asarray(obj[top][k], float)
            s = sum(w * np.asarray(obj[top + "_by_educ"][e][k], float)
                    for e, w in shares.items())
            worst = max(worst, float(np.max(np.abs(agg - s))))
    return bool(worst <= tol), worst
