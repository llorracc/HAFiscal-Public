#!/usr/bin/env python
"""HAFiscal "tool map" benchmark harness — Phase A (v1).

PURPOSE
-------
Benchmark the DEFAULT HAFiscal solve+simulate path on the cheapest *real*
HAFiscal economy, and emit a platform-tagged, cross-platform-comparable JSON.
The JSON is a transparency artifact: run the identical script on x86_64 Linux
and on an arm64 Mac, then diff the two `results/<hostname>.json` files to get
the x86-vs-arm64 timing ratio and the floating-point delta (the "fingerprint").

This is v1 of a tool map that will later grow to compare alternative solvers
(Anderson-EGM, TM-ergodic, JAX, FTI). To make adding a tool trivial, the
benchmark body is a registry (`TOOLS`, a list of named `Tool` callables). v1
registers exactly two tools: the default EGM solve, and a short Monte-Carlo
forward simulation off that solution. To add a tool later, append one more
`Tool(...)` entry — nothing else in the harness changes.

DESIGN NOTES
------------
* SOLVE entry point: `AggregateDemandEconomy.solve()` on a HARK economy built
  exactly as `test_tm_baseline.py` builds it (the canonical minimal MC setup),
  using the `HS_Only` parametrization — the cheapest genuine HAFiscal config
  (single High-School cohort, `DiscFacCount=1`, `AgentCountTotal=1500`,
  `T_age=100`). This is the real default EGM solver (HARK's `solve_agent`
  iterating `solve_agg_cons_markov_alt`), NOT a stub.
* SIM entry point: `AggregateDemandEconomy.run_experiment(**base_dict,
  Full_Output=True)` — the same MC forward simulator the production welfare /
  multiplier pipeline uses (`Simulate.py`, `welfare6_scenario.py`), restricted
  here to the short HS_Only horizon (`act_T=100`).
* FINGERPRINT: we do NOT hash raw float bytes (x86 vs arm64 differ in the last
  ULP after transcendental ops, so a byte hash would always mismatch). Instead
  we record actual float VALUES at fixed query points: the solved consumption
  function evaluated on a fixed grid of normalized market-resources `m` (at the
  base Markov state, with the aggregate-consumption-ratio argument pinned to
  1.0), plus a handful of aggregate simulation moments (mean/var of consumption
  and assets). The caller diffs these with a tolerance to read off the
  cross-platform delta.
* DETERMINISM: agent RNG seeds are fixed in the build (mirroring
  `test_tm_baseline.py`), so the sim moments are reproducible run-to-run on a
  given platform.

CONSTRAINTS honored
-------------------
* Default deps only — NO GPU, NO JAX. The script runs unchanged on x86_64 Linux
  and arm64 macOS.
* This file lives in `Code/HA-Models/toolmap/` (NOT in `FromPandemicCode/`,
  which is reserved for original Pandemic-paper code).
* Target total runtime < ~2 min.

USAGE
-----
    # from the repo root:
    uv run python Code/HA-Models/toolmap/bench_toolmap.py
    # or, if uv is unavailable, with the platform venv directly:
    .venv-<platform>-<arch>/bin/python Code/HA-Models/toolmap/bench_toolmap.py

Writes Code/HA-Models/toolmap/results/<hostname>.json and prints it.
"""

import os

# ---------------------------------------------------------------------------
# Single-thread the BLAS pools BEFORE importing numpy (mirrors the production
# entry points). Keeps the solve timing comparable across machines with
# different default thread counts, and avoids oversubscription noise.
# ---------------------------------------------------------------------------
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
# Headless matplotlib (HAFiscal modules import it at module load).
os.environ.setdefault("MPLBACKEND", "Agg")

import json
import platform
import socket
import sys
from collections import OrderedDict
from copy import deepcopy
from importlib.metadata import PackageNotFoundError, version
from time import perf_counter

import numpy as np

# ---------------------------------------------------------------------------
# Make the HAFiscal model package importable. The model code lives in
# FromPandemicCode/ and (a) reads sys.argv at import (Parameters.py) and
# (b) expects its own directory to be the CWD for some relative Results/ loads.
# We patch argv to a bare program name BEFORE importing, then chdir into the
# model dir (restoring CWD afterward is unnecessary — we write results via an
# absolute path computed up front).
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))           # .../toolmap
_HA_MODELS = os.path.abspath(os.path.join(_THIS_DIR, ".."))      # .../HA-Models
_PANDEMIC = os.path.join(_HA_MODELS, "FromPandemicCode")
_RESULTS_DIR = os.path.join(_THIS_DIR, "results")

