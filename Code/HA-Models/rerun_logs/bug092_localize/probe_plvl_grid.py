"""BUG-092 probe: is the TM's analytical pLvl cross-section — the object the stimulus check's
50-bucket delivery integrates over — resolved differently in the uncapped world than under a cap?

`compute_pLvl_distribution` lays a 200-point grid in log p over [min(mu_k - 4 s_k), max(mu_k + 4 s_k)]
across ALL age cohorts k. Uncapped, the age chain runs to ~3300 quarters (weights ~1e-9 but they
still set the bounds) with s_k ~ sqrt(k)*sigma_psi and mu_k ~ k*log g, so the grid can be an order
of magnitude coarser over the bulk — and over the check's phase-out band — than under T_age=200.
Measures, per Reduced_Run agent and for T_age in (None, 200): chain length, grid spacing, points in
the phase-out band, and the check-delivery moments at n_points = 200 (production) vs 20000 (reference).
"""
import os, sys
sys.argv = ['probe']
os.environ.setdefault('HAFISCAL_FTI_REPO', '/home/shared/github/llorracc/fast-time-iteration')
os.environ.setdefault('HAFISCAL_TM_A_INDEXED', '1')
os.environ['HAFISCAL_POLICY_STORE_REQUIRE'] = '0'
os.environ.setdefault('HAFISCAL_POLICY_STORE_DIR', os.path.expanduser('~/.cache/hafiscal/policy_store_bug092'))
FPC = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode'
sys.path.insert(0, FPC); sys.path.insert(0, os.path.dirname(FPC))
import numpy as np
import welfare6_scenario as ws
import tm_methods as tm

ctx = ws.build_and_solve('Reduced_Run')
eco = ctx['AggEco']
print(f"\n=== {len(eco.agents)} agents; LivPrb={eco.agents[0].LivPrb[0][0]:.6f}; "
      f"check {eco.agents[0].CheckStimLvl:.4f}, phase-out [{eco.agents[0].CheckStimLvl_PLvl_Cutoff_start}, "
      f"{eco.agents[0].CheckStimLvl_PLvl_Cutoff_end}]")


def moments(agent, n_points):
    grid, w = tm.compute_pLvl_distribution(agent, n_points=n_points, unemployment_rate=None)
    lo, hi = agent.CheckStimLvl_PLvl_Cutoff_start, agent.CheckStimLvl_PLvl_Cutoff_end
    phase = np.ones_like(grid); band = (grid >= lo) & (grid <= hi); phase[band] = 1.0 - (grid[band] - lo) / (hi - lo); phase[grid > hi] = 0.0
    lp = np.log(grid); dp = lp[1] - lp[0]
    return dict(dp=dp, n_band=int(band.sum()), E_p=float(w @ grid), var_log=float(w @ lp**2 - (w @ lp)**2),
                E_check_level=float(w @ (agent.CheckStimLvl * phase)), E_check_nrm=float(w @ (agent.CheckStimLvl * phase / grid)),
                share_band=float(w[band].sum()), share_above=float(w[grid > hi].sum()), lo=float(lp[0]), hi=float(lp[-1]))


orig = tm.compute_pLvl_distribution
for i, a in enumerate(eco.agents):
    for T in (None, 200):
        a.T_age = T
        age_prbs, mu_k, s_k = tm._pLvl_mixture_components(a, None)
        m200, mfine = moments(a, 200), moments(a, 20000)
        print(f"\n--- agent {i} (DiscFac {a.DiscFac:.4f}) T_age={T}: chain {len(age_prbs)}, sigma_k max {s_k.max():.3f}, "
              f"mu_k range [{mu_k.min():.2f}, {mu_k.max():.2f}] -> log-p grid [{m200['lo']:.2f}, {m200['hi']:.2f}], dp(200)={m200['dp']:.4f}")
        for name, m in (('n=200', m200), ('n=20000', mfine)):
            print(f"    {name:8s} band pts={m['n_band']:4d}  E[p]={m['E_p']:.4f}  var log p={m['var_log']:.4f}  "
                  f"E[check level]={m['E_check_level']:.5f}  E[check/p]={m['E_check_nrm']:.5f}  "
                  f"mass band={m['share_band']:.4f} above={m['share_above']:.4f}")
        r = lambda k: 100 * (m200[k] - mfine[k]) / mfine[k]
        print(f"    200 vs 20000: E[p] {r('E_p'):+.2f}%  var log p {r('var_log'):+.2f}%  E[check level] {r('E_check_level'):+.2f}%  E[check/p] {r('E_check_nrm'):+.2f}%")
        # the production check buckets (50, 200-point grid) vs the same buckets on the fine grid
        b200 = tm._compute_check_buckets(a, n_buckets=50)
        tm.compute_pLvl_distribution = lambda ag, n_points=200, unemployment_rate=None: orig(ag, n_points=20000, unemployment_rate=unemployment_rate)
        try:
            bfine = tm._compute_check_buckets(a, n_buckets=50)
        finally:
            tm.compute_pLvl_distribution = orig
        def agg(bs, key, j=0):
            return sum(b['weight'] * (b[key][j] if np.ndim(b[key]) else b[key]) for b in bs)
        for key in [k for k in ('E_check_level_b', 'E_pLvl_b', 'mNrm_shift') if k in b200[0]]:
            v200, vf = agg(b200, key), agg(bfine, key)
            print(f"    buckets {key:16s}: prod={v200:.6f} fine={vf:.6f} diff={100*(v200-vf)/vf:+.2f}%")
        # The MC side's cross-section: the welfare battery / MC engine seed pLvl with the stratified
        # inverse-CDF sampler of the SAME analytical mixture at the agent's finite N (then simulate).
        # Compare the delivered normalized check E[check*phase/p] and var log p, sampler vs analytical.
        lo, hi = a.CheckStimLvl_PLvl_Cutoff_start, a.CheckStimLvl_PLvl_Cutoff_end
        for N in (int(a.AgentCount), 100000):
            p = tm.sample_pLvl_steady_state(a, N, np.random.default_rng(0))
            phase = np.ones_like(p); band = (p >= lo) & (p <= hi); phase[band] = 1.0 - (p[band] - lo) / (hi - lo); phase[p > hi] = 0.0
            E_chk = float(np.mean(a.CheckStimLvl * phase / p)); vlp = float(np.var(np.log(p))); Ep = float(np.mean(p))
            print(f"    sampler N={N:6d}: E[check/p]={E_chk:.5f} ({100*(E_chk-mfine['E_check_nrm'])/mfine['E_check_nrm']:+.2f}% vs analytical)  "
                  f"var log p={vlp:.4f} ({100*(vlp-mfine['var_log'])/mfine['var_log']:+.2f}%)  E[p]={Ep:.4f} ({100*(Ep-mfine['E_p'])/mfine['E_p']:+.2f}%)  "
                  f"min p={p.min():.3f} max p={p.max():.1f}")
    a.T_age = None
print("\nPROBE DONE")
