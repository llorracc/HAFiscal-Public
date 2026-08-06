"""HAFiscal glue for the hark_fti accelerated fixed-point drivers.

Universal-solver-acceleration plan (plans/20260804-0745h). Adapts the generic
Aitken/Anderson drivers (fast-time-iteration ``hark_fti.accel_driver``) to the
C-conditional Markov consumption solver (``solve_agg_cons_markov_alt``):

- step:    one production cycle via ``HARK.core.solve_one_cycle`` -- byte-wise
           the same one-period solve the plain loop runs.
- probe:   coarse evaluation of the per-state 2-D consumption policies on a
           FIXED tensor (state x C-subgrid x bound-anchored m-offsets). Used
           only for ratio/least-squares algebra and c>0 feasibility screening;
           the convergence metric is the production ``distance_metric``.
- combine: a jumped iterate is a FUNCTIONAL linear combination of REAL step
           outputs: cFunc*_j = sum_i w_i cFunc_i_j (lazy wrapper), with the
           envelope-consistent vPfunc*_j = u'(cFunc*_j) rebuilt on top -- so
           the next plain step consumes exactly the two fields the solver
           reads (vPfunc call/derivativeX + mNrmMin) and regenerates all
           byproducts (tails, Q-hat, Hermite dydx) itself.

The solver consumes ONLY solution_next.vPfunc[j] and solution_next.mNrmMin[j]
(verified 2026-08-04 against AggFiscalModel.py:2142-2204), which is what makes
this injection exact-by-construction at the consumption sites.

Nothing here imports hark_fti until a driver entry point is actually called
(default-path import rule).
"""

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")


def export_fti_pythonpath():
    """Make hark_fti importable in SPAWNED descendants (fresh interpreters):
    resolve the sibling checkout and prepend it to PYTHONPATH. MUST run
    before any multiprocessing pool is created — pool workers that receive
    newton2d solutions (hark_fti-class interpolants) die unpickling
    otherwise, and the pool then deadlocks waiting on dead workers (route
    smokes 3-5). Called at AggFiscalModel import when the flag is set, and
    defensively at every newton2d entry."""
    import sys as _sys
    if _FPC not in _sys.path:
        _sys.path.insert(0, _FPC)
    import _hark_fti_path  # noqa: F401
    import hark_fti
    _fti_root = os.path.dirname(os.path.dirname(
        os.path.abspath(hark_fti.__file__)))
    _pp = os.environ.get("PYTHONPATH", "")
    if _fti_root not in _pp.split(os.pathsep):
        os.environ["PYTHONPATH"] = (_fti_root + os.pathsep + _pp) if _pp             else _fti_root


def _load_driver():
    """Lazy import of hark_fti.accel_driver via the sibling-checkout resolver."""
    if _FPC not in sys.path:
        sys.path.insert(0, _FPC)
    import _hark_fti_path  # noqa: F401  (resolves ../fast-time-iteration)
    from hark_fti import accel_driver
    return accel_driver


class LinCombFunc2D:
    """Lazy functional linear combination sum_i w_i f_i(m, C) of 2-D policy
    functions, with derivativeX for the Hermite slice mode."""

    def __init__(self, weights, fns):
        self.weights = [float(w) for w in weights]
        self.fns = list(fns)

    def __call__(self, m, C=None):
        args = (m,) if C is None else (m, C)
        out = self.weights[0] * self.fns[0](*args)
        for w, f in zip(self.weights[1:], self.fns[1:]):
            out = out + w * f(*args)
        return out

    def derivativeX(self, m, C=None):
        args = (m,) if C is None else (m, C)
        out = self.weights[0] * self.fns[0].derivativeX(*args)
        for w, f in zip(self.weights[1:], self.fns[1:]):
            out = out + w * f.derivativeX(*args)
        return out


