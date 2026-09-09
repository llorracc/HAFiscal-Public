"""Weighted-tail permanent-income sampler for the MC cross-section (BUG-092, owner 2026-08-25).

Problem. In the uncapped world mean permanent income is carried by a thin tail of very old,
very rich dynasties (E[p] = 4.7x entry; p-weighted mean age ~180 years). A panel of N
equal-weight households drawn from the ergodic pLvl distribution cannot represent a mean that
lives in the top 1e-4 of the distribution: at Baseline N its level sits ~11 % below the TM's
and the shortfall shrinks only as N^-0.2. So the welfare battery measures the spending
program's (TM) equilibrium on a population poorer than the one that equilibrium was computed
for — the residual of the sharing gap once BUG-093 is fixed.

Idea. Keep N households, but stop representing the tail with equal-weight draws:
  * the BULK — the bottom (1-q) of the population — is N-K strata of equal population mass,
    each represented by its CONDITIONAL-MEAN p (not the quantile point), so its mean is exact;
  * the TAIL — the top q of the population — is K strata of equal p-MASS, each represented by
    ONE household carrying the stratum's conditional-mean p (huge) and the stratum's population
    weight (tiny). Each tail household carries 1/K of the tail's income, so a single death (the
    slot keeps its weight; the newborn restarts at p=1) moves the aggregate by at most that.
The weighted mean sum_i w_i p_i / N equals the analytical E[p] EXACTLY at t=0 by construction
(law of total expectation); in expectation the weighted E[p] then follows the model's own law
E[p'] = (1-delta) G E[p] + delta. Behaviour is not touched: p is independent of the normalized
state at the seed (the same assumption the current seed makes — the model is homogeneous of
degree one in p), so a tail household is an ordinary household with a huge p that draws its
(j, aNrm) from the same ergodic and uses the same normalized rules; the one level-denominated
object (the check's phase-out) treats it correctly as a non-recipient.

All partial expectations are closed-form on the lognormal-mixture components the analytic
sampler already uses (``tm_methods._pLvl_components_select``): with X = log p,
    F(x) = sum_k w_k Phi((x - mu_k)/sig_k),
    M(x) = E[p 1{X < x}] = sum_k w_k exp(mu_k + sig_k^2/2) Phi((x - mu_k - sig_k^2)/sig_k),
so the top stratum's representative captures the true tail mean beyond any grid.

Flags (docs/ENV_FLAGS.md): HAFISCAL_MC_WEIGHTED_TAIL = K (0/unset = off),
HAFISCAL_MC_WEIGHTED_TAIL_POP = q (default 0.01). Consumed by
``tm_methods.initialize_mc_from_tm_ergodic`` (sets ``agent.agent_weights``); the weights
flow through ``AggregateDemandEconomy.run_experiment`` / ``mill_rule`` aggregation and the
welfare battery's household sums (``run_welfare6_parallel.welfare6_mc``).
"""
from __future__ import annotations

import os

import numpy as np
from scipy.stats import norm as _norm

ENV_K = "HAFISCAL_MC_WEIGHTED_TAIL"
ENV_Q = "HAFISCAL_MC_WEIGHTED_TAIL_POP"
ENV_CACHE = "HAFISCAL_MC_WEIGHTED_TAIL_CACHE"        # 0 disables the on-disk mixture-table cache
ENV_CACHE_DIR = "HAFISCAL_MC_WEIGHTED_TAIL_CACHE_DIR"
_TABLES_FORMAT = "wtt-v1"                              # bump if mixture_tables' grid rule changes


def _cache_enabled():
    return os.environ.get(ENV_CACHE, "1").strip().lower() not in ("0", "off", "false", "no")


def _cache_dir():
    d = os.environ.get(ENV_CACHE_DIR, "").strip()
    if not d:
        store = os.environ.get("HAFISCAL_POLICY_STORE_DIR", "").strip() or os.path.join(
            os.path.expanduser("~"), ".cache", "hafiscal", "policy_store")
        d = os.path.join(store, "weighted_tail_tables")
    return d


def _tables_key(w, mu, sig, n_grid):
    """Content hash of the (normalized) mixture components + grid size + format tag."""
    import hashlib
    h = hashlib.sha256()
    for a in (w, mu, sig):
        h.update(np.ascontiguousarray(np.asarray(a, dtype=np.float64)).tobytes())
    h.update(f"|n_grid={int(n_grid)}|{_TABLES_FORMAT}".encode())
    return h.hexdigest()


