"""onset_dist_top.py — the onset ∧ support distribution-grid-top rule (BUG-084).

STATUS: PROMOTED 2026-08-21 (Phase 4 of plans_local/20260821-1530h_bug084-onset-support-
test-then-implement_plan.md, gates G1 ∧ G2-College green) — this module is the documented
re-derivation path for `dist_aGrid_max`, replacing the retired cap-atom-quantile rule
(BUG-084; owner ruling `conclusions_private/2026-08-21_dist-top-onset-rule-ruling.md`).
Verdict (2026-08-21): ρ=2 required_top = 611 ⟹ the production 1300 is RATIFIED with 2.1×
margin; ladder arms at tops {300, 800, 2900} moved College by ≤1.2e-4 (∇) and dropout by
≤1e-3-relative — top-insensitive down to 300 (the tail state absorbing truncation), so the
rule is a conservative guardrail. Still off the production run path: nothing imports this
at run time; it is the tool a human runs when the calibration changes.

THE RULE (owner construction + ruling, 2026-08-21). For each estimated atom i:

    a*_i = min( kernel_onset_i(tau), support_i(eps) )
    required_top(tau, eps) = max_i a*_i     (+ margin; production 1300 stands unless
                                             the plan's tests demand otherwise)

- kernel_onset_i(tau): do ONE EGM step back from the PF anchor c̄(m) = κ̲(m + h) — a
  one-shot computation from primitives, so the 2026-06-09 `iterate()` grid↔estimate
  2-cycle cannot arise — and form the MORTALITY-INCLUSIVE one-step population kernel of a
  (with prob 1−L_eff: death → newborn at the bottom, a down-move for every relevant a;
  with prob L_eff: the survivor kernel). The onset is the a beyond which the up/down
  asymmetry A(a) = P(a'>a|a) − P(a'<a|a) stays within tau of its plateau. NOTE the
  criterion is FLATTENING, not smallness: cap-class atoms plateau ABOVE ½ (up-moves stay
  more likely forever); stationarity is mortality's alone.
- support_i(eps): the atom's WEALTH-weighted (1−eps) ergodic quantile on a covering grid
  (wealth, not population mass, is the integrand the estimands care about — the P2 lesson
  of plans/20260726_dist-grid-top-scoping_plan.md).
- The min: an atom whose support ends below its kernel-onset never visits the region
  where its kernel misbehaves (e.g. the ρ=3 dropout/HS top atoms); an atom whose support
  extends beyond its onset is carried by the analytic Pareto tail state
  (HAFISCAL_DIST_TAIL_STATE), whose validity requires the grid top ≥ the onset.

Mortality split follows the certified tail-state convention: CULL at L_eff (stationary-age
effective survival with the T_age cliff), DISCOUNT the policy at β·L_raw. Tail exponent
α = root of L_eff·E[(GPF_eff/ψ)^α] = 1 via per_atom_alpha.kesten_alpha (T_age-split call).

Simplifications in the kernel leg (scale diagnostic, ±tens-of-percent on onsets, all
O(1/a)-constant effects): iid unemployment (no spell persistence), splurge ignored,
single employed-state income process. The one-EGM-step policy is exact where it is used:
the deviation from the anchor is tau-small in the scan region by construction.

Dialect per the 2026-07-14 ruling: ρ (CRRA), Γ (growth factor), κ̲ (MPCmin).
"""
from __future__ import annotations

import os
import sys
import ast
import numpy as np
from scipy.stats import norm

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")

# T_age (quarters): the deterministic cull age used by the production simulation and the
# tail-state derivation ("L_eff(T_age=200)=0.991254"). Kept as a module constant with a
# guard test against the closed form; override via the T_age argument where needed.
T_AGE_DEFAULT = 200

GROUP_INDEX = {"dropout": 0, "highschool": 1, "college": 2}
TOP_ATOM_OFFSET = 6.0 / 7.0   # 7-point uniform β discretization: top atom = β + (6/7)·∇


def effective_livprb(L_raw: float, T_age: int = T_AGE_DEFAULT) -> float:
    """Stationary-age effective survival with a hard cull at T_age.

    The stationary age distribution is p(age) ∝ L^age truncated at T_age, so the newborn
    (= death) share is n = (1−L)/(1−L^T_age) and L_eff = 1 − n. Reproduces the recorded
    0.991254 at (L_raw = 1−1/160, T_age = 200) exactly.
    """
    return 1.0 - (1.0 - L_raw) / (1.0 - L_raw ** T_age)


