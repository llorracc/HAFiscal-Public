#!/usr/bin/env python3
"""Earnings phase — the age-free end of the permanent-income growth phase (owner ruling 2026-08-28; decision record
conclusions_private/2026-08-28_earnings-phase-state_decision.md; plan plans/20260828-2030h_earnings-phase-state_plan.md).

WHY. With education-specific permanent-income growth for an unbounded (perpetual-youth) life the cross-section of
permanent income is Pareto with tail index 1.2–1.6: Gini 0.71 against the SCF's ≈ 0.5 (cstwMPC §3.4) and an infinite
second moment (BUG-038). The original code's undocumented 200-quarter age cap was what held it to Gini 0.41, and a cap
is unavailable: the ergodic transition-matrix machinery is age-free. The Blanchard-Yaari move applied to the earnings
profile fixes it without an age: a household's deterministic growth stops with a constant hazard h per quarter (the
"matured-earner" phase; absorbing until death; newborns are born growing). Everything else — permanent shocks, the
employment/UI chain, income levels, taxes, transfers, the death hazard — is identical across phases: it is the plateau
of the age–earnings profile, NOT a retirement. At h = 1/120 (an expected growth phase of 30 years) the closed form gives
Gini 0.49, E[p] by education 8.4 / 17.2 / 24.6 $k/quarter (the original capped model's 8.6 / 17.6 / 25.2) and tail
index 2.65 / 2.34 / 2.23 (finite variance). `perm_income_alternatives.py` has the grid.

ENCODING (macro outermost, PHASE IN THE MIDDLE, employment innermost):
    Mrkv = J_full * macro + J * phase + emp,      J_full = n_phases * J,
with J = num_base_MrkvStates (the employment/UI micro chain, 7 under calendar+window; unchanged) and macro the scenario's
macro state. Consequences: the employment decode `emp = Mrkv % J` used throughout the code stays valid; the macro
decode becomes `Mrkv // J_full` (was `// J`); every macro block stays CONTIGUOUS — its 2J micro states are the growing
J followed by the matured J — so the transition-matrix builders keep their `src_offset = macro * J_micro` structure with
J_micro = J_full and the 2J×2J wrapped conditional chain; per-state arrays are [macro 0: growing | matured][macro 1: ...];
the full transition matrix has, for every macro pair (i, k), the block [[(1-h) M_ik, h M_ik], [0, M_ik]] of the
employment block M_ik (the phase transition is independent of the employment/macro transitions of the same period).
(Phase-outermost was the first draft; the 2026-08-28 inventory showed it makes a macro block's states non-contiguous,
which would have forced a redesign of every TM propagator.)

FLAG. HAFISCAL_EARNINGS_PHASE_HAZARD — the hazard per quarter as a float or a fraction ("1/120"); "0" (or unset) = OFF:
one phase, every wrapper below is the identity and the model is byte-for-byte the pre-2026-08-28 one. The default
world's value comes from config/catalog.py (`earnings_phase_hazard`, canonical "0" until the wiring's gates pass,
then "1/120"; paper "0").
"""
import os
from fractions import Fraction

import numpy as np

ENV = "HAFISCAL_EARNINGS_PHASE_HAZARD"
MATURED_GROWTH = 1.0   # the matured phase grows with the economy (PermGroFacAgg = 1): no deterministic drift


def parse_hazard(text):
    """'0' / '' / None -> 0.0; '1/120' -> 1/120; '0.0083' -> 0.0083. Raises on negatives or >= 1."""
    if text is None:
        return 0.0
    t = str(text).strip().lower()
    if t in ("", "0", "off", "none", "false"):
        return 0.0
    h = float(Fraction(t)) if "/" in t else float(t)
    if not (0.0 <= h < 1.0):
        raise ValueError(f"{ENV}={text!r}: the hazard must be in [0, 1)")
    return h


def hazard(environ=None):
    """The per-quarter growing -> matured hazard from the environment (0.0 = the phase machinery is OFF)."""
    env = os.environ if environ is None else environ
    return parse_hazard(env.get(ENV))


def enabled(environ=None):
    return hazard(environ) > 0.0


def _h(h):
    return hazard() if h is None else float(h)


def n_phases(h=None):
    return 2 if _h(h) > 0.0 else 1


def j_full(J, h=None):
    """The micro count per macro block: n_phases * J."""
    return n_phases(h) * int(J)


def n_states(J, n_macro, h=None):
    """Total composite states: n_phases * J * n_macro."""
    return n_phases(h) * int(J) * int(n_macro)


def phase_matrix(h=None):
    """P[p, q] = Pr(phase q next | phase p now): growing -> matured with hazard h; matured absorbing."""
    h = _h(h)
    if h <= 0.0:
        return np.array([[1.0]])
    return np.array([[1.0 - h, h], [0.0, 1.0]])


# ----------------------------------------------------------------------------- decoders / composer
def emp_of(mrkv, J):
    return np.asarray(mrkv) % int(J)


