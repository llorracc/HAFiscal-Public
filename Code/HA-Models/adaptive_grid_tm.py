"""adaptive_grid_tm.py — TM-ergodic determination of the single global aNrm grid.

Supersedes the MC-max heuristic in adaptive_grid_bounds.py. The MC max was a single-agent
tail draw (noisy); the ergodic mass distribution is reproducible and distribution-aware.

CURRENT SCHEME (production path since the 2026-06-09 BUG-053 pre-flight audit):
  aNrmMin = 0 (fixed: the ergodic piles mass at the constraint, nothing to trim at the bottom)
  aNrmMax = production_dist_aGrid_max(): the (1 - 1e-4) ergodic-aNrm quantile of the
    MOST-PATIENT POSSIBLE college atom (the GIC cap atom, GPF = theGICfactor = 0.9995 under
    the BUG-053 fix), built ONCE on a fixed large covering grid and interpolated from the CDF.
    beta-INDEPENDENT (no fixed point with the (beta, nabla) estimation), monotone,
    reproducible. Production value: quantile ~1224 -> dist_aGrid_max = 1300 (the
    HAFISCAL_TM_AMAX canonical default; see EstimParameters.py and
    reestimate_bug053_orchestrate.py).

NAMING (owner ruling 2026-07-25): the TM/distribution-grid top is `dist_aGrid_max`
(extending HARK's object naming); the bare `aMax` spelling collided with the solve grid's
`aXtraMax`. `production_aMax` survives one deprecation cycle as a warning alias below.

OPT-IN PER-ATOM MODE (2026-07-26, dist-grid-top scoping plan component B):
  per_atom_dist_aGrid_max(agent): THE PASSED ATOM'S OWN (1 - threshold) WEALTH-weighted
  ergodic-aNrm quantile on the same fixed covering grid, rounded like the incumbent.
  Consumed by tm_methods.build_tm_agg_fiscal_a under HAFISCAL_DIST_TOP_MODE=per_atom
  (default 'global' keeps the scheme above byte-for-byte). Motivation + evidence:
  plans/20260726_dist-grid-top-scoping_plan.md (P2: the truncation knee is
  ATOM-specific — dropout/HS ~300-500 vs College >1300 — and WEALTH, not population
  mass, is the integrand the estimands care about).

RETIRED ORIGINAL SCHEME (user, 2026-06-09; retired the same day by the BUG-053 audit):
  iterate() ran a trim/grow fixed point WITH the discount-factor estimation (estimate the
  college (beta, nabla) on [0, aNrmMax]; trim aNrmMax to the last gridpoint with ergodic
  mass > 1e-4; repeat). The audit proved that loop is a non-convergent stable 2-cycle
  (trim-low <-> grow-high) whose result depends on MAX_ITERS parity; iterate() is kept
  only as a FAIL-FAST stub (raises RuntimeError instead of returning a non-converged value).

Only the COLLEGE ergodic is needed for the bound — it is the highest-growth-patience cohort
(highest beta* and Gamma), so its ergodic tail dominates; dropout/HS tails sit inside it.

estimate_college() and college_top_ergodic() wired from the estimation map (general-purpose
agent, 2026-06-09): subprocess estim_phase2_tm_a.py with HAFISCAL_EDTYPES=2, and an in-process
build_tm_agg_fiscal_a -> find_ergodic_distribution (j-major, sum over j).
"""
import os
import sys
import ast
import warnings
import subprocess

import numpy as np

THRESHOLD = 1e-4          # mass threshold for the upper-tail trim
ANRM_MAX_INIT = 1000.0    # wide starting upper bound
ANRM_MIN = 0.0            # fixed lower bound (constraint)
REL_TOL = 0.01            # convergence: |aNrmMax_new - aNrmMax| / aNrmMax < REL_TOL
MAX_ITERS = 8
ACOUNT = 200              # grid points (estimation default)
GROW_FACTOR = 2.0         # when the grid TRUNCATES (top gridpoint mass > THRESHOLD), grow aNrmMax x this
ANRM_MAX_CAP = 50000.0    # safety: growth beyond this => most-patient atom tail pathologically fat

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")
_RES = os.path.join(_HERE, "Results")
_LOGDIR = os.path.join(_RES, "tmp", "grid_estim")