class GapLogLinCombFunc2D:
    """Mixed policy in GAP-LOG space: c*(m,C) = T(m,C) - exp(sum_i w_i
    ln(T - c_i)), where T is the model's analytic upper bound (the AD-aware
    constrained-PF terminal policy -- the Carroll-Kimball line).

    Why not mix c directly: iterates approach the PF line from below and the
    line-violation direction is UNSTABLE under the solver map (T1 round-2
    finding: an off-probe above-line bulge in a mixed iterate amplified and
    tripped the BUG-062 guard one step LATER, from a real iterate). Any
    affine combination in gap-log space stays strictly below T at EVERY
    (m,C) by construction -- the failure class is closed analytically, not
    screened statistically. First order (bulk, gap >> displacement) this is
    identical to linear mixing: d(log g) = -dc/g; in the tail it linearizes
    the approach to the asymptote, which is exactly where the acceleration
    is needed.

    Degenerate regions (T1 round-3 finding): wherever the gap machinery is
    ill-posed -- the bound is non-positive (below-bound evaluation points,
    where the terminal's constrained branch goes through zero) or the
    fallback constituent's own gap is at the clip floor (constrained region,
    both policies pinned to the constraint) -- the mix defers to the NEWEST
    real constituent in BOTH value and slope. Without this, (a) c* inherits
    T<=0 and CRRA=2.0 turns negative c into silently-positive garbage vP
    ((-x)**-2 > 0, no NaN tripwire), and (b) the slope term w*g'/g amplifies
    by ~1/eps at clipped points and poisons the Hermite vPP feed."""

    def __init__(self, weights, fns, termFunc, fallbackFunc=None, eps=1e-12,
                 degeneracy_floor=1e-9):
        self.weights = [float(w) for w in weights]
        self.fns = list(fns)
        self.termFunc = termFunc
        self.fallbackFunc = fallbackFunc if fallbackFunc is not None else fns[0]
        self.eps = float(eps)
        self.floor = float(degeneracy_floor)

    def _parts(self, args):
        t = np.asarray(self.termFunc(*args), dtype=float)
        fb = np.asarray(self.fallbackFunc(*args), dtype=float)
        degenerate = (t <= self.floor) | ((t - fb) <= self.floor)
        return t, fb, degenerate

    def __call__(self, m, C=None):
        args = (m,) if C is None else (m, C)
        t, fb, bad = self._parts(args)
        acc = 0.0
        for w, f in zip(self.weights, self.fns):
            g = np.maximum(t - np.asarray(f(*args)), self.eps)
            acc = acc + w * np.log(g)
        mixed = t - np.exp(acc)
        return np.where(bad, fb, np.maximum(mixed, self.eps))

    def derivativeX(self, m, C=None):
        args = (m,) if C is None else (m, C)
        t, fb, bad = self._parts(args)
        tp = np.asarray(self.termFunc.derivativeX(*args), dtype=float)
        fbp = np.asarray(self.fallbackFunc.derivativeX(*args), dtype=float)
        acc = 0.0
        ratio = 0.0
        for w, f in zip(self.weights, self.fns):
            g = np.maximum(t - np.asarray(f(*args)), self.eps)
            gp = tp - np.asarray(f.derivativeX(*args))
            acc = acc + w * np.log(g)
            ratio = ratio + w * gp / g
        mixed = tp - np.exp(acc) * ratio
        return np.where(bad, fbp, mixed)


class LinCombMargValue2D:
    """Envelope-consistent marginal value u'(c*(m,C)) over a combined policy
    (LinCombFunc2D or GapLogLinCombFunc2D) -- NOT the linear combination of
    the constituents' vPfuncs (u' is nonlinear; the envelope condition pins
    vP to the combined policy)."""

    def __init__(self, cFunc, CRRA):
        self.cFunc = cFunc  # no deepcopy: jump iterates are transient
        self.CRRA = float(CRRA)

    def __call__(self, m, C=None):
        args = (m,) if C is None else (m, C)
        return np.asarray(self.cFunc(*args)) ** (-self.CRRA)

    def derivativeX(self, m, C=None):
        args = (m,) if C is None else (m, C)
        c = np.asarray(self.cFunc(*args))
        return -self.CRRA * c ** (-self.CRRA - 1.0) * self.cFunc.derivativeX(*args)


