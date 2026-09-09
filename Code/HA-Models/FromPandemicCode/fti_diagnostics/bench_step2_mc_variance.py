"""Step-2 MC estimator variance vs N + wealth-tail decomposition (Phase B).

Phase-B instrument for the simulation-speedup assessment
(`plans/20260617-1153h_step2-simulation-speedup-assessment.md`). Premise (from the
Phase-A finding): the LEVEL-wealth Lorenz target keeps MC as the default Step-2
estimator, so the question is how small N can be at fixed moment accuracy.

Method: build the MC economy once, solve+simulate ONE warm eval at production
N=50000 for a chosen cohort at a fixed (beta, nabla), then **bootstrap-subsample**
the pooled cohort cross-section at a ladder of N. Because the Step-2 moments
(`medianLWPI`, level `LorenzPts`, `distance`) are equal-weight functionals of the
stationary cross-section over INDEPENDENT agents, uniform subsampling reproduces
the dominant finite-N sampling variance the objective actually sees (it omits the
second-order burn-in / per-type-count-granularity effects of an end-to-end small-N
re-sim — noted as a caveat). It also tags each agent by its beta-atom so we can see
which atoms drive the wealth-tail (Lorenz p80) variance.

Default OFF / read-only. Writes nothing to tracked result files.

Run (from FromPandemicCode/):
  PYTHONPATH=. HAFISCAL_SKIP_ESTIMATION=1 HAFISCAL_SERIAL=1 \
      HAFISCAL_INTERPRETATION=ESC BENCH_EDTYPE=1 \
      <python> fti_diagnostics/bench_step2_mc_variance.py
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

os.environ.setdefault("HAFISCAL_SKIP_ESTIMATION", "1")
os.environ.setdefault("HAFISCAL_SERIAL", "1")
os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")

_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_FROMPANDEMIC, os.path.normpath(os.path.join(_FROMPANDEMIC, ".."))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from HARK.utilities import get_lorenz_shares, get_percentiles  # noqa: E402

LORENZ_PCTS = [0.2, 0.4, 0.6, 0.8]


def _moments(aLvl, aNrm, w_l=None, w_n=None):
    """Replicate the Step-2 cohort moments on a (sub)sample.

    Optional importance weights w_l / w_n make the weighted median/Lorenz unbiased
    under non-uniform (stratified / oversampled) sampling.
    """
    if w_l is None:
        w_l = np.ones(len(aLvl)) / len(aLvl)
    if w_n is None:
        w_n = np.ones(len(aNrm)) / len(aNrm)
    median = 100.0 * float(get_percentiles(aNrm, weights=w_n, percentiles=[0.5])[0])
    lorenz = 100.0 * np.array(get_lorenz_shares(aLvl, weights=w_l, percentiles=LORENZ_PCTS))
    return median, lorenz


def main():
    edtype = int(os.environ.get("BENCH_EDTYPE", "1"))
    educ_names = ["Dropout", "Highschool", "College"]
    probe = {0: (0.6810, 0.4248), 1: (0.9075, 0.1109), 2: (0.9872, 0.0336)}[edtype]

    print("Importing MC economy (EstimAggFiscalMAIN)...", flush=True)
    t0 = time.time()
    import EstimAggFiscalMAIN as E
    from EstimParameters import DiscFacCount, data_LorenzPts, data_medianLWPI
    print(f"  MC build: {time.time() - t0:.1f}s", flush=True)

    GICx = float(np.log(E.theGICfactor / (1 - E.theGICfactor)))
    beta, nabla = probe
    print(f"\nSimulating ONE warm eval at production N: edType={edtype} "
          f"({educ_names[edtype]}) beta={beta} nabla={nabla} ...", flush=True)
    t0 = time.time()
    E.betas_obj_func_educ(beta, nabla, GICx, educ_type=edtype)
    print(f"  eval (solve+sim): {time.time() - t0:.1f}s", flush=True)

    cohort = E.AggDemandEconomy.agents[edtype * DiscFacCount:(edtype + 1) * DiscFacCount]
    # Per-agent arrays, tagged by beta-atom index (0=lowest beta .. 6=highest).
    aLvl_parts, aNrm_parts, atom_parts, beta_by_atom = [], [], [], []
    for k, ag in enumerate(cohort):
        al = E._aLvl_for(ag)
        an = E._aNrm_for(ag)
        aLvl_parts.append(al)
        aNrm_parts.append(an)
        atom_parts.append(np.full(len(al), k, dtype=int))
        beta_by_atom.append(float(ag.DiscFac))
    aLvl = np.concatenate(aLvl_parts)
    aNrm = np.concatenate(aNrm_parts)
    atom = np.concatenate(atom_parts)
    N_full = len(aLvl)
    print(f"  pooled cohort cross-section: {N_full} agents across {DiscFacCount} beta-atoms "
          f"(betas={[round(b,4) for b in beta_by_atom]})", flush=True)

    full_median, full_lorenz = _moments(aLvl, aNrm)
    data_med = data_medianLWPI[edtype]
    data_lor = data_LorenzPts[edtype]
    print(f"\n  N=50000 reference moments: median={full_median:.2f} "
          f"Lorenz(level)=[{', '.join(f'{x:.2f}' for x in full_lorenz)}]", flush=True)
    print(f"  data target:               median={data_med:.2f} "
          f"Lorenz=[{', '.join(f'{x:.2f}' for x in data_lor)}]", flush=True)

    # --- Wealth-tail (top-20% level wealth) composition by beta-atom ---
    print("\n--- Who holds the wealth tail (top 20% of level wealth)? ---", flush=True)
    thr = np.quantile(aLvl, 0.80)
    top = aLvl >= thr
    print(f"  top-20% level-wealth share of total: "
          f"{100*aLvl[top].sum()/aLvl.sum():.1f}%", flush=True)
    for k in range(DiscFacCount):
        in_atom = atom == k
        frac_pop = 100.0 * in_atom.mean()
        frac_of_top = 100.0 * (top & in_atom).sum() / max(top.sum(), 1)
        wealth_share = 100.0 * aLvl[in_atom].sum() / aLvl.sum()
        print(f"    atom {k} (beta={beta_by_atom[k]:.4f}): pop {frac_pop:5.1f}%  "
              f"| {frac_of_top:5.1f}% of the top-20%  | holds {wealth_share:5.1f}% of total wealth",
              flush=True)

    # --- Bootstrap subsampling: moment std vs N ---
    print("\n--- Finite-N sampling variance (bootstrap subsample, K=200 resamples) ---",
          flush=True)
    rng = np.random.default_rng(12345)
    K = 200
    Ns = [250, 500, 1000, 2000, 5000, 10000, 25000]
    print(f"  {'N':>7} | {'median (mean±sd)':>22} | "
          f"{'p80 Lorenz (mean±sd)':>24} | {'distance (mean±sd)':>22}", flush=True)
    for N in Ns:
        meds, p80s, dists = [], [], []
        for _ in range(K):
            idx = rng.integers(0, N_full, size=N)
            m, lz = _moments(aLvl[idx], aNrm[idx])
            ss = (m - data_med) ** 2 + np.sum((lz - data_lor) ** 2)
            meds.append(m)
            p80s.append(lz[3])
            dists.append(np.sqrt(ss))
        print(f"  {N:>7} | {np.mean(meds):8.2f} ± {np.std(meds):5.2f} ({100*np.std(meds)/np.mean(meds):4.1f}%) | "
              f"{np.mean(p80s):8.2f} ± {np.std(p80s):5.2f} ({100*np.std(p80s)/np.mean(p80s):4.1f}%) | "
              f"{np.mean(dists):8.3f} ± {np.std(dists):5.3f}", flush=True)
    print(f"\n  NM resolution reference: xtol=1e-2 on (beta,nabla); the objective `distance` "
          f"sd above must be << the distance CHANGE over an xtol step to avoid NM stalling on noise.",
          flush=True)

    # --- Lever assessment: stratified oversampling of the wealth-tail atom(s) ---
    # The tail atom (highest beta) holds ~all the wealth but only 1/DiscFacCount of
    # the population. At a fixed total budget N, give the tail atom a larger share
    # of draws and REWEIGHT (w_k = pop_k / sampled_k) so the weighted moments stay
    # unbiased. Compare the p80 Lorenz / distance sd to uniform sampling.
    print("\n--- Lever: stratified IS toward the wealth-tail atom (fixed total N, reweighted) ---",
          flush=True)
    pop_frac = np.array([(atom == k).mean() for k in range(DiscFacCount)])
    tail_atoms = [DiscFacCount - 1]  # the dominant high-beta atom (extend if needed)
    by_atom = {k: np.where(atom == k)[0] for k in range(DiscFacCount)}
    TAIL_BUDGET = 0.50  # give the tail atom 50% of the draws (vs its ~14% population)
    for N in [1000, 2000, 5000]:
        # allocation: TAIL_BUDGET to tail atoms (split), remainder spread by population
        alloc = np.zeros(DiscFacCount)
        for k in tail_atoms:
            alloc[k] = TAIL_BUDGET / len(tail_atoms)
        rest = [k for k in range(DiscFacCount) if k not in tail_atoms]
        rest_pop = pop_frac[rest] / pop_frac[rest].sum()
        for k, rp in zip(rest, rest_pop):
            alloc[k] = (1.0 - TAIL_BUDGET) * rp
        n_k = np.maximum((alloc * N).astype(int), 1)

        u_p80, u_dist, s_p80, s_dist = [], [], [], []
        for _ in range(K):
            # uniform baseline at this N
            iu = rng.integers(0, N_full, size=int(n_k.sum()))
            mu, lu = _moments(aLvl[iu], aNrm[iu])
            u_p80.append(lu[3])
            u_dist.append(np.sqrt((mu - data_med) ** 2 + np.sum((lu - data_lor) ** 2)))
            # stratified-IS: draw n_k from each atom, reweight by pop_k / n_k
            idx_parts, w_parts = [], []
            for k in range(DiscFacCount):
                pick = by_atom[k][rng.integers(0, len(by_atom[k]), size=n_k[k])]
                idx_parts.append(pick)
                w_parts.append(np.full(n_k[k], pop_frac[k] / n_k[k]))
            ii = np.concatenate(idx_parts)
            ww = np.concatenate(w_parts)
            ww = ww / ww.sum()
            ms, ls = _moments(aLvl[ii], aNrm[ii], w_l=ww, w_n=ww)
            s_p80.append(ls[3])
            s_dist.append(np.sqrt((ms - data_med) ** 2 + np.sum((ls - data_lor) ** 2)))
        print(f"  N={N:>5}: p80 sd  uniform {np.std(u_p80):5.2f}  ->  stratified {np.std(s_p80):5.2f} "
              f"({np.std(u_p80)/max(np.std(s_p80),1e-9):.1f}x)   | "
              f"distance sd  uniform {np.std(u_dist):5.3f}  ->  stratified {np.std(s_dist):5.3f} "
              f"({np.std(u_dist)/max(np.std(s_dist),1e-9):.1f}x)", flush=True)

    print("\n  CAVEAT: subsampling captures cross-sectional sampling variance (the dominant term); "
          "it omits burn-in / per-type count-granularity effects of an end-to-end small-N re-sim.",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