def trim_aNrmMax(grid, mass, threshold=THRESHOLD):
    """Walk DOWN from the top gridpoint; return (aNrmMax, index) of the first gridpoint whose
    ergodic aNrm-marginal mass exceeds `threshold`.

    Example: grid[-4:]=[..], mass[-4:]=[0.01, 0.00011, 0.00009, 0.00001] -> returns grid[-3].
    """
    grid = np.asarray(grid, dtype=float)
    mass = np.asarray(mass, dtype=float)
    assert grid.shape == mass.shape, (grid.shape, mass.shape)
    for k in range(len(grid) - 1, -1, -1):
        if mass[k] > threshold:
            return float(grid[k]), k
    return float(grid[0]), 0  # degenerate: all mass below threshold


def _read_estim_record(path, edtype):
    """(beta, nabla, GICx) for `edtype` from a DiscFacEstim TM-a file (plain-float or np.float64)."""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line.startswith("{") or f"'EducationGroup': {edtype}" not in line:
                continue
            try:
                rec = ast.literal_eval(line)
            except (ValueError, SyntaxError):
                rec = eval(line, {"np": np, "__builtins__": {}})
            return float(rec["beta"]), float(rec["nabla"]), float(rec["GICx"])
    raise KeyError(f"edType={edtype} not in {path}")


def estimate_college(aNrmMax, interpretation="ESC", warm_start=False,
                     CRRA=2.0, Rfree=1.01, log_tag="0"):
    """Estimate COLLEGE (edType=2) (beta, nabla) via TM-a on grid [0, aNrmMax] (subprocess).

    warm_start=False -> cold NM from the script default (HAFISCAL_NM_START_FROM_SAVED=0);
    warm_start=True  -> NM from the just-written edType2 file (loop's own previous beta).
    """
    os.makedirs(_LOGDIR, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "HAFISCAL_EDTYPES": "2",
        "HAFISCAL_INTERPRETATION": interpretation,
        "HAFISCAL_TM_AMAX": repr(float(aNrmMax)),
        "HAFISCAL_TM_AMIN": repr(float(ANRM_MIN)),
        "HAFISCAL_GICX_MODE": "hardcoded",
        "HAFISCAL_NUM_STARTS": "1",
        "HAFISCAL_NM_START_FROM_SAVED": "1" if warm_start else "0",
        "HAFISCAL_SERIAL": "1",
        "PYTHONUNBUFFERED": "1",
    })
    out_file = os.path.join(_RES, f"DiscFacEstim_CRRA_{CRRA}_R_{Rfree}_edType2_TM_a_{interpretation}.txt")
    log_file = os.path.join(_LOGDIR, f"iter{log_tag}_edType2.log")
    with open(log_file, "w") as lf:
        subprocess.run([sys.executable, "-u", "estim_phase2_tm_a.py"],
                       cwd=_FPC, env=env, check=True, stdout=lf, stderr=subprocess.STDOUT)
    beta, nabla, _ = _read_estim_record(out_file, 2)
    return beta, nabla


