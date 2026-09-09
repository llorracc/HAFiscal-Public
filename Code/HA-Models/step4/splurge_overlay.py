"""The splurge overlay — single home (SST) for the arm formulas ge.py applies.

Extracted 2026-09-01 so that (i) the GE stage and the PE-reproduction gate apply the
IDENTICAL arithmetic, (ii) the by-education branch uses the SAME arm as the aggregate
(it used to hardcode the legacy formula — under a `cash` aggregate that overstated the
education incidence decomposition's impact C by +12.6 % transfers/Taylor), and (iii) the
`cash` arm's return operator can be the model constant rho = R*LivPrb instead of an
estimate read off the DiscFac column (the estimate is biased low by the column's own
~1e-3 budget error and injects a one-signed +0.4-0.9 % NPV drizzle).

Arms (HAFISCAL_HANK_SPLURGE_DIAG):
  legacy : as shipped and as in the frozen monolith. `present_value` is NOT a present
           value -- both R**arange factors broadcast on the column axis and cancel,
           leaving the undiscounted column sum (BUG-111).
  pv     : the one-line broadcasting correction (discounts along TIME).
  cash   : the paper's rule c_sp = varsigma*y -- the splurge component is the cash the
           column actually delivers, dY from the household flow budget; the UNIQUE
           budget-consistent pair {varsigma*dY + (1-varsigma)*J_C, (1-varsigma)*J_A}.

Return-operator source inside `cash` (HAFISCAL_HANK_SPLURGE_RHO):
  livprb   : rho = R*LivPrb, the model constant (default).
  estimate : the shipped f_t identification from the DiscFac column (kept as the
             reproduction reference for the pre-upgrade construction).
"""
import os

import numpy as np

OVERLAID_INPUTS = ['transfers', 'tau', 'UI_extend', 'UI_rr', 'eta', 'w']
EDUCS = ['dropout', 'highschool', 'college']


def resolve_diag_arm():
    # DEFAULT FLIPPED to `cash` 2026-09-01 with the column-0 flip, by the owner's
    # PE-reproduction rule (never separately: cash alone on the shipped column moves
    # the check AWAY from the PE -- the measured ordering constraint). `legacy` stays
    # as the reproduction reference arm with its recorded failure signature.
    arm = os.environ.get("HAFISCAL_HANK_SPLURGE_DIAG", "cash").strip().lower()
    if arm not in ("legacy", "pv", "cash"):
        raise ValueError(f"HAFISCAL_HANK_SPLURGE_DIAG={arm!r}; expected legacy|pv|cash")
    return arm


def resolve_rho_mode():
    mode = os.environ.get("HAFISCAL_HANK_SPLURGE_RHO", "livprb").strip().lower()
    if mode not in ("livprb", "estimate"):
        raise ValueError(f"HAFISCAL_HANK_SPLURGE_RHO={mode!r}; expected livprb|estimate")
    return mode


def f_t_estimate(C_disc, A_disc, periods):
    """The shipped return-operator identification (BUG-111 `cash` as first coded):
    the DiscFac column has dY == 0 by construction, so f_t = (A_t + C_t)/A_{t-1}
    read at one interior column. Kept byte-for-byte for the `estimate` arm."""
    _c = periods // 10                      # a column clear of both edges
    f_t = np.ones(periods)
    for _t in range(1, periods):
        _den = A_disc[_t - 1, _c]
        f_t[_t] = (A_disc[_t, _c] + C_disc[_t, _c]) / _den if _den != 0 else 1.0
    return f_t


def recover_dY(JC, JA, f_t):
    """dY[t,s] = C[t,s] + A[t,s] - f_t*A[t-1,s] -- the household flow budget, the same
    identity BUG-112 scores the columns with. f_t may be a length-T vector (estimate
    mode) or a scalar rho broadcast over t (livprb mode)."""
    JC = np.asarray(JC)
    JA = np.asarray(JA)
    f = np.asarray(f_t, dtype=float)
    if f.ndim == 0:
        f = np.full(JC.shape[0], float(f))
    dY = np.zeros_like(JC)
    dY[0] = JC[0] + JA[0]
    dY[1:] = JC[1:] + JA[1:] - f[1:, None] * JA[:-1]
    return dY


