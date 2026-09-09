"""Household-block setup for the Step-4 Jacobian stage (live engine).

Calibration ingestion, the SAM employment chain, and the income
distributions — built CLEAN: every distribution is constructed directly
as a DiscreteDistributionLabeled from its intended atoms, so positional
and labeled views agree by construction. This is the fixed-semantics
equivalent of the frozen monolith's deepcopy-mutate-then-relabel dance
(BUG-071 fix ON): identical pmv/atom values, hence identical solves.
Historical (stale-shock / Gamma=1 / baseline-zeroth) arms live ONLY in
the frozen monolith; the entry scripts route there.

Intentionally NOT carried over from the monolith (display-only or dead
in the live path): the UJAC plot block (the GE stage recomputes UJAC),
the scipy eigs ergodic-distribution computation (unused by this stage),
and the AggDemandEconomy construction (never consumed).

Earnings phase (2026-08-29; conclusions_private/2026-08-28_earnings-phase-
state_decision.md, SST Code/HA-Models/earnings_phase.py): with
HAFISCAL_EARNINGS_PHASE_HAZARD on, the household block carries the PE
model's second household state — the earnings PHASE {growing, matured} —
in the PE model's own layout, `J_full*macro + J*phase + emp` with one
macro block here: [growing `states` | matured `states`] = 2 x 6 = 12
states. The SAM employment chain is UNCHANGED (the phase rides on top of
it): the PE base chain arrives wrapped (14 = 2 x 7 states), its
employment block is extracted (`pe_employment_block`), normalized to the
HANK's 6 as before, and re-wrapped with the hazard
(`earnings_phase.wrap_chain`: [[(1-h)M6, hM6], [0, M6]]); PermGroFac is
the employment block's in the growing states and 1 in every matured
state (`wrap_permgrofac`); Rfree/LivPrb/the six income-distribution
lists are duplicated block-wise (the matured phase's income process IS
the growing phase's); newborns are born growing (the transition builders'
newborn reset, `step4_fast_tranmat.newborn_phase_J`, keyed on the agent
attribute `earnings_phase_hazard` set here). The GE stage (ge.py) works
on the employment chain only — `unemployment_chains()` returns the same
6-state chains with the phase on or off — because the household
Jacobians it consumes are already aggregated over every state. OFF: every
wrapper is the identity and the block is byte-for-byte the pre-phase one.
"""
import os
from copy import deepcopy
from types import SimpleNamespace

import numpy as np

from .common import ensure_paths

ensure_paths()

from HARK.distributions import DiscreteDistributionLabeled  # noqa: E402
from ConsMarkovModel import MarkovConsumerType  # noqa: E402
# BUG-105 (2026-08-30): the unemployed income process has ONE source of truth, created by BUG-090's fix; Step 4 was the
# fourth construction site and is now routed onto it. The SST decides the permanent/transitory rows from the PE flags;
# this module supplies only the benefit LEVEL (where its wage_ss*(1-tau_ss) wedge and the dx arms live).
from income_process_sst import build_unemployed_inc_shk_dstn  # noqa: E402
from Parameters import return_parameters  # noqa: E402
import earnings_phase  # noqa: E402  (Code/HA-Models; the phase SST)
from step4_fast_tranmat import PHASE_HAZARD_ATTR, phase_hazard_of  # noqa: E402

# Grid and horizon constants — identical to the frozen monolith.
mCount = 200
bigT = int(os.environ.get("HAFISCAL_HANK_BIGT", "300"))   # S3 knob (2026-08-30): truncation horizon of the Jacobians/GE; 300 = the published value

# HAFISCAL_HANK_NEWBORN_M default resolution (owner ruling 2026-09-02: the
# `income` newborn — newborns hold their state's own first income draw — is
# the DEFAULT-world HANK convention, an IMPROVEMENT: PE-faithful, since PE
# newborns hold ZERO assets (kLogInitMean = log(1e-5)), and scale-covariant,
# closing the A7 homotheticity boundary permanently; production materiality
# +0.14%..+0.29% on all six multiplier cells). Scoped HERE, at the step4
# entry, ON PURPOSE: the knob's reader lives in the SHARED transition
# builders (ConsMarkovModel / step4_fast_tranmat) that the PE TM-a engine
# also uses — a global default flip would silently change Step-2/5a, which
# was neither measured nor ruled. PE consumers never set the env and the
# reader's own default is `unit`. Published-reproduction arms stay `unit`:
# QE_FIDELITY (the frozen shape) and the as-corrected world (IMPROVEMENTs
# off there per the world scheme). setdefault, so an explicit env always wins.
_qe_fid = os.environ.get("HAFISCAL_QE_FIDELITY", "").strip().lower() in ("1", "on", "true")
_world_ac = os.environ.get("HAFISCAL_WORLD", "default").strip().lower() == "as-corrected"
os.environ.setdefault("HAFISCAL_HANK_NEWBORN_M",
                      "unit" if (_qe_fid or _world_ac) else "income")
if os.environ["HAFISCAL_HANK_NEWBORN_M"] == "income":
    print("[hank-newborn] HAFISCAL_HANK_NEWBORN_M=income (default-world "
          "IMPROVEMENT, owner 2026-09-02: newborns hold their first income "
          "draw — PE-faithful, scale-covariant)", flush=True)
aMax = 1_000_000
aCount = 200
states = 4 + 2      # EMPLOYMENT states per phase block: employed + 5 unemployment durations
num_mrkv = states
dx = 0.0001
# Quarterly survival probability (perpetual youth). Module-level so the GE stage's
# splurge overlay can use the model constant rho = R*LivPrb (BUG-111 upgrade) from
# the same source the household block builds with.
LIVPRB_SS = 0.99375



