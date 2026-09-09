"""Spending around UI benefit expiry, computed from the transition matrix instead of a panel.

WHAT THIS REPLACES. `FromPandemicCode/EvalConsDropUponUILeave.py` draws two of the paper's
model-validation panels -- "Spending upon UI benefit expiry" and its with/without-splurge companion
-- from a simulated panel: it finds every household episode that ENTERS the benefit-exhausted micro
state and stays there at least `min_spell` quarters, takes a window from `lead` quarters before entry
to `lag` after, normalises by that household's own permanent income `lead` quarters before entry, and
averages across episodes.

Every one of those operations is a conditional expectation over (micro state, assets), which the
a-indexed transition matrix already carries. Simulating it buys sampling noise and drags in the whole
panel-quality question: on the uncapped calibration the MC baseline fails its own drift gate
(college Lorenz p80 drift -4.47pp against +/-3.00pp -- the N^-0.2 heavy-tail sampler limit of
BUG-092), so a VALIDATION figure would rest on a panel known to misstate the wealth distribution.
Plan: `plans_local/20260906-0500h_ui-expiry-panels-from-the-transition-matrix_plan.md`.

THE STATE. With `UBspell_normal = 2` the chain `small_MrkvArray` builds is
0 = employed, 1 = unemployed (benefits), 2 = unemployed (benefits), 3 = unemployed, benefits
EXHAUSTED. So "enters state 3" means "benefits just ran out", which is what the panel is named for.
The index is NOT hardcoded here (`exhausted_state`): under `HAFISCAL_UI_STATE_ENCODING=calendar`
there are 7 micro states and exhaustion is elsewhere. The MC generator DOES hardcode `== 3` and is
wrong under that encoding -- fix it before comparing the two engines.

THE NORMALISATION, which is the one real subtlety. The panel divides by each household's own
permanent income `lead` quarters before entry, so the ratio spans dates while the TM's policy is
per-CURRENT-permanent-income. Carrying it across the window needs the cumulative growth
p_t / p_{t-lead} = prod_s psi_s * PermGroFac_{j_s}: state-dependent through PermGroFac and
stochastic through psi. Under the P-measure E[psi] = 1 and psi is independent of the employment
chain, so the EXPECTED cumulative factor along a known state path is the product of PermGroFac over
that path -- exact for the ratio of expectations. It is NOT the expectation of the ratio when psi is
heavy-tailed, which is why `growth='pathwise'` (the default) is stated explicitly and
`growth='none'` is available to isolate the effect. See the plan's section 2.1.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, "FromPandemicCode")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def exhausted_state(agent):
    """Index of the 'unemployed, benefits exhausted' micro state for this agent's chain.

    The chain is 0 = employed, 1..ub = unemployed WITH benefits, ub+1 = exhausted, and the
    exhausted state is the one that is absorbing-until-reemployment: its only transitions are to
    itself and to employment. Found by that property rather than by index, so the calendar
    encoding (7 states) and the legacy encoding (4) both work.
    """
    M = np.asarray(agent.MrkvArray[0], dtype=float)
    J = M.shape[0]
    cands = [j for j in range(1, J)
             if M[j, j] > 1e-12 and abs(M[j, j] + M[j, 0] - 1.0) < 1e-9]
    if len(cands) != 1:
        raise ValueError(
            f"exhausted_state: expected exactly one absorbing-until-reemployment micro state, "
            f"found {cands} in a {J}-state chain. Pass the index explicitly.")
    return cands[0]


def _period_means(agent, tm_data, interpretation='CDC', neutral_measure=False):
    """Per-(carried assets, arrival state) conditional means, mirroring
    `tm_methods.compute_type_aggregates_tm_a`'s integrand line for line.

    Returns (cbar, ybar): cbar[a, jp] = E[c_actual | carried a, arrived in jp], integrating the
    post-arrival income shock exactly as the aggregator does; ybar[jp] = E[xi | jp].
    """
    import tm_methods as tm
    dist_aGrid = np.asarray(tm_data['dist_aGrid'], dtype=float)
    A = len(dist_aGrid)
    M = np.asarray(agent.MrkvArray[0], dtype=float)
    J = M.shape[0]
    IncShkDstn_list = tm_data['IncShkDstn_list']
    if neutral_measure:
        IncShkDstn_list = tm._to_neutral_measure(IncShkDstn_list)
    Splurge = float(agent.Splurge)
    Cratio = float(tm_data.get('Cratio', 1.0))
    Rfree_arr = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    sol = agent.solution[0]

    cbar = np.zeros((A, J))
    ybar = np.zeros(J)
    for jp in range(J):
        d = IncShkDstn_list[jp]
        psi, xi, pmv = d.atoms[0], d.atoms[1], d.pmv
        ybar[jp] = float(np.dot(pmv, xi))
        S = len(pmv)
        inv_pG = 1.0 / (psi * PermGroFac_arr[jp])
        m_next = (Rfree_arr[jp] * dist_aGrid)[:, None] * inv_pG[None, :] + xi[None, :]
        m_flat = m_next.ravel()
        c_star = sol.cFunc[jp](m_flat, np.full_like(m_flat, Cratio)).reshape(A, S)
        c_actual = (1.0 - Splurge) * c_star + Splurge * np.broadcast_to(xi[None, :], (A, S))
        cbar[:, jp] = c_actual @ pmv
    return cbar, ybar


def episode_distributions(kernel, ergodic, J, A, target, lead=3, lag=2, min_spell=3):
    """The conditional distribution over (micro state, assets) at each window offset.

    `kernel[x, y] = P(x -> y)` on the flattened index `x = j*A + i` (the layout
    `tm_methods` uses: `erg.reshape(J, A)`). Returns a list of length `lead+lag+1`; entry k is
    the distribution at offset `k - lead` relative to the entry date, conditional on the episode
    (enter `target` at offset 0 from some other state, and remain in it for `min_spell` periods).
    Each entry carries the episode's own mass, so the caller can normalise or weight.

    Construction, in the order the conditioning applies:

      * ENTRY. Mass sitting outside `target` that moves into it. `enter = (pi restricted to
        j != target) @ kernel, restricted to j == target`.
      * SURVIVAL. Propagate `enter` forward `min_spell-1` steps through the kernel RESTRICTED to
        `target` at every step. What survives is the episode population at offset 0; its mass is
        the episode weight.
      * LEAD. The distribution `k` periods BEFORE entry, conditional on the whole episode
        happening, by Bayes on the same kernel: propagate the SURVIVAL INDICATOR backward,
        `phi_{k+1} = kernel_restricted @ phi_k`, and weight the ergodic by it. One sparse mat-vec
        per lead period; no new machinery, and the step where an off-by-one would hide.
      * LAG. Forward from the surviving sub-distribution under the UNRESTRICTED kernel: the panel
        version does not require the household to stay past `min_spell`.
    """
    K = np.asarray(kernel, dtype=float)
    pi = np.asarray(ergodic, dtype=float).ravel()
    n = J * A
    if K.shape != (n, n) or pi.size != n:
        raise ValueError(f"episode_distributions: kernel {K.shape} / ergodic {pi.size} "
                         f"inconsistent with J={J}, A={A}")
    in_t = np.zeros(n, dtype=bool)
    in_t[target * A:(target + 1) * A] = True

    # --- forward: entry, then survival ------------------------------------------------
    pre = pi.copy()
    pre[in_t] = 0.0                       # must come from OUTSIDE the target state
    enter = pre @ K
    enter[~in_t] = 0.0                    # ... and land inside it
    K_stay = K * in_t[None, :]            # restricted: only transitions that remain inside
    surv = [enter]
    for _ in range(max(0, min_spell - 1)):
        surv.append(surv[-1] @ K_stay)
    at_entry = enter                      # offset 0 population, before survival is imposed
    survivors = surv[-1]                  # mass that lasted the whole minimum spell

    # The episode population AT EACH offset >= 0 is the sub-distribution that will survive the
    # full spell -- so run the survival indicator backward over the in-spell offsets too.
    phi_in = [np.ones(n)]
    for _ in range(max(0, min_spell - 1)):
        phi_in.append(K_stay @ phi_in[-1])
    at = []
    for k in range(min_spell):
        d = surv[k] * phi_in[min_spell - 1 - k]
        at.append(d)
    # --- lag: unrestricted forward from the end of the minimum spell ------------------
    tail = survivors.copy()
    while len(at) < min_spell + max(0, lag - (min_spell - 1)):
        tail = tail @ K
        at.append(tail)
    at = at[:lag + 1] if lag + 1 <= len(at) else at

    # --- lead: backward Bayes ---------------------------------------------------------
    # phi_0 = indicator of "enters the target next period and then survives the spell"
    phi = (K * (~in_t)[:, None]) @ (in_t.astype(float) * phi_in[min_spell - 1])
    before = []
    for _ in range(lead):
        before.append(pi * phi)
        phi = K @ phi
    before.reverse()                      # offsets -lead .. -1
    return before + at[:lag + 1]


def _state_weights(dist, J, A):
    """Mass per micro state of a flattened (J, A) distribution."""
    return np.asarray(dist, dtype=float).reshape(J, A).sum(axis=1)