def build_probe_cache(agent, sol, n_offsets=24, max_c_points=32,
                      m_top=None):
    """Fixed probe tensor anchored on a REAL solution's borrowing bounds.

    Per state j: M_j[k, i] = mNrmMin_j(C_i) + off_k with off_k geometric in
    (1e-3, m_top]. Bounds move only during the first few (warmup) iterations,
    so anchoring once on the first real output is sufficient for the algebra
    this feeds (ratios / least squares / feasibility)."""
    Cgrid = np.asarray(agent.Cgrid, dtype=float).reshape(-1)
    if Cgrid.size > max_c_points:
        stride = int(np.ceil(Cgrid.size / max_c_points))
        Csub = Cgrid[::stride]
        if Csub[-1] != Cgrid[-1]:
            Csub = np.append(Csub, Cgrid[-1])
    else:
        Csub = Cgrid
    top = float(m_top if m_top is not None else agent.aXtraGrid[-1])
    offs = np.geomspace(1e-3, top, int(n_offsets))
    grids = []
    for j in range(len(sol.cFunc)):
        b = np.asarray(sol.mNrmMin[j](Csub), dtype=float).reshape(-1)
        M = b[None, :] + offs[:, None]              # (K, Cc)
        Cm = np.tile(Csub, (offs.size, 1))          # (K, Cc)
        grids.append((M, Cm))
    return grids


def probe_solution(sol, grids):
    vals = [np.asarray(sol.cFunc[j](M, Cm)).ravel()
            for j, (M, Cm) in enumerate(grids)]
    return np.concatenate(vals)


def make_hooks(agent, n_offsets=32, max_c_points=32):
    """Build (step, probe, combine, metric, feasible) closures for one solve."""
    from HARK.core import solve_one_cycle
    from HARK.metric import distance_metric
    from HARK.ConsumptionSaving.ConsIndShockModel import ConsumerSolution

    cache = {}

    def step(sol):
        return solve_one_cycle(agent, sol, None)[0]

    _GAP_EPS = 1e-12

    def _ensure_grids(sol):
        if "grids" not in cache:
            # First probe target is always a REAL step output (driver
            # contract) -- safe to anchor bounds on it. The tensor tops out
            # at 1.35x the solve-grid top: the next step evaluates the input
            # policy at mNext beyond the grid top (income shocks + growth).
            cache["grids"] = build_probe_cache(
                agent, sol, n_offsets=n_offsets, max_c_points=max_c_points,
                m_top=1.35 * float(agent.aXtraGrid[-1]))
            cache["term_vec"] = probe_solution(agent.solution_terminal,
                                               cache["grids"])

    def probe(sol):
        """LOG-GAP image ln(T - c) on the fixed tensor -- the coordinates the
        drivers mix in (matches combine(), so a candidate's probe is exactly
        the affine combination of its constituents' probes)."""
        _ensure_grids(sol)
        cv = probe_solution(sol, cache["grids"])
        if not isinstance(sol.cFunc[0], GapLogLinCombFunc2D):
            cache["last_real_cvec"] = cv   # collapse-guard reference
        gap = np.maximum(cache["term_vec"] - cv, _GAP_EPS)
        return np.log(gap)

    def feasible(vec):
        """vec is a log-gap image. Rejects (a) non-finite images, (b) c <= 0
        (exp(vec) >= T), and (c) COLLAPSE: mixed c below 10% of the newest
        real iterate's c anywhere. (c) is load-bearing: c ~ 0 is a numerical
        pseudo-fixed-point of the EGM map (vP blows up, next c ~ 0 again),
        so a wild downward mix can "converge" the production metric onto a
        100%-wrong policy (T1 round 4). Genuine per-step downward motion of
        the true iteration is orders of magnitude smaller than 10x."""
        if not np.all(np.isfinite(vec)):
            return False
        tv = cache.get("term_vec")
        if tv is None:
            return True
        cv = tv - np.exp(vec)
        if not np.all(cv > 0.0):
            return False
        ref = cache.get("last_real_cvec")
        if ref is not None and np.any(cv < 0.1 * ref):
            return False
        return True

    def combine(weights, sols):
        weights = np.asarray(weights, dtype=float)
        _ensure_grids(sols[int(np.argmax(np.abs(weights)))])
        term = agent.solution_terminal
        anchor = sols[int(np.argmax(np.abs(weights)))]
        n_states = len(sols[0].cFunc)
        cFunc, vPfunc = [], []
        for j in range(n_states):
            cf = GapLogLinCombFunc2D(weights, [s.cFunc[j] for s in sols],
                                     term.cFunc[j],
                                     fallbackFunc=anchor.cFunc[j],
                                     eps=_GAP_EPS)
            cFunc.append(cf)
            vPfunc.append(LinCombMargValue2D(cf, agent.CRRA))
        return ConsumerSolution(cFunc=cFunc, vPfunc=vPfunc,
                                mNrmMin=anchor.mNrmMin)

    return step, probe, combine, distance_metric, feasible