def splurge_component(JC, JA, arm, R, periods, f_t=None):
    """The splurge's own spending matrix K for one input, per arm."""
    JC = np.asarray(JC)
    if arm == "cash":
        return recover_dY(JC, JA, f_t)
    if arm == "pv":
        present_value = np.sum(JC / R ** np.arange(periods)[:, None], axis=0)
    else:  # legacy -- the factors cancel; kept verbatim (BUG-111)
        present_value = np.sum((JC / R ** np.arange(periods)), axis=0)
    return np.diag(present_value * R ** np.arange(periods))


def overlay_pair(JC, JA, arm, splurge, R, periods, f_t=None):
    """One input's overlaid (J_C', J_A')."""
    K = splurge_component(JC, JA, arm, R, periods, f_t=f_t)
    JC_new = splurge * K + (1 - splurge) * np.asarray(JC)
    JA_new = (1 - splurge) * np.asarray(JA)
    return JC_new, JA_new


def resolve_f_t(arm, rho_mode, C_dict, A_dict, R, livprb, periods):
    """The return operator the cash arm uses; None for the diagonal arms."""
    if arm != "cash":
        return None
    if rho_mode == "livprb":
        return R * livprb
    C_disc = np.asarray(C_dict.get('DiscFac'))
    A_disc = np.asarray(A_dict.get('DiscFac'))
    if C_disc.ndim != 2 or not np.any(C_disc):
        raise ValueError("HAFISCAL_HANK_SPLURGE_RHO=estimate needs a live DiscFac column "
                         "to identify the return operator (see BUG-111)")
    return f_t_estimate(C_disc, A_disc, periods)


def apply_aggregate(Jacobian_Dict, old_Jacobian_Dict, arm, splurge, R, livprb,
                    periods, rho_mode=None):
    """Overlay the aggregate JacobianDict in place (mirrors ge.py's historical loop)."""
    rho_mode = rho_mode or resolve_rho_mode()
    f_t = resolve_f_t(arm, rho_mode, old_Jacobian_Dict['C'], old_Jacobian_Dict['A'],
                      R, livprb, periods)
    for inp in OVERLAID_INPUTS:
        JC_new, JA_new = overlay_pair(old_Jacobian_Dict['C'][inp],
                                      old_Jacobian_Dict['A'][inp],
                                      arm, splurge, R, periods, f_t=f_t)
        Jacobian_Dict['C'][inp] = JC_new
        Jacobian_Dict['A'][inp] = JA_new
    return f_t


def apply_by_educ(Jacobian_Dict_by_educ, old_by_educ, arm, splurge, R, livprb,
                  periods, rho_mode=None):
    """Overlay the by-education dicts with the SAME arm as the aggregate.

    Historical defect (fixed here): this branch applied the legacy formula
    unconditionally. Under `cash` each education's dY is recovered from its own
    columns with the same operator (LivPrb is common across groups; the per-educ
    budget closes at rho = R*LivPrb to ~1e-5 away from the cap atom)."""
    rho_mode = rho_mode or resolve_rho_mode()
    for educ in EDUCS:
        Ck, Ak = 'C_' + educ, 'A_' + educ
        f_t = resolve_f_t(arm, rho_mode, old_by_educ[Ck], old_by_educ[Ak],
                          R, livprb, periods)
        for inp in OVERLAID_INPUTS:
            JC_new, JA_new = overlay_pair(old_by_educ[Ck][inp], old_by_educ[Ak][inp],
                                          arm, splurge, R, periods, f_t=f_t)
            Jacobian_Dict_by_educ[Ck][inp] = JC_new
            Jacobian_Dict_by_educ[Ak][inp] = JA_new