def college_top_ergodic(beta, nabla, aNrmMax, interpretation="ESC", aCount=ACOUNT):
    """Most-patient (GIC-clipped top) college atom's ergodic aNrm marginal on grid [0, aNrmMax].

    Returns (dist_aGrid, mass) on the KERNEL grid (the one HAFISCAL_TM_AMAX bounds), so the
    trimmed aNrmMax is a kernel gridpoint usable directly as the next HAFISCAL_TM_AMAX.
    """
    os.environ.setdefault("HAFISCAL_INTERPRETATION", interpretation)
    if _FPC not in sys.path:
        sys.path.insert(0, _FPC)
    # EstimParameters/Parameters read sys.argv[1:4] (Rfree/CRRA/IncUnemp) AT IMPORT; the
    # driver's own argv (--aNrmMax-init/--max-iters) would crash float(). Neutralize it
    # for the import so EstimParameters uses its production defaults (1.01/2.0/0.7).
    _saved_argv = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        import numpy as _np
        from HARK.distributions import Uniform, DiscreteDistribution
        import EstimParameters as ep
        from EstimParameters import init_college, init_ADEconomy, DiscFacCount, GICmaxBetas, minBeta, gic_capped_beta
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        from tm_methods import build_tm_agg_fiscal_a, find_ergodic_distribution
    finally:
        sys.argv = _saved_argv

    # GIC-clipped most-patient atom (mirrors estim_phase2_tm_a.py:106-119 / Parameters.py:352-357).
    # BUG-053: route the cap through gic_capped_beta so the GIC ceiling is imposed on the GROWTH
    # PATIENCE FACTOR (GPF), not on beta directly. The earlier hand-rolled `GICmaxBetas[2]*GICfactor`
    # was the old beta-shave (GPF = 0.999^(1/CRRA) = 0.9995), which fattened the most-patient atom's
    # ergodic tail and inflated this grid (~674 -> ~489 at beta=0.9921). gic_capped_beta honors the
    # HAFISCAL_GIC_SHAVE_ON_GPF toggle (default-on = the fix).
    cap = gic_capped_beta(2, ep.theGICfactor)
    dfs = Uniform(beta - nabla, beta + nabla).discretize(DiscFacCount)
    beta_top = float(_np.clip(dfs.atoms[0], minBeta, cap).max())

    # one college agent at beta_top (mirrors estim_phase2_tm_a.py:62-98 for a single atom)
    ag = AggFiscalType(**init_college)
    ag.cycles = 0
    eco = AggregateDemandEconomy(**init_ADEconomy)
    ag.get_economy_data(eco)
    Dunemp = DiscreteDistribution(_np.array([1.0]), [_np.array([1.0]), _np.array([ag.IncUnemp])])
    Dunemp_nb = DiscreteDistribution(_np.array([1.0]), [_np.array([1.0]), _np.array([ag.IncUnempNoBenefits])])
    ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Dunemp] * ep.UBspell_normal + [Dunemp_nb]]
    ag.IncShkDstn_base = ag.IncShkDstn
    ag.DiscFac = beta_top
    ag.AgentCount = 1
    ag.tm_a_indexed = True
    ag.interpretation = interpretation
    eco.agents = [ag]
    eco.solve()

    tm = build_tm_agg_fiscal_a(ag, aCount=aCount, dist_aGrid_max=float(aNrmMax), interpretation=interpretation)
    erg = _np.asarray(find_ergodic_distribution(tm["TranMatrix"]))
    J = ag.MrkvArray[0].shape[0]
    grid = _np.asarray(tm["dist_aGrid"], dtype=float)
    A = len(grid)
    mass = erg.reshape(J, A).sum(axis=0)
    mass = mass / mass.sum()
    return grid, mass, beta_top