def n_hank_states():
    """Total household states of the HANK block: {growing, matured} x `states` (= 12) under the earnings
    phase, `states` (= 6) without it — `earnings_phase.n_states(J, n_macro=1)`, the PE model's own count."""
    return earnings_phase.n_states(states, 1)
# BUG-077 stage B: the steady-state tax rate is DERIVED (the shared
# tau* funding the full-0.7 eligible UI + debt interest, G==0) rather
# than the historical arbitrary 0.3 — one source for the whole engine
# (this retires the twin literals this file and ge.py used to carry).
from .common import resolve_tau_ss  # noqa: E402
tau_ss, _tau_mode = resolve_tau_ss()
print(f"[hank-tau] tau_ss = {tau_ss:.6f} ({_tau_mode}"
      + (", the shared BUG-077 tau*" if _tau_mode == "derived" else "")
      + ")", flush=True)
wage_ss = 1.0

# SAM employment chain (6 states: employed + 5 unemployment durations).
job_find = 2 / 3
EU_prob = 0.0306834
job_sep = EU_prob / (1 - job_find)

markov_array_ss = np.array(
    [[1 - job_sep * (1 - job_find), job_find, job_find, job_find, job_find, job_find],
     [job_sep * (1 - job_find), 0., 0., 0, 0, 0],
     [0., (1 - job_find), 0., 0., 0., 0.],
     [0., 0, (1 - job_find), 0., 0., 0.],
     [0., 0, 0., (1 - job_find), 0., 0.],
     [0., 0., 0, 0, (1 - job_find), (1 - job_find)]])


def create_matrix_U(dx, base_rs=None):
    """The chain with the job-finding probability perturbed by dx.

    base_rs=None reproduces the legacy shared chain from the module
    literals above (byte-identical to the historical construction).
    Passing a group's ROW-stochastic base chain (init['MrkvArray'][0] —
    the PE education-specific chain, BUG-076) builds the same
    perturbation pattern at THAT group's separation rate:
    jf = base_rs[1,0] (the u1->e flow), sep = base_rs[0,1]/(1-jf)
    (since e->u1 = sep*(1-jf)). Returns the COLUMN-stochastic form
    (callers transpose for HARK, matching the legacy convention).
    """
    if base_rs is None:
        jf = job_find
        sep = job_sep
    else:
        jf = float(base_rs[1, 0])
        sep = float(base_rs[0, 1]) / (1.0 - jf)
    job_find_dx = jf + dx
    markov_array = np.array(
        [[1 - sep * (1 - job_find_dx), job_find_dx, job_find_dx, job_find_dx, job_find_dx, job_find_dx],
         [sep * (1 - job_find_dx), 0., 0., 0, 0, 0],
         [0., (1 - job_find_dx), 0., 0., 0., 0.],
         [0., 0, (1 - job_find_dx), 0., 0., 0.],
         [0., 0, 0., (1 - job_find_dx), 0., 0.],
         [0., 0., 0, 0, (1 - job_find_dx), (1 - job_find_dx)]])
    return markov_array


def _split_wrapped_chain(m, J, h, what="chain"):
    """The employment block M of a phase-wrapped chain [[(1-h)M, hM], [0, M]] over 2J states, after checking
    that structure (a chain that is not the wrapped layout is REFUSED, never silently sliced). M is read from
    the matured block, which `earnings_phase.wrap_chain` fills with exactly 1.0 * M (bitwise the employment
    chain); the growing block carries (1-h) M."""
    n = m.shape[0]
    if m.shape != (n, n) or n != 2 * J:
        raise ValueError(f"earnings phase: {what} has shape {m.shape}, not the wrapped 2J = {2 * J} states")
    M = m[J:, J:]
    if not (np.all(m[J:, :J] == 0.0) and np.allclose(m[:J, :J], (1.0 - h) * M, rtol=1e-12, atol=1e-15)
            and np.allclose(m[:J, J:], h * M, rtol=1e-12, atol=1e-15)):
        raise ValueError(f"earnings phase: {what} is not the wrapped [[(1-h)M, hM], [0, M]] structure "
                         "(matured absorbing, growing = (1-h) M, growing->matured = h M)")
    return M


def pe_employment_block(m_rs, PermGroFac=None):
    """The EMPLOYMENT block of the PE base chain (and of its per-state PermGroFac) as the PE calibration
    delivers it: with HAFISCAL_EARNINGS_PHASE_HAZARD on the chain arrives wrapped over 2J states
    ([growing J | matured J], J = 7 under calendar/window) and PermGroFac is 2J long (growth in the growing
    block, 1 in every matured state); the employment chain M (J x J) and the growing block's growth vector are
    what the HANK's 6-state normalization consumes (`normalize_to_hank_states`). OFF: identity (the same
    objects pass through). The matured growth entries are checked to be earnings_phase.MATURED_GROWTH."""
    h = earnings_phase.hazard()
    m = np.asarray(m_rs, dtype=float)
    if h <= 0.0:
        return m if PermGroFac is None else (m, np.asarray(PermGroFac, dtype=float).ravel())
    J = m.shape[0] // 2
    M = _split_wrapped_chain(m, J, h, what="PE base chain")
    if PermGroFac is None:
        return M
    g = np.asarray(PermGroFac, dtype=float).ravel()
    if g.shape[0] != 2 * J:
        raise ValueError(f"earnings phase: PE PermGroFac has {g.shape[0]} entries for a {2 * J}-state chain")
    if not np.all(g[J:] == earnings_phase.MATURED_GROWTH):
        raise ValueError("earnings phase: the PE PermGroFac's matured block is not MATURED_GROWTH")
    return M, g[:J]