def _load_ep(rho: float = 2.0):
    """Import EstimParameters at the requested ρ (argv-driven CRRA since the BUG-085 fix).

    EstimParameters caches in sys.modules, so ONE process serves ONE ρ: a second call at a
    different ρ raises — run per-ρ analyses in separate processes (the CLI does).
    """
    if _FPC not in sys.path:
        sys.path.insert(0, _FPC)
    saved = sys.argv
    sys.argv = [saved[0]] if abs(rho - 2.0) < 1e-12 else [saved[0], "1.01", f"{float(rho)}"]
    try:
        import EstimParameters as ep
    finally:
        sys.argv = saved
    if abs(float(ep.CRRA) - float(rho)) > 1e-12:
        raise RuntimeError(
            f"EstimParameters already imported at CRRA={ep.CRRA}; requested rho={rho}. "
            "Run per-rho computations in separate processes.")
    return ep


def group_params(ep, group: str) -> dict:
    """The kernel leg's primitives for one education group, read from EstimParameters."""
    g = group.lower()
    Gamma = {"dropout": ep.PermGroFac_base_d[0],
             "highschool": ep.PermGroFac_base_h[0],
             "college": ep.PermGroFac_base_c[0]}[g]
    urate = {"dropout": ep.Urate_normal_d,
             "highschool": ep.Urate_normal_h,
             "college": ep.Urate_normal_c}[g]
    return dict(
        R=ep.Rfree_base[0], L_raw=ep.LivPrb_base[0], Gamma=Gamma, urate=urate,
        rep=ep.IncUnemp, sigma_psi=float(ep.PermShkStd[0]), sigma_theta=float(ep.TranShkStd[0]),
    )


def equiprob_lognormal(sigma: float, n: int = 61) -> np.ndarray:
    z = norm.ppf((np.arange(n) + 0.5) / n)
    x = np.exp(-0.5 * sigma ** 2 + sigma * z)
    return x / x.mean()          # exact mean-1


def kernel_onset(rho: float, beta: float, params: dict, *,
                 taus=(0.02, 0.01, 0.005), T_age: int = T_AGE_DEFAULT,
                 n_shock: int = 61, scan=(2.0, 3e4, 1100)) -> dict:
    """Mortality-inclusive kernel-asymmetry onset for one atom (discount factor `beta`).

    Returns {GPF_eff, A_inf, alpha, onset: {tau: a}, dev_at: {800, 1300}}.
    """
    R, Lraw, G = params["R"], params["L_raw"], params["Gamma"]
    u, rep = params["urate"], params["rep"]
    sP, sT = params["sigma_psi"], params["sigma_theta"]
    Leff = effective_livprb(Lraw, T_age)

    psi = equiprob_lognormal(sP, n_shock)
    wpsi = np.full(len(psi), 1.0 / len(psi))
    th_e = equiprob_lognormal(sT, n_shock) * (1 - u * rep) / (1 - u)
    theta = np.concatenate([th_e, [rep]])
    wth = np.concatenate([np.full(len(th_e), (1 - u) / len(th_e)), [u]])

    beta_eff = beta * Lraw                        # policy discount: β·L_raw
    kappa = 1 - (R * beta_eff) ** (1 / rho) / R   # κ̲ (MPCmin)
    h = (G / R) / (1 - G / R)                     # normalized human wealth (FHWC holds)
    GPFe = (R * beta_eff) ** (1 / rho) / G

    # --- one EGM step back from the PF anchor ---
    a_bld = np.geomspace(1e-2, 1e5, 3000)
    w2 = (wpsi[:, None] * wth[None, :])[:, :, None]
    Mp = (R / (G * psi))[:, None, None] * a_bld[None, None, :] + theta[None, :, None]
    integ = ((G * psi)[:, None, None] ** (-rho) * (kappa * (Mp + h)) ** (-rho) * w2).sum((0, 1))
    c1 = (R * beta_eff * integ) ** (-1 / rho)
    m1 = a_bld + c1
    slope_hi = (c1[-1] - c1[-2]) / (m1[-1] - m1[-2])

    def chat(m):
        c = np.interp(m, m1, c1)
        hi = m > m1[-1]
        c[hi] = c1[-1] + slope_hi * (m[hi] - m1[-1])
        return c

    # --- mortality-inclusive kernel scan ---
    a_scan = np.geomspace(*scan)
    Mp2 = (R / (G * psi))[:, None, None] * a_scan[None, None, :] + theta[None, :, None]
    Ap = Mp2 - chat(Mp2.ravel()).reshape(Mp2.shape)
    A_surv = (np.sign(Ap - a_scan[None, None, :]) * w2).sum((0, 1))
    Ainf_surv = (wpsi * np.sign(GPFe / psi - 1)).sum()
    # death (prob 1−L_eff) → newborn at the bottom: a down-move for every scanned a, so
    # A and its plateau shift by the SAME constant and the deviation scales by L_eff.
    A_m = Leff * A_surv - (1 - Leff)
    Ainf_m = Leff * Ainf_surv - (1 - Leff)
    dev = np.abs(A_m - Ainf_m)

    def onset(tol):
        bad = np.nonzero(dev >= tol)[0]
        if not len(bad):
            return float(a_scan[0])
        return float(a_scan[bad[-1] + 1]) if bad[-1] + 1 < len(a_scan) else float("inf")

    from per_atom_alpha import kesten_alpha       # T_age-split call (certified convention)
    alpha = kesten_alpha(beta * Lraw / Leff, R, rho, G, Leff, psi, wpsi)

    idx = {m: int(np.searchsorted(a_scan, m)) for m in (800, 1300)}
    return {
        "GPF_eff": float(GPFe), "A_inf": float(Ainf_m), "alpha": float(alpha),
        "kappa": float(kappa), "L_eff": float(Leff),
        "onset": {t: onset(t) for t in taus},
        "dev_at": {m: float(dev[i]) for m, i in idx.items()},
    }