def production_dist_aGrid_max(interpretation="ESC", threshold=THRESHOLD,
                              covering_aMax=20000.0, covering_aCount=4000, round_to=100.0,
                              verbose=True):
    """Production single global distribution-grid top `dist_aGrid_max` = the (1-threshold)
    ergodic-aNrm quantile of the MOST-PATIENT POSSIBLE college atom (the GIC cap itself:
    GPF=theGICfactor under the BUG-053 fix). Returns (dist_aGrid_max_rounded, quantile_raw,
    beta_top). (Renamed from `production_aMax` per the owner ruling 2026-07-25; the old name
    remains a deprecated warning alias below.)

    This REPLACES iterate() (below), which the 2026-06-09 BUG-053 pre-flight audit proved is
    a non-convergent stable 2-cycle (trim-low ~650 <-> grow-high ~1350) whose returned value
    depends on MAX_ITERS PARITY — with max_iters=8 it lands on the GROW leg and returns
    ~1100-1700 (+88..103% too large). The rel<REL_TOL convergence test is mathematically
    unreachable because the exponential grid's top cell is ~12% of the grid top.

    WHY THE CAP ATOM (not the estimated beta): the cap atom is the most patient atom ANY cohort
    can have (every estimated top atom clips to <= it), so its ergodic tail is the widest
    possible. Sizing the grid to it makes dist_aGrid_max beta-INDEPENDENT — no chicken-and-egg
    with the (beta,nabla) estimation, and it covers wherever the optimum lands (slack OR
    binding). Income shocks + Rfree are identical across education groups, so the college cap
    atom (highest GICmaxBetas) dominates dropout/HS tails too.

    WHY A QUANTILE BY INTERPOLATION (not a coarse-grid trim): snapping dist_aGrid_max to a
    ~12%-wide exponential rung is grid-quantized and, with HARK jump_to_grid edge-clipping, is
    what drives the old loop's oscillation. Build the cap-atom ergodic ONCE on a fixed large
    covering grid (top-cell mass << threshold, so no edge inflation) and INTERPOLATE the CDF.
    Verified stable to +/-0.6 across covering_aMax 5k-30k / aCount 2k-4k: the 1e-4 quantile
    = 856, which matches the independently-measured bucketed5d college most-patient support
    ~867 (BUG-053 followup). (Stability numbers measured at theGICfactor=0.999; at the
    production theGICfactor=0.9995 — set 2026-06-09, BUG-053 — the cap atom is more patient,
    so the quantile is ~1224 -> dist_aGrid_max=1300, the HAFISCAL_TM_AMAX canonical default.
    See reestimate_bug053_orchestrate.py.)
    """
    # beta=1.01 (> any cohort beta) with nabla=0 -> every discretized atom clips down to the
    # GIC cap, so college_top_ergodic returns beta_top = gic_capped_beta(2, theGICfactor) (the
    # patched, correct GPF-shave cap). No separate import of the cap needed.
    grid, mass, beta_top = college_top_ergodic(1.01, 0.0, covering_aMax,
                                               interpretation=interpretation, aCount=covering_aCount)
    cdf = np.cumsum(mass)
    cdf = cdf / cdf[-1]
    q = float(np.interp(1.0 - threshold, cdf, grid))
    dist_aGrid_max = float(np.ceil(q / round_to) * round_to) if round_to else q
    # AWARENESS NOTE (TM upward connectivity, 2026-06-10): keep dist_aGrid_max at/below the
    # natural saving limit — the asset level where even the BEST-case shock no longer lifts
    # assets, a'_hi(a) = a'(psi_min, xi_max) <= a. Below that limit every interior node keeps a
    # live upward edge (the TM stays irreducible and the upper tail gets positive ergodic mass);
    # above it, top nodes become one-way valves and their mass is zeroed. The (1-threshold)
    # ergodic quantile here sits well below that limit (verified: a'_hi(a) > a held at every
    # node up to dist_aGrid_max=1300 for the college cap atom), so this is a non-issue at
    # production thresholds — flagged only so a future, much larger dist_aGrid_max is not
    # chosen blindly. See memory project_tm_ergodic_single_stationary_not_backward.
    if verbose:
        print(f"[production_dist_aGrid_max] cap-atom beta_top={beta_top:.6f} (GPF={interpretation}); "
              f"(1-{threshold:g}) quantile={q:.1f} -> dist_aGrid_max={dist_aGrid_max:.1f} "
              f"(covering_aMax={covering_aMax:.0f}, aCount={covering_aCount})", flush=True)
    return dist_aGrid_max, q, beta_top


# Per-process memo for per_atom_dist_aGrid_max: the production Step-5a flow builds
# TMs for 21 discount-factor types, several times each (baseline ergodic + per-scenario
# rebuilds) — the covering-grid ergodic must be computed ONCE per atom, not per build.
_PER_ATOM_TOP_CACHE = {}