def _looks_wrapped(m):
    """True when a square matrix has an absorbing upper half: the phase-wrapped layout's fingerprint
    (a zero lower-left block). Used only as a tripwire, and only while the phase is on."""
    n = m.shape[0]
    return n % 2 == 0 and n >= 4 and bool(np.all(m[n // 2:, :n // 2] == 0.0))


def normalize_to_hank_states(m_rs, n_states=None, PermGroFac=None):
    """Bring a PE base chain (and its per-state PermGroFac) to the HANK's `states` count.

    The HANK household block carries `states` = 6 micro states (employed + 5
    unemployment durations). The PE calibration's base chain has
    2 + UBspell_normal + n_extension states (4 under HAFISCAL_UI_STATE_ENCODING=
    legacy, 6 under bug_fix or calendar/history, 7 under calendar/window -- the
    2026-08-26 default). In the BASE scenario every state past u{UBspell_normal}Q
    pays no benefits and has the same exit probability, so those tail states are
    LUMPABLE: merging them (7 -> 6) or splitting the absorbing no-benefit state
    (4 -> 6) yields exactly the 6-state chain the bug_fix encoding delivered --
    the same floats in the same places (the tail rows are copies of one another).
    Asserted below (lumpability), not assumed.

    This operates on the EMPLOYMENT chain only. Under the earnings phase the PE
    chain arrives wrapped over 2J states; callers extract the employment block
    first (`pe_employment_block`) and re-wrap the result (`build()`). A wrapped
    chain handed in directly is refused: its matured block would be "lumped" into
    the unemployment tail.
    """
    n = states if n_states is None else int(n_states)
    m = np.asarray(m_rs, dtype=float)
    k = m.shape[0]
    if earnings_phase.enabled() and k != n and _looks_wrapped(m):
        raise ValueError(f"normalize_to_hank_states: a {k}-state chain with an absorbing upper half under the "
                         "earnings phase — pass the employment block (pe_employment_block), not the wrapped chain")
    if k == n:
        out_m = m
    elif k > n:
        # collapse: states n-1..k-1 -> one absorbing tail state (columns summed; the merged
        # rows must coincide after the column collapse -- lumpability, asserted)
        out_m = np.zeros((n, n))
        out_m[:n - 1, :n - 1] = m[:n - 1, :n - 1]
        out_m[:n - 1, n - 1] = m[:n - 1, n - 1:].sum(axis=1)
        tail = np.concatenate([m[n - 1, :n - 1], [m[n - 1, n - 1:].sum()]])
        out_m[n - 1] = tail
        for r in range(n, k):
            row = np.concatenate([m[r, :n - 1], [m[r, n - 1:].sum()]])
            assert np.allclose(row, tail), (
                f"PE chain tail state {r} is not lumpable into the HANK tail: {row} vs {tail}")
    else:
        # expand: split the absorbing tail state (index k-1) into n-k+1 duration states,
        # each advancing to the next with the tail's own persistence
        out_m = np.zeros((n, n))
        out_m[:k - 1, :k - 1] = m[:k - 1, :k - 1]
        out_m[:k - 1, k - 1] = m[:k - 1, k - 1]          # ..-> first split state
        tail = m[k - 1]
        for r in range(k - 1, n):
            out_m[r, :k - 1] = tail[:k - 1]
            out_m[r, min(r + 1, n - 1)] = tail[k - 1]
    assert np.allclose(out_m.sum(axis=1), 1.0), "normalized chain not row-stochastic"
    if PermGroFac is None:
        return out_m
    g = np.asarray(PermGroFac, dtype=float).ravel()
    if g.shape[0] == n:
        out_g = g
    elif g.shape[0] > n:
        assert np.allclose(g[n - 1:], g[-1]), "PE PermGroFac tail states differ; cannot trim"
        out_g = g[:n]
    else:
        out_g = np.concatenate([g, np.full(n - g.shape[0], g[-1])])
    return out_m, out_g


def chain_base_for(agent):
    """The base chain to perturb for the job_find instrument (BUG-076).

    None under the legacy shared chain (create_matrix_U then follows the
    byte-identical literal path); the agent's own row-stochastic base
    chain under the pe default, so each education group's eta-Jacobian
    is computed on ITS chain. Under the earnings phase the agent's chain
    is the wrapped 2 x 6; the perturbation is an EMPLOYMENT-chain object,
    so its 6 x 6 employment block is returned (`perturbed_mrkv` re-wraps).
    """
    if os.environ.get("HAFISCAL_HANK_UNEMP_CHAINS", "pe").strip().lower() == "legacy":
        return None
    return employment_block_of(agent)


def employment_block_of(agent):
    """The agent's 6 x 6 employment chain (row-stochastic): its MrkvArray[0] itself without the phase, the
    matured block of the wrapped chain with it (keyed on the agent's own `earnings_phase_hazard`, the value
    build() constructed it with — never re-read from the environment)."""
    m = np.asarray(agent.MrkvArray[0], dtype=float)
    h = phase_hazard_of(agent)
    if h <= 0.0:
        return agent.MrkvArray[0]
    return _split_wrapped_chain(m, m.shape[0] // 2, h, what="agent MrkvArray[0]")


def perturbed_mrkv(agent, dx_):
    """The row-stochastic MrkvArray entry with the job-finding probability perturbed by dx (the eta
    instrument; it touches the CHAIN ONLY -- no income object -- which is the precondition for the
    eta column 0 being purely compositional: see jacobians.py, "THE DATING OF eta") on the agent's OWN state space: create_matrix_U on this group's employment chain (BUG-076;
    None = the legacy literal chain), transposed to HARK's row convention, and — when the agent carries the
    earnings phase — re-wrapped by the same hazard ([[(1-h)M_dx, hM_dx], [0, M_dx]]: the phase transition is
    independent of the employment transition of the same period, so the perturbation touches both phases
    alike). Without the phase `wrap_chain` is the identity and this is byte-for-byte
    `create_matrix_U(dx, base_rs=chain_base_for(agent)).T`."""
    m_dx = create_matrix_U(dx_, base_rs=chain_base_for(agent)).T
    h = phase_hazard_of(agent)
    return earnings_phase.wrap_chain(m_dx, h=h) if h > 0.0 else m_dx


def unemployment_chains(inits=None):
    """Per-education employment chains for the GE stage (BUG-076 fix;
    stage A of plans/20260810-1030h_pe-hank-tax-alignment_plan.md).

    Returns dict(mode, jf, shares, chains_cs, seps):
      chains_cs — list of three COLUMN-stochastic 6x6 chains
        (dropout/highschool/college; ge.py's UJAC convention);
      seps — the implied per-group separation rates;
      shares — data_EducShares population weights (None under legacy).
    mode='legacy': the single shared literal chain replicated three
    times (the historical construction — the PE HIGHSCHOOL process,
    EU_prob 0.0306834 = the HS separation rate rounded to 7 digits,
    applied to every group). Callers MUST then use the single-chain
    code path with NO population weighting, so the escape stays
    byte-identical to the historical construction.
    mode='pe' (default): the education-specific PE base chains the
    calibration delivers in init['MrkvArray'] (Urate_normal_{d,h,c} =
    0.085/0.044/0.027 through make_cond_mrkv_arrays_base) — consumed,
    not re-typed.
    """
    mode = os.environ.get("HAFISCAL_HANK_UNEMP_CHAINS", "pe").strip().lower()
    if mode == "legacy":
        return dict(mode=mode, jf=job_find, shares=None,
                    chains_cs=[markov_array_ss] * 3, seps=[job_sep] * 3)
    if inits is None:
        inits = return_parameters(Parametrization='Baseline',
                                  OutputFor='_Main.py')[0:3]
    # Normalized to the HANK's `states` count (lumpable no-benefit tail; see
    # normalize_to_hank_states) -- the PE chain has 4/6/7 states by UI encoding,
    # and arrives phase-wrapped (2 x 7) under the earnings phase: the GE's SAM
    # chain is the EMPLOYMENT chain, identical with the phase on or off.
    chains_rs = [normalize_to_hank_states(pe_employment_block(i['MrkvArray'][0])) for i in inits]
    for _m in chains_rs:
        assert _m.shape == (states, states), (
            f"BUG-076 pe chains: got MrkvArray shape {_m.shape} after normalization "
            f"(check HAFISCAL_UI_STATE_ENCODING)")
        assert np.allclose(_m.sum(axis=1), 1.0), "MrkvArray not row-stochastic"
    jf = float(chains_rs[0][1, 0])
    seps = [float(_m[0, 1]) / (1.0 - jf) for _m in chains_rs]
    from EstimParameters import data_EducShares as _shares
    return dict(mode=mode, jf=jf, shares=list(_shares),
                chains_cs=[_m.T for _m in chains_rs], seps=seps)


def _labeled(pmv, atoms):
    return DiscreteDistributionLabeled(
        pmv=np.asarray(pmv), atoms=np.asarray(atoms),
        var_names=["PermShk", "TranShk"])


def wrap_phase_dstns(per_state):
    """A per-employment-state list of income distributions -> the phase layout [growing 6 | matured 6]:
    the matured phase's income process IS the growing phase's (permanent shocks, benefit levels, taxes
    identical across phases — only the deterministic growth differs, and that lives in PermGroFac).
    Unlike `earnings_phase.wrap_list` (which aliases), the matured entries are DISTINCT deep copies:
    `MarkovConsumerType.harmenberg_income_process` rescales each state's pmv IN PLACE, so an aliased
    object would be rescaled twice. Identity (the same list object) when the phase is off."""
    if not earnings_phase.enabled():
        return per_state
    return list(per_state) + [deepcopy(d) for d in per_state]


def _build_income_dstns(base_type_list, p_on, t_on=False):
    """The six per-education income-distribution lists (baseline + the
    five instrument perturbations). The EMPLOYED slots are built here with
    the monolith's own expressions (same IEEE values); the UNEMPLOYED slots
    come from the income-process SST (`build_unemployed_inc_shk_dstn`) at
    the benefit level this block computes -- BUG-105.

    Slots per list: [employed, u1, u2 (with UI), u3, u4, u5 (post-UI)].
    p_on / t_on: the PE agent's `perm_/tran_shocks_during_unemployment`
    (resolved in build(); HAFISCAL_HANK_UNEMP_PSI is an explicit override
    of p_on, no longer an independent source).
    p_on: True keeps the employed permanent-shock marginal during
    unemployment (HAFISCAL_HANK_UNEMP_PSI=main); False is the default
    degenerate psi=1 during unemployment.
    """
    IncShkDstn = []
    IncShkDstn_transfers_dx = []
    IncShkDstn_wage_dx = []
    IncShkDstn_tax_dx = []
    IncShkDstn_ui_extend_dx = []
    IncShkDstn_ui_rr_dx = []

    # R-e item-2 MATERIALITY PROBE arm (diagnostic; ruling open):
    # HAFISCAL_HANK_INCOME_LEVEL = "net" (default — the historical
    # (1−τ_ss) level wedge on every flow) | "gross" (the PE-identical
    # income levels: employed mean-one, replacement 0.7/0.5, NO wedge).
    # Under "gross" every instrument's perturbation INCREMENT is kept
    # absolutely identical to the net arm (same +dx, same −θ·w·dx tax
    # point, same 0.7-scaled wage/UI increments) so all Jacobian UNITS
    # are unchanged and the GE stage consumes them as-is: the deltas
    # isolate the pure steady-state-level effect (the β̂-mismatch
    # question). NOT a coherent GE default without further accounting
    # (the fiscal blocks collect τ·w·N).
    _gross = os.environ.get("HAFISCAL_HANK_INCOME_LEVEL", "net").strip().lower() == "gross"
    if _gross:
        print("[hank-income] GROSS income level (R-e item-2 probe arm; "
              "J units unchanged)", flush=True)

    for ThisType in base_type_list:
        src = ThisType.IncShkDstn[0]
        pmv = np.asarray(src.pmv).copy()
        base = np.asarray(src.atoms).copy()  # (2, n): [PermShk, TranShk]
        b0, b1 = base[0], base[1]

        if _gross:
            # PE-identical levels; increments identical to the net arm.
            emp1 = b1 * wage_ss
            emp1_wage_dx = emp1 + b1 * dx * (1 - tau_ss)
            emp1_transfers_dx = emp1 + dx
            emp1_tax_dx = emp1 - b1 * wage_ss * dx
            # Unemployment BENEFIT LEVELS (the SST builds the rows from them; BUG-105)
            ue_lvl = 0.7 * wage_ss                                  # with UI
            nb_lvl = 0.5 * wage_ss                                  # UI exhausted
            ue_lvl_dx = ue_lvl + dx
            nb_lvl_dx = nb_lvl + dx
            ue_lvl_rr_dx = ue_lvl + dx * wage_ss * (1 - tau_ss)
            nb_lvl_ext_dx = nb_lvl + dx * wage_ss * (1 - tau_ss)
        else:
            # Employed rows (same expressions as the monolith, so the same
            # IEEE values): net-wage scaling and the three employed-side dx's.
            emp1 = b1 * wage_ss * (1 - tau_ss)
            emp1_wage_dx = b1 * (wage_ss + dx) * (1 - tau_ss)
            emp1_transfers_dx = b1 * wage_ss * (1 - tau_ss) + dx
            emp1_tax_dx = b1 * wage_ss * (1 - (tau_ss + dx))

            # Unemployment BENEFIT LEVELS (the SST builds the rows from them; BUG-105). Same
            # arithmetic as before, expressed as scalars: the rows were constant by construction.
            ue_lvl = 0.7 * wage_ss * (1 - tau_ss)                  # with UI
            nb_lvl = 0.5 * wage_ss * (1 - tau_ss)                  # UI exhausted
            ue_lvl_dx = ue_lvl + dx
            nb_lvl_dx = nb_lvl + dx
            ue_lvl_rr_dx = ue_lvl + dx * wage_ss * (1 - tau_ss)
            nb_lvl_ext_dx = nb_lvl + dx * wage_ss * (1 - tau_ss)

        def L(level):
            """One unemployment slot. The income-process SST (BUG-105) DECIDES it — same call, same flags,
            same object as `Simulate.py`, the Step-2 estimators and the welfare drivers — and this block then
            re-expresses that object on the employed state's support.

            Why the re-expression is necessary: `ConsMarkovModel.calc_transition_matrix` allocates one
            rectangular shock array for all Markov states (`shk_prbs[m] = shk_dstn[m].pmv`), so every state must
            carry the SAME number of shock points. The SST returns the ψ MARGINAL (7 points) or a point mass (1),
            while the employed state carries the 7×7 product (49) — feeding the SST's object in directly raises
            `could not broadcast input array from shape (7,) into shape (49,)`. The expansion below puts the
            SST's ψ row on the employed support with the employed pmv, which is the same distribution: summing
            the employed pmv over the transitory coordinate reproduces the ψ marginal. Asserted, not assumed —
            the moments that the solver and the growth-impatience bound actually use, E[ψ] and E[1/ψ], must agree
            with the SST's object to 1e-12, so an SST change that this expansion cannot represent fails loudly."""
            d = build_unemployed_inc_shk_dstn(src, float(level), p_on, t_on)
            p_sst = np.asarray(d.pmv, dtype=float)
            a_sst = np.asarray(d.atoms, dtype=float)
            psi_sst, theta_sst = a_sst[0], a_sst[1]
            assert np.allclose(theta_sst, float(level)), "the SST's unemployed transitory row is not the level"
            if p_sst.size == pmv.size:                       # already on the employed support
                psi_row = psi_sst
            elif psi_sst.size == 1:                          # point mass -> constant row
                psi_row = np.full_like(b0, float(psi_sst[0]))
            else:                                            # the ψ marginal -> the employed ψ coordinate
                psi_row = b0.copy()
            theta_row = np.full_like(b0, float(level))
            for name, f in (("E[psi]", lambda x: x), ("E[1/psi]", lambda x: 1.0 / x)):
                m_sst = float(np.sum(p_sst * f(psi_sst)))
                m_exp = float(np.sum(pmv * f(psi_row)))
                assert abs(m_sst - m_exp) <= 1e-12 * max(1.0, abs(m_sst)), (
                    f"unemployed slot: {name} {m_exp!r} on the employed support differs from the SST's "
                    f"{m_sst!r} — the expansion no longer represents the SST's object")
            return _labeled(pmv, np.stack([psi_row, theta_row]))

        emp = lambda: _labeled(pmv, np.stack([b0, emp1]))  # noqa: E731

        # Employment-state slots; the earnings phase duplicates each list block-wise
        # ([growing 6 | matured 6], distinct objects) — see wrap_phase_dstns.
        IncShkDstn.append(wrap_phase_dstns(
            [emp(), L(ue_lvl), L(ue_lvl), L(nb_lvl), L(nb_lvl), L(nb_lvl)]))
        IncShkDstn_transfers_dx.append(wrap_phase_dstns(
            [_labeled(pmv, np.stack([b0, emp1_transfers_dx])),
             L(ue_lvl_dx), L(ue_lvl_dx), L(nb_lvl_dx), L(nb_lvl_dx), L(nb_lvl_dx)]))
        IncShkDstn_wage_dx.append(wrap_phase_dstns(
            [_labeled(pmv, np.stack([b0, emp1_wage_dx])),
             L(ue_lvl), L(ue_lvl), L(nb_lvl), L(nb_lvl), L(nb_lvl)]))
        IncShkDstn_tax_dx.append(wrap_phase_dstns(
            [_labeled(pmv, np.stack([b0, emp1_tax_dx])),
             L(ue_lvl), L(ue_lvl), L(nb_lvl), L(nb_lvl), L(nb_lvl)]))
        IncShkDstn_ui_extend_dx.append(wrap_phase_dstns(
            [emp(), L(ue_lvl), L(ue_lvl), L(nb_lvl_ext_dx), L(nb_lvl_ext_dx), L(nb_lvl)]))
        IncShkDstn_ui_rr_dx.append(wrap_phase_dstns(
            [emp(), L(ue_lvl_rr_dx), L(ue_lvl_rr_dx), L(nb_lvl), L(nb_lvl), L(nb_lvl)]))

    return (IncShkDstn, IncShkDstn_transfers_dx, IncShkDstn_wage_dx,
            IncShkDstn_tax_dx, IncShkDstn_ui_extend_dx, IncShkDstn_ui_rr_dx)


def income_process_guard(permgrofac_mode, psi_mode, guard_mode=None, pe_perm_on=None, pe_tran_on=None):
    """GIC-consistency guard (HANK session 2026-08-30, owner: "it's not appropriate to change to Gamma = 1 while leaving
    preference parameters the same ... this does not respect the GIC constraint").

    The PE estimation places each education group's most patient atom ON the population growth-impatience boundary
    (the GIC-cap atom, GPF_out = (R beta)^(1/rho) * L * E[1/psi] / Gamma_e = the cap) under ITS income process: the
    education-specific growth factors Gamma_e and permanent shocks that persist through unemployment. A HANK household
    block that keeps those betas but drops the growth (Gamma == 1) or the unemployment psi moves the cap atoms past the
    boundary (column B's calibration: 0.9986 -> 1.0008) — an ill-posed block, not a counterfactual (fixed-nominal
    multipliers collapse through a near-permanent asset-demand response; record
    conclusions_private/2026-08-30_hank-cross-machine-debugging-session.md). So the live package REFUSES an income
    process other than the PE's unless HAFISCAL_HANK_INCOME_GUARD says otherwise:
      raise (default) | warn (diagnostic arms: run, but say so loudly) | off.
    The frozen monolith (QE_FIDELITY / column A) is the reproduction path for the paper's own Gamma == 1 block (BUG-073)
    and is not routed through here."""
    mode = (guard_mode if guard_mode is not None
            else os.environ.get("HAFISCAL_HANK_INCOME_GUARD", "raise")).strip().lower()
    problems = []
    if permgrofac_mode not in ("main", "1", "on"):
        problems.append("HAFISCAL_HANK_PERMGROFAC=%s (Gamma == 1; the betas were estimated with growth)" % permgrofac_mode)
    psi_on = psi_mode in ("main", "1", "on", "true") if isinstance(psi_mode, str) else bool(psi_mode)
    if pe_perm_on is None:
        # back-compatible form: "differs from the estimation" == psi off
        if not psi_on:
            problems.append("HAFISCAL_HANK_UNEMP_PSI=%s (no permanent shocks in unemployment; the betas were "
                            "estimated with them)" % psi_mode)
    elif psi_on != bool(pe_perm_on):
        # BUG-105: the block and the PE model must agree about the SAME process
        problems.append("the HANK block's unemployment psi (%s) disagrees with the PE model's "
                        "perm_shocks_during_unemployment=%s (HAFISCAL_PERM_DURING_UNEMP; the catalog axis that "
                        "distinguishes the worlds) — an explicit HAFISCAL_HANK_UNEMP_PSI override caused this"
                        % ("on" if psi_on else "off", bool(pe_perm_on)))
    if pe_tran_on:
        problems.append("the PE model has tran_shocks_during_unemployment=True, which this block's level-based "
                        "unemployment construction does not implement (the dx arms perturb a constant benefit "
                        "level); route the transitory case through the SST's own object before enabling it")
    if not problems or mode == "off":
        return problems
    msg = ("[hank-income-guard] the HANK household block's income process differs from the one the discount factors were "
           "estimated under: " + "; ".join(problems) + " -- the GIC-cap atoms are then past the population growth-impatience "
           "boundary (ill-posed block; see hh_setup.income_process_guard). Set HAFISCAL_HANK_INCOME_GUARD=warn for a "
           "diagnostic arm or =off to silence.")
    if mode == "warn":
        print(msg + " [WARN: running anyway]", flush=True)
        return problems
    raise RuntimeError(msg)


def build():
    """Ingest the Baseline calibration and return everything the
    Jacobian stage consumes."""
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes, Check_changes,
     recession_Check_changes] = \
        return_parameters(Parametrization='Baseline', OutputFor='_Main.py')

    # Earnings phase: read ONCE here (the construction site) and carried on every agent as
    # `earnings_phase_hazard`; everything below derives from it (n_hank_states() = 2 x states when on).
    _h = earnings_phase.hazard()
    _n_hh = n_hank_states()
    print(f"[hank-phase] {earnings_phase.describe(_h)}; household states = {_n_hh} "
          f"({'{growing, matured} x ' if _h > 0 else ''}{states} employment states)", flush=True)

    Rfree = np.ones(_n_hh) * 1.01
    LivPrb = [np.ones(_n_hh) * LIVPRB_SS]

    # R-e item-3 ruling (owner 2026-08-09: "keep everything possible
    # identical for HANK-SAM to PE ... we should also use the same
    # grids"). HAFISCAL_HANK_GRIDS:
    #   "pe" (DEFAULT): SOLVE grids = the PE per-group aXtraMax/
    #     aXtraCount already carried by the init dicts (the K·h̄
    #     production rule — NOT overwritten), and the DISTRIBUTION grid
    #     read BY-REFERENCE from the PE engine's own sources (owner
    #     2026-08-10: mimic PE's solve-vs-simulate grid split by
    #     reference, not by re-typed value): count = HAFISCAL_TM_MCOUNT
    #     (tm_methods module default 50 = the decided production
    #     dist_aGrid_count, 2026-05-13; the Step-5a entry's own default
    #     is 100 — the deferred R2 twin default), top = HAFISCAL_TM_AMAX
    #     (dist_aGrid_max, canonical 1300 — the owner-ruled top covering
    #     the GIC-cap College atom's (1−1e-4) ergodic quantile).
    #     A PE dist-grid change now propagates here instead of
    #     stranding a stale literal. Residual documented
    #     differences: the fake-news dist grid lives on market resources
    #     m (the PE TM's on end-of-period assets a), exp-mult spacing,
    #     mMin=1e-4 (m>0 required).
    #   "legacy": the historical HANK grids (solve 1e6/200 overwrite;
    #     dist 200/1e5) — the frozen monolith's construction.
    # BUG-075 (found by this ruling's first implementation, FIXED
    # 2026-08-10 by the ghost-run differencing in jacobians.py): the
    # historical construction differenced dated chains against the
    # STATIC steady state; on near-unit-root cells the backward chain's
    # convergence drift turned into O(0.1) spurious J entries under
    # these grids (and a ~4% UI contamination even under legacy). With
    # the ghost fix the PE grids are sane and "pe" is the DEFAULT per
    # the ruling; measured pure-grid effect vs ghost-corrected legacy:
    # <1% on all three multipliers.
    _grids = os.environ.get("HAFISCAL_HANK_GRIDS", "pe").strip().lower()
    _chains = os.environ.get("HAFISCAL_HANK_UNEMP_CHAINS", "pe").strip().lower()
    _emp_chains = []   # the three 6 x 6 employment chains (for the diagnostics print below)
    for init in (init_dropout, init_highschool, init_college):
        init["mFac"] = 3
        init["mMin"] = 1e-4
        if _grids == "legacy":
            init["mCount"] = 200
            init["mMax"] = 100000
            init['aXtraMax'] = 1_000_000
            init['aXtraCount'] = 200
        else:
            init["mCount"] = int(os.environ.get("HAFISCAL_TM_MCOUNT", "50"))
            init["mMax"] = float(os.environ.get("HAFISCAL_TM_AMAX", "1300"))
            # solve grids: the PE per-group values stay as built
        init['Rfree'] = [Rfree]  # HARK 0.17: time-vary list of per-state arrays
        init['LivPrb'] = LivPrb
        # BUG-076 (owner-ruled 2026-08-10, "just seems like a bug in HANK
        # that should be fixed"): the PE calibration already delivers each
        # education group its OWN 6-state base chain in init['MrkvArray']
        # (Urate_normal_{d,h,c} = 0.085/0.044/0.027 via
        # make_cond_mrkv_arrays_base); the historical construction
        # overwrote all three with ONE shared chain — the PE HIGHSCHOOL
        # process (EU_prob 0.0306834 = the HS separation rate rounded to
        # 7 digits). "pe" (DEFAULT) keeps the delivered per-group chains;
        # "legacy" reproduces the shared-chain overwrite byte-for-byte
        # (the frozen monolith's construction).
        # Earnings phase: the PE chain (and PermGroFac) arrive wrapped over 2 x 7 states; the
        # EMPLOYMENT block is what the 6-state normalization consumes (identity when off).
        _m_pe0, _g_pe0 = pe_employment_block(init['MrkvArray'][0], init['PermGroFac'][0])
        if _chains == "legacy":
            # BUG-099 (2026-08-28, found by the Econ-9 ladder): the shared 6-state chain
            # replaced the PE chain, but the per-state PermGroFac kept the PE encoding's
            # length (4 under legacy, 7 under calendar/window) -> IndexError in
            # def_boundary once HAFISCAL_HANK_PERMGROFAC=main keeps it. Normalize Gamma to
            # the HANK's 6 states exactly as the "pe" branch does (lumpable tail; the
            # 6-state encodings and the PERMGROFAC=ones arm are unchanged byte-for-byte).
            _, _g_pe = normalize_to_hank_states(_m_pe0, states, _g_pe0)
            _m_emp = markov_array_ss.T
        else:
            # The PE chain has 4/6/7 micro states by UI encoding (calendar/window = 7
            # since 2026-08-26); normalize it -- and the per-state PermGroFac -- to the
            # HANK's 6 (lumpable no-benefit tail; byte-identical to the bug_fix-era input).
            _m_emp, _g_pe = normalize_to_hank_states(_m_pe0, states, _g_pe0)
            assert _m_emp.shape == (states, states), (
                f"BUG-076 pe chains: got {_m_emp.shape} after normalization")
        # Re-wrap for the household solve: [growing 6 | matured 6] = [[(1-h)M6, hM6], [0, M6]],
        # growth only in the growing block (matured Gamma = 1). Both wrappers are the identity
        # at h = 0 (the same objects pass through: byte-identical to the pre-phase block).
        _g_pe = earnings_phase.wrap_permgrofac(_g_pe, h=_h)
        init['MrkvArray'] = [earnings_phase.wrap_chain(_m_emp, h=_h)]
        init['PermGroFac'] = [_g_pe]
        _emp_chains.append(_m_emp)
        if _h > 0.0:
            init[PHASE_HAZARD_ATTR] = _h   # the transition builders' newborn reset keys on this
            assert init['MrkvArray'][0].shape == (_n_hh, _n_hh) and _g_pe.shape == (_n_hh,)
    if _grids == "legacy":
        print("[hank-grids] LEGACY grids (solve 1e6/200 overwrite; dist 200/1e5)", flush=True)
    else:
        print(f"[hank-grids] PE grids: solve = per-group calibration values; "
              f"dist mCount={init_dropout['mCount']} mMax={init_dropout['mMax']:g} "
              "(R-e item-3; by-ref HAFISCAL_TM_MCOUNT/HAFISCAL_TM_AMAX)", flush=True)
    if _chains == "legacy":
        print("[hank-chains] LEGACY shared chain (the PE Highschool process "
              "applied to all education groups)", flush=True)
    else:
        _seps_dbg = [float(_m[0, 1] / (1.0 - _m[1, 0])) for _m in _emp_chains]
        print(f"[hank-chains] PE per-education chains (BUG-076 fix): "
              f"seps d/h/c = {_seps_dbg[0]:.6f}/{_seps_dbg[1]:.6f}/{_seps_dbg[2]:.6f} "
              f"(common jf=2/3)", flush=True)

    # BUG-073 (owner-ruled 2026-08-09): the PE calibration's education-
    # specific PermGroFac is KEPT — the historical Gamma=1 overwrite is a
    # monolith-only (QE-fidelity) construction. Explicit "ones" remains
    # as the sensitivity arm.
    if os.environ.get("HAFISCAL_HANK_PERMGROFAC", "main").strip().lower() \
            not in ("main", "1", "on"):
        for init in (init_dropout, init_highschool, init_college):
            init["PermGroFac"] = [np.ones(_n_hh)]
        print("[hank-h3] PermGroFac = ones (historical-sensitivity arm)", flush=True)
    else:
        print("[hank-h3] PermGroFac = main-pipeline education-specific values (BUG-073 fix)", flush=True)

    agent_DO = MarkovConsumerType(**init_dropout)
    agent_DO.cycles = 0
    agent_HS = MarkovConsumerType(**init_highschool)
    agent_HS.cycles = 0
    agent_CG = MarkovConsumerType(**init_college)
    agent_CG.cycles = 0
    BaseTypeList = [agent_DO, agent_HS, agent_CG]

    # R-e item-1 ruling (owner 2026-08-09: "do it like in the PE model,
    # but have a flag to do the psi=1 version optionally"): DEFAULT
    # "main" = the employed psi marginal persists during unemployment,
    # exactly as in the PE model. "one" = the historical degenerate
    # psi=1 arm (the frozen monolith's default; measured <=2%).
    # BUG-105 (2026-08-30): the unemployment income process follows the PE agent's own flags —
    # `perm_/tran_shocks_during_unemployment`, which Parameters.py sets from HAFISCAL_PERM_DURING_UNEMP, the
    # catalog axis that is the SOLE economic difference between the worlds (default on, as-corrected off).
    # Before this fix the block took psi from HAFISCAL_HANK_UNEMP_PSI alone (default "main"), unlinked to that
    # axis, so an as-corrected run gave HANK households a permanent-shock process the PE model does not have.
    # The env knob is now an explicit OVERRIDE of the PE default, announced when it is used.
    _pe_p_on = bool(getattr(BaseTypeList[0], "perm_shocks_during_unemployment", False))
    _pe_t_on = bool(getattr(BaseTypeList[0], "tran_shocks_during_unemployment", False))
    for _a in BaseTypeList[1:]:
        assert bool(getattr(_a, "perm_shocks_during_unemployment", False)) == _pe_p_on, \
            "education groups disagree on perm_shocks_during_unemployment"
        assert bool(getattr(_a, "tran_shocks_during_unemployment", False)) == _pe_t_on, \
            "education groups disagree on tran_shocks_during_unemployment"
    _psi_env = os.environ.get("HAFISCAL_HANK_UNEMP_PSI", "").strip().lower()
    if _psi_env:
        psi_main = _psi_env in ("main", "1", "on", "true")
        print(f"[hank-h3] unemployment psi OVERRIDDEN by HAFISCAL_HANK_UNEMP_PSI={_psi_env} "
              f"(psi_main={psi_main}); the PE model has perm_shocks_during_unemployment={_pe_p_on}", flush=True)
    else:
        psi_main = _pe_p_on
        print(f"[hank-h3] unemployment psi follows the PE model: perm_shocks_during_unemployment={_pe_p_on} "
              f"(BUG-105; HAFISCAL_HANK_UNEMP_PSI overrides)", flush=True)
    income_process_guard(os.environ.get("HAFISCAL_HANK_PERMGROFAC", "main").strip().lower(),
                         "main" if psi_main else "one", pe_perm_on=_pe_p_on, pe_tran_on=_pe_t_on)
    (IncShkDstn, IncShkDstn_transfers_dx, IncShkDstn_wage_dx,
     IncShkDstn_tax_dx, IncShkDstn_ui_extend_dx, IncShkDstn_ui_rr_dx) = \
        _build_income_dstns(BaseTypeList, psi_main, _pe_t_on)

    for _a in BaseTypeList:   # the block's state count, derived from the chain (never the literal 6)
        assert _a.MrkvArray[0].shape == (_n_hh, _n_hh), (_a.MrkvArray[0].shape, _n_hh)
        assert len(_a.solution_terminal.cFunc) == _n_hh

    return SimpleNamespace(
        init_dropout=init_dropout, init_highschool=init_highschool,
        init_college=init_college, DiscFacDstns=DiscFacDstns,
        data_EducShares=data_EducShares,
        BaseTypeList=BaseTypeList,
        n_states=_n_hh, phase_hazard=_h,
        IncShkDstn=IncShkDstn,
        IncShkDstn_transfers_dx=IncShkDstn_transfers_dx,
        IncShkDstn_wage_dx=IncShkDstn_wage_dx,
        IncShkDstn_tax_dx=IncShkDstn_tax_dx,
        IncShkDstn_ui_extend_dx=IncShkDstn_ui_extend_dx,
        IncShkDstn_ui_rr_dx=IncShkDstn_ui_rr_dx,
    )