def support_from_ergodic(grid: np.ndarray, mass: np.ndarray, eps: float = 1e-4,
                         wealth_weighted: bool = True) -> float:
    """The (1−eps) quantile of the atom's ergodic on `grid`, WEALTH-weighted by default:
    weights w_k ∝ mass_k · grid_k, quantile by interpolating the weighted CDF."""
    grid = np.asarray(grid, dtype=float)
    w = np.asarray(mass, dtype=float) * (grid if wealth_weighted else 1.0)
    tot = w.sum()
    if tot <= 0:
        raise ValueError("support_from_ergodic: ergodic carries no (weighted) mass")
    cdf = np.cumsum(w) / tot
    return float(np.interp(1.0 - eps, cdf, grid))


def group_top_ergodic(group: str, beta: float, nabla: float, aNrmMax: float,
                      interpretation: str = "ESC", aCount: int = 2000,
                      rho: float = 2.0):
    """The group's GIC-clipped TOP atom's ergodic aNrm marginal on [0, aNrmMax].

    Generalizes adaptive_grid_tm.college_top_ergodic (borrowed pattern, provenance:
    that function at the 2026-08-21 tree) to any education group. Returns
    (grid, mass, beta_top). HEAVY: solves one agent and builds an aCount-node TM.
    """
    os.environ.setdefault("HAFISCAL_INTERPRETATION", interpretation)
    ep = _load_ep(rho)                      # ρ-consistent model (asserts on mismatch)
    saved = sys.argv
    sys.argv = [saved[0]]
    try:
        from HARK.distributions import Uniform, DiscreteDistribution
        from EstimParameters import init_dropout, init_highschool, init_college, \
            init_ADEconomy, DiscFacCount, minBeta, gic_capped_beta  # same module as ep
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        from tm_methods import build_tm_agg_fiscal_a, find_ergodic_distribution
    finally:
        sys.argv = saved

    e = GROUP_INDEX[group.lower()]
    init = {0: init_dropout, 1: init_highschool, 2: init_college}[e]
    cap = gic_capped_beta(e, ep.theGICfactor)
    dfs = Uniform(beta - nabla, beta + nabla).discretize(DiscFacCount)
    beta_top = float(np.clip(dfs.atoms[0], minBeta, cap).max())

    ag = AggFiscalType(**init)
    ag.cycles = 0
    eco = AggregateDemandEconomy(**init_ADEconomy)
    ag.get_economy_data(eco)
    Dunemp = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnemp])])
    Dunemp_nb = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
    ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Dunemp] * ep.UBspell_normal + [Dunemp_nb]]
    ag.IncShkDstn_base = ag.IncShkDstn
    ag.DiscFac = beta_top
    ag.AgentCount = 1
    ag.tm_a_indexed = True
    ag.interpretation = interpretation
    eco.agents = [ag]
    eco.solve()

    tm = build_tm_agg_fiscal_a(ag, aCount=aCount, dist_aGrid_max=float(aNrmMax),
                               interpretation=interpretation)
    erg = np.asarray(find_ergodic_distribution(tm["TranMatrix"]))
    J = ag.MrkvArray[0].shape[0]
    grid = np.asarray(tm["dist_aGrid"], dtype=float)
    mass = erg.reshape(J, len(grid)).sum(axis=0)
    return grid, mass / mass.sum(), beta_top