def accel_solve_agent(agent, from_solution=None, method="anderson",
                      tol=None, n_offsets=32, max_c_points=32, **driver_kw):
    """Drop-in accelerated replacement for ``HARK.core.solve_agent`` on
    infinite-horizon AggFiscal-family agents. Returns (solution_list, info);
    sets agent.solution_distance / agent.completed_cycles like solve_agent.

    method: 'plain' (reference driver, production stopping rule), 'aitken',
    or 'anderson'. The returned solution is always a REAL final plain-step
    output (jump-hygiene contract in hark_fti.accel_driver)."""
    drv = _load_driver()
    if agent.cycles != 0:
        raise ValueError("accel_solve_agent handles infinite-horizon "
                         "(cycles=0) agents only")
    x0 = from_solution if from_solution is not None else agent.solution_terminal
    tol = float(tol if tol is not None else agent.tolerance)
    step, probe, combine, metric, feasible = make_hooks(
        agent, n_offsets=n_offsets, max_c_points=max_c_points)
    if method == "plain":
        x, info = drv.plain_solve(x0, step, metric, tol, **driver_kw)
    elif method == "aitken":
        x, info = drv.aitken_solve(x0, step, probe, combine, metric, tol,
                                   feasible=feasible, **driver_kw)
    elif method == "anderson":
        x, info = drv.anderson_solve(x0, step, probe, combine, metric, tol,
                                     feasible=feasible, **driver_kw)
    else:
        raise ValueError(f"unknown method {method!r}")
    agent.solution_distance = info["final_metric"]
    agent.completed_cycles = info["steps"]
    return [x], info


# --- Arm (c): composite-block atom builder (plan §C7 step 4, §C8 schema) ----