def phase_of(mrkv, J, h=None):
    return (np.asarray(mrkv) // int(J)) % n_phases(h)


def macro_of(mrkv, J, h=None):
    return np.asarray(mrkv) // j_full(J, h)


def compose(phase, macro, emp, J, h=None):
    """Mrkv = J_full * macro + J * phase + emp."""
    return j_full(J, h) * np.asarray(macro) + int(J) * np.asarray(phase) + np.asarray(emp)


def to_growing(mrkv, J, h=None):
    """The same (macro, emp) state in the growing phase."""
    return compose(0, macro_of(mrkv, J, h), emp_of(mrkv, J), J, h)


# ----------------------------------------------------------------------------- wrappers (identity when OFF)
def wrap_chain(M, J=None, h=None):
    """Full transition matrix over J*n_macro states (layout J*macro + emp) -> over J_full*n_macro states (layout
    J_full*macro + J*phase + emp): for every macro pair (i, k) the employment block M_ik becomes
    [[(1-h) M_ik, h M_ik], [0, M_ik]]. Row-stochastic in, row-stochastic out. `J=None` means one macro block (the
    base scenario / a conditional micro chain), i.e. J = M.shape[0]. Accepts a list of per-period arrays."""
    h = _h(h)
    if isinstance(M, (list, tuple)):
        return [wrap_chain(m, J, h) for m in M]
    M = np.asarray(M, dtype=float)
    if h <= 0.0:
        return M
    n = M.shape[0]
    J = n if J is None else int(J)
    if n % J:
        raise ValueError(f"wrap_chain: matrix size {n} is not a multiple of J={J}")
    n_macro = n // J
    P = phase_matrix(h)
    M4 = M.reshape(n_macro, J, n_macro, J)                              # [i, e, k, f]
    W6 = np.einsum("pq,iekf->ipekqf", P, M4)                              # [i, p, e, k, q, f]
    return W6.reshape(2 * n, 2 * n)


def wrap_states(arr, J=None, matured=None, h=None):
    """Per-state array over J*n_macro states -> over J_full*n_macro states, block by block: each macro block's J
    entries become [J entries | matured J entries] (the matured entries equal the growing ones unless `matured` is a
    scalar or a J-vector). Identity when OFF. `J=None` means one macro block."""
    h = _h(h)
    a = np.asarray(arr)
    if h <= 0.0:
        return a
    n = a.shape[0]
    J = n if J is None else int(J)
    if n % J:
        raise ValueError(f"wrap_states: array length {n} is not a multiple of J={J}")
    n_macro = n // J
    g = a.reshape(n_macro, J)
    if matured is None:
        m = g
    elif np.isscalar(matured):
        m = np.full_like(g, matured, dtype=float)
    else:
        m = np.broadcast_to(np.asarray(matured, dtype=float).reshape(1, J), g.shape)
    return np.stack([g, m], axis=1).reshape(2 * n)


def wrap_permgrofac(pgf, J=None, h=None):
    """Per-state PermGroFac -> growth stops in the matured phase (MATURED_GROWTH in every matured state)."""
    return wrap_states(np.asarray(pgf, dtype=float), J, matured=MATURED_GROWTH, h=h)


def wrap_list(items, J=None, h=None):
    """Per-state Python list over J*n_macro states (e.g. IncShkDstn per state) -> J_full*n_macro, block by block
    (the matured entries are the SAME objects as the growing ones). Identity when OFF."""
    h = _h(h)
    items = list(items)
    if h <= 0.0:
        return items
    n = len(items)
    J = n if J is None else int(J)
    if n % J:
        raise ValueError(f"wrap_list: list length {n} is not a multiple of J={J}")
    out = []
    for b in range(n // J):
        block = items[b * J:(b + 1) * J]
        out += block + block
    return out


def wrap_birth(dist, J=None, h=None):
    """Newborn state distribution (over one macro block's J employment states, or over J*n_macro) -> everyone is born
    growing: each macro block's J entries become [dist | zeros]. Identity when OFF."""
    h = _h(h)
    d = np.asarray(dist, dtype=float)
    if h <= 0.0:
        return d
    return wrap_states(d, J, matured=0.0, h=h)


def growing_block_ergodic(M_full_base, J, h=None):
    """Birth distribution helper: the ergodic vector of the EMPLOYMENT chain (the growing J×J block of a one-macro
    wrapped chain, rescaled by 1/(1-h)), wrapped into the growing phase. Needed because the ergodic eigenvector of the
    wrapped chain is degenerate (matured is absorbing: all its mass is matured)."""
    h = _h(h)
    M = np.asarray(M_full_base, dtype=float)
    if h <= 0.0:
        M_emp = M
    else:
        M_emp = M[:J, :J] / (1.0 - h)
    vals, vecs = np.linalg.eig(M_emp.T)
    idx = int(np.argmin(np.abs(vals - 1.0)))
    pi = np.abs(vecs[:, idx].real); pi /= pi.sum()
    return wrap_birth(pi, None, h)


def tile_permgrofac_composite(PermGroFac_base, PermGroFac_unemp, num_mrkv_states, num_base_MrkvStates, h=None):
    """Phase-aware twin of income_process_sst.tile_PermGroFac_composite for the composite state space: state j is
    employed iff emp_of(j) == 0; it grows at G_emp only in the growing phase; the matured phase grows at
    MATURED_GROWTH; unemployed growing states grow at G_unemp. With the phase OFF this is exactly the SST's rule."""
    h = _h(h)
    G_emp = float(np.asarray(PermGroFac_base).ravel()[0]); G_u = float(PermGroFac_unemp)
    J = int(num_base_MrkvStates); n = int(num_mrkv_states)
    out = np.empty(n, dtype=np.float64)
    for j in range(n):
        if h > 0.0 and phase_of(j, J, h) == 1:
            out[j] = MATURED_GROWTH
        else:
            out[j] = G_emp if emp_of(j, J) == 0 else G_u
    return out


def describe(h=None):
    h = _h(h)
    if h <= 0.0:
        return "earnings phase OFF (one phase; growth for life)"
    return (f"earnings phase ON: growing -> matured hazard {h:.6g}/quarter (expected growth phase "
            f"{1.0 / h / 4:.1f} years); matured PermGroFac = {MATURED_GROWTH}; layout Mrkv = 2J*macro + J*phase + emp")