def installed_calibration(rho: float, results_dir: str | None = None) -> dict:
    """{group: (beta, nabla)} from the assembled DiscFacEstim file for this ρ."""
    results_dir = results_dir or os.path.join(_HERE, "Results")
    stem = f"DiscFacEstim_CRRA_{rho:.1f}_R_1.01_ESC.txt"
    path = os.path.join(results_dir, stem)
    out = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = ast.literal_eval(line)
            name = {0: "dropout", 1: "highschool", 2: "college"}[int(d["EducationGroup"])]
            out[name] = (float(d["beta"]), float(d["nabla"]))
    if set(out) != set(GROUP_INDEX):
        raise ValueError(f"{path}: expected 3 groups, got {sorted(out)}")
    return out


def required_top(rho: float, calibration: dict | None = None, *, tau: float = 0.01,
                 eps: float = 1e-4, covering_top: float = 20000.0,
                 support_aCount: int = 2000, compute_support: bool = True,
                 ep=None) -> dict:
    """The rule: required = max over estimated atoms of min(kernel_onset(tau), support(eps)).

    With compute_support=False the (heavy) ergodic builds are skipped and support is
    reported as None (a*_i falls back to the kernel onset — an UPPER bound on the
    requirement). Returns {"required": float, "atoms": {group: {...}}}.
    """
    ep = ep or _load_ep(rho)
    calibration = calibration or installed_calibration(rho)
    atoms, required = {}, 0.0
    for group, (beta, nabla) in calibration.items():
        beta_top = beta + TOP_ATOM_OFFSET * nabla
        params = group_params(ep, group)
        k = kernel_onset(rho, beta_top, params, taus=(tau,))
        row = {"beta_top": beta_top, "onset": k["onset"][tau],
               "alpha": k["alpha"], "GPF_eff": k["GPF_eff"], "support": None}
        if compute_support:
            grid, mass, bt = group_top_ergodic(group, beta, nabla, covering_top,
                                               aCount=support_aCount, rho=rho)
            row["support"] = support_from_ergodic(grid, mass, eps)
            row["beta_top_clipped"] = bt
        a_star = row["onset"] if row["support"] is None else min(row["onset"], row["support"])
        row["a_star"] = a_star
        atoms[group] = row
        required = max(required, a_star)
    return {"required": required, "rho": rho, "tau": tau, "eps": eps, "atoms": atoms}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="onset ∧ support required dist-grid top")
    p.add_argument("--rho", type=float, default=2.0)
    p.add_argument("--tau", type=float, default=0.01)
    p.add_argument("--eps", type=float, default=1e-4)
    p.add_argument("--no-support", action="store_true",
                   help="skip the heavy ergodic builds (kernel onsets only)")
    args = p.parse_args()
    res = required_top(args.rho, tau=args.tau, eps=args.eps,
                       compute_support=not args.no_support)
    for g, r in res["atoms"].items():
        sup = "None" if r["support"] is None else f"{r['support']:8.0f}"
        print(f"{g:11s} beta_top={r['beta_top']:.6f} onset(tau={args.tau})={r['onset']:8.0f} "
              f"support(eps={args.eps})={sup} alpha={r['alpha']:.3f} a*={r['a_star']:8.0f}")
    print(f"required_top = {res['required']:.0f}   (production dist_aGrid_max = 1300)")