# Parameters.py parses sys.argv for optional numeric overrides (Rfree/CRRA/...);
# a bare argv means "use the parametrization's own calibrated values".
sys.argv = ["bench_toolmap"]

sys.path.insert(0, _PANDEMIC)
# HAFiscal model code assumes CWD == FromPandemicCode for some loads.
os.chdir(_PANDEMIC)

# The cheapest genuine HAFiscal config: single HS cohort, DiscFacCount=1,
# AgentCountTotal=1500, T_age=100. See Parameters.py HS_Only branch.
PARAMETRIZATION = "HS_Only"

# Fixed query grid for the consumption-function fingerprint: normalized
# market resources m. Chosen to span the economically relevant range
# (near the borrowing constraint up through moderate wealth) at round
# values so the points are identical on every platform.
CFUNC_M_POINTS = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0]
# The HAFiscal cFunc is 2-D: cFunc(mNrm, Cratio). Pin the aggregate-
# consumption-ratio argument to 1.0 (its steady-state / base value).
CFUNC_CRATIO = 1.0


# ===========================================================================
# Economy build (mirrors test_tm_baseline.py: the canonical minimal MC setup)
# ===========================================================================
def build_economy(parametrization):
    """Build + return an unsolved AggregateDemandEconomy and its base_dict.

    Replicates the agent-type construction in test_tm_baseline.py exactly
    (IncShkDstn per-micro-state assembly, per-type seeds, AgentCount split),
    so the solve and sim we time below are the genuine HAFiscal default path.
    """
    from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
    from HARK.distributions import DiscreteDistribution
    from Parameters import return_parameters
    # UI-state encoding governs the micro-state count (6 under the default
    # bug_fix encoding, 4 under legacy); the per-micro-state IncShkDstn lists
    # below must match it. Mirrors welfare6_scenario.py's construction (the
    # production path); test_tm_baseline.py hardcodes the legacy 4-state form.
    from EstimParameters import (
        HAFISCAL_UI_STATE_ENCODING, Policy_ExtraBenefitQuarters)

    (
        init_dropout, init_highschool, init_college, init_ADEconomy,
        DiscFacDstns, DiscFacCount, AgentCountTotal, base_dict,
        num_max_iterations_solvingAD, convergence_tol_solvingAD,
        UBspell_normal, num_base_MrkvStates, data_EducShares,
        max_recession_duration, num_experiment_periods, recession_changes,
        UI_changes, recession_UI_changes, TaxCut_changes,
        recession_TaxCut_changes, Check_changes, recession_Check_changes,
    ) = return_parameters(Parametrization=parametrization, OutputFor="_Main.py")

    econ = AggregateDemandEconomy(**init_ADEconomy)

    base_inits = [init_dropout, init_highschool, init_college]
    # Build only the active education cohorts (data_EducShares is the
    # effective share vector; HS_Only zeroes out dropout & college).
    BaseTypeList = []
    base_index = []  # education-group index for each base type built
    for e, init_params in enumerate(base_inits):
        if data_EducShares[e] <= 0.0:
            continue
        bt = AggFiscalType(**init_params)
        bt.cycles = 0
        BaseTypeList.append(bt)
        base_index.append(e)

    for bt in BaseTypeList:
        bt.get_economy_data(econ)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseTypeList[0].IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseTypeList[0].IncUnempNoBenefits])])

    # Helper: assemble a per-micro-state IncShkDstn list whose length matches
    # num_base_MrkvStates under the active UI encoding (6 = bug_fix, 4 = legacy).
    # Order: [state0, u1Q, ..., uK Q, (extra-benefit quarters), noBen].
    def _per_state_list(state0):
        if HAFISCAL_UI_STATE_ENCODING == "bug_fix":
            return (
                [state0]
                + [IncShkDstn_unemp] * UBspell_normal
                + [IncShkDstn_unemp_nobenefits] * Policy_ExtraBenefitQuarters
                + [IncShkDstn_unemp_nobenefits])
        return (
            [state0]
            + [IncShkDstn_unemp] * UBspell_normal
            + [IncShkDstn_unemp_nobenefits])

    for ThisType in BaseTypeList:
        EmployedIncShkDstn = deepcopy(ThisType.IncShkDstn[0])
        ThisType.IncShkDstn = [_per_state_list(EmployedIncShkDstn)]
        ThisType.IncShkDstn_base = ThisType.IncShkDstn
        IncShkDstn_recession = [
            ThisType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
        ThisType.IncShkDstn_recession = IncShkDstn_recession
        ThisType.IncShkDstn_recessionUI = IncShkDstn_recession
        ThisType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)
        # TaxCut income vector: employed atom's TranShk rescaled by the tax-cut
        # factor; rest of the micro-states unchanged. List length matches the
        # encoding (mirrors welfare6_scenario.py).
        EmployedIncShkDstn_tax = deepcopy(EmployedIncShkDstn)
        EmployedIncShkDstn_tax.atoms = (
            np.asarray(EmployedIncShkDstn_tax.atoms[0], dtype=np.float64),
            np.asarray(EmployedIncShkDstn_tax.atoms[1], dtype=np.float64)
            * ThisType.TaxCutIncFactor,
        )
        TaxCutStatesIncShkDstn = _per_state_list(EmployedIncShkDstn_tax)
        IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
        for idx in range(2 * num_base_MrkvStates,
                         2 * (num_experiment_periods + 1) * num_base_MrkvStates):
            IncShkDstn_recessionTaxCut[0][idx] = TaxCutStatesIncShkDstn[
                np.mod(idx, num_base_MrkvStates)]
        ThisType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut

    # Expand BaseTypeList -> TypeList across (active edu) x (DiscFacCount betas).
    TypeList = []
    n = 0
    for bi, e in enumerate(base_index):
        for b in range(DiscFacCount):
            DiscFac = DiscFacDstns[e].atoms[0][b]
            AgentCount = int(np.floor(
                AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[b]))
            ThisType = deepcopy(BaseTypeList[bi])
            ThisType.AgentCount = AgentCount
            ThisType.DiscFac = DiscFac
            ThisType.seed = n          # fixed seed => reproducible sim moments
            TypeList.append(ThisType)
            n += 1

    econ.agents = TypeList
    for agent in econ.agents:
        agent.get_economy_data(econ)

    return econ, base_dict