def enabled():
    """K > 0 from the env, else 0 (off)."""
    v = os.environ.get(ENV_K, "").strip()
    if not v:
        return 0
    k = int(v)
    if k < 0:
        raise ValueError(f"{ENV_K}={v!r}: K must be a non-negative integer")
    return k


def tail_pop_share():
    v = os.environ.get(ENV_Q, "").strip()
    q = float(v) if v else 0.01
    if not (0.0 < q < 0.5):
        raise ValueError(f"{ENV_Q}={v!r}: q must be in (0, 0.5)")
    return q


def mixture_F_M(w, mu, sig, x, chunk=128):
    """CDF F(x) of X = log p and partial expectation M(x) = E[p 1{X < x}] of the
    lognormal mixture (weights w, log-means mu, log-sds sig) at the points x.
    The unemployment-aware mixture has ~20 000 components (ages x states), so the
    components are accumulated in chunks (a dense grid x components matrix would be GBs)."""
    x = np.asarray(x, dtype=np.float64)[:, None]
    w = np.asarray(w, dtype=np.float64); mu = np.asarray(mu, dtype=np.float64)
    sig = np.maximum(np.asarray(sig, dtype=np.float64), 1e-12)
    F = np.zeros(x.shape[0]); M = np.zeros(x.shape[0])
    for i in range(0, len(w), chunk):
        wc, mc, sc = w[None, i:i + chunk], mu[None, i:i + chunk], sig[None, i:i + chunk]
        F += np.sum(wc * _norm.cdf((x - mc) / sc), axis=1)
        M += np.sum(wc * np.exp(mc + 0.5 * sc ** 2) * _norm.cdf((x - mc - sc ** 2) / sc), axis=1)
    return F, M


def mixture_tables(w, mu, sig, n_grid=20000):
    """Evaluate the mixture's CDF and partial expectation once: returns ``(xs, F, M, Ep)`` on a
    log-p grid wide enough that both saturate at the top. Independent of (N, K, q), so one
    evaluation (the expensive part, ~17 s for the ~20 000-component mixture) serves any number
    of stratifications — ``weighted_tail_pLvl(..., tables=...)``."""
    w = np.asarray(w, float); mu = np.asarray(mu, float); sig = np.maximum(np.asarray(sig, float), 1e-12)
    keep = w > 1e-15
    w, mu, sig = w[keep] / np.sum(w[keep]), mu[keep], sig[keep]
    Ep = float(np.sum(w * np.exp(mu + 0.5 * sig ** 2)))
    # On-disk cache (2026-08-25): the tables are a pure function of (w, mu, sig, n_grid) and cost
    # ~17 s per atom; a battery child re-evaluated 21 of them (~6 min, most of its setup). A HIT
    # returns the stored float64 arrays unchanged, so the sampler's output is bit-identical.
    key = _tables_key(w, mu, sig, n_grid) if _cache_enabled() else None
    if key is not None:
        fp = os.path.join(_cache_dir(), key + ".npz")
        if os.path.exists(fp):
            try:
                z = np.load(fp)
                xs, F, M = z["xs"], z["F"], z["M"]
                if abs(float(z["Ep"]) - Ep) <= 1e-12 * max(1.0, abs(Ep)):
                    return xs, F, M, Ep
            except Exception as e:  # unreadable entry: recompute and overwrite
                print(f"[weighted-tail-cache] unreadable {fp}: {e}; recomputing", flush=True)
    lo = float(np.min(mu - 12.0 * sig)); hi = float(np.max(mu + sig ** 2 + 14.0 * sig))
    xs = np.linspace(lo, hi, int(n_grid))
    F, M = mixture_F_M(w, mu, sig, xs)
    F = np.maximum.accumulate(F); M = np.maximum.accumulate(M)
    F_top, M_top = F[-1], M[-1]
    if F_top < 1 - 1e-9 or M_top < Ep * (1 - 1e-7):
        raise RuntimeError(f"weighted_tail_pLvl: grid does not saturate (F_top={F_top:.12f}, M_top/Ep={M_top/Ep:.12f})")
    F = F / F_top                       # renormalize the 1e-9 truncation
    if key is not None:
        try:
            os.makedirs(_cache_dir(), exist_ok=True)
            tmp = fp + f".tmp{os.getpid()}"
            np.savez(tmp, xs=xs, F=F, M=M, Ep=np.float64(Ep))
            os.replace(tmp + ".npz" if not tmp.endswith(".npz") else tmp, fp)
        except Exception as e:  # cache is an optimization only
            print(f"[weighted-tail-cache] could not save {fp}: {e}", flush=True)
    return xs, F, M, Ep


