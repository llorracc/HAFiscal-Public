"""
Bypass JAX RNG: use HARK's actual per-agent shock realizations
(derived from pLvl/TranShk panels) as deterministic inputs.

If JAX still drifts from HARK with same shocks, bug is in income/cons
computation (kernel logic). If matches, bug is in JAX shock generation.
"""
from __future__ import annotations
import os, sys, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import extract_hark_kernel_inputs


def main():
    pkl = 'welfare6_HS_clean_nshuf/base.pkl'
    hark = pickle.load(open(pkl, 'rb'))
    h_pLvl = np.asarray(hark['pLvl_all_bs'])    # (T, N)
    h_aNrm = np.asarray(hark['aNrm_all_bs'])    # (T, N)
    h_TranShk = np.asarray(hark['TranShk_all_bs'])  # (T, N)
    h_mrkv = np.asarray(hark['Mrkv_hist_bs']) % 6
    h_inc = np.asarray(hark['AggIncome'])
    h_cons = np.asarray(hark['AggCons'])
    T, N = h_pLvl.shape

    # Derive PermShk per agent per period from pLvl panel:
    # pLvl[t, n] = pLvl[t-1, n] * PermShk[t, n]  for surviving agents
    # For newborns (where pLvl resets), PermShk is unrecoverable from panel
    # — flag them.
    PermShk = np.ones_like(h_pLvl)
    PermShk[0] = 1.0  # t=0 is initial, no prev
    for t in range(1, T):
        PermShk[t] = h_pLvl[t] / np.maximum(h_pLvl[t-1], 1e-12)

    # Detect newborns: huge pLvl jump (down or up) likely means replacement
    is_newborn = (PermShk < 0.1) | (PermShk > 10.0)
    print(f"Newborn-replacement events detected: {is_newborn.sum()} out of {T*N}")
    print(f"PermShk stats (non-newborn): mean={PermShk[~is_newborn].mean():.5f}  std={PermShk[~is_newborn].std():.5f}")

    # Get model context
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']; AggEco.switch_shock_type('base'); AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_hark_kernel_inputs(agent, scenario='base')
    Rfree = float(agent.Rfree[0])
    Splurge = float(agent.Splurge)
    LivPrb = float(np.mean(agent.LivPrb[0][:6]))

    # Now: simulate JAX manually using HARK's exact shock realizations.
    # State: aNrm, pLvl, mrkv at each period.
    # Step (using HARK shocks):
    #   psi = PermShk[t, n] (from panel)
    #   xi = h_TranShk[t, n] (from panel)
    #   mrkv_now = h_mrkv[t, n]
    #   G = PermGroFac[mrkv_now]
    #   bNrm = R*aNrm/(G*psi)
    #   mNrm = bNrm + xi*ADF
    #   cNrm = cFunc[mrkv_now](mNrm)
    #   pLvl_now = pLvl_prev * G * psi
    #   cLvl_splurge = (1-S)*cNrm*pLvl_now + S*pLvl_now*xi
    #   aNrm_next = mNrm - cLvl_splurge/pLvl_now

    cfunc_table = inp['cfunc_table']
    m_grid = inp['m_grid']
    PermGroFac = inp['PermGroFac']

    AggInc_jax = np.zeros(T)
    AggCons_jax = np.zeros(T)
    aNrm = h_aNrm[0].astype(np.float64).copy()
    pLvl = h_pLvl[0].astype(np.float64).copy()

    for t in range(T):
        mrkv = h_mrkv[t].astype(int)
        # Use HARK's actual PermShk/TranShk
        if t == 0:
            psi = np.ones(N)  # at t=0 PermShk effectively "applied" — pLvl[0] is starting state
        else:
            psi = PermShk[t].copy()
        xi = h_TranShk[t].copy()
        G = PermGroFac[mrkv]

        bNrm = Rfree * aNrm / np.maximum(G * psi, 1e-12)
        mNrm = bNrm + xi * 1.0

        # cFunc lookup
        cNrm = np.zeros(N)
        for j in range(6):
            mask = mrkv == j
            if mask.sum() > 0:
                cNrm[mask] = np.interp(mNrm[mask], m_grid, cfunc_table[j])

        # Apply pLvl update — for newborn-replacement periods, this is tricky
        # because pLvl[t] is the post-replacement value, not pLvl[t-1]*psi.
        # For consistency with HARK, use pLvl_now = h_pLvl[t] directly.
        pLvl_now = h_pLvl[t].astype(np.float64)
        cLvl = cNrm * pLvl_now
        cLvl_splurge = (1.0 - Splurge) * cLvl + Splurge * pLvl_now * xi
        aNrm_next = mNrm - cLvl_splurge / pLvl_now

        # Income for this period
        income = pLvl_now * xi
        AggInc_jax[t] = income.sum()
        AggCons_jax[t] = cLvl_splurge.sum()

        # Update state for next period
        aNrm = aNrm_next
        pLvl = pLvl_now

    print(f"\nWith DETERMINISTIC HARK shocks (no JAX RNG):")
    print(f"  HARK AggInc mean: {h_inc.mean():.4f}")
    print(f"  JAX  AggInc mean: {AggInc_jax.mean():.4f}")
    print(f"  ratio: {AggInc_jax.mean()/h_inc.mean():.6f}")
    print(f"  HARK AggCons mean: {h_cons.mean():.4f}")
    print(f"  JAX  AggCons mean: {AggCons_jax.mean():.4f}")
    print(f"  ratio: {AggCons_jax.mean()/h_cons.mean():.6f}")
    print(f"\nPer-period AggInc comparison (should be exact if income formula matches):")
    for t in [0, 1, 5, 10, 20, 30, 39]:
        print(f"  t={t}: HARK={h_inc[t]:.3f}  JAX={AggInc_jax[t]:.3f}  diff={AggInc_jax[t]-h_inc[t]:+.4f}")


if __name__ == '__main__':
    main()