def build_composite_edges(agent, clip_omega=True):
    """Extract the C-conditional composite-Markov structure from an
    AggFiscalType agent into the §C8 edge/block schema (combine='nvrs',
    per-target ADFunc-scaled atoms).

    Blocks are (Markov state j, C-knot k), index b = j*Ccount + k. Per source
    (i,k) and next state j with MrkvArray[i,j]>0: Cnext = CFunc[i][j](C_k)
    selects the two adjacent C-knots with linear weights (clipped at the grid
    ends), each target carrying its own atoms {R_j, psi*G_j,
    theta*ADFunc(C_k', Rec_j), probs_j}. Per-source LivPrb folds into
    R_own[b(i,k)] = Rfree[i]*LivPrb[i] with DiscFacEff = DiscFac (the
    consumed-space const then equals 1/(DiscFac*LivPrb_i*R_i), matching the
    production Euler). hNrm_blocks[b(j,k)] = h_AD[k][j] from
    compute_pf_decay_limits (the AD-aware PF asymptote per (C-knot, state)).

    Returns (edges, hNrm_blocks, R_own_blocks, MPCmin, meta).
    """
    from AggFiscalModel import compute_pf_decay_limits

    def _p0(x):
        # HARK time-varying attrs are per-period lists (T_cycle=1 here):
        # unwrap period 0; harmless for already-flat attrs.
        return x[0] if isinstance(x, list) and len(x) == 1 else x

    MrkvArray = agent.MrkvArray[0]
    S = MrkvArray.shape[0]
    Cgrid = np.asarray(agent.Cgrid, dtype=float).reshape(-1)
    Ccount = Cgrid.size
    IncShkDstn = _p0(agent.IncShkDstn)
    Rfree = np.broadcast_to(np.asarray(_p0(agent.Rfree), dtype=float), (S,))
    PermGroFac = np.broadcast_to(
        np.asarray(_p0(agent.PermGroFac), dtype=float), (S,))
    LivPrb = np.broadcast_to(np.asarray(_p0(agent.LivPrb), dtype=float),
                             (S,))
    nbase = int(agent.num_base_MrkvStates)
    ADFunc = agent.ADFunc
    CFunc = agent.CFunc
    DiscFac = float(agent.DiscFac)
    CRRA = float(agent.CRRA)

    MPCmin, h_AD = compute_pf_decay_limits(
        MrkvArray, Rfree, PermGroFac, IncShkDstn, Cgrid, ADFunc,
        nbase, DiscFac, CRRA, LivPrb)
    h_AD = np.asarray(h_AD, dtype=float)          # (Ccount, S)

    def b_of(j, k):
        return j * Ccount + k

    def atoms(j, kprime):
        d = IncShkDstn[j]
        AggState = int(np.floor(j / nbase))
        RecState = (AggState % 2) == 1
        ad = float(ADFunc(Cgrid[kprime], RecState))
        return {"R": float(Rfree[j]),
                "Gk": np.asarray(d.atoms[0], float) * float(PermGroFac[j]),
                "Tran": np.asarray(d.atoms[1], float) * ad,
                "Probs": np.asarray(d.pmv, float)}

    N = S * Ccount
    hNrm_blocks = np.empty(N)
    R_own_blocks = np.empty(N)
    for j in range(S):
        for k in range(Ccount):
            hNrm_blocks[b_of(j, k)] = h_AD[k, j]
            R_own_blocks[b_of(j, k)] = float(Rfree[j]) * float(LivPrb[j])

    edges = [[] for _ in range(N)]
    for i in range(S):
        for k in range(Ccount):
            src = b_of(i, k)
            for j in range(S):
                pij = float(MrkvArray[i, j])
                if pij == 0.0:
                    continue
                Cnext = float(np.asarray(CFunc[i][j](np.array([Cgrid[k]])))
                              .reshape(-1)[0])
                kk = int(np.clip(np.searchsorted(Cgrid, Cnext) - 1,
                                 0, max(Ccount - 2, 0)))
                if Ccount == 1:
                    targets = [(b_of(j, 0), 1.0, atoms(j, 0))]
                else:
                    om = (Cnext - Cgrid[kk]) / (Cgrid[kk + 1] - Cgrid[kk])
                    # clip_omega=False reproduces production's BilinearInterp
                    # EXTRAPOLATION beyond the C-grid edge (ω outside [0,1]) —
                    # the §C13 live suspect for the 2.7e-4 systematic.
                    om = float(np.clip(om, 0.0, 1.0)) if clip_omega \
                        else float(om)
                    targets = [(b_of(j, kk), 1.0 - om, atoms(j, kk)),
                               (b_of(j, kk + 1), om, atoms(j, kk + 1))]
                edges[src].append({"p": pij, "combine": "nvrs",
                                   "targets": targets})
    meta = {"S": S, "Ccount": Ccount, "MPCmin": float(MPCmin),
            "DiscFacEff": DiscFac, "CRRA": CRRA,
            "LivPrb": LivPrb.copy(), "Cgrid": Cgrid.copy()}
    return edges, hNrm_blocks, R_own_blocks, float(MPCmin), meta