def weighted_tail_pLvl(w, mu, sig, N, K, q, rng, n_grid=20000, tables=None):
    """Return ``(pLvl, weights, diag)`` for N households: the bottom (1-q) of the population as
    N-K equal-population strata at their conditional-mean p, the top q as K equal-p-mass strata
    at their conditional-mean p with population weights. ``weights`` average to 1 (sum N);
    ``pLvl`` and ``weights`` are returned in the same random permutation (p ⊥ (j, aNrm)).
    ``tables`` = a precomputed ``mixture_tables(w, mu, sig)`` result (optional)."""
    N = int(N); K = int(K)
    if K <= 0 or K >= N:
        raise ValueError(f"weighted_tail_pLvl: need 0 < K < N, got K={K}, N={N}")
    xs, F, M, Ep = mixture_tables(w, mu, sig, n_grid) if tables is None else tables
    N_b = N - K
    # ---- bulk: equal population strata on u in [0, 1-q], conditional-mean representatives
    u_edges = np.linspace(0.0, 1.0 - q, N_b + 1)
    x_edges = np.interp(u_edges, F, xs)
    M_edges = np.interp(x_edges, xs, M)
    bulk_mass = (1.0 - q) / N_b
    p_bulk = np.diff(M_edges) / bulk_mass
    w_bulk = np.full(N_b, bulk_mass * N)
    # ---- tail: K equal-p-mass strata on u in [1-q, 1]
    x_tail_lo = x_edges[-1]
    M_tail_lo = M_edges[-1]
    T = Ep - M_tail_lo                  # the tail's p-mass (exact, beyond the grid too)
    M_targets = M_tail_lo + T * np.arange(K + 1) / K
    y = np.interp(M_targets[:-1], M, xs)          # chunk lower boundaries in log p
    F_y = np.interp(y, xs, F)
    F_y[0] = 1.0 - q                              # exact lower edge
    m_pop = np.diff(np.append(F_y, 1.0))           # population mass per chunk (last runs to +inf)
    m_pop = np.maximum(m_pop, 1e-300)
    p_tail = (T / K) / m_pop
    w_tail = m_pop * N
    pLvl = np.concatenate([p_bulk, p_tail])
    weights = np.concatenate([w_bulk, w_tail])
    # exactness fix-up: the bulk partial expectations are grid-interpolated; rescale the
    # bulk representatives so the weighted mean is the analytical E[p] to machine precision
    Ep_hat = float(np.sum(weights * pLvl) / N)
    tail_part = float(np.sum(w_tail * p_tail) / N)
    scale = (Ep - tail_part) / max(Ep_hat - tail_part, 1e-300)
    pLvl[:N_b] *= scale
    Ep_hat = float(np.sum(weights * pLvl) / N)
    shares = weights * pLvl / (Ep_hat * N)
    diag = {"E_p_analytical": Ep, "E_p_weighted": Ep_hat, "bulk_scale": float(scale),
            "max_income_share": float(np.max(shares)), "min_weight": float(np.min(weights)),
            "tail_income_share": float(np.sum(shares[N_b:])), "K": K, "q": q, "N": N,
            "p_tail_min": float(np.min(p_tail)), "p_tail_max": float(np.max(p_tail))}
    perm = rng.permutation(N)
    return pLvl[perm], weights[perm], diag


def weighted_tail_pLvl_for_agent(agent, N, rng, K, q, pLvl_dist="markov"):
    """Convenience: mixture components from tm_methods for ``agent``, then the sampler."""
    from tm_methods import _pLvl_components_select
    w, mu, sig = _pLvl_components_select(agent, pLvl_dist=pLvl_dist)
    return weighted_tail_pLvl(w, mu, sig, N, K, q, rng)
