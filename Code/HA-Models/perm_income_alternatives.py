"""Age-free alternatives to the age cap: permanent-income inequality by Monte Carlo on the closed-form process.
Each household: age a (quarters survived) ~ Geometric(L); growth quarters n = min(a, N_end) where N_end ~ Geometric(h)
is the (age-free, Markov) end of the growth phase (h = 0: the current uncapped model; h = 1: no drift);
log p = mu0 + n*(1-u)*log G - a*s^2/2 + sqrt(s0^2 + a*s^2) * Z   (mean-one permanent shocks continue for life).
Capped original: a resampled to < T_age.  Pooled with SCF education shares."""
import sys, os, math, numpy as np
sys.path.insert(0, "FromPandemicCode"); sys.argv = sys.argv[:1]; os.environ.setdefault("HAFISCAL_QUIET_BETADISTR", "1")
import EstimParameters as E
G = [E.PermGroFac_base_d[0], E.PermGroFac_base_h[0], E.PermGroFac_base_c[0]]
mu0 = [E.pLogInitMean_d, E.pLogInitMean_h, E.pLogInitMean_c]; s0 = [E.pLogInitStd_d, E.pLogInitStd_h, E.pLogInitStd_c]
u = [0.085, 0.044, 0.027]; sig2 = float(E.PermShkStd[0])**2; L = float(E.LivPrb_base[0]); shares = list(E.data_EducShares)
rng = np.random.default_rng(0); N = 3_000_000

def stats(p, a):
    p = np.sort(p); n = len(p); cum = np.cumsum(p); tot = cum[-1]
    gini = 1 - 2 * cum.sum() / (tot * n) + 1.0 / n
    lor = lambda q: cum[int(q * n) - 1] / tot
    return dict(gini=gini, top10=1 - lor(0.9), top1=1 - lor(0.99), b50=lor(0.5), mean=p.mean(), med=np.median(p),
                stdlog=np.std(np.log(p)))

def run(label, h, t_age=None, drift=True, perm_unemp=False):
    P = []; A = []; Eg = []
    for g in range(3):
        n_g = int(N * shares[g])
        a = np.floor(np.log(rng.random(n_g)) / np.log(L)).astype(int)
        if t_age is not None:
            while True:
                bad = a >= t_age
                if not bad.any(): break
                a[bad] = np.floor(np.log(rng.random(bad.sum())) / np.log(L)).astype(int)
        if h >= 1: n = np.zeros_like(a)
        elif h <= 0: n = a.copy()
        else: n = np.minimum(a, np.floor(np.log(rng.random(n_g)) / np.log(1 - h)).astype(int))
        gq = (1 - u[g]) * math.log(G[g]) if drift else 0.0
        s2 = sig2 * (1.0 if perm_unemp else 1 - u[g])
        m = mu0[g] + n * gq - a * s2 / 2; v = s0[g]**2 + a * s2
        lp = m + np.sqrt(v) * rng.standard_normal(n_g)
        P.append(np.exp(lp)); A.append(a); Eg.append(np.exp(lp).mean())
    p = np.concatenate(P); a = np.concatenate(A); st = stats(p, a)
    old = p[a >= 200].sum() / p.sum(); wage = (a * p).sum() / p.sum() / 4
    alpha = []
    for g in range(3):
        gq = (1 - u[g]) * math.log(G[g]) if drift else 0.0; s2 = sig2 * (1 - u[g])
        f = lambda x: math.log(L * (1 - min(h, 0.999999))) + x * gq + x * (x - 1) * s2 / 2
        if t_age is not None or h >= 1 or not drift: alpha.append("—"); continue
        lo, hi = 1.0, 60.0
        if f(1.0) >= 0: alpha.append("<1"); continue
        for _ in range(100):
            mid = (lo + hi) / 2; lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
        alpha.append(f"{mid:.2f}")
    print(f"| {label} | {st['gini']:.2f} | {st['stdlog']:.2f} | {100*st['top10']:.1f} % | {100*st['top1']:.1f} % | "
          f"{st['mean']/st['med']:.2f} | {wage:.0f} | {100*old:.1f} % | {Eg[0]:.1f} / {Eg[1]:.1f} / {Eg[2]:.1f} | {st['mean']:.1f} | "
          f"{' / '.join(alpha)} |", flush=True)

print("| process | pooled Gini | std log p | top 10 % | top 1 % | mean/median | income-weighted mean age (y past entry) | income from > 50 y past entry | E[p] D / HS / C | pooled E[p] | Pareto α D / HS / C |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
run("original: capped at 200 quarters (validation of the sampler)", 0.0, t_age=200)
run("current: uncapped, growth for life (h = 0)", 0.0)
run("A. no idiosyncratic drift (G_e = 1; cstwMPC / StickyE structure)", 1.0, drift=False)
run("B. growth phase ends with hazard h = 1/160 (expected 40-year career; Markov 'matured' state)", 1/160)
run("B'. h = 1/120 (30-year expected growth phase)", 1/120)
run("B''. h = 1/200 (50-year expected growth phase)", 1/200)
run("B‴. h = 1/80 (20-year expected growth phase)", 1/80)