def _per_atom_top_cache_key(agent, interpretation, threshold, covering_aMax,
                            covering_aCount, round_to):
    """Stable per-process memo key over the atom's stationary inputs.

    Covers everything the covering-grid ergodic depends on: (DiscFac, CRRA,
    Splurge, per-state Rfree/PermGroFac/LivPrb, T_age, MrkvArray, IncShkDstn
    contents) plus the derivation knobs (interpretation, threshold, covering
    grid, rounding). Two agents differing in ANY of these get distinct keys;
    the 21 production types (same edu params, different beta) each compute
    once. Returns None when the agent cannot be keyed reliably — the caller
    then recomputes rather than risk serving a mis-keyed top.
    """
    import hashlib
    try:
        mrkv = np.asarray(agent.MrkvArray[0], dtype=np.float64)
        J = int(mrkv.shape[0])
        h = hashlib.sha256()
        h.update(str(mrkv.shape).encode())
        h.update(np.ascontiguousarray(mrkv).tobytes())
        for d in agent.IncShkDstn[0]:
            pmv = np.asarray(d.pmv, dtype=np.float64)
            h.update(str(pmv.shape).encode())
            h.update(np.ascontiguousarray(pmv).tobytes())
            try:
                atoms_arr = np.asarray(d.atoms, dtype=np.float64)
                h.update(str(atoms_arr.shape).encode())
                h.update(np.ascontiguousarray(atoms_arr).tobytes())
            except (ValueError, TypeError):
                for arr in d.atoms:  # ragged atoms container: hash per variable
                    a2 = np.asarray(arr, dtype=np.float64)
                    h.update(str(a2.shape).encode())
                    h.update(np.ascontiguousarray(a2).tobytes())
        return (
            float(np.asarray(agent.DiscFac, dtype=float).ravel()[0]),
            float(agent.CRRA),
            float(getattr(agent, 'Splurge', 0.0)),
            tuple(float(x) for x in np.asarray(agent.Rfree, dtype=float).ravel()[:J]),
            tuple(float(x) for x in np.asarray(agent.PermGroFac[0], dtype=float).ravel()[:J]),
            tuple(float(x) for x in np.asarray(agent.LivPrb[0], dtype=float).ravel()[:J]),
            (int(agent.T_age) if getattr(agent, 'T_age', None) is not None else None),
            h.hexdigest(),
            str(interpretation), float(threshold), float(covering_aMax),
            int(covering_aCount), float(round_to),
        )
    except Exception:
        return None