# ===========================================================================
# Tool registry. Each Tool wraps one named, timed step of the default path.
# v1 has two; later phases append Anderson-EGM / TM-ergodic / JAX / FTI here.
# ===========================================================================
class Tool:
    """A named, timed benchmark step.

    fn(state) -> dict : runs the step (mutating/reading the shared `state`
    dict that threads the built economy and sim results between tools) and
    returns a small dict of fingerprint/diagnostic values to merge into the
    JSON. The Tool records its own wall time under `seconds`.
    """

    def __init__(self, name, fn):
        self.name = name
        self.fn = fn

    def run(self, state):
        t0 = perf_counter()
        out = self.fn(state)
        elapsed = perf_counter() - t0
        return elapsed, (out or {})


def tool_solve(state):
    """DEFAULT EGM solve: AggregateDemandEconomy.solve() on the HS_Only economy.

    This is HARK's real infinite-horizon EGM/markov solver
    (solve_agg_cons_markov_alt iterated by solve_agent), the exact solver the
    production pipeline uses. We also extract the consumption-function
    fingerprint here, off the freshly solved cFunc.
    """
    econ = state["econ"]
    econ.solve()

    # Fingerprint: evaluate the solved base-state consumption function on the
    # fixed m-grid. solution[0].cFunc[0] is c(mNrm, Cratio) in the base Markov
    # micro-state (employed) of the base macro state. We pin Cratio=1.0.
    agent = econ.agents[0]
    cfunc0 = agent.solution[0].cFunc[0]
    m = np.array(CFUNC_M_POINTS, dtype=np.float64)
    cratio = np.full_like(m, CFUNC_CRATIO)
    c_vals = np.asarray(cfunc0(m, cratio), dtype=np.float64)
    return {"cfunc_at_points": [float(x) for x in c_vals]}


