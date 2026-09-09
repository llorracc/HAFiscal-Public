#!/usr/bin/env python3
"""Cross-sectional PERMANENT-INCOME inequality implied by the HAFiscal income process — closed form, no simulation.

Owner question 2026-08-28: is permanent-income inequality in the revised (uncapped) model massively different from the
original (T_age = 200) model, which was close to the SCF (cstwMPC §3.4: the SCF Gini of permanent income is roughly 0.5)?

The cross-section of p for education group g is a mixture over age a (quarters since entry at 25) of lognormals,
the same object tm_methods._pLvl_mixture_components builds for the TM's income integration:
    log p | a  ~  N( mu0_g + a*(g_g - s_g^2/2) ,  s0_g^2 + a*s_g^2 ),        E[p | a] = p0_g * exp(a*g_g)
with the ergodic age distribution  w_a ∝ LivPrb^a  (geometric; truncated at T_age when there is an age cap — the
published code killed every household at 200 quarters), g_g = (1-u_g)*log(G_g) (growth suspended in unemployment,
PermGroFac_unemp = 1), s_g^2 = sigma_psi^2 * (1 if permanent shocks continue in unemployment else (1-u_g)); permanent
shocks are mean-one (E[psi] = 1, so log psi has mean -s^2/2). Newborns: Lognormal(pLogInitMean_g, pLogInitStd_g) — the
SCF age-25 earnings by education (EstimParameters). The pooled distribution mixes the three groups with the SCF 2004
education shares.

Without a cap the LEVEL p has a Pareto tail: alpha_g solves LivPrb * exp(alpha*g_g) * E[psi^alpha] = 1;
E[p^2] = infinity when alpha < 2 (BUG-038); the mean is finite iff LivPrb * exp(g_g) < 1. Everything below is computed on a
fine log grid with the age sum carried to where the age weight is negligible (1e-9), which for the uncapped mean is
conservative (the level-weighted age sum decays as (L e^g)^a, e-folding ~650 quarters; K covers > 30 e-foldings).

Usage:  python perm_income_inequality.py [--t-age 200|none] [--perm-shocks-unemp on|off] [--label TEXT] [--header]
        [--no-drift]   (cstwMPC-style reference: no education-specific growth, G = 1)
Prints one markdown row.
"""
import argparse, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); FPC = os.path.join(HERE, "FromPandemicCode")
sys.path.insert(0, FPC)


def primitives():
    """Pull the income-process primitives from EstimParameters (the SST); argv patched for its sys.argv parsing."""
    argv0 = list(sys.argv); sys.argv = [sys.argv[0]]
    os.environ.setdefault("HAFISCAL_QUIET_BETADISTR", "1")
    # The closed form reads the PAPER's growth rates so that --growth-scale / --solve-lambda are absolute (the
    # catalog's canonical scale would otherwise be applied on import and double-scale them).
    _prev = os.environ.get("HAFISCAL_PERM_GROWTH_SCALE"); os.environ["HAFISCAL_PERM_GROWTH_SCALE"] = "1"
    try:
        import EstimParameters as E
    finally:
        sys.argv = argv0
        if _prev is None: os.environ.pop("HAFISCAL_PERM_GROWTH_SCALE", None)
        else: os.environ["HAFISCAL_PERM_GROWTH_SCALE"] = _prev
    G = [E.PermGroFac_base_d[0], E.PermGroFac_base_h[0], E.PermGroFac_base_c[0]]
    mu0 = [E.pLogInitMean_d, E.pLogInitMean_h, E.pLogInitMean_c]
    s0 = [E.pLogInitStd_d, E.pLogInitStd_h, E.pLogInitStd_c]
    u = [getattr(E, "Urate_normal_d", None), getattr(E, "Urate_normal_h", None), getattr(E, "Urate_normal_c", None)]
    if any(x is None for x in u):
        u = [0.085, 0.044, 0.027]   # SCF-calibrated normal-times unemployment rates by education (EstimParameters)
    return dict(G=[float(x) for x in G], mu0=[float(x) for x in mu0], s0=[float(x) for x in s0], u=[float(x) for x in u],
                sig2=float(E.PermShkStd[0]) ** 2, L=float(E.LivPrb_base[0]), shares=[float(x) for x in E.data_EducShares])


def pareto_alpha(L, g, s2):
    """alpha with L * exp(alpha g) * E[psi^alpha] = 1, psi lognormal mean one (E[psi^a] = exp(a(a-1) s2/2))."""
    f = lambda a: math.log(L) + a * g + a * (a - 1) * s2 / 2.0
    if f(1.0) >= 0:
        return 1.0
    lo, hi = 1.0, 50.0
    if f(hi) < 0:
        return float("inf")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return 0.5 * (lo + hi)