def per_atom_dist_aGrid_max(agent, threshold=1e-4, interpretation=None,
                            covering_aMax=20000.0, covering_aCount=4000,
                            round_to=100.0, verbose=False):
    """Per-ATOM distribution-grid top: the PASSED (solved) agent's OWN
    (1 - threshold) WEALTH-weighted ergodic-aNrm quantile, computed with the
    module's covering-grid machinery and rounded up like the incumbent
    (ceil to `round_to`). Returns the scalar `dist_aGrid_max` for THIS atom.

    Scope vs :func:`production_dist_aGrid_max` (the global rule being
    superseded in scope by the 2026-07-26 dist-grid-top scoping plan): the
    incumbent sizes ONE global top to the most-patient POSSIBLE college atom
    (the GIC cap) by a POPULATION-mass quantile. The plan's P2 sweep measured
    both defects of that proxy:
      (a) the truncation knee is ATOM-specific — dropout/HS knees sit at
          ~300-500 while the College knee is >1300 — so a single cap-sized top
          over-grids every thin atom (and, at fixed dist count, starves their
          bulk resolution);
      (b) population mass is the WRONG INTEGRAND — the estimands (Lorenz
          targets, E[a], top shares, multipliers) integrate WEALTH, and a fat
          tail carries wealth above T scaling as T^(1-alpha) (slowly decaying),
          so wealth truncation bites long before headcount does.
    Hence: per-atom construction on the wealth integrand — `threshold` bounds
    the share of the ATOM'S OWN ergodic WEALTH above the grid top (not its
    headcount). Per-atom is also what makes the tail well-defined: each atom's
    ergodic tail is a clean single-alpha Kesten tail (alpha solves
    L*E[(Thorn_Gamma/psi)^alpha] = 1; no positive root at L=1 — mortality is
    the tail stabilizer), while POOLED-distribution exponents drift with the
    measurement window (a mixture artifact; plan capstone). Measured deep-tail
    alpha ~= 1.5 at the GIC cap vs lognormal-caricature 1.70 — the quantile
    here is MEASURED from the atom's own ergodic CDF; the Kesten root is the
    prior/fallback, never the pin (memory:
    feedback_local_measurement_over_asymptotic_anchors).

    beta-DEPENDENCE (deliberate, unlike the incumbent): the top is the atom's
    own, so call with the SOLVED agent whose TM is about to be built. There is
    no chicken-and-egg with the (beta, nabla) estimation here because the
    derivation takes the agent's configuration as given at build time; the
    incumbent's beta-independent cap anchor remains available as the global
    mode. Consumed by ``tm_methods.build_tm_agg_fiscal_a`` under
    ``HAFISCAL_DIST_TOP_MODE=per_atom`` (default ``global`` = incumbent path,
    byte-for-byte). NO silent floor at the global top: per-atom means
    per-atom (thin atoms genuinely get short grids).

    Cost/caching: one covering-grid ergodic (J x covering_aCount sparse
    states, the incumbent's own budget at base-Mrkv J~6) per DISTINCT atom
    per process — memoized on (beta, key params) via
    ``_per_atom_top_cache_key`` so the 21 production types do not recompute
    across repeated TM builds. The covering build passes an explicit
    ``dist_aGrid_max=covering_aMax``, so it can never re-enter the per-atom
    resolution (no recursion). Derived at Cratio=1.0: the top is a
    STATIONARY sizing rule; transient AD scaling is not part of the grid's
    definition (experiment TMs reuse the baseline grid).
    """
    # Resolve the interpretation like the surrounding machinery: explicit arg
    # > the agent's own attribute > the HAFISCAL_INTERPRETATION single source.
    if interpretation is None:
        interpretation = getattr(agent, 'interpretation', None)
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    if _FPC not in sys.path:
        sys.path.insert(0, _FPC)
    if interpretation is None:
        from _interpretation import get_interpretation
        interpretation = get_interpretation()

    key = _per_atom_top_cache_key(agent, interpretation, threshold,
                                  covering_aMax, covering_aCount, round_to)
    if key is not None and key in _PER_ATOM_TOP_CACHE:
        return _PER_ATOM_TOP_CACHE[key]

    from tm_methods import build_tm_agg_fiscal_a, find_ergodic_distribution

    J = int(agent.MrkvArray[0].shape[0])
    if J > 12:
        warnings.warn(
            f"per_atom_dist_aGrid_max: agent has J={J} Mrkv states; the covering "
            f"build (J*{covering_aCount} sparse states) is sized for base-Mrkv "
            f"agents (J~6). The production resolution site fires on 'base' agents "
            f"only (experiment TMs reuse the baseline dist_aGrid); a "
            f"recession-Mrkv agent here will be slow.")

    tm = build_tm_agg_fiscal_a(agent, aCount=int(covering_aCount),
                               dist_aGrid_max=float(covering_aMax),
                               Cratio=1.0, interpretation=interpretation)
    erg = np.asarray(find_ergodic_distribution(tm["TranMatrix"]))
    grid = np.asarray(tm["dist_aGrid"], dtype=float)
    A = len(grid)
    mass = erg.reshape(J, A).sum(axis=0)  # j-major, sum over j (module convention)
    tot = float(mass.sum())
    if tot <= 0.0:
        raise RuntimeError(
            "per_atom_dist_aGrid_max: covering-grid ergodic carries no mass — "
            "the atom's TM is degenerate (check the ergodicity guard / GPF_out).")
    mass = mass / tot
    # WEALTH-weighted CDF: W(a) = sum_{a_i <= a} m_i * a_i / sum_i m_i * a_i.
    # Interpolated like the incumbent's population CDF (same covering-grid
    # rationale: top-cell mass << threshold, so no edge inflation).
    wealth = mass * grid
    w_tot = float(wealth.sum())
    if w_tot > 0.0:
        wcdf = np.cumsum(wealth) / w_tot
        q = float(np.interp(1.0 - threshold, wcdf, grid))
    else:
        q = 0.0
    dist_aGrid_max = float(np.ceil(q / round_to) * round_to) if round_to else q
    if dist_aGrid_max <= 0.0:
        # Degenerate atom: (essentially) all ergodic wealth at the constraint.
        # A zero-width dist grid cannot exist, so use one rounding unit and SAY
        # so — this is a degenerate-grid guard, NOT a floor at the global top.
        dist_aGrid_max = float(round_to) if round_to else max(q, 1.0)
        warnings.warn(
            f"per_atom_dist_aGrid_max: wealth-weighted quantile is {q:g} (atom's "
            f"ergodic wealth ~ all at the constraint); using the minimal grid top "
            f"{dist_aGrid_max:g} (one rounding unit) instead of a zero-width grid.")
    if verbose:
        _dfac = float(np.asarray(agent.DiscFac, dtype=float).ravel()[0])
        print(f"[per_atom_dist_aGrid_max] DiscFac={_dfac:.6f} J={J} "
              f"({interpretation}): (1-{threshold:g}) WEALTH quantile={q:.1f} -> "
              f"dist_aGrid_max={dist_aGrid_max:.1f} "
              f"(covering_aMax={covering_aMax:.0f}, aCount={covering_aCount})",
              flush=True)
    if key is not None:
        _PER_ATOM_TOP_CACHE[key] = dist_aGrid_max
    return dist_aGrid_max