def tool_sim(state):
    """Representative MC forward simulation off the solved economy.

    Uses the same run_experiment MC simulator the production welfare/multiplier
    pipeline uses, on the base (no-recession) scenario over the short HS_Only
    horizon. Mirrors the burn-in + counterfactual-mode handshake from
    test_tm_baseline.py / welfare6_scenario.py so the sim is a genuine HAFiscal
    forward simulation, then records aggregate moments for the fingerprint.
    """
    econ = state["econ"]
    base_dict = state["base_dict"]

    econ.reset()
    for agent in econ.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0
    econ.make_history()                         # burn-in to ergodic-ish state
    econ.save_state()
    econ.switch_to_counterfactual_mode("base")
    econ.make_idiosyncratic_shock_histories()

    results = econ.run_experiment(**base_dict, Full_Output=True)
    state["sim_results"] = results

    # Aggregate moments for the fingerprint. AggCons/AggIncome are length-act_T
    # aggregate time series; cLvl/aNrm panels are (act_T x N_agents). We take
    # cross-time mean/var of the aggregates and cross-everything mean/var of the
    # per-agent consumption and asset panels — all platform-stable scalars.
    agg_cons = np.asarray(results["AggCons"], dtype=np.float64)
    agg_income = np.asarray(results["AggIncome"], dtype=np.float64)
    cLvl = np.asarray(results["cLvl_all_splurge"], dtype=np.float64)
    aNrm = np.asarray(results["aNrm_all"], dtype=np.float64)

    moments = OrderedDict([
        ("agg_cons_mean", float(np.mean(agg_cons))),
        ("agg_cons_var", float(np.var(agg_cons))),
        ("agg_income_mean", float(np.mean(agg_income))),
        ("cLvl_splurge_mean", float(np.mean(cLvl))),
        ("cLvl_splurge_var", float(np.var(cLvl))),
        ("aNrm_mean", float(np.mean(aNrm))),
        ("aNrm_var", float(np.var(aNrm))),
    ])
    return {"agg_moments": moments}


def tool_anderson_solve(state):
    """Opt-in NAMG (global-Newton) solve: the SAME HS_Only economy, but solved with
    the multi-state global-Newton base solver (``HAFISCAL_STEP2_NAMG=1``) instead of
    stock HARK EGM — measured against the default ``solve`` tool. (The result keys
    below keep the historical ``anderson_*`` label — see NOTE.)

    ENTRY POINT: identical to the ``solve`` tool — ``AggregateDemandEconomy.solve()``.
    The NAMG path is selected INSIDE ``solve()`` by ``_step2_namg_enabled()`` reading
    ``HAFISCAL_STEP2_NAMG`` (added in commit 03b82a74 as ``HAFISCAL_STEP2_ANDERSON``;
    renamed 2026-06-21). When set, each base/AD-off agent's stationary policy is
    solved by ``hark_fti.global_newton_markov.solve_stationary_NAMG_markov(
    method='newton', c_init=<prior policy>)`` and wrapped back into the 2-D
    ``c(m,Cratio)`` ``ConsumerSolution`` the simulator expects (AD-off ⇒ identical
    ``Cgrid`` slices); on any qualification miss / non-convergence / error it falls
    back to the exact EGM ``solve_agent``. ``hark_fti`` is the external opt-in package
    homed in the sibling ``fast-time-iteration`` repo (resolved via ``_hark_fti_path``);
    if it cannot be imported the NAMG path simply never engages and this tool
    transparently times an EGM solve (we flag that below via ``anderson_engaged``).

    NOTE (2026-06-21): the Step-2 opt-in was renamed ANDERSON->NAMG and repointed at
    ``method='newton'`` (a machine-precision Euler root) vs the former ``method='anderson'``
    contraction. The committed Phase-A result JSONs (``results/*.json``) were measured under
    the old ``method='anderson'`` default, so a FRESH bench run differs slightly (tighter
    parity). The ``anderson_*`` result keys + ``tool_anderson_solve`` name are kept for
    ``results/*.json`` + ``compare_results.py`` continuity (full label rename deferred).

    WHY A SEPARATE ECONOMY: the shared ``state['econ']`` was already solved with
    default EGM by the ``solve`` tool and its solution is consumed downstream by
    ``sim``/``tm_ergodic``; re-solving it in place would corrupt that. So we build a
    fresh, independent HS_Only economy (same ``build_economy``) and solve only it
    under the flag. The flag is scoped to this ``solve()`` call (set then restored)
    so it cannot leak into any other tool.

    QUALIFICATION at HS_Only: HS_Only is the base / aggregate-demand-OFF regime
    (``num_macro_states == 1``), which is EXACTLY the regime the Anderson path
    requires, and ``permgrofac_fix_on()`` defaults True, so — provided ``hark_fti``
    resolves and ``BoroCnstArt==0`` / uniform ``LivPrb`` hold (they do for the base
    HS economy) — the NAMG solver genuinely engages here. We confirm engagement
    by checking the ``_step2_namg_used`` attribute ``_try_solve_namg_base``
    stamps on each agent it solves, and surface it as ``anderson_engaged`` so the
    headline can never silently report an EGM-vs-EGM "speedup".

    FINGERPRINT: the Anderson-solved base-state cFunc evaluated on the SAME
    ``CFUNC_M_POINTS`` / ``CFUNC_CRATIO`` as the ``solve`` tool. The caller / headline
    diffs ``anderson_cfunc_at_points`` vs ``cfunc_at_points``; they should agree to
    solver tolerance (~2e-3 policy parity per the Step-2 assessment — same fixed
    point, just accelerated). DETERMINISM: no RNG in the solve; the Anderson
    contraction is a fixed-point iteration to the solver tol, reproducible run-to-run.
    """
    # Build an independent economy so we do NOT disturb the EGM-solved shared econ
    # that `sim` / `tm_ergodic` consume.
    econ_a, _ = build_economy(PARAMETRIZATION)

    # Scope HAFISCAL_STEP2_NAMG=1 to just this solve() call, then restore the
    # caller's prior value (so the flag cannot leak into any other tool / run).
    _prev = os.environ.get("HAFISCAL_STEP2_NAMG")
    os.environ["HAFISCAL_STEP2_NAMG"] = "1"
    try:
        econ_a.solve()
    finally:
        if _prev is None:
            os.environ.pop("HAFISCAL_STEP2_NAMG", None)
        else:
            os.environ["HAFISCAL_STEP2_NAMG"] = _prev

    # Did the NAMG path actually fire? `_try_solve_namg_base` stamps
    # `_step2_namg_used=True` on every agent it solves via NAMG; if the
    # flag/qualification/import did not hold, the agent was solved by EGM and the
    # attribute is absent -> this tool then merely re-times an EGM solve (we say so).
    anderson_engaged = all(
        bool(getattr(agent, "_step2_namg_used", False))
        for agent in econ_a.agents)

    # Fingerprint: same query points / Cratio as the `solve` tool, off the
    # Anderson-solved cFunc, for the apples-to-apples Anderson-vs-EGM cFunc delta.
    agent = econ_a.agents[0]
    cfunc0 = agent.solution[0].cFunc[0]
    m = np.array(CFUNC_M_POINTS, dtype=np.float64)
    cratio = np.full_like(m, CFUNC_CRATIO)
    c_vals = np.asarray(cfunc0(m, cratio), dtype=np.float64)
    return {
        "anderson_cfunc_at_points": [float(x) for x in c_vals],
        "anderson_engaged": bool(anderson_engaged),
    }