def newton2d_solve_agent(agent, tol_delta=1e-9, tol_EE=1e-9, maxit=120,
                         verbose=False):
    """Arm-c route (plan §C7 step 5): solve the agent's C-conditional system
    by the composite-block consumed Newton and reassemble the per-state 2-D
    ConsumerSolution (LinearInterpOnInterp1D over the C-knot slice policies —
    the terminal builder's own 2-D construction). Returns (solution_list,
    info); raises on non-convergence (the safe-graft ladder falls back)."""
    import sys as _sys
    if _FPC not in _sys.path:
        _sys.path.insert(0, _FPC)
    export_fti_pythonpath()
    from hark_fti.consumed_ati_markov import solve_stationary_consumed_blocks
    from HARK.ConsumptionSaving.ConsIndShockModel import ConsumerSolution
    from HARK.interpolation import (LinearInterpOnInterp1D,
                                    MargValueFuncCRRA, ConstantFunction)

    edges, hb, rb, MPCmin, meta = build_composite_edges(agent)
    # Warm start (the top wall lever; plan §C7): reuse the agent's previous
    # newton2d consumed(a) iterate when the composite SHAPE matches (same
    # state-count x C-count x grid). Shape mismatch (base<->recession
    # switches) falls back to the PF seed inside the solver.
    aG = np.asarray(agent.aXtraGrid, dtype=float)
    c_init = getattr(agent, "_newton2d_cInterior", None)
    if c_init is not None and np.shape(c_init) != (len(hb), aG.size):
        c_init = None
    X, conts, info = solve_stationary_consumed_blocks(
        aG, edges, hb, rb, MPCmin,
        meta["CRRA"], meta["DiscFacEff"], inner="gmres",
        tol_delta=tol_delta, tol_EE=tol_EE, maxit=maxit,
        tail_form="powerlaw", verbose=verbose, c_init=c_init)
    if not info.get("converged"):
        raise RuntimeError(
            f"newton2d did not converge ({info.get('converged_reason')}) "
            f"after {info.get('iters')} iters")
    S, Cc = meta["S"], meta["Ccount"]
    Cgrid = meta["Cgrid"]
    cFunc, vPfunc, mNrmMin = [], [], []
    for j in range(S):
        slices = [conts[j * Cc + k][3] for k in range(Cc)]
        cf2 = (LinearInterpOnInterp1D(slices, Cgrid) if Cc > 1
               else slices[0])
        cFunc.append(cf2)
        vPfunc.append(MargValueFuncCRRA(cf2, meta["CRRA"]))
        mNrmMin.append(ConstantFunction(0.0))
    sol = ConsumerSolution(cFunc=cFunc, vPfunc=vPfunc, mNrmMin=mNrmMin)
    # Representation-repair confirmation step (§C13 closing fix): the
    # consumed fixed-a-grid covers the below-kink band with ONE segment from
    # the (0,0) anchor (first unconstrained knot at m1 = a_min + X(a_min) ~
    # 0.5) — a chord under the concave policy, the source of the
    # grid-independent 2.7e-4 band error. One production EGM step from the
    # Newton fixed point rebuilds production-grade endogenous-m knots
    # through the kink region (and every byproduct: tails, Q-hat, dydx)
    # while moving the interior by ~the Newton residual only.
    from HARK.core import solve_one_cycle
    # Step 1 consumes the chord-poisoned continuation once; steps 2-3
    # consume the REPAIRED representation (rescore: 1 step -> 7.9e-5 median
    # with the peak shifted one step downstream; >=2 steps converge the
    # representation fixed point). Env-tunable.
    _nc = int(os.environ.get("HAFISCAL_NEWTON2D_CONFIRM", "5"))
    for _ in range(max(1, _nc)):
        sol = solve_one_cycle(agent, sol, None)[0]
    agent._newton2d_cInterior = X.copy()   # warm-start handle for re-solves
    info["engine"] = "newton2d/consumed_blocks+egm_confirm"
    info["warm_started"] = bool(c_init is not None)
    return [sol], info