def production_aMax(*args, **kwargs):
    """DEPRECATED alias for :func:`production_dist_aGrid_max` (owner ruling 2026-07-25:
    the TM distribution-grid top is `dist_aGrid_max`; the bare `aMax` spelling collided
    with the solve grid's `aXtraMax`). Warns once, then delegates unchanged — kept for
    one deprecation cycle (the HAFISCAL_MODE→MULTIPLIER_ENGINE precedent)."""
    warnings.warn(
        "adaptive_grid_tm.production_aMax() is deprecated; use "
        "production_dist_aGrid_max() (owner ruling 2026-07-25 rename of the TM "
        "distribution-grid top; behavior unchanged).",
        DeprecationWarning, stacklevel=2)
    return production_dist_aGrid_max(*args, **kwargs)


def iterate(aNrmMax=ANRM_MAX_INIT, interpretation="ESC", max_iters=MAX_ITERS, verbose=True):
    """DEPRECATED / BROKEN — use production_dist_aGrid_max() instead.

    The 2026-06-09 BUG-053 audit proved this trim/grow fixed-point loop is a non-convergent
    stable 2-cycle that returns an arbitrary, ~2x-too-large value set by MAX_ITERS parity.
    Kept only for reproducing the prior session's (wrong) behavior. It now FAILS FAST rather
    than silently returning a non-converged value (see the end of the loop)."""
    history = []
    for it in range(max_iters):
        # BUG-053 re-estimation: the FIRST iteration is COLD (no warm-start from the pre-fix
        # beta=0.9921 pickle, which was estimated under the buggy beta-shave —
        # feedback_no_warmstart_when_validating_solver_fix). Subsequent iterations may warm-start:
        # grid-adaptation is a fixed point (not a fix-validation), NM converges to the same optimum
        # regardless of the starting simplex (verified cold==warm in the prior session), so warming
        # 1+ only saves NM evals.
        beta, nabla = estimate_college(aNrmMax, interpretation=interpretation,
                                       warm_start=(it > 0), log_tag=str(it))
        grid, mass, beta_top = college_top_ergodic(beta, nabla, aNrmMax, interpretation=interpretation)
        edge = float(mass[-1])
        truncating = edge > THRESHOLD
        if truncating:
            # top gridpoint still carries mass > THRESHOLD => the grid truncates the most-patient
            # atom's tail (it sits ~at the GIC boundary). GROW, do NOT trim/converge.
            aNrmMax_new, kidx, rel = aNrmMax * GROW_FACTOR, len(grid) - 1, float('inf')
        else:
            aNrmMax_new, kidx = trim_aNrmMax(grid, mass)
            rel = abs(aNrmMax_new - aNrmMax) / max(aNrmMax, 1e-12)
        history.append(dict(iter=it, aNrmMax_in=aNrmMax, beta=beta, nabla=nabla, beta_top=beta_top,
                            aNrmMax_out=aNrmMax_new, trim_index=kidx, n_grid=len(grid),
                            edge_mass=edge, rel=rel, truncating=truncating))
        if verbose:
            tag = "  GROW (truncating)" if truncating else ""
            print(f"[iter {it}] aNrmMax {aNrmMax:.2f} -> {aNrmMax_new:.2f}{tag}  "
                  f"beta={beta:.4f} nabla={nabla:.4f} beta_top={beta_top:.4f}  "
                  f"trim@grid[{kidx}]/{len(grid)} edgeMass={edge:.2e} rel={rel:.4f}", flush=True)
        if aNrmMax_new > ANRM_MAX_CAP:
            print(f"  WARNING: aNrmMax {aNrmMax_new:.0f} exceeded cap {ANRM_MAX_CAP:.0f} — the "
                  f"GIC-clipped most-patient atom's tail is pathologically fat (tighten the "
                  f"GICfactor shave). Stopping.", flush=True)
            return aNrmMax_new, history
        if (not truncating) and rel < REL_TOL:
            if verbose:
                print(f"converged: aNrmMax = {aNrmMax_new:.2f}", flush=True)
            return aNrmMax_new, history
        aNrmMax = aNrmMax_new
    # FAIL FAST (audit 2026-06-09): the loop is a stable 2-cycle and ALWAYS reaches here.
    # Returning aNrmMax would hand Phase 2 an arbitrary GROW/TRIM-leg value set by max_iters
    # parity. Do NOT silently return it.
    raise RuntimeError(
        f"adaptive_grid_tm.iterate() did not converge in {max_iters} iters (last aNrmMax="
        f"{aNrmMax:.2f}); this loop is a known non-convergent 2-cycle (BUG-053 audit). "
        f"Use production_dist_aGrid_max() instead.")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="TM-ergodic production aNrm grid (college cap-atom quantile).")
    ap.add_argument("--interpretation", default="ESC", choices=["ESC", "CDC"])
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--covering-aMax", type=float, default=20000.0)
    ap.add_argument("--covering-aCount", type=int, default=4000)
    ap.add_argument("--legacy-iterate", action="store_true",
                    help="run the DEPRECATED non-convergent trim/grow loop (will fail-fast)")
    a = ap.parse_args()
    THRESHOLD = a.threshold
    if a.legacy_iterate:
        dist_aGrid_max, hist = iterate(aNrmMax=ANRM_MAX_INIT, interpretation=a.interpretation)
    else:
        dist_aGrid_max, q, beta_top = production_dist_aGrid_max(
            interpretation=a.interpretation, threshold=a.threshold,
            covering_aMax=a.covering_aMax, covering_aCount=a.covering_aCount)
    print(f"\nPRODUCTION single global grid: [{ANRM_MIN}, {dist_aGrid_max:.2f}]")
    print(f"Next: estimate all 3 edTypes with HAFISCAL_TM_AMAX={dist_aGrid_max:.4f}.")