def group_mixture(P, g, t_age, perm_unemp, n_grid=8000, tail_prob=1e-9):
    L, sig2, u = P["L"], P["sig2"], P["u"][g]
    drift = (1.0 - u) * math.log(P["G"][g])
    s2 = sig2 * (1.0 if perm_unemp else (1.0 - u))
    K = int(t_age) if t_age is not None else max(int(math.ceil(math.log(tail_prob) / math.log(L))), 4000)
    a = np.arange(K)
    w = (1 - L) * L ** a
    w = w / w.sum()                                   # exact for the truncated geometric; renormalizes the 1e-9 tail otherwise
    mu = P["mu0"][g] + a * (drift - s2 / 2.0)
    var = P["s0"][g] ** 2 + a * s2
    sd = np.sqrt(var)
    lo = float((mu - 6 * sd).min()); hi = float((mu + 6 * sd).max())
    x = np.linspace(lo, hi, n_grid); dx = x[1] - x[0]
    dens = np.zeros_like(x)
    for k in range(K):
        if w[k] < 1e-17:
            break
        dens += w[k] * np.exp(-0.5 * ((x - mu[k]) / sd[k]) ** 2) / (sd[k] * math.sqrt(2 * math.pi))
    pw = dens * dx; pw /= pw.sum()
    return x, pw, (w, mu, var, drift, s2)


def stats_from_grid(x, pw):
    p = np.exp(x)
    mean = float(pw @ p)
    cdf = np.cumsum(pw); med = float(p[min(int(np.searchsorted(cdf, 0.5)), len(p) - 1)])
    lx = float(pw @ x); std_log = float(math.sqrt(pw @ (x - lx) ** 2))
    inc = pw * p; inc_cum = np.cumsum(inc) / inc.sum()
    lorenz = lambda q: float(inc_cum[min(int(np.searchsorted(cdf, q)), len(p) - 1)])
    gini = 1.0 - 2.0 * float(np.sum(inc_cum * pw)) + float(np.sum(inc * pw)) / float(inc.sum())
    return dict(mean=mean, median=med, std_log=std_log, gini=gini, b50=lorenz(0.5), top10=1 - lorenz(0.9),
                top1=1 - lorenz(0.99))


def scaled_growth(P, lam):
    """The growth factors under the uniform downscaling lambda (plan 20260829-0845h): G_e(lam) = 1 + lam * (G_e - 1),
    i.e. PermGroFac_e = 1 + lam * g_e / 4 with the paper's annual g_e unchanged."""
    Q = dict(P); Q["G"] = [1.0 + lam * (float(G) - 1.0) for G in P["G"]]
    return Q


def pooled_stats(P, t_age=None, perm_unemp=True):
    """Per-group and pooled cross-section statistics of permanent income for the primitives P (closed form)."""
    grids = [group_mixture(P, g, t_age, perm_unemp) for g in range(3)]
    per = [stats_from_grid(x, pw) for x, pw, _ in grids]
    lo = min(float(x.min()) for x, _, _ in grids); hi = max(float(x.max()) for x, _, _ in grids)
    X = np.linspace(lo, hi, 16000); dens = np.zeros_like(X)
    for g, (x, pw, _) in enumerate(grids):
        dens += P["shares"][g] * np.interp(X, x, pw / (x[1] - x[0]), left=0.0, right=0.0)
    PW = dens * (X[1] - X[0]); PW /= PW.sum()
    pooled = stats_from_grid(X, PW)
    alphas = [pareto_alpha(P["L"], grids[g][2][3], grids[g][2][4]) for g in range(3)]
    means = [float(pw @ np.exp(x)) for x, pw, _ in grids]
    old = den = 0.0
    for g, (x, pw, (w, mu, var, drift, s2)) in enumerate(grids):
        Ep_a = w * np.exp(mu + var / 2)
        den += P["shares"][g] * float(Ep_a.sum()); old += P["shares"][g] * float(Ep_a[200:].sum())   # > 50 y since entry at 25 = older than 75
    return dict(per=per, pooled=pooled, alphas=alphas, means=means, old75=old / den)