def tool_tm_ergodic(state):
    """TM-ergodic aggregate moments off the SAME solved economy (no re-solve).

    The Step-2 simulation-speedup assessment
    (`conclusions_private/2026-06-17_step2-simulation-tm-ergodic-vs-mc-assessment.md`)
    found that replacing the Monte-Carlo forward-sim panel with the
    transition-matrix (TM) ERGODIC moments is ~20x faster per eval and fully
    deterministic — the likely Phase-B win. This tool measures that here on the
    cheapest real economy: it computes the a-indexed TM ergodic over the already
    solved HS_Only cFunc and reads off the normalized-asset moments, so they sit
    next to the MC sim's `aNrm_mean`/`aNrm_var` in the fingerprint for a direct
    speedup-and-agreement comparison.

    ENTRY POINTS (tm_methods.py), the exact production TM path the welfare /
    multiplier pipeline uses to seed MC from the TM ergodic
    (welfare6_scenario.py:534, Simulate.py):
      * `compute_baseline_tm_data(economy, dist_aGrid_count, neutral_measure=False)`
        — builds the per-agent a-indexed transition matrix (internally
        `build_tm_agg_fiscal_a`) and its stationary distribution
        (`find_ergodic_distribution`), returning per-agent `ergodic` +
        `dist_aGrid`. `neutral_measure=False` => the P-measure ergodic, the
        one used to seed the ACTUAL agents (matches the MC cross-section the
        `sim` tool measures; the Q/Harmenberg measure is for aggregation only).
      * `compute_type_aggregates_tm_a(agent, tm_data, ergodic, interpretation)`
        — the canonical TM aggregate; we call it for the interpretation-aware
        HOUSEHOLD mean `A_nrm` reported for reference.

    MOMENT DEFINITION (why raw-kernel, not `A_nrm`): the MC `sim` tool records
    `aNrm_mean`/`aNrm_var` from the RAW `aNrm_all` panel (HARK's
    `state_now['aNrm']`), i.e. it does NOT apply the per-interpretation
    `(1-splurge)` household rescale that `_aNrm_for` (EstimAggFiscalMAIN.py) and
    `compute_type_aggregates_tm_a`'s `A_nrm` apply under ESC. To compare like
    with like, we record the TM ergodic's RAW-KERNEL moments here —
    E[a]=sum pi(a)*a and Var[a]=sum pi(a)*a^2 - E[a]^2 over the SAME grid the
    MC is seeded from (`initialize_mc_from_tm_ergodic` uses `grid[bins]`
    un-rescaled) — which is the direct analog of the raw MC `aNrm_all`. The
    interpretation-aware household mean `A_nrm_household` (= (1-splurge)*E[a]
    under ESC) is also reported, but it is NOT the MC-fingerprint analog.

    DETERMINISM: the TM ergodic is a fixed-point of a fixed matrix (power
    iteration to tol=1e-12) — no RNG — so these moments are exactly
    reproducible run-to-run. The distribution-grid top `dist_aGrid_max` is left
    at the builder default (500 for HS_Only via `build_tm_agg_fiscal_a`), which
    comfortably contains the small HS_Only wealth tail (support ~1.9); no
    `HAFISCAL_TM_AMAX` override is needed at this scale (the canonical
    dist_aGrid_max=1300 only matters for the most-patient College atom, absent
    here).
    """
    from tm_methods import (compute_baseline_tm_data,
                            compute_type_aggregates_tm_a,
                            build_tm_agg_fiscal_a)

    econ = state["econ"]

    # Mark agents a-indexed (what welfare6_scenario / Simulate do before the
    # TM warm-start). The economy is already solved; we only read its cFunc.
    for agent in econ.agents:
        agent.tm_a_indexed = True

    # P-measure ergodic (neutral_measure=False) => the distribution the real
    # agents are seeded from, comparable to the MC cross-section.
    dist_aGrid_count = int(os.environ.get("HAFISCAL_TM_MCOUNT", "200"))
    bd = compute_baseline_tm_data(
        econ, dist_aGrid_count=dist_aGrid_count, neutral_measure=False, verbose=False)

    # Pool the per-agent ergodic asset moments by AgentCount (so a multi-cohort
    # economy would aggregate exactly like the concatenated MC `aNrm_all`
    # panel; HS_Only has a single cohort so this is a no-op weighting).
    tot_w = 0.0
    m1_raw = 0.0          # sum_i w_i * E_i[a]
    m2_raw = 0.0          # sum_i w_i * E_i[a^2]
    A_nrm_household = 0.0  # sum_i w_i * interpretation-aware household mean
    for i, agent in enumerate(econ.agents):
        erg = np.asarray(bd[i]["ergodic"], dtype=np.float64)
        grid = np.asarray(bd[i]["dist_aGrid"], dtype=np.float64)
        A = len(grid)
        J = len(erg) // A
        # Ergodic layout is [j=0, a=0..A-1, j=1, ...]; marginalize over the
        # Markov micro-states to get the asset marginal pi(a).
        pa = erg.reshape(J, A).sum(axis=0)
        s = pa.sum()                       # == 1.0 (mass-conserving TM)
        if s > 0:
            pa = pa / s
        E_a = float(np.sum(pa * grid))
        E_a2 = float(np.sum(pa * grid * grid))

        w = float(agent.AgentCount)
        tot_w += w
        m1_raw += w * E_a
        m2_raw += w * E_a2

        # Interpretation-aware HOUSEHOLD mean (reference only; matches the
        # production TM aggregate). Rebuilds the (cheap) tm_data dict the
        # aggregate function expects; the ergodic itself is reused.
        interp = getattr(agent, "interpretation", "CDC")
        tm_data = build_tm_agg_fiscal_a(
            agent, aCount=dist_aGrid_count, Cratio=1.0, neutral_measure=False,
            interpretation=interp)
        agg = compute_type_aggregates_tm_a(
            agent, tm_data, erg, interpretation=interp)
        A_nrm_household += w * float(agg["A_nrm"])

    E_a_pooled = m1_raw / tot_w
    E_a2_pooled = m2_raw / tot_w
    tm_moments = OrderedDict([
        # Direct analog of the MC sim's raw aNrm_all moments (apples-to-apples).
        ("aNrm_mean", float(E_a_pooled)),
        ("aNrm_var", float(E_a2_pooled - E_a_pooled * E_a_pooled)),
        # Interpretation-aware household mean (ESC: (1-splurge)*E[a]); NOT the
        # MC-fingerprint analog — recorded for provenance only.
        ("A_nrm_household", float(A_nrm_household / tot_w)),
        ("interpretation", getattr(econ.agents[0], "interpretation", "CDC")),
        ("dist_aGrid_count", dist_aGrid_count),
    ])
    return {"tm_moments": tm_moments}


# Tool registry. Order matters: solve must precede sim AND tm_ergodic (both
# consume the solved economy). anderson_solve builds its OWN economy (so it can
# run anywhere), but is placed right after solve so the EGM-vs-Anderson seconds
# and cFunc are recorded back-to-back. To add a tool, append a Tool(...) here.
TOOLS = [
    Tool("solve", tool_solve),
    Tool("anderson_solve", tool_anderson_solve),  # same solve, Anderson base solver
    Tool("sim", tool_sim),
    Tool("tm_ergodic", tool_tm_ergodic),  # TM-ergodic moments off the same solve
]


# ===========================================================================
# Environment record
# ===========================================================================
def _pkg_version(dist_name, module_name=None):
    """Best-effort version lookup: try the installed-distribution metadata
    first, then the imported module's __version__."""
    try:
        return version(dist_name)
    except PackageNotFoundError:
        pass
    if module_name:
        try:
            mod = __import__(module_name)
            return getattr(mod, "__version__", None)
        except Exception:
            return None
    return None


def collect_env():
    """Record everything needed to make the JSON cross-platform comparable."""
    env = OrderedDict()
    env["hostname"] = socket.gethostname()
    env["arch"] = platform.machine()                    # == `uname -m`
    env["platform"] = platform.platform()
    env["system"] = platform.system()
    env["python_version"] = platform.python_version()
    env["numpy_version"] = _pkg_version("numpy", "numpy")
    env["numba_version"] = _pkg_version("numba", "numba")
    # HARK is distributed as the `econ-ark` PyPI distribution.
    env["hark_version"] = _pkg_version("econ-ark", "HARK")
    return env