def solve_lambda(P, target, t_age=None, perm_unemp=True, tol=1e-4):
    """lambda* with pooled Gini(lambda*) = target; the Gini is monotone increasing in lambda (bisection on [0, 1])."""
    lo, hi = 0.0, 1.0
    g_lo = pooled_stats(scaled_growth(P, lo), t_age, perm_unemp)["pooled"]["gini"]
    g_hi = pooled_stats(scaled_growth(P, hi), t_age, perm_unemp)["pooled"]["gini"]
    if not (g_lo <= target <= g_hi):
        raise SystemExit(f"target Gini {target} outside [Gini(0)={g_lo:.4f}, Gini(1)={g_hi:.4f}]")
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if pooled_stats(scaled_growth(P, mid), t_age, perm_unemp)["pooled"]["gini"] < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def from_model(parametrization="Baseline", n_grid=6000):
    """The MODEL's own ergodic permanent-income cross-section (the gate for the earnings-phase state): the exact
    per-(age, state) Markov mixture `tm_methods._pLvl_markov_mixture_components` on the economy's agents (built and
    solved through welfare6_scenario.build_and_solve — policy-store hits, so ~1-2 min), one agent per education
    group, pooled with the SCF education shares. Reads whatever chain / per-state growth the environment wires
    (HAFISCAL_WORLD, HAFISCAL_T_AGE, HAFISCAL_EARNINGS_PHASE_HAZARD, ...), so it measures the implemented model, not
    the closed form. Returns (per-group stats, pooled stats, E[p] by group)."""
    os.environ.setdefault("HAFISCAL_POLICY_STORE_REQUIRE", "0"); os.environ.setdefault("HAFISCAL_QUIET_BETADISTR", "1")
    argv0 = list(sys.argv); sys.argv = [sys.argv[0]]
    try:
        import tm_methods as tm
        import welfare6_scenario as ws
        from Parameters import return_parameters
        shares = list(return_parameters(Parametrization=parametrization, OutputFor="_Main.py")[12])
        ctx = ws.build_and_solve(parametrization)
    finally:
        sys.argv = argv0
    agents = ctx["AggEco"].agents
    grids = []
    for e in range(3):
        agent = next(ag for ag in agents if int(getattr(ag, "EducType", -1)) == e)
        w, mu, sd = tm._pLvl_markov_mixture_components(agent)
        lo = float((mu - 6 * sd).min()); hi = float((mu + 6 * sd).max())
        x = np.linspace(lo, hi, n_grid); dx = x[1] - x[0]
        dens = np.zeros_like(x)
        for k in range(len(w)):
            dens += w[k] * np.exp(-0.5 * ((x - mu[k]) / max(sd[k], 1e-12)) ** 2) / (max(sd[k], 1e-12) * math.sqrt(2 * math.pi))
        pw = dens * dx; pw /= pw.sum()
        grids.append((x, pw))
    per = [stats_from_grid(x, pw) for x, pw in grids]
    lo = min(float(x.min()) for x, _ in grids); hi = max(float(x.max()) for x, _ in grids)
    X = np.linspace(lo, hi, 16000); dens = np.zeros_like(X)
    for g, (x, pw) in enumerate(grids):
        dens += shares[g] * np.interp(X, x, pw / (x[1] - x[0]), left=0.0, right=0.0)
    PW = dens * (X[1] - X[0]); PW /= PW.sum()
    return per, stats_from_grid(X, PW), [st["mean"] for st in per]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t-age", default="none"); ap.add_argument("--perm-shocks-unemp", default="off")
    ap.add_argument("--label", default=None); ap.add_argument("--header", action="store_true")
    ap.add_argument("--no-drift", action="store_true", help="cstwMPC-style reference: G = 1 for every group")
    ap.add_argument("--from-model", action="store_true",
                    help="measure the IMPLEMENTED model's ergodic p cross-section (the earnings-phase gate) instead of the closed form")
    ap.add_argument("--parametrization", default="Baseline")
    ap.add_argument("--growth-scale", type=float, default=1.0,
                    help="uniform downscaling lambda of the three education growth rates: G_e = 1 + lambda*(G_e-1)")
    ap.add_argument("--solve-lambda", action="store_true",
                    help="solve lambda* with pooled Gini = --target-gini (closed form) and print the row at lambda* and at its 2-decimal rounding")
    ap.add_argument("--target-gini", type=float, default=0.50)
    a = ap.parse_args()
    if a.from_model:
        per, pooled, means = from_model(a.parametrization)
        label = a.label or f"MODEL ({a.parametrization}; env: T_AGE={os.environ.get('HAFISCAL_T_AGE', 'unset')}, EARNINGS_PHASE_HAZARD={os.environ.get('HAFISCAL_EARNINGS_PHASE_HAZARD', 'unset')})"
        if a.header:
            print("| configuration | Gini D / HS / C | pooled Gini | pooled std log p | bottom 50 % share | top 10 % | top 1 % | mean/median | mean p D / HS / C ($k/q) | pooled mean p |")
            print("|---|---|---|---|---|---|---|---|---|---|")
        print(f"| {label} | {per[0]['gini']:.2f} / {per[1]['gini']:.2f} / {per[2]['gini']:.2f} | {pooled['gini']:.2f} | "
              f"{pooled['std_log']:.2f} | {100*pooled['b50']:.1f} % | {100*pooled['top10']:.1f} % | {100*pooled['top1']:.1f} % | "
              f"{pooled['mean']/pooled['median']:.2f} | {means[0]:.1f} / {means[1]:.1f} / {means[2]:.1f} | {pooled['mean']:.1f} |")
        return
    t_age = None if str(a.t_age).lower() in ("none", "", "0") else int(a.t_age)
    perm_unemp = str(a.perm_shocks_unemp).lower() in ("on", "1", "true")
    P = primitives()
    if a.no_drift:
        P["G"] = [1.0, 1.0, 1.0]
    if a.solve_lambda:
        lam = solve_lambda(P, a.target_gini, t_age, perm_unemp)
        fa = lambda v: "inf" if v == float("inf") else f"{v:.2f}"
        print(f"lambda* = {lam:.4f}  (target pooled Gini {a.target_gini:.3f}; T_age={t_age}, perm shocks in unemployment {'on' if perm_unemp else 'off'})")
        print("| lambda | growth D / HS / C (%/yr) | Gini D / HS / C | pooled Gini | std log p | top 10 % | top 1 % | alpha D / HS / C | mean p D / HS / C ($k/q) | income from > 75 y |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for lab, lv in (("lambda*", lam), ("rounded", round(lam, 2)), ("1 (paper)", 1.0), ("0.5", 0.5)):
            Q = scaled_growth(P, lv); r = pooled_stats(Q, t_age, perm_unemp); po = r["pooled"]
            gr = " / ".join(f"{400*(G-1):.2f}" for G in Q["G"])
            print(f"| {lab} = {lv:.4f} | {gr} | {r['per'][0]['gini']:.3f} / {r['per'][1]['gini']:.3f} / {r['per'][2]['gini']:.3f} | "
                  f"**{po['gini']:.4f}** | {po['std_log']:.3f} | {100*po['top10']:.1f} % | {100*po['top1']:.1f} % | "
                  f"{fa(r['alphas'][0])} / {fa(r['alphas'][1])} / {fa(r['alphas'][2])} | "
                  f"{r['means'][0]:.1f} / {r['means'][1]:.1f} / {r['means'][2]:.1f} | {100*r['old75']:.0f} % |")
        return
    if a.growth_scale != 1.0:
        P = scaled_growth(P, a.growth_scale)
    label = a.label or f"T_age={t_age}, perm shocks in unemployment {'on' if perm_unemp else 'off'}{' (no drift)' if a.no_drift else ''}"
    grids = [group_mixture(P, g, t_age, perm_unemp) for g in range(3)]
    per = [stats_from_grid(x, pw) for x, pw, _ in grids]
    lo = min(float(x.min()) for x, _, _ in grids); hi = max(float(x.max()) for x, _, _ in grids)
    X = np.linspace(lo, hi, 16000); dens = np.zeros_like(X)
    for g, (x, pw, _) in enumerate(grids):
        dens += P["shares"][g] * np.interp(X, x, pw / (x[1] - x[0]), left=0.0, right=0.0)
    PW = dens * (X[1] - X[0]); PW /= PW.sum()
    pooled = stats_from_grid(X, PW)
    num = den = old = 0.0
    for g, (x, pw, (w, mu, var, drift, s2)) in enumerate(grids):
        Ep_a = w * np.exp(mu + var / 2)           # = w_a * p0 * exp(a*drift)
        num += P["shares"][g] * float((np.arange(len(w)) * Ep_a).sum()); den += P["shares"][g] * float(Ep_a.sum())
        old += P["shares"][g] * float(Ep_a[200:].sum())
    alphas = [pareto_alpha(P["L"], grids[g][2][3], grids[g][2][4]) for g in range(3)]
    means = [float(pw @ np.exp(x)) for x, pw, _ in grids]
    if a.header:
        print("| configuration | Gini D / HS / C | pooled Gini | pooled std log p | bottom 50 % share | top 10 % | top 1 % | "
              "mean/median | income-weighted mean age (years since entry) | income share from ages > 50 y | "
              "Pareto alpha D / HS / C | mean p D / HS / C ($k/q) | pooled mean p |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    fa = lambda v: "inf" if v == float("inf") else f"{v:.2f}"
    print(f"| {label} | {per[0]['gini']:.2f} / {per[1]['gini']:.2f} / {per[2]['gini']:.2f} | {pooled['gini']:.2f} | "
          f"{pooled['std_log']:.2f} | {100*pooled['b50']:.1f} % | {100*pooled['top10']:.1f} % | {100*pooled['top1']:.1f} % | "
          f"{pooled['mean']/pooled['median']:.2f} | {num/den/4:.0f} | {100*old/den:.1f} % | "
          f"{fa(alphas[0])} / {fa(alphas[1])} / {fa(alphas[2])} | {means[0]:.1f} / {means[1]:.1f} / {means[2]:.1f} | "
          f"{pooled['mean']:.1f} |")


if __name__ == "__main__":
    main()