# ===========================================================================
# Main
# ===========================================================================
def main():
    t_total = perf_counter()

    env = collect_env()

    # Build the economy once; both tools operate on the shared state.
    t_build = perf_counter()
    econ, base_dict = build_economy(PARAMETRIZATION)
    build_seconds = perf_counter() - t_build

    state = {"econ": econ, "base_dict": base_dict}

    # Run each registered tool, collecting per-tool seconds + fingerprint bits.
    tool_seconds = OrderedDict()
    fingerprint = OrderedDict()
    for tool in TOOLS:
        elapsed, out = tool.run(state)
        tool_seconds[tool.name] = elapsed
        fingerprint.update(out)
        print(f"[bench] tool {tool.name!r}: {elapsed:.3f}s", flush=True)

    total_seconds = perf_counter() - t_total

    # Assemble the result with a stable key order. solve_seconds / sim_seconds
    # are surfaced as named top-level keys (the headline numbers the caller
    # diffs across platforms); per-tool times also live under tool_seconds so
    # later phases' extra tools are captured without changing the schema.
    result = OrderedDict()
    result["env"] = env
    result["parametrization"] = PARAMETRIZATION
    result["solve_seconds"] = tool_seconds.get("solve")
    result["anderson_solve_seconds"] = tool_seconds.get("anderson_solve")
    result["sim_seconds"] = tool_seconds.get("sim")
    result["tm_ergodic_seconds"] = tool_seconds.get("tm_ergodic")
    result["build_seconds"] = build_seconds
    result["total_seconds"] = total_seconds
    result["tool_seconds"] = tool_seconds
    result["fingerprint"] = OrderedDict([
        ("cfunc_m_points", CFUNC_M_POINTS),
        ("cfunc_cratio", CFUNC_CRATIO),
        ("cfunc_at_points", fingerprint.get("cfunc_at_points")),
        ("anderson_cfunc_at_points", fingerprint.get("anderson_cfunc_at_points")),
        ("anderson_engaged", fingerprint.get("anderson_engaged")),
        ("agg_moments", fingerprint.get("agg_moments")),
        ("tm_moments", fingerprint.get("tm_moments")),
    ])
    result["notes"] = (
        "Phase-A tool map. SOLVE = default HARK EGM/markov solver "
        "(AggregateDemandEconomy.solve, solve_agg_cons_markov_alt) on the "
        "HS_Only economy (single HS cohort, DiscFacCount=1, AgentCountTotal="
        "1500, T_age=100), built per test_tm_baseline.py. ANDERSON_SOLVE = the "
        "SAME solve() on an independent copy of that economy with "
        "HAFISCAL_STEP2_NAMG=1 (the opt-in multi-state global-Newton (NAMG) base solver, "
        "hark_fti.global_newton_markov.solve_stationary_NAMG_markov(method='newton'), homed in the "
        "sibling fast-time-iteration repo); fingerprint.anderson_cfunc_at_points "
        "is its cFunc at the SAME cfunc_m_points, and fingerprint.anderson_engaged "
        "records whether the Anderson path actually fired (vs falling back to EGM, "
        "e.g. if hark_fti is absent). anderson_solve_seconds vs solve_seconds is "
        "the Anderson-vs-EGM solve speedup; anderson_cfunc_at_points vs "
        "cfunc_at_points is the policy delta (same fixed point ⇒ ~solver-tol). "
        "SIM = "
        "run_experiment(base, Full_Output=True) MC forward sim over act_T=100. "
        "TM_ERGODIC = a-indexed TM ergodic moments off the SAME solved economy "
        "(tm_methods.compute_baseline_tm_data, neutral_measure=False / "
        "P-measure); deterministic, no RNG. fingerprint.cfunc_at_points are "
        "c(mNrm, Cratio=1.0) at the base Markov micro-state on cfunc_m_points; "
        "agg_moments are MC sim aggregates; tm_moments.aNrm_mean/aNrm_var are "
        "the RAW-KERNEL TM ergodic asset moments (the direct analog of the raw "
        "MC aNrm_all; tm_moments.A_nrm_household is the interpretation-aware "
        "household mean, NOT the MC analog). The tm_ergodic-vs-sim seconds give "
        "the per-eval speedup; tm_moments.aNrm_* vs agg_moments.aNrm_* give the "
        "TM-vs-MC agreement (expected within MC sampling noise, a few %). "
        "Compare cfunc_at_points / *_moments across platforms with a tolerance "
        "(NOT a byte hash) for the x86-vs-arm64 FP delta. Default deps only; "
        "no GPU/JAX."
    )

    os.makedirs(_RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(_RESULTS_DIR, f"{env['hostname']}.json")
    text = json.dumps(result, indent=2)
    with open(out_path, "w") as f:
        f.write(text + "\n")

    print(f"\n[bench] wrote {out_path}\n", flush=True)
    print(text)

    # One-line TM-vs-MC headline: (a) the per-eval speedup of the deterministic
    # TM ergodic over the MC forward sim, and (b) how closely the TM ergodic's
    # raw-kernel aNrm moments match the MC sim's (expected within a few % of
    # MC sampling noise). This is the POINT of the tm_ergodic tool.
    tm_s = tool_seconds.get("tm_ergodic")
    sim_s = tool_seconds.get("sim")
    tm_m = fingerprint.get("tm_moments") or {}
    mc_m = fingerprint.get("agg_moments") or {}
    tm_mean = tm_m.get("aNrm_mean")
    mc_mean = mc_m.get("aNrm_mean")
    if tm_s and sim_s and tm_mean is not None and mc_mean is not None:
        speedup = sim_s / tm_s
        dpct = 100.0 * (tm_mean - mc_mean) / mc_mean if mc_mean else float("nan")
        print(
            f"\n[bench] tm_ergodic={tm_s:.3f}s  sim={sim_s:.3f}s  "
            f"speedup={speedup:.1f}x  | aNrm_mean: tm={tm_mean:.5f} "
            f"mc={mc_mean:.5f} (Δ{dpct:+.2f}%)",
            flush=True,
        )

    # One-line Anderson-vs-EGM headline: (a) the Anderson base-solver seconds vs
    # the default EGM solve seconds (a speedup, parity, OR slowdown — HS_Only is
    # tiny so Anderson need not win at this scale), and (b) the cFunc max abs
    # delta between the two solves (same fixed point ⇒ ~solver tol). This is the
    # POINT of the anderson_solve tool.
    and_s = tool_seconds.get("anderson_solve")
    egm_s = tool_seconds.get("solve")
    egm_c = fingerprint.get("cfunc_at_points")
    and_c = fingerprint.get("anderson_cfunc_at_points")
    engaged = fingerprint.get("anderson_engaged")
    if and_s and egm_s and egm_c is not None and and_c is not None:
        a_speedup = egm_s / and_s
        cdelta = float(np.max(np.abs(
            np.asarray(and_c, dtype=np.float64)
            - np.asarray(egm_c, dtype=np.float64))))
        eng = "engaged" if engaged else "FELL BACK TO EGM (Anderson did NOT engage)"
        print(
            f"\n[bench] anderson={and_s:.3f}s  egm={egm_s:.3f}s  "
            f"speedup={a_speedup:.2f}x  | cfunc max|Δ|={cdelta:.3e}  "
            f"[{eng}]",
            flush=True,
        )

    return out_path


if __name__ == "__main__":
    main()
